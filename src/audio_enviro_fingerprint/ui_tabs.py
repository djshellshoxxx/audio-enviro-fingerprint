"""Tk tab widgets. Each tab renders from pipeline results and owns no analysis logic."""
from __future__ import annotations

import base64
import tkinter as tk
from tkinter import messagebox, ttk

from .reference import REQUIRED, ReferenceMetadata, review_reference
from .spectrogram import compute_spectrogram, colorize, encode_png

BG, PANEL, FG, MUTED, ACCENT, WARN = "#111827", "#1f2937", "#e5e7eb", "#9ca3af", "#67e8f9", "#fb7185"


class ScrollableTab(ttk.Frame):
    """Vertically scroll review controls without changing native table scrolling."""
    def __init__(self, parent, padding=12):
        super().__init__(parent)
        self.scroll_canvas = tk.Canvas(self, background=BG, highlightthickness=0,
                                       width=1, height=1, takefocus=True, yscrollincrement=24)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.scroll_canvas.yview)
        self.scroll_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.content = ttk.Frame(self.scroll_canvas, padding=padding)
        self._window = self.scroll_canvas.create_window(0, 0, window=self.content, anchor="nw")
        self._padding = padding
        self._wired = set()
        self.content.bind("<Configure>", self._content_changed)
        self.scroll_canvas.bind("<Configure>", self._viewport_changed)
        self.scroll_canvas.bind("<Button-1>", lambda _event: self.scroll_canvas.focus_set())
        for sequence, action in (("<Prior>", lambda: self.scroll_canvas.yview_scroll(-1, "pages")),
                                 ("<Next>", lambda: self.scroll_canvas.yview_scroll(1, "pages")),
                                 ("<Home>", lambda: self.scroll_canvas.yview_moveto(0)),
                                 ("<End>", lambda: self.scroll_canvas.yview_moveto(1))):
            self.scroll_canvas.bind(sequence, lambda _event, callback=action: (callback(), "break")[1])
        self.scroll_canvas.bind("<MouseWheel>", self._wheel)
        self.scroll_canvas.bind("<Button-4>", lambda _event: self.scroll_canvas.yview_scroll(-1, "units"))
        self.scroll_canvas.bind("<Button-5>", lambda _event: self.scroll_canvas.yview_scroll(1, "units"))

    def _viewport_changed(self, event):
        self.scroll_canvas.itemconfigure(self._window, width=event.width)
        for widget in self.content.winfo_children():
            if isinstance(widget, ttk.Label):
                widget.configure(wraplength=max(120, event.width - 2 * self._padding))

    def _content_changed(self, _event=None):
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
        self._wire_focus(self.content)

    def _wire_focus(self, parent):
        for widget in (parent, *parent.winfo_children()):
            if str(widget) not in self._wired:
                self._wired.add(str(widget))
                widget.bind("<FocusIn>", self._reveal_focus, add="+")
                # Treeview/Text/Spinbox keep their own wheel and keyboard behavior.
                if isinstance(widget, (ttk.Frame, ttk.Label)):
                    widget.bind("<MouseWheel>", self._wheel, add="+")
                    widget.bind("<Button-4>", lambda _e: self.scroll_canvas.yview_scroll(-1, "units"), add="+")
                    widget.bind("<Button-5>", lambda _e: self.scroll_canvas.yview_scroll(1, "units"), add="+")
            if widget is not parent:
                self._wire_focus(widget)

    def _reveal_focus(self, event):
        top = event.widget.winfo_rooty() - self.content.winfo_rooty()
        current = self.scroll_canvas.canvasy(0)
        height = self.scroll_canvas.winfo_height()
        total = max(1, self.content.winfo_height())
        bottom = top + event.widget.winfo_height()
        if top < current or event.widget.winfo_height() > height:
            self.scroll_canvas.yview_moveto(top / total)
        elif bottom > current + height:
            self.scroll_canvas.yview_moveto((bottom - height) / total)

    def _wheel(self, event):
        if event.delta:
            amount = -1 if event.delta > 0 else 1
            self.scroll_canvas.yview_scroll(amount * max(1, abs(event.delta) // 120), "units")
        return "break"


def tree(parent, columns, height=8, **kw):
    """Treeview with native vertical/horizontal scrolling and readable columns."""
    frame = ttk.Frame(parent)
    view = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height, **kw)
    for cid, title, width in columns:
        view.heading(cid, text=title)
        view.column(cid, width=width, minwidth=width, anchor="w")
    bar = ttk.Scrollbar(frame, orient="vertical", command=view.yview)
    horizontal = ttk.Scrollbar(frame, orient="horizontal", command=view.xview)
    view.configure(yscrollcommand=bar.set, xscrollcommand=horizontal.set)
    view.grid(row=0, column=0, sticky="nsew")
    bar.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    return frame, view


def fill(view, rows):
    view.delete(*view.get_children())
    for row in rows:
        view.insert("", "end", values=row)


def heading(parent, text):
    ttk.Label(parent, text=text, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(8, 4))


class SpectrogramTab(ttk.Frame):
    def __init__(self, parent, on_marker=None):
        super().__init__(parent, padding=12)
        ttk.Label(self, text="Log-frequency-axis not applied: linear 0 Hz (bottom) to Nyquist (top). "
                  "Click to place the note time.", style="Sub.TLabel").pack(anchor="w")
        self.canvas = tk.Canvas(self, background="#000", highlightthickness=0, height=300)
        self.canvas.pack(fill="both", expand=True, pady=6)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Configure>", lambda _e: self._draw())
        self.cursor_label = ttk.Label(self, text="", style="Sub.TLabel")
        self.cursor_label.pack(anchor="w")
        self.on_marker, self._image, self._png, self._duration = on_marker, None, None, 0.0

    def update_result(self, result):
        audio = result["audio"]
        spec = compute_spectrogram(audio.samples, audio.sample_rate)
        rgb = colorize(spec["db"], 256)
        self._png = encode_png(rgb)
        self._duration, self._nyquist = audio.duration_seconds, audio.sample_rate / 2
        self._draw()

    @property
    def png_bytes(self):
        return self._png

    def _draw(self):
        self.canvas.delete("all")
        if not self._png:
            return
        w, h = max(self.canvas.winfo_width(), 200), max(self.canvas.winfo_height(), 100)
        img = tk.PhotoImage(data=base64.b64encode(self._png), format="png")
        fx, fy = max(1, round(img.width() / w)), max(1, round(img.height() / h))
        img = img.subsample(fx, fy) if (fx > 1 or fy > 1) else img
        self._image = img
        self.canvas.create_image(0, 0, anchor="nw", image=img)
        self._scale = img.width()

    def _click(self, event):
        if self._png and getattr(self, "_scale", 0):
            t = max(0.0, min(self._duration, event.x / self._scale * self._duration))
            self.cursor_label.configure(text=f"Selected time {t:.2f} s")
            if self.on_marker:
                self.on_marker(t)


class MusicalTab(ScrollableTab):
    def __init__(self, parent):
        super().__init__(parent, padding=12)
        ttk.Label(self.content, text="Heuristic musical description of channel 1. Confidence values are not probabilities.",
                  style="Sub.TLabel").pack(anchor="w")
        self.summary = ttk.Label(self.content, text="", font=("Segoe UI", 13, "bold"), foreground=ACCENT)
        self.summary.pack(anchor="w", pady=8)
        heading(self.content, "Dominant stationary tones (room tone, hum, instruments)")
        frame, self.tones = tree(self.content, [("note", "Note", 80), ("hz", "Frequency (Hz)", 130),
                                        ("cents", "Cents", 90), ("lvl", "Level over median (dB)", 170)], 7)
        frame.pack(fill="x")
        heading(self.content, "Key candidates (Krumhansl-Schmuckler correlation)")
        frame, self.keys = tree(self.content, [("key", "Key", 150), ("r", "Correlation", 120)], 4)
        frame.pack(fill="x")
        self.hum = ttk.Label(self.content, text="", style="Sub.TLabel")
        self.hum.pack(anchor="w", pady=8)

    def update_result(self, result):
        m = result["musical"]
        if not m:
            self.summary.configure(text="Musical analysis was skipped (quick analysis)")
            fill(self.tones, [])
            fill(self.keys, [])
        else:
            key, tempo, pitch = m["key"], m["tempo"], m["median_pitch"]
            parts = [f"Key: {key['key']} {key['mode']} (r={key['correlation']:.2f})" if key["key"] else "Key: indeterminate",
                     f"Tempo: {tempo['bpm']:.0f} BPM (conf {tempo['confidence']:.2f})" if tempo["bpm"] else "Tempo: none detected",
                     f"Pitch: {pitch['note']} ({pitch['cents']:+.0f}¢)" if pitch else "Pitch: none detected"]
            self.summary.configure(text="   ·   ".join(parts))
            fill(self.tones, [(t["note"], f"{t['frequency_hz']:.2f}", f"{t['cents']:+.1f}",
                               f"{t['level_db_above_median']:.1f}") for t in m["dominant_tones"]])
            alts = [{"key": key["key"], "mode": key["mode"], "correlation": key["correlation"]}] + key["alternatives"] if key["key"] else []
            fill(self.keys, [(f"{a['key']} {a['mode']}", f"{a['correlation']:.3f}") for a in alts])
        hum = result["hum"]
        if hum.get("reason"):
            hum_text = f"Mains hum: unavailable — {hum['reason']}"
        elif hum.get("detected"):
            hum_text = f"Mains hum: {hum['fundamental_hz']:.0f} Hz candidate fundamental"
        else:
            hum_text = "Mains hum: not detected"
        if "frequency_resolution_hz" in hum:
            hum_text += f" · frequency resolution {hum['frequency_resolution_hz']:.3g} Hz"
        self.hum.configure(text=hum_text + "  (tonal interference only; not ENF analysis)")


class RecurrenceTab(ScrollableTab):
    def __init__(self, parent):
        super().__init__(parent, padding=12)
        ttk.Label(self.content, text="Later segments whose measured features return to an earlier segment after a "
                  "departure. Review candidates; they do not identify a place.", style="Sub.TLabel").pack(anchor="w")
        frame, self.view = tree(self.content, [("id", "ID", 50), ("earlier", "Earlier (s)", 130), ("later", "Returns (s)", 130),
                                       ("dist", "Mean distance", 110), ("peak", "Departure peak", 110),
                                       ("why", "Largest feature differences", 520)], 12)
        frame.pack(fill="both", expand=True, pady=8)
        self.note = ttk.Label(self.content, text="", style="Sub.TLabel", wraplength=1000)
        self.note.pack(anchor="w")

    def update_result(self, result):
        rows = []
        for r in result["recurrences"]:
            top = sorted(r.feature_deltas.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
            rows.append((r.segment_id, f"{r.earlier_start_s:.0f}–{r.earlier_end_s:.0f}",
                         f"{r.later_start_s:.0f}–{r.later_end_s:.0f}", f"{r.mean_distance:.3f}",
                         f"{r.departure_peak:.2f}" if r.departure_peak is not None else "—",
                         ", ".join(f"{k} {v:+.2f}" for k, v in top)))
        fill(self.view, rows)
        self.note.configure(text="" if rows else "No recurrence found at the default thresholds.")


class ChannelsTab(ScrollableTab):
    def __init__(self, parent):
        super().__init__(parent, padding=12)
        heading(self.content, "Per-channel levels")
        frame, self.channels = tree(self.content, [("ch", "Channel", 80), ("rms", "RMS (dBFS)", 120), ("peak", "Peak (dBFS)", 120),
                                           ("fp", "Fingerprint SHA-256", 600)], 6)
        frame.pack(fill="x")
        heading(self.content, "Channel 1 vs other channels")
        frame, self.pairs = tree(self.content, [("pair", "Pair", 80), ("corr", "Correlation", 100), ("lag", "Lag (ms)", 90),
                                        ("ild", "Level diff (dB)", 120), ("side", "Side/Mid (dB)", 120)], 6)
        frame.pack(fill="x")
        self.note = ttk.Label(self.content, text="", style="Sub.TLabel")
        self.note.pack(anchor="w", pady=8)

    def update_result(self, result):
        data = result["channels"]
        if not data:
            fill(self.channels, [])
            fill(self.pairs, [])
            self.note.configure(text="Single-channel recording: no inter-channel metrics.")
            return
        fill(self.channels, [(c["channel"], f"{c['rms_dbfs']:.1f}", f"{c['peak_dbfs']:.1f}",
                              c["fingerprint_sha256"] or "—") for c in data["channels"]])
        fill(self.pairs, [("1–%d" % p["channels"][1], f"{p['correlation_zero_lag']:+.3f}", f"{p['peak_lag_ms']:+.3f}" if p["peak_lag_ms"] is not None else "Unavailable",
                           f"{p['level_difference_db']:+.2f}", f"{p['side_to_mid_db']:+.1f}") for p in data["pairs"]])
        self.note.configure(text="Negative correlation indicates opposite polarity; lag is limited to ±1.5 ms.")


class ReferenceTab(ScrollableTab):
    """Guided known-location exemplar documentation with a quality review."""
    FIELDS = [("location_id", "Location identifier *"), ("recorded_utc", "Recorded (UTC) *"), ("operator", "Operator *"),
              ("recorder_make_model", "Recorder make/model *"), ("recorder_serial", "Recorder serial"),
              ("microphone_make_model", "Microphone make/model *"), ("microphone_serial", "Microphone serial"),
              ("input_chain", "Input chain *"), ("channel_assignment", "Channel assignment *"),
              ("placement", "Placement *"), ("orientation", "Orientation *"), ("height_m", "Height (m) *"),
              ("source_signal", "Source signal *"), ("occupancy_activity", "Occupancy / activity *"),
              ("weather", "Weather"), ("calibration", "Calibration"), ("authority_or_consent", "Authority / consent *"),
              ("deviations", "Deviations")]

    def __init__(self, parent, on_save):
        super().__init__(parent, padding=12)
        ttk.Label(self.content, text="Document the exemplar for the loaded recording (* required). A location label alone "
                  "never establishes a match.", style="Sub.TLabel").pack(anchor="w")
        form = ttk.Frame(self.content)
        form.pack(fill="x", pady=6)
        self.entries = {}
        for n, (key, label) in enumerate(self.FIELDS):
            r, c = divmod(n, 2)
            ttk.Label(form, text=label).grid(row=r, column=c * 2, sticky="w", padx=(0, 6), pady=2)
            entry = ttk.Entry(form, width=34)
            entry.grid(row=r, column=c * 2 + 1, sticky="ew", padx=(0, 18), pady=2)
            self.entries[key] = entry
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        self.repeat = ttk.Spinbox(form, from_=1, to=99, width=5)
        self.repeat.set("1")
        self.planned = ttk.Spinbox(form, from_=1, to=99, width=5)
        self.planned.set("3")
        row = len(self.FIELDS) // 2 + 1
        ttk.Label(form, text="Repeat # / planned").grid(row=row, column=0, sticky="w")
        pair = ttk.Frame(form)
        pair.grid(row=row, column=1, sticky="w")
        self.repeat.pack(in_=pair, side="left")
        self.planned.pack(in_=pair, side="left", padx=6)
        buttons = ttk.Frame(self.content)
        buttons.pack(anchor="w", pady=6)
        ttk.Button(buttons, text="Review quality", command=self.review).pack(side="left")
        ttk.Button(buttons, text="Save reference record", command=lambda: on_save(self)).pack(side="left", padx=8)
        frame, self.checks = tree(self.content, [("check", "Check", 160), ("status", "Status", 80), ("detail", "Detail", 700)], 8)
        frame.pack(fill="both", expand=True)
        self.provider = lambda: None
        self.last_review = None

    def reset_for_recording(self):
        """A previous exemplar's metadata and review never label new evidence."""
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.repeat.set("1")
        self.planned.set("3")
        self.last_review = None
        fill(self.checks, [])

    def metadata(self) -> ReferenceMetadata:
        values = {k: e.get().strip() for k, e in self.entries.items()}
        try:
            values["repeat_number"], values["repeats_planned"] = int(self.repeat.get()), int(self.planned.get())
        except ValueError:
            raise ValueError("Repeat numbers must be integers")
        return ReferenceMetadata.from_dict(values)

    def review(self):
        audio = self.provider()
        if audio is None:
            messagebox.showinfo("Load evidence", "Open a recording first.")
            return None
        try:
            self.last_review = review_reference(self.metadata(), audio.samples, audio.sample_rate)
        except ValueError as exc:
            messagebox.showerror("Reference", str(exc))
            return None
        fill(self.checks, [(c["check"], c["status"].upper(), c["detail"]) for c in self.last_review["checks"]])
        return self.last_review
