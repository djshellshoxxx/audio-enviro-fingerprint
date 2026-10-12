"""Drives the Tk workstation end to end with dialogs stubbed. Skipped without Tk or a display."""
import math
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

import numpy as np

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAVE_DISPLAY = True
except Exception:  # no tkinter module or no display
    HAVE_DISPLAY = False


def _write_wav(path, freqs, seconds=6, rate=8000):
    t = np.arange(rate * seconds) / rate
    mono = np.concatenate([0.2 * np.sin(2 * math.pi * f * t) for f in freqs])
    stereo = np.stack([mono, -0.5 * mono], axis=1)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes((stereo * 32767).astype("<i2").tobytes())


@unittest.skipUnless(HAVE_DISPLAY, "Tk display not available")
class AppWorkflowTests(unittest.TestCase):
    def setUp(self):
        from audio_enviro_fingerprint import app as app_module
        self.module = app_module
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.wav = self.dir / "evidence.wav"
        _write_wav(self.wav, [220, 1800, 220])
        self.other = self.dir / "other.wav"
        _write_wav(self.other, [3000, 220])
        self.errors = []
        patches = [mock.patch.object(app_module.messagebox, "showerror",
                                     side_effect=lambda title, msg, **_: self.errors.append(f"{title}: {msg}")),
                   mock.patch.object(app_module.messagebox, "showinfo", return_value=None)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.app = app_module.FingerprinterApp(self.dir / "data")
        self.app.withdraw()

    def tearDown(self):
        self.app._close()
        self.tmp.cleanup()

    def _wait(self):
        for _ in range(600):
            self.app.update()
            if not self.app.busy and self.app.jobs.empty():
                self.app.update()
                return
            self.app.after(10)
        self.fail("job did not finish")

    def test_full_workflow(self):
        app = self.app
        app.setting_vars["transition_threshold"].set("0.25")
        app.load_path(self.wav)
        self._wait()
        self.assertEqual(self.errors, [])
        self.assertEqual(app.bundle.audio.channels, 2)
        self.assertTrue(app.transitions.get_children())
        self.assertEqual(len(app.channel_table.get_children()), 2)
        self.assertTrue(app.recurrence_table.get_children())

        app.channel_var.set("2")
        app._channel_changed()
        self._wait()
        self.assertEqual(app.bundle.audio.selected_channel, 1)

        with mock.patch.object(self.module.filedialog, "askopenfilename", return_value=str(self.other)):
            app.compare_file()
            self._wait()
        self.assertTrue(app.compare_table.get_children())
        self.assertIn("descriptive score", app.compare_label.cget("text"))

        with mock.patch.object(self.module.filedialog, "askopenfilenames", return_value=(str(self.other),)):
            app.add_recurrence_files()
            self._wait()
        self.assertEqual(len(app.extra_bundles), 1)
        app.save_recurrence_run()
        self.assertEqual(len(app.store.recurrence_runs()), 1)
        self.assertEqual(len(app.run_table.get_children()), 1)
        self.assertEqual(len(app.case_table.get_children()), 1)

        with mock.patch.object(self.module.simpledialog, "askfloat", return_value=3.0), \
                mock.patch.object(self.module.simpledialog, "askstring", side_effect=["Door", "Door (edit)", "refined"]):
            app.add_marker()
            marker_id = int(app.marker_table.get_children()[0])
            app.marker_table.selection_set(str(marker_id))
            app.edit_marker()
        self.assertEqual(len(app.store.marker_history(marker_id)), 2)

        app.note_time.insert(0, "1")
        app.note_title.insert(0, "Fan")
        app.note_body.insert("1.0", "Low hum")
        app.save_note()
        self.assertEqual(len(app.notes_view.get_children()), 1)

        dialog = self.module.ReferenceDialog(app)
        values = {"location_id": "LAB-1", "captured_at_utc": "2026-10-01T12:00:00Z", "operator": "A",
                  "consent_authority": "permit", "recorder_make_model": "R", "microphone_make_model": "M",
                  "placement": "table", "source_signal": "ambient"}
        for key, value in values.items():
            dialog.vars[key].set(value)
        dialog.save()
        self.assertEqual(self.errors, [])
        self.assertEqual(len(app.store.references()), 1)

        app.load_path(self.other)
        self._wait()
        app.rank_references()
        rows = [app.reference_table.item(i, "values") for i in app.reference_table.get_children()]
        self.assertEqual(rows[0][2], "LAB-1")

        target = self.dir / "report.json"
        with mock.patch.object(self.module.filedialog, "asksaveasfilename", return_value=str(target)):
            app.export_json()
        from audio_enviro_fingerprint.report import verify_report
        self.assertTrue(verify_report(target, evidence_path=self.other)["ok"])
        self.assertEqual(self.errors, [])

    def test_rt60_on_impulse_response(self):
        rate = 8000
        t = np.arange(rate * 3) / rate
        impulse = 10 ** (-60 * t / (20 * 0.8)) * np.random.default_rng(1).normal(0, 0.2, len(t))
        path = self.dir / "ir.wav"
        with wave.open(str(path), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes((np.clip(impulse, -1, 1) * 32767).astype("<i2").tobytes())
        self.app.load_path(path)
        self._wait()
        with mock.patch.object(self.module.messagebox, "askyesno", return_value=True):
            self.app.estimate_rt60()
        import re
        estimate = float(re.search(r"RT60 ≈ ([0-9.]+) s", self.app.rt60_label.cget("text")).group(1))
        self.assertAlmostEqual(estimate, 0.8, delta=0.1)
        from audio_enviro_fingerprint.cli import main
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["rt60", str(path)]), 0)
        self.assertIn("RT60", out.getvalue())

    def test_cancel_keeps_previous_results_and_bad_file_reports_error(self):
        app = self.app
        app.load_path(self.wav)
        self._wait()
        before = app.bundle
        app.cancel_event.set()
        with mock.patch.object(self.module, "analyze_file",
                               side_effect=self.module.AnalysisCancelled("cancelled")):
            app.load_path(self.other)
            self._wait()
        self.assertIs(app.bundle, before)
        self.assertIn("cancelled", app.status_label.cget("text"))
        bad = self.dir / "bad.wav"
        bad.write_bytes(b"RIFF....WAVEjunk")
        app.load_path(bad)
        self._wait()
        self.assertIs(app.bundle, before)
        self.assertTrue(self.errors)


if __name__ == "__main__":
    unittest.main()
