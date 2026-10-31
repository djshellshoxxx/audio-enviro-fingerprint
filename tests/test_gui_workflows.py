"""Headless behavior checks for desktop workflows and persisted preferences."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from audio_enviro_fingerprint.app import FingerprinterApp
from audio_enviro_fingerprint.case_store import CaseStore
from audio_enviro_fingerprint.ui_tabs import MusicalTab


class Widget:
    def __init__(self, text=''):
        self.text = text
        self.rows = {}
    def configure(self, **kw):
        self.text = kw.get('text', self.text)
    def get(self): return self.text
    def delete(self, *args):
        if args == (0, 'end'): self.text = ''
        else: self.rows.clear()
    def insert(self, *args, **kw):
        if 'values' in kw: self.rows[str(len(self.rows))] = kw['values']
        else: self.text = args[-1]
    def get_children(self): return tuple(self.rows)
    def selection(self): return ('selected',)
    def item(self, *args): return ('1', '1.23', 'door')


class GuiWorkflowTests(unittest.TestCase):
    def test_missing_source_at_apply_preserves_previous_result_and_reports_error(self):
        with TemporaryDirectory() as tmp, CaseStore(Path(tmp) / 'case.db') as store:
            app = SimpleNamespace(store=store, result={'previous': True}, evidence_id=3)
            with patch('audio_enviro_fingerprint.app.messagebox.showerror') as error:
                FingerprinterApp.apply_result(app, {'path': Path(tmp)/'gone.wav', 'sha256': '0'*64})
            self.assertTrue(error.called)
            self.assertEqual(app.result, {'previous': True})
            self.assertEqual(app.evidence_id, 3)

    def test_skipped_music_clears_old_values_and_updates_hum(self):
        app = SimpleNamespace(summary=Widget('old'), tones=Widget(), keys=Widget(), hum=Widget('old hum'))
        app.tones.rows = {'old': ('old tone',)}
        app.keys.rows = {'old': ('old key',)}
        MusicalTab.update_result(app, {'musical': None, 'hum': {'detected': False}})
        self.assertEqual(app.tones.rows, {})
        self.assertEqual(app.keys.rows, {})
        self.assertIn('not detected', app.hum.text)

    def test_marker_delete_preserves_exact_stored_timestamp(self):
        with TemporaryDirectory() as tmp, CaseStore(Path(tmp)/'case.db') as store:
            path = Path(tmp)/'evidence'; path.write_bytes(b'a')
            eid = store.register_evidence(path)
            store.save_marker(eid, 1.23456, 'door')
            app = SimpleNamespace(store=store, evidence_id=eid, markers_view=Widget(), _load_notes=lambda:None)
            app._selected_marker = lambda: FingerprinterApp._selected_marker(app)
            FingerprinterApp.delete_marker(app)
            self.assertEqual([m['timestamp_seconds'] for m in store.markers_for(eid, True)], [1.23456, 1.23456])

    def test_busy_comparison_and_search_do_not_open_dialog(self):
        app = SimpleNamespace(busy=True, result={'old': True})
        with patch('audio_enviro_fingerprint.app.filedialog.askopenfilename') as dialog:
            FingerprinterApp.compare_file(app)
            FingerprinterApp.cross_recurrence(app)
        dialog.assert_not_called()

    def test_marker_edit_uses_clock_input_and_appends_revision(self):
        with TemporaryDirectory() as tmp, CaseStore(Path(tmp)/'case.db') as store:
            path = Path(tmp)/'evidence'; path.write_bytes(b'a')
            eid = store.register_evidence(path)
            store.save_marker(eid, 1.23456, 'door')
            app = SimpleNamespace(store=store, evidence_id=eid, markers_view=Widget(),
                note_time=Widget('0:02.34567'), note_title=Widget('door moved'),
                result={'audio': SimpleNamespace(duration_seconds=10)}, _load_notes=lambda:None)
            app._selected_marker = lambda: FingerprinterApp._selected_marker(app)
            app._timestamp = lambda: FingerprinterApp._timestamp(app)
            FingerprinterApp.edit_marker(app)
            history = store.markers_for(eid, True)
            self.assertEqual([(r['timestamp_seconds'],r['label']) for r in history],
                             [(1.23456,'door'),(2.34567,'door moved')])

    def test_cross_search_finds_both_occurrences_in_selected_recording(self):
        import numpy as np
        from test_extended import tone, write_wav
        from audio_enviro_fingerprint.pipeline import analyze_file
        from audio_enviro_fingerprint.app import search_recording
        with TemporaryDirectory() as tmp:
            source, other = Path(tmp)/'reference.wav', Path(tmp)/'search.wav'
            write_wav(source, tone(440,4))
            write_wav(other, np.concatenate([tone(1500,8),tone(440,4),tone(1500,8),tone(440,4)]))
            path, found = search_recording(analyze_file(source,musical=False), other)
            self.assertEqual(path,other)
            self.assertEqual([(r.later_start_s,r.later_end_s) for r in found],[(8.0,12.0),(20.0,24.0)])
            self.assertTrue(all(r.earlier_start_s == 0.0 and r.earlier_end_s <= 4.0 for r in found))


import os
import time


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name == 'nt', 'A Tk display is required')
class DesktopIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.home = Path(self.temp.name)
        (self.home/'preferences.json').write_text('{corrupt')
        self.app = FingerprinterApp(self.home)
        self.app.withdraw()
        self.dialogs = []
        self.error_patch = patch('audio_enviro_fingerprint.app.messagebox.showerror',
                                 side_effect=lambda *a,**k:self.dialogs.append(a))
        self.info_patch = patch('audio_enviro_fingerprint.app.messagebox.showinfo')
        self.error_patch.start(); self.info_patch.start()
        from test_extended import tone, write_wav
        self.source = self.home/'recording.wav'
        write_wav(self.source,tone(440,4))

    def tearDown(self):
        self.error_patch.stop(); self.info_patch.stop()
        self.app._close()
        self.temp.cleanup()

    def finish_jobs(self):
        deadline = time.monotonic()+15
        while self.app.busy and time.monotonic() < deadline:
            self.app.update()
            time.sleep(.01)
        self.assertFalse(self.app.busy,'Background operation timed out')
        self.assertEqual(self.dialogs,[])

    def test_recent_quick_annotation_and_html_export_journey(self):
        self.app.start_analysis(self.source)
        self.finish_jobs()
        first = self.app.result
        self.assertIsNotNone(first['musical'])
        self.assertEqual(self.app.recent_paths,[str(self.source)])
        self.app.quick_analysis.set(True)
        self.app._open_recent(str(self.source))
        self.finish_jobs()
        self.assertIsNone(self.app.result['musical'])
        self.assertEqual(self.app.musical.tones.get_children(),())
        self.assertEqual(self.app.musical.keys.get_children(),())
        self.assertNotEqual(self.app.musical.hum.cget('text'),'')
        self.app.note_time.delete(0,'end'); self.app.note_time.insert(0,'0:01.23456')
        self.app.note_title.insert(0,'door')
        self.app.add_marker()
        item, = self.app.markers_view.get_children()
        self.app.markers_view.selection_set(item)
        self.app._marker_selected()
        self.assertEqual(self.app.note_time.get(),'1.23456')
        self.app.note_time.delete(0,'end'); self.app.note_time.insert(0,'0:02.34567')
        self.app.edit_marker()
        history = self.app.store.markers_for(self.app.evidence_id,True)
        self.assertEqual([m['timestamp_seconds'] for m in history],[1.23456,2.34567])
        self.assertEqual(len(self.app.store.recurrence_runs_for(self.app.evidence_id)),2)
        from audio_enviro_fingerprint.pipeline import report_sections
        target=self.home/'report.html'
        self.app._start_report_export(target,self.source,self.app.result['sha256'],report_sections(self.app.result))
        self.finish_jobs()
        self.assertIn('<html',target.read_text().lower())
        previous=self.app.result
        self.app._open_recent(str(self.home/'missing.wav'))
        self.assertIs(self.app.result,previous)
        self.assertEqual(len(self.dialogs),1)

    def test_cancelled_analysis_retains_previous_result(self):
        self.app.quick_analysis.set(True)
        self.app.start_analysis(self.source)
        self.finish_jobs()
        previous=self.app.result
        self.app.start_analysis(self.source)
        self.app.cancel_event.set()
        self.finish_jobs()
        self.assertIs(self.app.result,previous)

    def test_comparison_runs_as_background_job_and_shows_completed_result(self):
        self.app.quick_analysis.set(True)
        self.app.start_analysis(self.source)
        self.finish_jobs()
        with patch('audio_enviro_fingerprint.app.filedialog.askopenfilename',return_value=str(self.source)):
            self.app.compare_file()
        self.assertTrue(self.app.busy)
        self.finish_jobs()
        import tkinter as tk
        windows=[w for w in self.app.winfo_children() if isinstance(w,tk.Toplevel)]
        self.assertEqual(len(windows),1)

    def test_minimum_window_scrolls_to_every_review_table(self):
        self.app.geometry('900x600')
        self.app.deiconify()
        self.app.quick_analysis.set(True)
        self.app.start_analysis(self.source)
        self.finish_jobs()
        targets = [(self.app.notebook.tabs()[0],self.app.features),
                   (self.app.notes_tab,self.app.markers_view),
                   (self.app.reference,self.app.reference.checks),
                   (self.app.musical,self.app.musical.hum),
                   (self.app.recurrence,self.app.recurrence.view),
                   (self.app.channels,self.app.channels.pairs)]
        for tab_id,target in targets:
            with self.subTest(target=str(target)):
                self.app.notebook.select(tab_id)
                self.app.update()
                tab=self.app.nametowidget(str(tab_id))
                canvas=getattr(tab,'scroll_canvas',None)
                self.assertIsNotNone(canvas,'Review tabs must expose a scrollable viewport at minimum size')
                canvas.focus_force()
                canvas.event_generate('<End>')
                self.app.update()
                viewport_top=canvas.winfo_rooty()
                viewport_bottom=viewport_top+canvas.winfo_height()
                target_bottom=target.winfo_rooty()+target.winfo_height()
                self.assertLessEqual(target_bottom,viewport_bottom+2)
                self.assertGreater(target_bottom,viewport_top)
                self.assertLessEqual(target.winfo_rootx()+target.winfo_width(),canvas.winfo_rootx()+canvas.winfo_width()+2)
                canvas.event_generate('<Home>')
                self.app.update()
                self.assertAlmostEqual(canvas.yview()[0],0.0)
        self.app.notebook.select(self.app.notes_tab)
        self.app.update()
        self.app.markers_view.focus_force()
        self.app.update()
        canvas=self.app.notes_tab.scroll_canvas
        self.assertLessEqual(self.app.markers_view.winfo_rooty()+self.app.markers_view.winfo_height(),
                             canvas.winfo_rooty()+canvas.winfo_height()+2)
        self.app.notebook.select(self.app.reference)
        self.app.update()
        canvas=self.app.reference.scroll_canvas
        for entry in self.app.reference.entries.values():
            self.assertGreaterEqual(entry.winfo_rootx(),canvas.winfo_rootx())
            self.assertLessEqual(entry.winfo_rootx()+entry.winfo_width(),canvas.winfo_rootx()+canvas.winfo_width())
