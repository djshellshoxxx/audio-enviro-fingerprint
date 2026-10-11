"""Tk desktop workstation for the beta analysis workflow.

Long analyses run on a worker thread; the Tk thread only polls a queue, so the
window stays responsive and analysis can be cancelled.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__
from .audio_io import SUPPORTED_EXTENSIONS, soundfile_available
from .case_store import CaseStore
from .comparison import compare_fingerprints
from .features import AnalysisCancelled
from .integrity import sha256_file
from .pipeline import DEFAULT_SETTINGS, analyze_file, bundle_report
from .recurrence import CONFOUNDERS, find_recurrences
from .reference import CAPTURE_CHECKLIST, RANKING_CAVEAT, ReferenceMetadata, quality_review, rank_against_references
from .report import verify_report, write_report

BG, PANEL, TEXT, MUTED, ACCENT = "#111827", "#1f2937", "#e5e7eb", "#9ca3af", "#67e8f9"
SCORE_CAVEAT = "Descriptive score only — not a probability of common location or an identification."
REFERENCE_FIELDS = (
    ("location_id", "Location identifier *"), ("captured_at_utc", "Captured at (ISO-8601 UTC) *"),
    ("operator", "Operator *"), ("consent_authority", "Consent / authority *"),
    ("recorder_make_model", "Recorder make/model *"), ("recorder_serial", "Recorder serial"),
    ("microphone_make_model", "Microphone make/model *"), ("input_chain", "Input chain"),
    ("sample_rate_hz", "Sample rate (Hz) *"), ("placement", "Placement *"), ("orientation", "Orientation"),
    ("height_m", "Height (m)"), ("source_signal", "Source signal *"),
    ("occupancy_activity", "Occupancy / activity"), ("weather", "Weather"), ("calibration", "Calibration"),
    ("repeat_index", "Repeat index"), ("deviations", "Deviations from protocol"), ("notes", "Notes"))


def _data_dir() -> Path:
    override = os.environ.get("AEFP_DATA_DIR")
    return Path(override) if override else Path.home() / ".audio-enviro-fingerprint"


def _clear(tree: ttk.Treeview) -> None:
    for item in tree.get_children():
        tree.delete(item)


def _table(parent, columns, height=8) -> ttk.Treeview:
    """Treeview with headings and a vertical scrollbar; columns = ((id, title, width), ...)."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height)
    for key, title, width in columns:
        tree.heading(key, text=title)
        tree.column(key, width=width, anchor="w", stretch=True)
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return tree


class FingerprinterApp(tk.Tk):
    def __init__(self, data_dir: Path | None = None):
        super().__init__()
        self.title(f"Audio Environment Fingerprinter {__version__}")
        self.geometry("1180x800")
        self.minsize(900, 620)
        self.configure(background=BG)
        self.bundle = None
        self.evidence_id = None
        self.extra_bundles = []
        self.comparison_bundle = None
        self.jobs: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self.busy = False
        self.closed = False
        self.exit_code = 0
        self.store = CaseStore((data_dir or _data_dir()) / "cases.sqlite3")
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.poll_id = self.after(100, self._poll_jobs)

    # ---------------------------------------------------------------- layout
    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.configure("Header.TLabel", font=("Segoe UI", 17, "bold"), foreground=ACCENT)
        style.configure("Section.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Sub.TLabel", foreground=MUTED)
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL, rowheight=24)
        style.configure("Treeview.Heading", background="#374151", foreground="#f9fafb")

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="ROOM & ENVIRONMENT FINGERPRINTER", style="Header.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Evidence integrity · measurable acoustic features · reviewable findings",
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 10))

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill="x", pady=(0, 6))
        self.action_buttons = []
        for text, command in (("Open recording…", self.open_file), ("Compare recording…", self.compare_file),
                              ("Export report…", self.export_json), ("Verify report…", self.verify_report_file)):
            button = ttk.Button(toolbar, text=text, command=command)
            button.pack(side="left", padx=(0, 6))
            self.action_buttons.append(button)
        ttk.Label(toolbar, text="Channel").pack(side="left", padx=(12, 4))
        self.channel_var = tk.StringVar(value="1")
        self.channel_box = ttk.Combobox(toolbar, textvariable=self.channel_var, width=4, state="disabled", values=["1"])
        self.channel_box.pack(side="left")
        self.channel_box.bind("<<ComboboxSelected>>", self._channel_changed)

        settings = ttk.Frame(outer)
        settings.pack(fill="x", pady=(0, 6))
        self.setting_vars = {}
        for key, label in (("frame_seconds", "Frame (s)"), ("hop_seconds", "Hop (s)"),
                           ("transition_threshold", "Transition threshold"),
                           ("minimum_separation_seconds", "Min. separation (s)"),
                           ("recurrence_max_distance", "Recurrence max distance")):
            ttk.Label(settings, text=label, style="Sub.TLabel").pack(side="left", padx=(0, 3))
            var = tk.StringVar(value=f"{DEFAULT_SETTINGS[key]:g}")
            ttk.Entry(settings, textvariable=var, width=6).pack(side="left", padx=(0, 10))
            self.setting_vars[key] = var
        ttk.Button(settings, text="Re-analyze", command=self._reanalyze).pack(side="left")
        ttk.Label(settings, text="(heuristic, unvalidated defaults)", style="Sub.TLabel").pack(side="left", padx=8)

        progress_row = ttk.Frame(outer)
        progress_row.pack(fill="x", pady=(0, 6))
        self.progress = ttk.Progressbar(progress_row, maximum=1.0, length=300)
        self.progress.pack(side="left")
        self.cancel_button = ttk.Button(progress_row, text="Cancel", command=self.cancel_event.set, state="disabled")
        self.cancel_button.pack(side="left", padx=6)
        self.status_label = ttk.Label(progress_row, text="No evidence loaded", style="Sub.TLabel")
        self.status_label.pack(side="left", padx=6)

        self.hash_label = ttk.Label(outer, text="Evidence SHA-256: —", style="Sub.TLabel", wraplength=1100)
        self.hash_label.pack(anchor="w", pady=(0, 6))
        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)
        self._build_analysis_tab()
        self._build_channels_tab()
        self._build_recurrence_tab()
        self._build_markers_tab()
        self._build_notes_tab()
        self._build_compare_tab()
        self._build_references_tab()
        ttk.Label(outer, text="Screening aid only. Similarity does not identify a physical location.",
                  style="Sub.TLabel").pack(anchor="w", pady=(6, 0))

    def _tab(self, title):
        frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(frame, text=title)
        return frame

    def _build_analysis_tab(self):
        tab = self._tab("Analysis")
        self.provenance_label = ttk.Label(tab, text="Decoder: —", style="Sub.TLabel", wraplength=1050)
        self.provenance_label.pack(anchor="w")
        ttk.Label(tab, text="Timeline: transition candidates (red), manual markers (amber), notes (cyan)",
                  style="Section.TLabel").pack(anchor="w", pady=(6, 0))
        self.timeline = tk.Canvas(tab, height=100, background="#0b1220", highlightthickness=0)
        self.timeline.pack(fill="x", pady=(4, 8))
        self.timeline.bind("<Configure>", lambda _e: self._draw_timeline())
        self.transitions = _table(tab, (("time", "Time (s)", 90), ("strength", "Change score", 110),
                                        ("evidence", "Measured changes", 800)), height=5)
        ttk.Label(tab, text="Median fingerprint features", style="Section.TLabel").pack(anchor="w", pady=(8, 2))
        self.features = _table(tab, (("feature", "Feature", 300), ("value", "Measured value", 300)), height=8)

    def _build_channels_tab(self):
        tab = self._tab("Channels")
        ttk.Label(tab, text="Descriptive per-channel statistics (analysis uses the selected channel; no downmix).",
                  style="Sub.TLabel").pack(anchor="w")
        self.channel_table = _table(tab, (("channel", "Channel", 80), ("rms", "RMS (dBFS)", 120),
                                          ("peak", "Peak (dBFS)", 120), ("dc", "DC offset", 120)), height=6)
        ttk.Label(tab, text="Inter-channel correlation and level difference", style="Section.TLabel").pack(anchor="w", pady=(8, 2))
        self.pair_table = _table(tab, (("pair", "Pair", 100), ("corr", "Pearson r", 120),
                                       ("level", "Level difference (dB)", 180)), height=5)
        self.channel_notes = ttk.Label(tab, text="", style="Sub.TLabel", wraplength=1050, justify="left")
        self.channel_notes.pack(anchor="w", pady=6)

    def _build_recurrence_tab(self):
        tab = self._tab("Recurrence")
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Add recordings for cross-recording search…", command=self.add_recurrence_files).pack(side="left")
        ttk.Button(bar, text="Clear added", command=self._clear_extra).pack(side="left", padx=6)
        ttk.Button(bar, text="Save run to case", command=self.save_recurrence_run).pack(side="left")
        self.extra_label = ttk.Label(bar, text="Only the loaded recording is searched.", style="Sub.TLabel")
        self.extra_label.pack(side="left", padx=10)
        ttk.Label(tab, text="Segments between transition candidates", style="Section.TLabel").pack(anchor="w", pady=(8, 2))
        self.segment_table = _table(tab, (("id", "Segment", 160), ("span", "Span (s)", 140), ("frames", "Frames", 70),
                                          ("rms", "RMS dBFS", 90), ("centroid", "Centroid Hz", 100),
                                          ("flatness", "Flatness", 90)), height=6)
        ttk.Label(tab, text="Candidate recurrences (screening only)", style="Section.TLabel").pack(anchor="w", pady=(8, 2))
        self.recurrence_table = _table(tab, (("first", "First", 200), ("second", "Second", 200),
                                             ("distance", "Distance", 90), ("largest", "Largest differences", 500)), height=6)
        ttk.Label(tab, text="Possible confounders: " + "; ".join(CONFOUNDERS) + ".", style="Sub.TLabel",
                  wraplength=1050).pack(anchor="w", pady=4)

    def _build_markers_tab(self):
        tab = self._tab("Markers")
        ttk.Label(tab, text="Manual transition markers. Every edit or deletion requires a reason and is kept "
                            "in the revision history.", style="Sub.TLabel").pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=6)
        for text, command in (("Add marker…", self.add_marker), ("Edit selected…", self.edit_marker),
                              ("Delete selected…", self.delete_marker), ("Show history", self.show_marker_history)):
            ttk.Button(bar, text=text, command=command).pack(side="left", padx=(0, 6))
        self.show_deleted = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Show deleted", variable=self.show_deleted, command=self._load_markers).pack(side="left", padx=8)
        self.marker_table = _table(tab, (("time", "Time (s)", 90), ("label", "Label", 360), ("kind", "Kind", 80),
                                         ("rev", "Revision", 80), ("status", "Status", 300)), height=10)

    def _build_notes_tab(self):
        tab = self._tab("Examiner Notes")
        ttk.Label(tab, text="Notes are saved with the evidence file hash and the selected timestamp.",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 6))
        form = ttk.Frame(tab)
        form.pack(fill="x")
        ttk.Label(form, text="Time (seconds)").grid(row=0, column=0, sticky="w")
        self.note_time = ttk.Entry(form, width=14)
        self.note_time.insert(0, "0")
        self.note_time.grid(row=0, column=1, sticky="w", padx=(8, 18))
        ttk.Label(form, text="Title").grid(row=0, column=2, sticky="w")
        self.note_title = ttk.Entry(form)
        self.note_title.grid(row=0, column=3, sticky="ew", padx=8)
        form.columnconfigure(3, weight=1)
        ttk.Label(tab, text="Observation").pack(anchor="w", pady=(10, 4))
        self.note_body = tk.Text(tab, height=4, background=PANEL, foreground="#f9fafb",
                                 insertbackground="white", wrap="word")
        self.note_body.pack(fill="x")
        ttk.Button(tab, text="Save timestamped note", command=self.save_note).pack(anchor="w", pady=6)
        self.notes_view = _table(tab, (("time", "Time (s)", 90), ("title", "Title", 200),
                                       ("body", "Observation", 600), ("created", "Created (UTC)", 200)))

    def _build_compare_tab(self):
        tab = self._tab("Compare")
        self.compare_label = ttk.Label(tab, text="Use “Compare recording…” to compare the loaded recording "
                                                  "with another file.", style="Sub.TLabel", wraplength=1050,
                                       justify="left")
        self.compare_label.pack(anchor="w")
        self.group_table = _table(tab, (("group", "Feature group", 160), ("count", "Features", 80),
                                        ("mean", "Mean normalized Δ", 150), ("share", "Share of distance", 150)), height=4)
        self.compare_table = _table(tab, (("feature", "Feature", 240), ("first", "Loaded", 110), ("second", "Other", 110),
                                          ("delta", "Δ", 100), ("norm", "Normalized Δ", 110),
                                          ("share", "Share of distance", 130)), height=12)

    def _build_references_tab(self):
        tab = self._tab("References")
        ttk.Label(tab, text="Known-location exemplars captured under the controlled protocol "
                            "(docs/REFERENCE_ACQUISITION.md). " + RANKING_CAVEAT,
                  style="Sub.TLabel", wraplength=1050, justify="left").pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=6)
        ttk.Button(bar, text="Register loaded recording as reference…", command=self.register_reference).pack(side="left")
        ttk.Button(bar, text="Rank loaded recording against references", command=self.rank_references).pack(side="left", padx=6)
        self.reference_table = _table(tab, (("rank", "Rank", 60), ("ref", "Ref", 50), ("location", "Location", 200),
                                            ("score", "Score", 80), ("status", "Status / notes", 600)), height=12)

    # ------------------------------------------------------------- workers
    def _settings(self) -> dict:
        values = {}
        for key, var in self.setting_vars.items():
            try:
                values[key] = float(var.get())
            except ValueError:
                raise ValueError(f"Setting '{key}' must be a number") from None
        return values

    def _set_busy(self, busy: bool, text: str = ""):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for button in self.action_buttons:
            button.configure(state=state)
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if busy:
            self.cancel_event.clear()
            self.progress.configure(value=0)
        if text:
            self.status_label.configure(text=text)

    def _run_job(self, label, work, on_done):
        """Run ``work(progress, cancel)`` on a thread and deliver its result to ``on_done`` on the Tk thread."""
        if self.busy:
            messagebox.showinfo("Busy", "Wait for the current analysis to finish or cancel it.")
            return
        self._set_busy(True, label)

        def progress(value):
            self.jobs.put(("progress", value))

        def runner():
            try:
                self.jobs.put(("done", on_done, work(progress, self.cancel_event), None))
            except Exception as exc:  # delivered to the UI thread
                self.jobs.put(("done", on_done, None, exc))

        threading.Thread(target=runner, daemon=True).start()

    def _poll_jobs(self):
        try:
            while True:
                message = self.jobs.get_nowait()
                if message[0] == "progress":
                    self.progress.configure(value=message[1])
                else:
                    _, on_done, result, error = message
                    self._set_busy(False)
                    if isinstance(error, AnalysisCancelled):
                        self.status_label.configure(text="Analysis cancelled; previous results kept.")
                    elif error is not None:
                        self.status_label.configure(text="Analysis failed; previous results kept.")
                        on_done(None, error)
                    else:
                        self.progress.configure(value=1.0)
                        on_done(result, None)
        except queue.Empty:
            pass
        self.poll_id = self.after(100, self._poll_jobs)

    # ------------------------------------------------------------- loading
    def _filetypes(self):
        patterns = " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS) if soundfile_available() else "*.wav *.wave *.bwf"
        return [("Audio", patterns), ("All files", "*.*")]

    def open_file(self):
        path = filedialog.askopenfilename(title="Select recording", filetypes=self._filetypes())
        if path:
            self.load_path(path, 0)

    def load_path(self, path, channel=0, on_loaded=None):
        try:
            settings = self._settings()
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return

        def done(bundle, error):
            if error is not None:
                messagebox.showerror("Unable to analyze recording", str(error))
                return
            try:
                self._accept_bundle(bundle)
            except Exception as exc:
                messagebox.showerror("Unable to register evidence", str(exc))
                return
            if on_loaded:
                on_loaded()

        self._run_job(f"Analyzing {Path(path).name}…",
                      lambda progress, cancel: analyze_file(path, channel, settings, progress, cancel), done)

    def _accept_bundle(self, bundle):
        evidence_id = self.store.register_evidence(bundle.path)
        if self.store.evidence_record(evidence_id)["sha256"] != bundle.sha256:
            raise ValueError("The source file changed after analysis. Re-open a stable copy of the evidence.")
        fp = bundle.fingerprint
        self.store.store_fingerprint(evidence_id, bundle.audio.selected_channel, fp.version, fp.canonical_json,
                                     fp.fingerprint_hash)
        if self.bundle is None or self.bundle.path != bundle.path:
            self.extra_bundles = []
            self.comparison_bundle = None
        self.bundle, self.evidence_id = bundle, evidence_id
        audio = bundle.audio
        channels = [str(i + 1) for i in range(audio.channels)]
        self.channel_box.configure(values=channels, state="readonly" if audio.channels > 1 else "disabled")
        self.channel_var.set(str(audio.selected_channel + 1))
        self.status_label.configure(text=f"{bundle.path.name} · {audio.duration_seconds:.2f} s · {audio.sample_rate} Hz · "
                                         f"channel {audio.selected_channel + 1} of {audio.channels}")
        self.hash_label.configure(text=f"Evidence SHA-256: {bundle.sha256}\n"
                                       f"Acoustic fingerprint {fp.version}: {fp.fingerprint_hash}")
        decoder = audio.decoder or {}
        notes = " ".join(decoder.get("notes", []))
        lossy = " · LOSSY SOURCE" if decoder.get("lossy") else ""
        self.provenance_label.configure(text=f"Decoder: {decoder.get('backend', '?')} ({decoder.get('backend_version', '?')})"
                                             f" · {decoder.get('container', '?')} / {decoder.get('encoding', '?')}{lossy}"
                                             + (f" · {notes}" if notes else ""))
        self._show_results()

    def _channel_changed(self, _event=None):
        if self.bundle:
            channel = int(self.channel_var.get()) - 1
            if channel != self.bundle.audio.selected_channel:
                self.load_path(self.bundle.path, channel)

    def _reanalyze(self):
        if self.bundle:
            self.load_path(self.bundle.path, self.bundle.audio.selected_channel)

    # ------------------------------------------------------------- display
    def _show_results(self):
        bundle = self.bundle
        _clear(self.transitions)
        _clear(self.features)
        for event in bundle.transitions:
            evidence = ", ".join(f"{key} {value:+.2f}" for key, value in event.evidence.items())
            self.transitions.insert("", "end", values=(f"{event.timestamp_seconds:.2f}", f"{event.strength:.3f}", evidence))
        for key, value in bundle.fingerprint.features.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    self.features.insert("", "end", values=(f"Band power · {subkey}", f"{subvalue:.2f} dB"))
            elif isinstance(value, float):
                unit = " Hz" if key.endswith("_hz") else " dBFS" if "dbfs" in key else " s" if key.endswith("seconds") else ""
                self.features.insert("", "end", values=(key, f"{value:.4f}{unit}"))
            else:
                self.features.insert("", "end", values=(key, value))
        self._show_channels()
        self._show_recurrence()
        self._load_markers()
        self._load_notes()
        self._draw_timeline()

    def _draw_timeline(self):
        canvas = self.timeline
        canvas.delete("all")
        width = max(canvas.winfo_width(), 600)
        canvas.create_line(24, 54, width - 24, 54, fill="#64748b", width=2)
        if not self.bundle or self.bundle.analysis.duration_seconds <= 0:
            return
        duration = self.bundle.analysis.duration_seconds
        canvas.create_text(24, 84, text="0 s", fill="#cbd5e1", anchor="w")
        canvas.create_text(width - 24, 84, text=f"{duration:.1f} s", fill="#cbd5e1", anchor="e")

        def x_of(seconds):
            return 24 + min(max(seconds, 0.0), duration) / duration * (width - 48)

        for event in self.bundle.transitions:
            x = x_of(event.timestamp_seconds)
            canvas.create_line(x, 26, x, 66, fill="#fb7185", width=2)
            canvas.create_text(x, 16, text=f"{event.timestamp_seconds:.1f}s", fill="#fda4af")
        if self.evidence_id:
            for marker in self.store.markers_for(self.evidence_id):
                x = x_of(marker["timestamp_seconds"])
                canvas.create_line(x, 36, x, 72, fill="#fbbf24", width=2, dash=(3, 2))
            for note in self.store.notes_for(self.evidence_id):
                x = x_of(note["timestamp_seconds"])
                canvas.create_oval(x - 3, 51, x + 3, 57, fill="#22d3ee", outline="")

    def _show_channels(self):
        summary = self.bundle.channel_summary
        _clear(self.channel_table)
        _clear(self.pair_table)
        for item in summary["per_channel"]:
            marker = " (analyzed)" if item["channel"] == self.bundle.audio.selected_channel else ""
            self.channel_table.insert("", "end", values=(f"{item['channel'] + 1}{marker}", f"{item['rms_dbfs']:.2f}",
                                                         f"{item['peak_dbfs']:.2f}", f"{item['dc_offset']:+.5f}"))
        correlation = summary["correlation"]
        for pair, difference in summary["level_difference_db"].items():
            i, j = (int(part) - 1 for part in pair.split("-"))
            self.pair_table.insert("", "end", values=(pair, f"{correlation[i][j]:+.3f}", f"{difference:+.2f}"))
        self.channel_notes.configure(text="\n".join(summary["notes"]))

    def _all_segments(self):
        segments = list(self.bundle.segments)
        for extra in self.extra_bundles:
            segments.extend(extra.segments)
        return segments

    def _recurrences(self):
        if not self.extra_bundles:
            return self.bundle.recurrences
        return find_recurrences(self._all_segments(), self.bundle.settings["recurrence_max_distance"])

    def _show_recurrence(self):
        _clear(self.segment_table)
        _clear(self.recurrence_table)
        for segment in self._all_segments():
            f = segment.features
            self.segment_table.insert("", "end", values=(segment.segment_id, f"{segment.start_seconds:.1f}–{segment.end_seconds:.1f}",
                                                         segment.frame_count, f"{f['rms_dbfs']:.1f}",
                                                         f"{f['spectral_centroid_hz']:.0f}", f"{f['spectral_flatness']:.3f}"))
        for match in self._recurrences():
            largest = sorted(match.differences.items(), key=lambda kv: kv[1]["normalized_delta"], reverse=True)[:3]
            text = "; ".join(f"{key} {item['delta']:+.2f}" for key, item in largest)
            self.recurrence_table.insert("", "end", values=(
                f"{match.first.segment_id} ({match.first.start_seconds:.0f}–{match.first.end_seconds:.0f} s)",
                f"{match.second.segment_id} ({match.second.start_seconds:.0f}–{match.second.end_seconds:.0f} s)",
                f"{match.distance:.3f}", text))
        names = ", ".join(b.path.name for b in self.extra_bundles)
        self.extra_label.configure(text=f"Also searching: {names}" if names else "Only the loaded recording is searched.")

    # ------------------------------------------------------------- recurrence
    def add_recurrence_files(self):
        if not self.bundle:
            messagebox.showinfo("Load evidence", "Open a recording first.")
            return
        paths = filedialog.askopenfilenames(title="Select recordings to search", filetypes=self._filetypes())
        if not paths:
            return
        settings = dict(self.bundle.settings)

        def work(progress, cancel):
            bundles = []
            for index, path in enumerate(paths):
                def scaled(value, index=index):
                    progress((index + value) / len(paths))
                try:
                    bundles.append(analyze_file(path, 0, settings, scaled, cancel))  # channel 1 of each added file
                except AnalysisCancelled:
                    raise
                except Exception as exc:
                    raise ValueError(f"{Path(path).name}: {exc}") from exc
            return bundles

        def done(bundles, error):
            if error is not None:
                messagebox.showerror("Unable to analyze recording", str(error))
                return
            known = {b.path for b in self.extra_bundles} | {self.bundle.path}
            self.extra_bundles.extend(b for b in bundles if b.path not in known)
            self._show_recurrence()

        self._run_job("Analyzing recordings for recurrence search…", work, done)

    def _clear_extra(self):
        self.extra_bundles = []
        if self.bundle:
            self._show_recurrence()

    def save_recurrence_run(self):
        if not self.bundle:
            messagebox.showinfo("Load evidence", "Open a recording first.")
            return
        from .report import to_plain
        recordings = [{"path": str(b.path), "sha256": b.sha256, "channel": b.audio.selected_channel}
                      for b in [self.bundle, *self.extra_bundles]]
        run_id = self.store.save_recurrence_run({"settings": self.bundle.settings, "recordings": recordings,
                                                 "application_version": __version__},
                                                to_plain(self._recurrences()))
        messagebox.showinfo("Saved", f"Recurrence run {run_id} saved to the case database.")

    # ------------------------------------------------------------- markers
    def _selected_marker(self):
        selection = self.marker_table.selection()
        if not selection:
            messagebox.showinfo("Select a marker", "Select a marker in the list first.")
            return None
        return int(selection[0])

    def _ask_time(self, title, initial=None):
        return simpledialog.askfloat(title, "Time (seconds)", parent=self, initialvalue=initial, minvalue=0.0,
                                     maxvalue=self.bundle.audio.duration_seconds)

    def add_marker(self):
        if not self.evidence_id:
            messagebox.showinfo("Load evidence", "Open a recording first.")
            return
        timestamp = self._ask_time("Add marker")
        if timestamp is None:
            return
        label = simpledialog.askstring("Add marker", "Label", parent=self)
        if not label:
            return
        try:
            self.store.add_marker(self.evidence_id, timestamp, label)
        except ValueError as exc:
            messagebox.showerror("Unable to add marker", str(exc))
        self._load_markers()

    def edit_marker(self):
        marker_id = self._selected_marker()
        if marker_id is None:
            return
        current = next((m for m in self.store.markers_for(self.evidence_id, True) if m["id"] == marker_id), None)
        if current is None or current["deleted_utc"]:
            messagebox.showinfo("Marker deleted", "Deleted markers cannot be edited.")
            return
        timestamp = self._ask_time("Edit marker", current["timestamp_seconds"])
        if timestamp is None:
            return
        label = simpledialog.askstring("Edit marker", "Label", parent=self, initialvalue=current["label"])
        reason = simpledialog.askstring("Edit marker", "Reason for this change (required)", parent=self)
        if label is None or reason is None:
            return
        try:
            self.store.update_marker(marker_id, timestamp, label, reason)
        except ValueError as exc:
            messagebox.showerror("Unable to edit marker", str(exc))
        self._load_markers()

    def delete_marker(self):
        marker_id = self._selected_marker()
        if marker_id is None:
            return
        reason = simpledialog.askstring("Delete marker", "Reason for deletion (required; history is kept)", parent=self)
        if reason is None:
            return
        try:
            self.store.delete_marker(marker_id, reason)
        except ValueError as exc:
            messagebox.showerror("Unable to delete marker", str(exc))
        self._load_markers()

    def show_marker_history(self):
        marker_id = self._selected_marker()
        if marker_id is None:
            return
        lines = [f"rev {h['revision']} {h['action']} @ {h['recorded_utc']}: {h['timestamp_seconds']:.2f} s "
                 f"“{h['label']}”" + (f" — reason: {h['reason']}" if h["reason"] else "")
                 for h in self.store.marker_history(marker_id)]
        messagebox.showinfo("Marker history", "\n".join(lines))

    def _load_markers(self):
        _clear(self.marker_table)
        if not self.evidence_id:
            return
        for marker in self.store.markers_for(self.evidence_id, self.show_deleted.get()):
            status = f"deleted: {marker['deleted_reason']}" if marker["deleted_utc"] else "active"
            self.marker_table.insert("", "end", iid=str(marker["id"]), values=(
                f"{marker['timestamp_seconds']:.2f}", marker["label"], marker["kind"], marker["revision"], status))
        self._draw_timeline()

    # ------------------------------------------------------------- notes
    def save_note(self):
        if not self.evidence_id:
            messagebox.showinfo("Load evidence", "Open evidence before writing a note.")
            return
        try:
            timestamp = float(self.note_time.get())
            if not 0 <= timestamp <= self.bundle.audio.duration_seconds:
                raise ValueError("Timestamp must be between 0 and the recording duration")
            self.store.add_note(self.evidence_id, timestamp, self.note_title.get(), self.note_body.get("1.0", "end"))
            self.note_title.delete(0, "end")
            self.note_body.delete("1.0", "end")
            self._load_notes()
        except Exception as exc:
            messagebox.showerror("Unable to save note", str(exc))

    def _load_notes(self):
        _clear(self.notes_view)
        if self.evidence_id:
            for note in self.store.notes_for(self.evidence_id):
                self.notes_view.insert("", "end", values=(f"{note['timestamp_seconds']:.2f}", note["title"],
                                                          note["body"], note["created_utc"]))
        self._draw_timeline()

    # ------------------------------------------------------------- compare
    def compare_file(self):
        if not self.bundle:
            messagebox.showinfo("Load evidence", "Open a recording before comparing.")
            return
        path = filedialog.askopenfilename(title="Select recording to compare", filetypes=self._filetypes())
        if not path:
            return
        settings = dict(self.bundle.settings)

        def done(other, error):
            if error is not None:
                messagebox.showerror("Comparison failed", str(error))
                return
            self.comparison_bundle = other
            self._show_comparison()

        self._run_job(f"Analyzing {Path(path).name} for comparison…",
                      lambda progress, cancel: analyze_file(path, 0, settings, progress, cancel), done)

    def _show_comparison(self):
        first, other = self.bundle.fingerprint, self.comparison_bundle.fingerprint
        try:
            result = compare_fingerprints({"version": first.version, "features": first.features},
                                          {"version": other.version, "features": other.features})
        except ValueError as exc:
            messagebox.showerror("Comparison failed", str(exc))
            return
        _clear(self.group_table)
        _clear(self.compare_table)
        for name, info in result.groups.items():
            self.group_table.insert("", "end", values=(name, info["feature_count"], f"{info['mean_normalized_delta']:.3f}",
                                                       f"{info['contribution']:.1%}"))
        for key, item in sorted(result.differences.items(), key=lambda kv: -result.contributions[kv[0]]):
            self.compare_table.insert("", "end", values=(key, f"{item['first']:.3f}", f"{item['second']:.3f}",
                                                         f"{item['delta']:+.3f}", f"{item['normalized_delta']:.3f}",
                                                         f"{result.contributions[key]:.1%}"))
        notes = []
        if first.features.get("sample_rate_hz") != other.features.get("sample_rate_hz"):
            notes.append("Sample rates differ; bands above the lower Nyquist limit are not comparable.")
        if self.comparison_bundle.audio.decoder.get("lossy") or self.bundle.audio.decoder.get("lossy"):
            notes.append("At least one source is lossy-coded; spectral/noise features are affected.")
        self.compare_label.configure(text=f"{self.bundle.path.name} vs {self.comparison_bundle.path.name} "
                                          f"(SHA-256 {self.comparison_bundle.sha256[:16]}…): descriptive score "
                                          f"{result.score:.3f}, distance {result.distance:.3f}. {SCORE_CAVEAT} "
                                          + " ".join(notes))
        self.notebook.select(5)

    # ------------------------------------------------------------- references
    def register_reference(self):
        if not self.bundle:
            messagebox.showinfo("Load evidence", "Open the reference recording first.")
            return
        ReferenceDialog(self)

    def rank_references(self):
        if not self.bundle:
            messagebox.showinfo("Load evidence", "Open a recording first.")
            return
        fp = self.bundle.fingerprint
        references = [ref for ref in self.store.references() if ref["evidence_sha256"] != self.bundle.sha256]
        ranked = rank_against_references({"version": fp.version, "features": fp.features}, references)
        _clear(self.reference_table)
        for item in ranked:
            status = item["status"] if item["status"] != "ranked" else "; ".join(item["notes"]) or "ranked"
            if item["status"] == "skipped":
                status += f": {item['explanation']}"
            score = "—" if item["score"] is None else f"{item['score']:.3f}"
            self.reference_table.insert("", "end", values=(item["rank"] or "—", item["reference_id"],
                                                           item["location_id"], score, status))
        if not ranked:
            messagebox.showinfo("No references", "No other reference recordings are registered in the case database.")

    # ------------------------------------------------------------- export
    def build_current_report(self) -> dict:
        if sha256_file(self.bundle.path) != self.bundle.sha256:
            raise ValueError("The source file no longer matches the hash recorded at import. "
                             "Re-open a stable copy before exporting.")
        return bundle_report(self.bundle, __version__, notes=self.store.notes_for(self.evidence_id),
                             markers=self.store.markers_for(self.evidence_id, include_deleted=True))

    def export_json(self):
        if not self.bundle:
            messagebox.showinfo("Load evidence", "Open a recording before exporting.")
            return
        target = filedialog.asksaveasfilename(title="Export analysis report", defaultextension=".json",
                                              filetypes=[("JSON", "*.json")])
        if not target:
            return
        try:
            write_report(self.build_current_report(), target)
            messagebox.showinfo("Export complete", f"Report written to {target}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def verify_report_file(self):
        path = filedialog.askopenfilename(title="Select report to verify", filetypes=[("JSON", "*.json")])
        if not path:
            return
        evidence = None
        if messagebox.askyesno("Verify evidence", "Also re-hash the original evidence file?"):
            evidence = filedialog.askopenfilename(title="Select original evidence file") or None
        result = verify_report(path, evidence_path=evidence)
        lines = [f"{'PASS' if c['ok'] else 'FAIL'} · {name}: {c['detail']}" for name, c in result["checks"].items()]
        (messagebox.showinfo if result["ok"] else messagebox.showerror)(
            "Report verified" if result["ok"] else "Report verification FAILED", "\n".join(lines))

    def _close(self):
        if self.closed:
            return
        self.closed = True
        self.after_cancel(self.poll_id)
        self.cancel_event.set()
        self.store.close()
        self.destroy()


class ReferenceDialog(tk.Toplevel):
    """Controlled-capture metadata form with a live quality review before saving."""

    def __init__(self, app: FingerprinterApp):
        super().__init__(app)
        self.app = app
        self.title("Register reference recording")
        self.configure(background=BG)
        self.transient(app)
        bundle = app.bundle
        body = ttk.Frame(self, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"{bundle.path.name} · SHA-256 {bundle.sha256[:16]}… · channel "
                             f"{bundle.audio.selected_channel + 1}", style="Sub.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        defaults = {"sample_rate_hz": str(bundle.audio.sample_rate), "repeat_index": "1"}
        self.vars = {}
        for index, (key, label) in enumerate(REFERENCE_FIELDS):
            row, col = 1 + index // 2, (index % 2) * 2
            ttk.Label(body, text=label).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=2)
            var = tk.StringVar(value=defaults.get(key, ""))
            ttk.Entry(body, textvariable=var, width=34).grid(row=row, column=col + 1, sticky="ew", padx=(0, 14), pady=2)
            self.vars[key] = var
        last = 2 + len(REFERENCE_FIELDS) // 2
        ttk.Label(body, text="Repeat captures of this location in the series").grid(row=last, column=0, sticky="w")
        self.repeat_count = tk.StringVar(value="1")
        ttk.Entry(body, textvariable=self.repeat_count, width=8).grid(row=last, column=1, sticky="w")
        self.review_label = ttk.Label(body, text="", style="Sub.TLabel", wraplength=760, justify="left")
        self.review_label.grid(row=last + 1, column=0, columnspan=4, sticky="w", pady=8)
        buttons = ttk.Frame(body)
        buttons.grid(row=last + 2, column=0, columnspan=4, sticky="e")
        ttk.Button(buttons, text="Review quality", command=self.review).pack(side="left", padx=4)
        ttk.Button(buttons, text="Save reference", command=self.save).pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=4)

    def metadata(self) -> ReferenceMetadata:
        values = {key: var.get().strip() for key, var in self.vars.items()}
        try:
            values["sample_rate_hz"] = int(values["sample_rate_hz"] or 0)
            values["repeat_index"] = int(values["repeat_index"] or 1)
            values["height_m"] = float(values["height_m"]) if values["height_m"] else None
        except ValueError:
            raise ValueError("Sample rate and repeat index must be integers; height must be a number") from None
        values["channel"] = self.app.bundle.audio.selected_channel
        return ReferenceMetadata(**values)

    def review(self) -> dict | None:
        try:
            meta = self.metadata()
            repeats = int(self.repeat_count.get() or 0)
        except ValueError as exc:
            self.review_label.configure(text=str(exc))
            return None
        audio = self.app.bundle.audio
        result = quality_review(meta, {"sample_rate": audio.sample_rate, "channels": audio.channels,
                                       "duration_seconds": audio.duration_seconds, "repeat_count": repeats,
                                       "sha256": self.app.bundle.sha256})
        missing = [item.replace("_", " ") for item in CAPTURE_CHECKLIST if not result["checklist"][item]]
        self.review_label.configure(text=f"Grade {result['grade']} · checklist {result['completeness']:.0%} complete\n"
                                         + ("Missing: " + ", ".join(missing) + "\n" if missing else "")
                                         + "\n".join(result["issues"]))
        return result

    def save(self):
        result = self.review()
        if result is None:
            return
        if result["grade"] == "insufficient":
            messagebox.showerror("Reference not saved", "Resolve the listed metadata problems first.", parent=self)
            return
        try:
            reference_id = self.app.store.add_reference(self.app.evidence_id, self.metadata(),
                                                        self.app.bundle.audio.selected_channel)
        except ValueError as exc:
            messagebox.showerror("Reference not saved", str(exc), parent=self)
            return
        messagebox.showinfo("Reference saved", f"Reference {reference_id} saved with grade {result['grade']}.",
                            parent=self)
        self.destroy()


def _smoke_test(app: FingerprinterApp) -> None:
    """CI hook: optionally analyze AEFP_SMOKE_FILE, write AEFP_SMOKE_REPORT, then exit with a status code."""
    path, report_path = os.environ.get("AEFP_SMOKE_FILE"), os.environ.get("AEFP_SMOKE_REPORT")

    def fail(message):
        if app.closed:
            return
        print(f"smoke test failed: {message}", file=sys.stderr)
        app.exit_code = 1
        app._close()

    def write_and_exit():
        try:
            if report_path:
                write_report(app.build_current_report(), report_path)
            app._close()
        except Exception as exc:
            fail(exc)

    if not path:
        app.after(750, app._close)
        return
    messagebox.showerror = lambda title, message, **_: fail(f"{title}: {message}")
    app.after(200, lambda: app.load_path(path, 0, on_loaded=write_and_exit))
    app.after(120000, lambda: fail("timed out"))


def main():
    smoke = os.environ.get("AEFP_SMOKE_TEST") == "1"
    data_dir = None
    if smoke and os.environ.get("AEFP_SMOKE_FILE"):
        import tempfile
        data_dir = Path(tempfile.mkdtemp(prefix="aefp-smoke-"))
    app = FingerprinterApp(data_dir)
    if smoke:
        _smoke_test(app)
    app.mainloop()
    if app.exit_code:
        sys.exit(app.exit_code)
