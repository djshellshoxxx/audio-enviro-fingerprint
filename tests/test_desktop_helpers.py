from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from audio_enviro_fingerprint.preferences import load_recent, remember_recent
from audio_enviro_fingerprint.timecode import parse_timecode


class DesktopHelperTests(unittest.TestCase):
    def test_seconds_and_clock_time_inputs(self):
        for text, expected in [('12.345',12.345),('1:02.5',62.5),('2:03:04.25',7384.25),(' 0 ',0)]:
            with self.subTest(text=text): self.assertEqual(parse_timecode(text),expected)
        for text in ('NaN','inf','-1','1:60','1:60:00','1::2','-1:00','1:2:3:4','', '1.5:02'):
            with self.subTest(text=text), self.assertRaises(ValueError): parse_timecode(text)

    def test_recent_history_recovers_corrupt_settings_and_deduplicates(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'settings.json'
            self.assertEqual(load_recent(p),[])
            p.write_text('{broken')
            self.assertEqual(load_recent(p),[])
            a,b=Path(tmp)/'first.wav',Path(tmp)/'second.wav'
            recent=remember_recent(p,a)
            recent=remember_recent(p,b,previous=recent)
            recent=remember_recent(p,a,previous=recent)
            self.assertEqual(recent,[str(a.resolve()),str(b.resolve())])
            self.assertEqual(p.read_text(),'{broken')
            self.assertEqual(load_recent(p),[])
            # Recognized settings restore persistent history; arbitrary bytes
            # are never replaced as an automatic corruption recovery action.
            p.write_text(json.dumps({'recent':[]}))
            remember_recent(p,a); remember_recent(p,b); remember_recent(p,a)
            self.assertEqual(load_recent(p),[str(a.resolve()),str(b.resolve())])
            p.write_text(json.dumps({'recent':['one',7,None]}))
            self.assertEqual(load_recent(p),[])

    def test_recent_history_is_bounded_and_settings_write_failure_is_nonfatal(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'settings.json'
            for i in range(15): remember_recent(p,Path(tmp)/str(i))
            self.assertEqual(len(load_recent(p)),10)
            self.assertTrue(load_recent(p)[0].endswith('/14'))
            parent=Path(tmp)/'file'; parent.write_bytes(b'x')
            self.assertEqual(remember_recent(parent/'settings.json',Path(tmp)/'audio.wav'),
                             [str((Path(tmp)/'audio.wav').resolve())])
            self.assertEqual(parent.read_bytes(),b'x')

    def test_recent_preferences_never_overwrite_selected_evidence_or_alias(self):
        with TemporaryDirectory() as tmp:
            settings=Path(tmp)/'preferences.json'
            source=Path(tmp)/'evidence.wav'
            original=b'RIFF-evidence-bytes'
            settings.write_bytes(original)
            remember_recent(settings,settings)
            self.assertEqual(settings.read_bytes(),original)
            settings.unlink(); source.write_bytes(original)
            try:
                settings.hardlink_to(source)
            except OSError:
                self.skipTest('Hardlinks unavailable')
            remember_recent(settings,source)
            self.assertEqual(settings.read_bytes(),original)
            self.assertEqual(source.read_bytes(),original)

    def test_malformed_recent_paths_cannot_crash_open_menu(self):
        with TemporaryDirectory() as tmp:
            settings=Path(tmp)/'preferences.json'
            settings.write_text(json.dumps({'recent':['bad\u0000path']}))
            self.assertEqual(load_recent(settings),[])

    def test_prior_evidence_at_settings_path_survives_later_opens_and_restart(self):
        from test_extended import tone, write_wav
        from audio_enviro_fingerprint.audio_io import load_wav
        with TemporaryDirectory() as tmp:
            settings=Path(tmp)/'preferences.json'
            other=Path(tmp)/'other.wav'
            write_wav(settings,tone(440,.1))
            write_wav(other,tone(660,.1))
            original=settings.read_bytes()
            remember_recent(settings,settings)
            remember_recent(settings,other)
            self.assertEqual(settings.read_bytes(),original)
            # A new process reads the file again, without any in-memory guard.
            self.assertEqual(load_recent(settings),[])
            remember_recent(settings,other)
            self.assertEqual(settings.read_bytes(),original)
            self.assertEqual(load_wav(settings).duration_seconds,.1)

    def test_unrecognized_json_is_preserved_when_other_recording_opens(self):
        with TemporaryDirectory() as tmp:
            settings=Path(tmp)/'preferences.json'
            original=b'{"another_application": true, "recent": []}'
            settings.write_bytes(original)
            recent=remember_recent(settings,Path(tmp)/'audio.wav')
            self.assertEqual(recent,[str((Path(tmp)/'audio.wav').resolve())])
            self.assertEqual(settings.read_bytes(),original)
            self.assertEqual(load_recent(settings),[])

    def test_oversized_preferences_do_not_trigger_an_unbounded_text_read(self):
        with TemporaryDirectory() as tmp:
            settings=Path(tmp)/'preferences.json'
            original=b'x'*(128*1024)
            settings.write_bytes(original)
            with patch.object(Path,'read_text',side_effect=AssertionError('unbounded text read')):
                self.assertEqual(load_recent(settings),[])
                remember_recent(settings,Path(tmp)/'other.wav')
            self.assertEqual(settings.read_bytes(),original)
