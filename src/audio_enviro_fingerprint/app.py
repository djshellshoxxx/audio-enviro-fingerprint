"""Tk desktop workstation for the beta analysis workflow."""
from __future__ import annotations

import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .audio_io import load_wav
from .case_store import CaseStore
from .comparison import compare_fingerprints
from .features import AnalysisCancelled, analyze_audio
from .fingerprint import make_fingerprint
from .integrity import sha256_file
from .methods.quality import review_quality
from .recurrence import find_recurrences, segment_recording
from .reference import (CHECKLIST, OPTIONAL_FIELDS, REQUIRED_FIELDS, caveat, declared_rate_conflict,
                        validate_reference_metadata)
from .report import build_report
from .transitions import detect_transitions


class FingerprinterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Audio Environment Fingerprinter {__version__}")
        self.geometry("1180x800")
        self.minsize(900, 620)
        self.configure(background="#111827")
        self.current_path = None
        self.audio = None
        self.analysis = None
        self.fingerprint = None
        self.evidence_id = None
        self.evidence_sha256 = None
        self.events = []
        self.segments = []
        self.comparisons = []
        self.cancel_event = threading.Event()
        self.results = queue.Queue()
        self.busy = False
        db_dir = Path.home() / ".audio-enviro-fingerprint"
        self.store = CaseStore(db_dir / "cases.sqlite3")
        self._build_ui()
        self._load_references()
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ---------------------------------------------------------------- layout
    def _tree(self, parent, columns, height=6, expand=False):
        tree = ttk.Treeview(parent, columns=[c[0] for c in columns], show="headings", height=height)
        for col, title, width in columns:
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor="w")
        tree.pack(fill="both" if expand else "x", expand=expand)
        return tree

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#111827")
        style.configure("TLabel", background="#111827", foreground="#e5e7eb")
        style.configure("TCheckbutton", background="#111827", foreground="#e5e7eb")
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
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="Open PCM WAV…", command=self.open_file).pack(side="left")
        ttk.Label(toolbar, text="Channel").pack(side="left", padx=(12, 4))
        self.channel_var = tk.StringVar(value="1")
        ttk.Spinbox(toolbar, from_=1, to=64, width=4, textvariable=self.channel_var).pack(side="left")
        ttk.Button(toolbar, text="Compare recording…", command=self.compare_file).pack(side="left", padx=8)
        ttk.Button(toolbar, text="Export analysis JSON…", command=self.export_json).pack(side="left")
        self.cancel_button = ttk.Button(toolbar, text="Cancel", command=self.cancel_analysis, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        self.progress = ttk.Progressbar(toolbar, length=140, maximum=100)
        self.progress.pack(side="left")
        self.file_label = ttk.Label(toolbar, text="No evidence loaded", style="Sub.TLabel")
        self.file_label.pack(side="right")

        self.hash_label = ttk.Label(outer, text="SHA-256: —", style="Sub.TLabel", wraplength=1100)
        self.hash_label.pack(anchor="w", pady=(0, 8))
        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)
        self._build_analysis_tab()
        self._build_recurrence_tab()
        self._build_compare_tab()
        self._build_reference_tab()
        self._build_notes_tab()
        ttk.Label(outer, text="Screening aid only. Similarity does not identify a physical location.",
                  style="Sub.TLabel").pack(anchor="w", pady=(9, 0))

    def _build_analysis_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Analysis")
        ttk.Label(tab, text="Transition candidates", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.timeline = tk.Canvas(tab, height=100, background="#0b1220", highlightthickness=0)
        self.timeline.pack(fill="x", pady=(6, 12))
        self.timeline.bind("<Configure>", self._redraw_timeline)
        self.transitions = self._tree(tab, (("time", "Time (s)", 110), ("strength", "Change score", 130),
                                            ("evidence", "Measured changes", 800)))
        ttk.Label(tab, text="Median fingerprint features", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(14, 4))
        self.features = self._tree(tab, (("feature", "Feature", 280), ("value", "Measured value", 300)), 8, True)

    def _build_recurrence_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Recurrence")
        ttk.Label(tab, text="Segments split at candidate transitions; segments with fewer than 2 complete frames "
                  "are not matched.", style="Sub.TLabel").pack(anchor="w")
        self.segment_view = self._tree(tab, (("id", "Segment", 120), ("span", "Span (s)", 150),
                                             ("frames", "Frames", 70), ("usable", "Used", 60),
                                             ("note", "Note", 400)), 6)
        ttk.Label(tab, text="Recurrence candidates (environment departs, then returns)",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(12, 4))
        self.recur_view = self._tree(tab, (("pair", "Segments", 220), ("score", "Descriptive score", 130),
                                           ("gap", "Gap (s)", 80), ("closest", "Closest features", 420),
                                           ("furthest", "Largest differences", 420)), 6)
        self.recur_view.bind("<<TreeviewSelect>>", self._show_recurrence_detail)
        self.recur_text = tk.Text(tab, height=9, background="#1f2937", foreground="#f9fafb", wrap="word")
        self.recur_text.pack(fill="both", expand=True, pady=(8, 0))
        self.recur_candidates = []

    def _build_compare_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Comparison")
        self.compare_summary = ttk.Label(tab, text="Use “Compare recording…” or compare to a stored reference.",
                                         style="Sub.TLabel", wraplength=1050)
        self.compare_summary.pack(anchor="w", pady=(0, 6))
        self.compare_view = self._tree(tab, (("feature", "Feature", 260), ("first", "Loaded", 110),
                                             ("second", "Other", 110), ("delta", "Delta", 110),
                                             ("share", "Share of distance", 130), ("dir", "Direction", 150)),
                                       16, True)
        self.compare_text = tk.Text(tab, height=6, background="#1f2937", foreground="#f9fafb", wrap="word")
        self.compare_text.pack(fill="x", pady=(8, 0))

    def _build_reference_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Reference acquisition")
        ttk.Label(tab, text="Known-location exemplars. Records are immutable and bound to the file SHA-256. "
                  "The location label is the operator's claim, not a verified fact.",
                  style="Sub.TLabel", wraplength=1050).pack(anchor="w")
        canvas = tk.Canvas(tab, height=250, background="#111827", highlightthickness=0)
        form = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=form, anchor="nw")
        scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        form.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.pack(fill="x", pady=6)
        scroll.place(relx=1.0, y=40, height=250, anchor="ne")
        self.ref_entries = {}
        fields = list(REQUIRED_FIELDS.items()) + list(OPTIONAL_FIELDS.items())
        for row, (key, label) in enumerate(fields):
            optional = key in OPTIONAL_FIELDS
            ttk.Label(form, text=label + (" (optional)" if optional else " *")).grid(row=row, column=0, sticky="w", pady=1)
            entry = ttk.Entry(form, width=70)
            entry.grid(row=row, column=1, sticky="w", padx=8, pady=1)
            self.ref_entries[key] = entry
        self.checklist_vars = []
        box = ttk.Frame(tab)
        box.pack(fill="x")
        ttk.Label(box, text="Acquisition checklist (confirm all, or record deviations above):").pack(anchor="w")
        for item in CHECKLIST:
            var = tk.BooleanVar(value=False)
            self.checklist_vars.append(var)
            ttk.Checkbutton(box, text=item, variable=var).pack(anchor="w")
        buttons = ttk.Frame(tab)
        buttons.pack(fill="x", pady=6)
        ttk.Button(buttons, text="Save reference from WAV…", command=self.save_reference).pack(side="left")
        ttk.Button(buttons, text="Verify selected", command=self.verify_reference).pack(side="left", padx=8)
        ttk.Button(buttons, text="Compare loaded recording to selected", command=self.compare_to_reference).pack(side="left")
        self.ref_view = self._tree(tab, (("id", "ID", 50), ("loc", "Location", 220), ("when", "Acquired", 200),
                                         ("quality", "Quality", 80), ("sha", "File SHA-256", 520)), 5, True)

    def _build_notes_tab(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text="Examiner Notes")
        ttk.Label(tab, text="Notes are saved with the evidence file hash and the selected timestamp.",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 8))
        form = ttk.Frame(tab)
        form.pack(fill="x")
        ttk.Label(form, text="Time (seconds)").grid(row=0, column=0, sticky="w")
        self.note_time = ttk.Entry(form, width=16)
        self.note_time.insert(0, "0")
        self.note_time.grid(row=0, column=1, sticky="w", padx=(8, 18))
        ttk.Label(form, text="Title").grid(row=0, column=2, sticky="w")
        self.note_title = ttk.Entry(form)
        self.note_title.grid(row=0, column=3, sticky="ew", padx=8)
        form.columnconfigure(3, weight=1)
        ttk.Label(tab, text="Observation").pack(anchor="w", pady=(12, 4))
        self.note_body = tk.Text(tab, height=5, background="#1f2937", foreground="#f9fafb",
                                 insertbackground="white", wrap="word")
        self.note_body.pack(fill="x")
        ttk.Button(tab, text="Save timestamped note", command=self.save_note).pack(anchor="w", pady=8)
        self.notes_view = self._tree(tab, (("time", "Time (s)", 100), ("title", "Title", 180),
                                           ("body", "Observation", 700)), 6, True)

    # --------------------------------------------------------------- loading
    def _set_busy(self, busy):
        self.busy = busy
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if not busy:
            self.progress.configure(value=0)

    def open_file(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(title="Select uncompressed PCM WAV",
                                          filetypes=[("WAV audio", "*.wav"), ("All files", "*.*")])
        if not path:
            return
        try:
            channel = int(self.channel_var.get()) - 1
            if channel < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid channel", "Channel must be a positive whole number.")
            return
        self.cancel_event.clear()
        self._set_busy(True)
        threading.Thread(target=self._worker, args=(path, channel), daemon=True).start()
        self.after(100, self._poll)

    def _worker(self, path, channel):
        try:
            initial_hash = sha256_file(path)
            audio = load_wav(path, channel)
            analysis = analyze_audio(audio.samples, audio.sample_rate, cancel=self.cancel_event,
                                     progress=lambda f: self.results.put(("progress", f)))
            fingerprint = make_fingerprint(analysis)
            if sha256_file(path) != initial_hash:
                raise ValueError("The source file changed while it was being loaded. Re-open a stable copy of the evidence.")
            self.results.put(("done", (path, initial_hash, audio, analysis, fingerprint)))
        except AnalysisCancelled:
            self.results.put(("cancelled", None))
        except Exception as exc:  # surfaced to the examiner, never swallowed
            self.results.put(("error", str(exc)))

    def _poll(self):
        try:
            while True:
                kind, payload = self.results.get_nowait()
                if kind == "progress":
                    self.progress.configure(value=payload * 100)
                    continue
                self._set_busy(False)
                if kind == "done":
                    self._finish_load(*payload)
                elif kind == "error":
                    messagebox.showerror("Unable to analyze recording", payload)
                return
        except queue.Empty:
            pass
        if self.busy:
            self.after(100, self._poll)

    def cancel_analysis(self):
        self.cancel_event.set()

    def _finish_load(self, path, digest, audio, analysis, fingerprint):
        try:
            evidence_id = self.store.register_evidence(path)
            if self.store.evidence_record(evidence_id)["sha256"] != digest:
                raise ValueError("Evidence record hash does not match the analyzed bytes.")
        except Exception as exc:
            messagebox.showerror("Unable to record evidence", str(exc))
            return
        self.current_path, self.audio, self.analysis = Path(path), audio, analysis
        self.fingerprint, self.evidence_id, self.evidence_sha256 = fingerprint, evidence_id, digest
        self.comparisons = []
        self.file_label.configure(text=f"{self.current_path.name} · {audio.duration_seconds:.2f} s · "
                                       f"{audio.sample_rate} Hz · channel {audio.channel_index + 1} of {audio.channels}")
        self.hash_label.configure(text=f"Evidence SHA-256: {digest}\nAcoustic fingerprint aefp-1: {fingerprint.fingerprint_hash}")
        self._show_results()
        self._load_notes()

    def _show_results(self):
        for tree in (self.transitions, self.features, self.segment_view, self.recur_view):
            tree.delete(*tree.get_children())
        self.recur_text.delete("1.0", "end")
        self.events = detect_transitions(self.analysis)
        for event in self.events:
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
        self.segments = segment_recording(self.analysis, self.events)
        for seg in self.segments:
            self.segment_view.insert("", "end", values=(seg.segment_id, f"{seg.start_seconds:.1f}–{seg.end_seconds:.1f}",
                                                        seg.frame_count, "yes" if seg.usable else "no", seg.note))
        self.recur_candidates = find_recurrences(self.segments, self.analysis.frame_seconds)
        for cand in self.recur_candidates:
            self.recur_view.insert("", "end", values=(f"{cand.first_segment} ↔ {cand.second_segment}", f"{cand.score:.3f}",
                                                      f"{cand.gap_seconds:.1f}", ", ".join(cand.features_closest),
                                                      ", ".join(cand.features_furthest)))
        if not self.recur_candidates:
            self.recur_text.insert("end", "No recurrence candidates under the current heuristic thresholds. "
                                          "This does not show that no environment recurred.")
        self._draw_timeline(self.events)

    def _show_recurrence_detail(self, _event=None):
        selected = self.recur_view.selection()
        if not selected:
            return
        cand = self.recur_candidates[self.recur_view.index(selected[0])]
        lines = [f"{cand.first_segment} ↔ {cand.second_segment}: descriptive score {cand.score:.3f}",
                 f"Thresholds: {cand.thresholds}", f"Boundary uncertainty: about ±{cand.boundary_uncertainty_seconds:.1f} s",
                 "Intervening segments (score vs first): " + (", ".join(f"{i['segment']} {i['score_vs_first']:.3f}" for i in cand.intervening) or "n/a (cross-recording)"),
                 "Delta exceeds 2x within-segment spread: " + ", ".join(f"{k}={v}" for k, v in cand.exceeds_spread.items()),
                 "Confounders to consider: " + "; ".join(cand.confounders), cand.rationale]
        self.recur_text.delete("1.0", "end")
        self.recur_text.insert("end", "\n".join(lines))

    def _draw_timeline(self, events):
        self.timeline.delete("all")
        width = max(self.timeline.winfo_width(), 600)
        self.timeline.create_line(24, 54, width - 24, 54, fill="#64748b", width=2)
        if not self.analysis or self.analysis.duration_seconds <= 0:
            return
        duration = self.analysis.duration_seconds
        self.timeline.create_text(24, 78, text="0 s", fill="#cbd5e1", anchor="w")
        self.timeline.create_text(width - 24, 78, text=f"{duration:.1f} s", fill="#cbd5e1", anchor="e")
        for seg in self.segments:
            x0 = 24 + seg.start_seconds / duration * (width - 48)
            x1 = 24 + seg.end_seconds / duration * (width - 48)
            self.timeline.create_rectangle(x0, 48, x1, 60, outline="", fill="#0e7490" if seg.usable else "#475569")
        for event in events:
            x = 24 + event.timestamp_seconds / duration * (width - 48)
            self.timeline.create_line(x, 26, x, 66, fill="#fb7185", width=2)
            self.timeline.create_text(x, 16, text=f"{event.timestamp_seconds:.1f}s", fill="#fda4af")

    def _redraw_timeline(self, _event=None):
        if self.analysis:
            self._draw_timeline(self.events)

    # ------------------------------------------------------------ comparison
    def _fingerprint_of(self, path, channel=0):
        other = load_wav(path, channel)
        return make_fingerprint(analyze_audio(other.samples, other.sample_rate))

    def _show_comparison(self, other_fp, label, reference=None):
        comparison = compare_fingerprints({"version": self.fingerprint.version, "features": self.fingerprint.features},
                                          {"version": other_fp.version, "features": other_fp.features})
        self.compare_view.delete(*self.compare_view.get_children())
        for key, item in comparison.ranked():
            self.compare_view.insert("", "end", values=(key, f"{item['first']:.3f}", f"{item['second']:.3f}",
                                                        f"{item['delta']:+.3f} {item['unit']}",
                                                        f"{item['contribution_fraction']:.1%}", item["direction"]))
        groups = ", ".join(f"{g} {v:.0%}" for g, v in sorted(comparison.group_contributions.items(), key=lambda kv: -kv[1]))
        text = [comparison.explanation, f"Contribution by group: {groups}"]
        text += [f"WARNING: {w}" for w in comparison.warnings]
        if reference:
            text.append(caveat(reference["metadata"]))
        self.compare_summary.configure(text=f"{self.current_path.name} vs {label} — descriptive score {comparison.score:.3f} (not a probability)")
        self.compare_text.delete("1.0", "end")
        self.compare_text.insert("end", "\n".join(text))
        self.comparisons.append({"other": label, "reference_id": reference["id"] if reference else None, **comparison.to_dict()})
        self.notebook.select(2)

    def compare_file(self):
        if not self.fingerprint:
            messagebox.showinfo("Load evidence", "Open a WAV file before comparing.")
            return
        path = filedialog.askopenfilename(title="Select second PCM WAV", filetypes=[("WAV audio", "*.wav")])
        if not path:
            return
        try:
            self._show_comparison(self._fingerprint_of(path, int(self.channel_var.get()) - 1), Path(path).name)
        except Exception as exc:
            messagebox.showerror("Comparison failed", str(exc))

    def compare_to_reference(self):
        if not self.fingerprint:
            messagebox.showinfo("Load evidence", "Open a recording before comparing to a reference.")
            return
        selected = self.ref_view.selection()
        if not selected:
            messagebox.showinfo("Select reference", "Select a stored reference first.")
            return
        try:
            ref_id = int(self.ref_view.item(selected[0], "values")[0])
            check = self.store.verify_reference(ref_id)
            if not (check["source_hash_matches"] and check["metadata_hash_matches"]):
                raise ValueError("Reference file or metadata no longer matches its recorded hash; refusing to compare.")
            record = self.store.reference_record(ref_id)
            self._show_comparison(self._fingerprint_of(record["source_path"]), f"reference {ref_id}", record)
        except Exception as exc:
            messagebox.showerror("Comparison failed", str(exc))

    # ------------------------------------------------------------ references
    def _load_references(self):
        self.ref_view.delete(*self.ref_view.get_children())
        for ref in self.store.list_references():
            self.ref_view.insert("", "end", values=(ref["id"], ref["metadata"]["location_identifier"],
                                                    ref["metadata"]["acquisition_datetime"],
                                                    ref["quality"]["overall"], ref["source_sha256"]))

    def save_reference(self):
        path = filedialog.askopenfilename(title="Select reference exemplar WAV", filetypes=[("WAV audio", "*.wav")])
        if not path:
            return
        try:
            metadata = {key: entry.get() for key, entry in self.ref_entries.items()}
            metadata["checklist_confirmed"] = all(v.get() for v in self.checklist_vars) or bool(metadata.get("deviations", "").strip())
            problems = validate_reference_metadata(metadata)
            if problems:
                raise ValueError("\n".join(problems))
            audio = load_wav(path, 0)
            conflict = declared_rate_conflict(metadata, audio.sample_rate)
            if conflict:
                raise ValueError(conflict)
            quality = review_quality(audio.samples, audio.sample_rate)
            summary = "\n".join(f"{c['status'].upper()}: {c['check']} = {c['value']:.4g} — {c['detail']}" for c in quality["checks"])
            if quality["overall"] == "fail" and not messagebox.askyesno(
                    "Reference quality review failed", f"{summary}\n\nStore this reference anyway? It will be flagged as failed."):
                return
            ref_id = self.store.add_reference(path, metadata, quality)
            self._load_references()
            messagebox.showinfo("Reference stored", f"Reference {ref_id} stored (immutable). Quality: {quality['overall']}\n\n{summary}")
        except Exception as exc:
            messagebox.showerror("Unable to store reference", str(exc))

    def verify_reference(self):
        selected = self.ref_view.selection()
        if not selected:
            return
        ref_id = int(self.ref_view.item(selected[0], "values")[0])
        result = self.store.verify_reference(ref_id)
        ok = result["source_hash_matches"] and result["metadata_hash_matches"]
        (messagebox.showinfo if ok else messagebox.showerror)("Reference verification",
            f"Source file hash matches: {result['source_hash_matches']}\nMetadata hash matches: {result['metadata_hash_matches']}")

    # ---------------------------------------------------------------- export
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
        try:
            import json
            report = build_report(source_path=str(self.current_path), sha256=self.evidence_sha256,
                                  channel_index=self.audio.channel_index, channel_count=self.audio.channels,
                                  analysis=self.analysis, fingerprint=self.fingerprint,
                                  notes=self.store.notes_for(self.evidence_id),
                                  references=[{k: r[k] for k in ("id", "source_sha256", "metadata_sha256", "metadata", "quality")}
                                              for r in self.store.list_references()],
                                  comparisons=self.comparisons)
            Path(target).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            messagebox.showinfo("Export complete", f"Report written to {target}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    # ----------------------------------------------------------------- notes
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
        self.notes_view.delete(*self.notes_view.get_children())
        if self.evidence_id:
            for note in self.store.notes_for(self.evidence_id):
                self.notes_view.insert("", "end", values=(f"{note['timestamp_seconds']:.2f}", note["title"], note["body"]))

    def _close(self):
        self.cancel_event.set()
        self.store.close()
        self.destroy()


def main():
    app = FingerprinterApp()
    if os.environ.get("AEFP_SMOKE_TEST") == "1":
        app.after(750, app._close)
    app.mainloop()
