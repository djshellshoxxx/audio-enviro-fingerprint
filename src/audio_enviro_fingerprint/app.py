"""Tk desktop workstation: orchestrates pipeline, case store, and tab widgets."""
from __future__ import annotations

import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .case_store import CaseStore
from .control import AnalysisCancelled
from .comparison import compare_fingerprints
from .fingerprint import make_fingerprint
from .features import analyze_audio
from .audio_io import load_audio
from .pipeline import analyze_file, full_report
from .recurrence import find_recurrences
from .report import write_report
from .ui_tabs import (BG, FG, MUTED, ACCENT, ChannelsTab, MusicalTab, RecurrenceTab, ReferenceTab,
                      SpectrogramTab, fill, heading, tree)


class FingerprinterApp(tk.Tk):
    def __init__(self, home: Path | None = None):
        super().__init__()
        self.title(f"Audio Environment Fingerprinter {__version__}")
        self.geometry("1180x800")
        self.minsize(900, 600)
        self.configure(background=BG)
        self.result = None
        self.evidence_id = None
        self.jobs: queue.Queue = queue.Queue()
        self.busy = False
        self.cancel_event = threading.Event()
        home = home or Path(os.environ.get("AEFP_HOME", Path.home() / ".audio-enviro-fingerprint"))
        self.store = CaseStore(Path(home) / "cases.sqlite3")
        self._build_ui()
        self.bind_all("<Control-o>", lambda _e: self.open_file())
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ---------------------------------------------------------------- layout
    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Header.TLabel", font=("Segoe UI", 17, "bold"), foreground=ACCENT)
        style.configure("Sub.TLabel", foreground=MUTED)
        style.configure("Treeview", background="#1f2937", foreground=FG, fieldbackground="#1f2937", rowheight=24)
        style.configure("Treeview.Heading", background="#374151", foreground="#f9fafb")
        style.configure("TNotebook", background=BG)
        style.configure("TNotebook.Tab", padding=(12, 5))

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="ROOM & ENVIRONMENT FINGERPRINTER", style="Header.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Evidence integrity · measurable acoustic features · musical description · reviewable findings",
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 8))
        bar = ttk.Frame(outer)
        bar.pack(fill="x", pady=(0, 6))
        for text, cmd in (("Open audio… (Ctrl+O)", self.open_file), ("Compare recording…", self.compare_file),
                          ("Find environment in other recording…", self.cross_recurrence),
                          ("Export report…", self.export_json), ("Export spectrogram PNG…", self.export_png)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 6))
        self.cancel_button = ttk.Button(bar, text="Cancel analysis", command=self.cancel_event.set, state="disabled")
        self.cancel_button.pack(side="left", padx=(0, 6))
        self.file_label = ttk.Label(bar, text="No evidence loaded", style="Sub.TLabel")
        self.file_label.pack(side="right")
        self.hash_label = ttk.Label(outer, text="SHA-256: —", style="Sub.TLabel", wraplength=1100)
        self.hash_label.pack(anchor="w")
        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=1.0)
        self.progress_label = ttk.Label(outer, text="", style="Sub.TLabel")

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True, pady=(6, 0))
        self._analysis_tab()
        self.spectrogram = SpectrogramTab(self.notebook, on_marker=self._set_note_time)
        self.musical = MusicalTab(self.notebook)
        self.recurrence = RecurrenceTab(self.notebook)
        self.channels = ChannelsTab(self.notebook)
        self.reference = ReferenceTab(self.notebook, self._save_reference)
        self.reference.provider = lambda: self.result["audio"] if self.result else None
        self._notes_tab()
        for tab, title in ((self.spectrogram, "Spectrogram"), (self.musical, "Musical"),
                           (self.recurrence, "Recurrence"), (self.channels, "Channels"),
                           (self.reference, "Reference"), (self.notes_tab, "Notes & Markers")):
            self.notebook.add(tab, text=title)
        ttk.Label(outer, text="Screening aid only. Similarity does not identify a physical location or establish authenticity.",
                  style="Sub.TLabel").pack(anchor="w", pady=(6, 0))

    def _analysis_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Analysis")
        heading(tab, "Transition candidates")
        self.timeline = tk.Canvas(tab, height=90, background="#0b1220", highlightthickness=0)
        self.timeline.pack(fill="x", pady=(0, 8))
        self.timeline.bind("<Configure>", lambda _e: self._draw_timeline())
        frame, self.transitions = tree(tab, [("time", "Time (s)", 100), ("strength", "Change score", 120),
                                             ("evidence", "Measured changes", 800)], 6)
        frame.pack(fill="x")
        heading(tab, "Median fingerprint features")
        frame, self.features = tree(tab, [("feature", "Feature", 300), ("value", "Measured value", 300)], 8)
        frame.pack(fill="both", expand=True)

    def _notes_tab(self):
        tab = self.notes_tab = ttk.Frame(self.notebook, padding=12)
        ttk.Label(tab, text="Notes and markers are saved with the evidence SHA-256. Marker edits keep revision history.",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 6))
        form = ttk.Frame(tab)
        form.pack(fill="x")
        ttk.Label(form, text="Time (s)").grid(row=0, column=0)
        self.note_time = ttk.Entry(form, width=12)
        self.note_time.insert(0, "0")
        self.note_time.grid(row=0, column=1, padx=8)
        ttk.Label(form, text="Title").grid(row=0, column=2)
        self.note_title = ttk.Entry(form)
        self.note_title.grid(row=0, column=3, sticky="ew", padx=8)
        form.columnconfigure(3, weight=1)
        self.note_body = tk.Text(tab, height=4, background="#1f2937", foreground="#f9fafb",
                                 insertbackground="white", wrap="word")
        self.note_body.pack(fill="x", pady=6)
        row = ttk.Frame(tab)
        row.pack(anchor="w")
        ttk.Button(row, text="Save timestamped note", command=self.save_note).pack(side="left")
        ttk.Button(row, text="Add marker at time", command=self.add_marker).pack(side="left", padx=8)
        ttk.Button(row, text="Delete selected marker", command=self.delete_marker).pack(side="left")
        frame, self.notes_view = tree(tab, [("time", "Time (s)", 90), ("title", "Title", 200), ("body", "Observation", 700)], 6)
        frame.pack(fill="both", expand=True, pady=6)
        frame, self.markers_view = tree(tab, [("key", "Marker", 70), ("time", "Time (s)", 90), ("label", "Label", 500)], 5)
        frame.pack(fill="x")

    # ------------------------------------------------------------ analysis
    def open_file(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(title="Select audio recording",
                                          filetypes=[("Audio recordings", "*.wav *.wave *.flac *.mp3 *.ogg *.opus *.m4a *.mp4"), ("All files", "*.*")])
        if path:
            self.start_analysis(path)

    def start_analysis(self, path):
        self.busy = True
        self.cancel_event.clear()
        self.cancel_button.configure(state="normal")
        self.progress.pack(fill="x", pady=(4, 0), before=self.notebook)
        self.progress_label.pack(anchor="w", before=self.notebook)

        def work():
            try:
                self.jobs.put(("done", analyze_file(path, progress=lambda m, f: self.jobs.put(("progress", (m, f))), cancel_event=self.cancel_event)))
            except Exception as exc:   # surfaced to the UI thread, never swallowed
                self.jobs.put(("error", exc))
        threading.Thread(target=work, daemon=True).start()
        self.after(50, self._poll)

    def _poll(self):
        try:
            while True:
                kind, payload = self.jobs.get_nowait()
                if kind == "progress":
                    self.progress.configure(value=payload[1])
                    self.progress_label.configure(text=payload[0])
                    continue
                self._finish(kind, payload)
                return
        except queue.Empty:
            self.after(50, self._poll)

    def _finish(self, kind, payload):
        self.busy = False
        self.cancel_button.configure(state="disabled")
        self.progress.pack_forget()
        self.progress_label.pack_forget()
        if kind == "error" and isinstance(payload, AnalysisCancelled):
            return
        if kind == "error":
            messagebox.showerror("Unable to analyze recording", str(payload))
            return
        self.apply_result(payload)

    def apply_result(self, result):
        evidence_id = self.store.register_evidence(result["path"])
        if self.store.evidence_record(evidence_id)["sha256"] != result["sha256"]:
            messagebox.showerror("Evidence changed", "The file changed while it was being loaded.")
            return
        self.evidence_id = evidence_id
        self.result = result
        audio, fp = result["audio"], result["fingerprint"]
        self.file_label.configure(text=f"{result['path'].name} · {audio.duration_seconds:.2f} s · {audio.sample_rate} Hz · "
                                       f"{audio.channels} ch ({audio.sample_format}) · analyzing channel 1")
        self.hash_label.configure(text=f"Evidence SHA-256: {result['sha256']}\nAcoustic fingerprint {fp.version}: {fp.fingerprint_hash}")
        fill(self.transitions, [(f"{e.timestamp_seconds:.2f}", f"{e.strength:.3f}",
                                 ", ".join(f"{k} {v:+.2f}" for k, v in e.evidence.items())) for e in result["transitions"]])
        rows = []
        for key, value in fp.features.items():
            if isinstance(value, dict):
                rows += [(f"Band power · {k}", f"{v:.2f} dB") for k, v in value.items()]
            elif isinstance(value, float):
                unit = " Hz" if key.endswith("_hz") else " dBFS" if "dbfs" in key else ""
                rows.append((key, f"{value:.4f}{unit}"))
            else:
                rows.append((key, value))
        fill(self.features, rows)
        self._draw_timeline()
        for tab in (self.spectrogram, self.musical, self.recurrence, self.channels):
            tab.update_result(result)
        self._load_notes()

    def _draw_timeline(self):
        c = self.timeline
        c.delete("all")
        if not self.result:
            return
        width, duration = max(c.winfo_width(), 600), self.result["audio"].duration_seconds
        c.create_line(24, 50, width - 24, 50, fill="#64748b", width=2)
        c.create_text(24, 74, text="0 s", fill="#cbd5e1", anchor="w")
        c.create_text(width - 24, 74, text=f"{duration:.1f} s", fill="#cbd5e1", anchor="e")
        x_of = lambda t: 24 + t / duration * (width - 48)
        for r in self.result["recurrences"]:
            c.create_rectangle(x_of(r.later_start_s), 44, x_of(min(r.later_end_s, duration)), 56, fill="#34d399", outline="")
            c.create_rectangle(x_of(r.earlier_start_s), 44, x_of(min(r.earlier_end_s, duration)), 56, fill="#2dd4bf", outline="")
        for e in self.result["transitions"]:
            x = x_of(e.timestamp_seconds)
            c.create_line(x, 22, x, 62, fill="#fb7185", width=2)
            c.create_text(x, 12, text=f"{e.timestamp_seconds:.1f}s", fill="#fda4af")

    # ------------------------------------------------------------- actions
    def _require(self):
        if not self.result:
            messagebox.showinfo("Load evidence", "Open an audio file first.")
            return False
        return True

    def compare_file(self):
        if not self._require():
            return
        path = filedialog.askopenfilename(title="Select second recording", filetypes=[("Audio recordings", "*.wav *.wave *.flac *.mp3 *.ogg *.opus *.m4a *.mp4"), ("All files", "*.*")])
        if not path:
            return
        try:
            other = load_audio(path)
            second = make_fingerprint(analyze_audio(other.samples, other.sample_rate))
            fp = self.result["fingerprint"]
            comparison = compare_fingerprints({"version": fp.version, "features": fp.features},
                                              {"version": second.version, "features": second.features})
        except Exception as exc:
            messagebox.showerror("Comparison failed", str(exc))
            return
        win = tk.Toplevel(self)
        win.title("Explainable comparison")
        win.configure(background=BG)
        win.geometry("760x480")
        ttk.Label(win, text=f"Descriptive score {comparison.score:.3f}", style="Header.TLabel").pack(anchor="w", padx=12, pady=8)
        ttk.Label(win, text=comparison.explanation, wraplength=720, style="Sub.TLabel").pack(anchor="w", padx=12)
        frame, view = tree(win, [("f", "Feature", 260), ("a", "First", 110), ("b", "Second", 110),
                                 ("d", "Delta", 100), ("n", "Normalized", 100)], 14)
        frame.pack(fill="both", expand=True, padx=12, pady=8)
        fill(view, [(k, f"{v['first']:.3f}", f"{v['second']:.3f}", f"{v['delta']:+.3f}", f"{v['normalized_delta']:.2f}")
                    for k, v in sorted(comparison.differences.items(), key=lambda kv: -kv[1]["normalized_delta"])])

    def cross_recurrence(self):
        if not self._require():
            return
        path = filedialog.askopenfilename(title="Search for this recording's environment in…",
                                          filetypes=[("Audio recordings", "*.wav *.wave *.flac *.mp3 *.ogg *.opus *.m4a *.mp4"), ("All files", "*.*")])
        if not path:
            return
        try:
            other = analyze_file(path, musical=False)
            found = find_recurrences(self.result["analysis"], other["analysis"])
        except Exception as exc:
            messagebox.showerror("Search failed", str(exc))
            return
        win = tk.Toplevel(self)
        win.title(f"Matches in {other['path'].name}")
        win.configure(background=BG)
        frame, view = tree(win, [("id", "ID", 50), ("here", "This recording (s)", 150), ("there", "Other recording (s)", 150),
                                 ("d", "Mean distance", 110)], 12)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        fill(view, [(r.segment_id, f"{r.later_start_s:.0f}–{r.later_end_s:.0f}",
                     f"{r.earlier_start_s:.0f}–{r.earlier_end_s:.0f}", f"{r.mean_distance:.3f}") for r in found])
        ttk.Label(win, text=f"{len(found)} candidate segment(s). Candidates only; not an identification.",
                  style="Sub.TLabel").pack(anchor="w", padx=12, pady=(0, 10))

    def export_json(self):
        if not self._require():
            return
        target = filedialog.asksaveasfilename(title="Export report", defaultextension=".json",
                                              filetypes=[("JSON report", "*.json")])
        if not target:
            return
        try:
            from .integrity import sha256_file
            if sha256_file(self.result["path"]) != self.result["sha256"]:
                raise ValueError("The source file no longer matches the hash recorded at import.")
            from .pipeline import report_sections
            from .report import build_report
            sections = report_sections(self.result, self.store.notes_for(self.evidence_id),
                                       self.store.markers_for(self.evidence_id),
                                       marker_history=self.store.markers_for(self.evidence_id, True),
                                       references=[r for r in self.store.references()
                                                   if r["evidence_id"] == self.evidence_id])
            write_report(target, build_report(self.result["path"], self.result["sha256"], sections))
            messagebox.showinfo("Export complete", f"Report with manifest written to {target}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def export_png(self):
        if not self._require():
            return
        target = filedialog.asksaveasfilename(title="Export spectrogram", defaultextension=".png",
                                              filetypes=[("PNG image", "*.png")])
        if target:
            try:
                from .integrity import write_export
                write_export(target, self.spectrogram.png_bytes, self.result["path"])
            except (ValueError, OSError) as exc:
                messagebox.showerror("Export failed", str(exc))

    def _set_note_time(self, seconds):
        self.note_time.delete(0, "end")
        self.note_time.insert(0, f"{seconds:.2f}")

    def _timestamp(self):
        t = float(self.note_time.get())
        if self.result and t > self.result["audio"].duration_seconds:
            raise ValueError("Timestamp is beyond the recording duration")
        return t

    def save_note(self):
        if not self.evidence_id:
            return messagebox.showinfo("Load evidence", "Open evidence before writing a note.")
        try:
            self.store.add_note(self.evidence_id, self._timestamp(), self.note_title.get(),
                                self.note_body.get("1.0", "end"))
            self.note_title.delete(0, "end")
            self.note_body.delete("1.0", "end")
            self._load_notes()
        except Exception as exc:
            messagebox.showerror("Unable to save note", str(exc))

    def add_marker(self):
        if not self.evidence_id:
            return messagebox.showinfo("Load evidence", "Open evidence before adding a marker.")
        try:
            self.store.save_marker(self.evidence_id, self._timestamp(), self.note_title.get() or "Marker")
            self._load_notes()
        except Exception as exc:
            messagebox.showerror("Unable to add marker", str(exc))

    def delete_marker(self):
        selected = self.markers_view.selection()
        if selected and self.evidence_id:
            values = self.markers_view.item(selected[0], "values")
            self.store.save_marker(self.evidence_id, float(values[1]), values[2], int(values[0]), deleted=True)
            self._load_notes()

    def _save_reference(self, tab):
        if not self.evidence_id:
            return messagebox.showinfo("Load evidence", "Open evidence first.")
        review = tab.review()
        if review is None:
            return
        if review["overall"] == "fail" and not messagebox.askyesno(
                "Reference review failed", "Checks failed. Save this record anyway (the failures are stored with it)?"):
            return
        self.store.add_reference(self.evidence_id, tab.metadata().to_dict(), review)
        messagebox.showinfo("Saved", "Reference record saved (append-only) and bound to the evidence hash.")

    def _load_notes(self):
        notes = self.store.notes_for(self.evidence_id) if self.evidence_id else []
        fill(self.notes_view, [(f"{n['timestamp_seconds']:.2f}", n["title"], n["body"]) for n in notes])
        markers = self.store.markers_for(self.evidence_id) if self.evidence_id else []
        fill(self.markers_view, [(m["marker_key"], f"{m['timestamp_seconds']:.2f}", m["label"]) for m in markers])

    def _close(self):
        self.cancel_event.set()
        self.store.close()
        self.destroy()


def _smoke(app: FingerprinterApp) -> None:
    """Headless-CI check: analyze a synthetic recording through every tab, then exit."""
    import numpy as np
    import wave
    sr = 16000
    t = np.arange(sr * 14) / sr
    rng = np.random.default_rng(0)
    left = np.concatenate([0.02 * rng.normal(size=sr * 5), 0.3 * np.sin(2 * np.pi * 440 * t[:sr * 4]),
                           0.02 * rng.normal(size=sr * 5)])
    data = np.stack([left, 0.5 * left], axis=1)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "smoke.wav"
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes((np.clip(data, -1, 1) * 32767).astype("<i2").tobytes())
        app.apply_result(analyze_file(path))
        app.update_idletasks()
        if not app.spectrogram.png_bytes or app.result is None:
            raise RuntimeError("smoke analysis produced no output")
        app.update()
    print("smoke test ok")


def main():
    smoke = os.environ.get("AEFP_SMOKE_TEST") == "1"
    home = Path(tempfile.mkdtemp(prefix="aefp-smoke-")) if smoke else None
    app = FingerprinterApp(home)
    if smoke:
        try:
            _smoke(app)
        except Exception as exc:
            print(f"smoke test FAILED: {exc!r}", file=sys.stderr)
            app._close()
            raise SystemExit(1)
        app.after(200, app._close)
    app.mainloop()
