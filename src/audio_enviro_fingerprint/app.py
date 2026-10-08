"""Tk desktop workstation for the beta analysis workflow."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .audio_io import load_wav
from .case_store import CaseStore
from .comparison import compare_fingerprints
from .features import analyze_audio
from .fingerprint import make_fingerprint
from .integrity import sha256_file
from .transitions import detect_transitions


class FingerprinterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Audio Environment Fingerprinter {__version__}")
        self.geometry("1100x760")
        self.minsize(850, 580)
        self.configure(background="#111827")
        self.current_path = None
        self.audio = None
        self.analysis = None
        self.fingerprint = None
        self.evidence_id = None
        self.evidence_sha256 = None
        db_dir = Path.home() / ".audio-enviro-fingerprint"
        self.store = CaseStore(db_dir / "cases.sqlite3")
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#111827")
        style.configure("TLabel", background="#111827", foreground="#e5e7eb")
        style.configure("Header.TLabel", font=("Segoe UI", 17, "bold"), foreground="#67e8f9")
        style.configure("Sub.TLabel", foreground="#9ca3af")
        style.configure("Treeview", background="#1f2937", foreground="#e5e7eb",
                        fieldbackground="#1f2937", rowheight=25)
        style.configure("Treeview.Heading", background="#374151", foreground="#f9fafb")

        outer = ttk.Frame(self, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="ROOM & ENVIRONMENT FINGERPRINTER", style="Header.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Evidence integrity · measurable acoustic features · reviewable findings",
                  style="Sub.TLabel").pack(anchor="w", pady=(3, 12))
        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Open PCM WAV…", command=self.open_file).pack(side="left")
        ttk.Button(toolbar, text="Compare recording…", command=self.compare_file).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Export analysis JSON…", command=self.export_json).pack(side="left")
        self.file_label = ttk.Label(toolbar, text="No evidence loaded", style="Sub.TLabel")
        self.file_label.pack(side="right")

        self.hash_label = ttk.Label(outer, text="SHA-256: —", style="Sub.TLabel", wraplength=1000)
        self.hash_label.pack(anchor="w", pady=(0, 10))
        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)

        analysis_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(analysis_tab, text="Analysis")
        ttk.Label(analysis_tab, text="Transition candidates", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.timeline = tk.Canvas(analysis_tab, height=100, background="#0b1220", highlightthickness=0)
        self.timeline.pack(fill="x", pady=(6, 12))
        self.timeline.bind("<Configure>", self._redraw_timeline)
        self.transitions = ttk.Treeview(analysis_tab, columns=("time", "strength", "evidence"), show="headings", height=6)
        for col, title, width in (("time", "Time (s)", 110), ("strength", "Change score", 130), ("evidence", "Measured changes", 650)):
            self.transitions.heading(col, text=title)
            self.transitions.column(col, width=width, anchor="w")
        self.transitions.pack(fill="x")
        ttk.Label(analysis_tab, text="Median fingerprint features", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(14, 4))
        self.features = ttk.Treeview(analysis_tab, columns=("feature", "value"), show="headings", height=8)
        self.features.heading("feature", text="Feature")
        self.features.heading("value", text="Measured value")
        self.features.column("feature", width=280, anchor="w")
        self.features.column("value", width=300, anchor="w")
        self.features.pack(fill="both", expand=True)

        notes_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(notes_tab, text="Examiner Notes")
        ttk.Label(notes_tab, text="Notes are saved with the evidence file hash and the selected timestamp.",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 8))
        form = ttk.Frame(notes_tab)
        form.pack(fill="x")
        ttk.Label(form, text="Time (seconds)").grid(row=0, column=0, sticky="w")
        self.note_time = ttk.Entry(form, width=16)
        self.note_time.insert(0, "0")
        self.note_time.grid(row=0, column=1, sticky="w", padx=(8, 18))
        ttk.Label(form, text="Title").grid(row=0, column=2, sticky="w")
        self.note_title = ttk.Entry(form)
        self.note_title.grid(row=0, column=3, sticky="ew", padx=8)
        form.columnconfigure(3, weight=1)
        ttk.Label(notes_tab, text="Observation").pack(anchor="w", pady=(12, 4))
        self.note_body = tk.Text(notes_tab, height=5, background="#1f2937", foreground="#f9fafb",
                                 insertbackground="white", wrap="word")
        self.note_body.pack(fill="x")
        ttk.Button(notes_tab, text="Save timestamped note", command=self.save_note).pack(anchor="w", pady=8)
        self.notes_view = ttk.Treeview(notes_tab, columns=("time", "title", "body"), show="headings")
        for col, title, width in (("time", "Time (s)", 100), ("title", "Title", 180), ("body", "Observation", 600)):
            self.notes_view.heading(col, text=title)
            self.notes_view.column(col, width=width, anchor="w")
        self.notes_view.pack(fill="both", expand=True)

        status = ttk.Label(outer, text="Screening aid only. Similarity does not identify a physical location.",
                           style="Sub.TLabel")
        status.pack(anchor="w", pady=(9, 0))

    def open_file(self):
        path = filedialog.askopenfilename(title="Select uncompressed PCM WAV", filetypes=[("WAV audio", "*.wav"), ("All files", "*.*")])
        if not path:
            return
        try:
            initial_hash = sha256_file(path)
            audio = load_wav(path)
            analysis = analyze_audio(audio.samples, audio.sample_rate)
            fingerprint = make_fingerprint(analysis)
            evidence_id = self.store.register_evidence(path)
            evidence = self.store.evidence_record(evidence_id)
            final_hash = sha256_file(path)
            if initial_hash != final_hash or evidence["sha256"] != initial_hash:
                raise ValueError("The source file changed while it was being loaded. Re-open a stable copy of the evidence.")
        except Exception as exc:
            messagebox.showerror("Unable to analyze recording", str(exc))
            return
        self.current_path, self.audio, self.analysis = Path(path), audio, analysis
        self.fingerprint, self.evidence_id = fingerprint, evidence_id
        self.evidence_sha256 = initial_hash
        self.file_label.configure(text=f"{self.current_path.name} · {audio.duration_seconds:.2f} s · {audio.sample_rate} Hz · channel 1 of {audio.channels}")
        self.hash_label.configure(text=f"Evidence SHA-256: {self.evidence_sha256}\nAcoustic fingerprint aefp-1: {fingerprint.fingerprint_hash}")
        self._show_results()
        self._load_notes()

    def _show_results(self):
        for item in self.transitions.get_children(): self.transitions.delete(item)
        for item in self.features.get_children(): self.features.delete(item)
        events = detect_transitions(self.analysis)
        for event in events:
            evidence = ", ".join(f"{key} {value:+.2f}" for key, value in event.evidence.items())
            self.transitions.insert("", "end", values=(f"{event.timestamp_seconds:.2f}", f"{event.strength:.3f}", evidence))
        for key, value in self.fingerprint.features.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    self.features.insert("", "end", values=(f"Band power · {subkey}", f"{subvalue:.2f} dB"))
            elif isinstance(value, float):
                unit = " Hz" if key.endswith("_hz") else " dBFS" if "dbfs" in key else ""
                self.features.insert("", "end", values=(key, f"{value:.4f}{unit}"))
            else:
                self.features.insert("", "end", values=(key, value))
        self._draw_timeline(events)

    def _draw_timeline(self, events):
        self.timeline.delete("all")
        width = max(self.timeline.winfo_width(), 600)
        height = 100
        self.timeline.configure(height=height)
        self.timeline.create_line(24, 54, width - 24, 54, fill="#64748b", width=2)
        if not self.analysis or self.analysis.duration_seconds <= 0:
            return
        self.timeline.create_text(24, 78, text="0 s", fill="#cbd5e1", anchor="w")
        self.timeline.create_text(width - 24, 78, text=f"{self.analysis.duration_seconds:.1f} s", fill="#cbd5e1", anchor="e")
        for event in events:
            x = 24 + event.timestamp_seconds / self.analysis.duration_seconds * (width - 48)
            self.timeline.create_line(x, 26, x, 66, fill="#fb7185", width=2)
            self.timeline.create_text(x, 16, text=f"{event.timestamp_seconds:.1f}s", fill="#fda4af")

    def _redraw_timeline(self, _event=None):
        if self.analysis:
            self._draw_timeline(detect_transitions(self.analysis))

    def compare_file(self):
        if not self.fingerprint:
            messagebox.showinfo("Load evidence", "Open a WAV file before comparing.")
            return
        path = filedialog.askopenfilename(title="Select second PCM WAV", filetypes=[("WAV audio", "*.wav")])
        if not path:
            return
        try:
            other = load_wav(path)
            result = make_fingerprint(analyze_audio(other.samples, other.sample_rate))
            comparison = compare_fingerprints({"version": self.fingerprint.version, "features": self.fingerprint.features},
                                              {"version": result.version, "features": result.features})
            differences = "\n".join(f"{key}: {item['delta']:+.3f}" for key, item in comparison.differences.items())
            messagebox.showinfo("Explainable comparison", f"Descriptive score: {comparison.score:.3f}\n\n{comparison.explanation}\n\nPer-feature differences:\n{differences}")
        except Exception as exc:
            messagebox.showerror("Comparison failed", str(exc))

    def export_json(self):
        if not self.analysis:
            messagebox.showinfo("Load evidence", "Open a WAV file before exporting.")
            return
        target = filedialog.asksaveasfilename(title="Export analysis", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not target:
            return
        if sha256_file(self.current_path) != self.evidence_sha256:
            messagebox.showerror("Evidence changed", "The source file no longer matches the hash recorded at import. Re-open a stable copy before exporting.")
            return
        report = {"schema_version": "aefp-report-1", "application_version": __version__,
                  "evidence": {"source_path": str(self.current_path), "sha256": self.evidence_sha256},
                  "analysis": self.analysis.to_dict(), "fingerprint": json.loads(self.fingerprint.canonical_json),
                  "fingerprint_sha256": self.fingerprint.fingerprint_hash,
                  "transitions": [event.__dict__ for event in detect_transitions(self.analysis)],
                  "notes": self.store.notes_for(self.evidence_id),
                  "limitations": ["PCM WAV only", "Transition scores are candidates requiring review",
                                  "Fingerprint score is not location probability", "RT60 requires a separate measured impulse response"]}
        try:
            Path(target).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            messagebox.showinfo("Export complete", f"Report written to {target}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def save_note(self):
        if not self.evidence_id:
            messagebox.showinfo("Load evidence", "Open evidence before writing a note.")
            return
        try:
            timestamp = float(self.note_time.get())
            if self.audio and timestamp > self.audio.duration_seconds:
                raise ValueError("Timestamp is beyond the recording duration")
            self.store.add_note(self.evidence_id, timestamp, self.note_title.get(), self.note_body.get("1.0", "end"))
            self.note_title.delete(0, "end")
            self.note_body.delete("1.0", "end")
            self._load_notes()
        except Exception as exc:
            messagebox.showerror("Unable to save note", str(exc))

    def _load_notes(self):
        for item in self.notes_view.get_children(): self.notes_view.delete(item)
        if self.evidence_id:
            for note in self.store.notes_for(self.evidence_id):
                self.notes_view.insert("", "end", values=(f"{note['timestamp_seconds']:.2f}", note["title"], note["body"]))

    def _close(self):
        self.store.close()
        self.destroy()


def main():
    app = FingerprinterApp()
    if os.environ.get("AEFP_SMOKE_TEST") == "1":
        app.after(750, app._close)
    app.mainloop()

