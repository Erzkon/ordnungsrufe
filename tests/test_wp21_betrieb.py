"""Status report should flag stale/missing data, never invent zero measures."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from wp21_betriebsbericht import EXPECTED, inspect, markdown


class TestOperations(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,15,8,tzinfo=timezone.utc)

    def test_no_source_is_missing_not_zero(self):
        with tempfile.TemporaryDirectory() as d:
            status=inspect(d,now=self.now)
        self.assertEqual({v['state'] for v in status.values()},{'missing'})
        self.assertIn('fehlt',markdown(status))
        self.assertIn('Keine automatische Bestätigung',markdown(status))

    def test_fresh_and_stale_report_time(self):
        with tempfile.TemporaryDirectory() as d:
            for name,(field,expected,date_field) in EXPECTED.items():
                (Path(d)/name).write_text(json.dumps({
                    field:expected,'wahlperiode':21,
                    date_field:'2026-10-15T07:00:00+00:00'
                }),encoding='utf-8')
            state=inspect(d,now=self.now)
            self.assertTrue(all(v['state']=='fresh' for v in state.values()))
            (Path(d)/'scan_21.json').write_text(json.dumps({
                'status':'bereit','wahlperiode':21,
                'zuletzt_geprueft_utc':'2026-10-01T07:00:00+00:00'
            }),encoding='utf-8')
            state=inspect(d,now=self.now)
            self.assertEqual(state['scan_21.json']['state'],'stale')

    def test_untrusted_status_fails(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'scan_21.json').write_text(json.dumps({
                'status':'bestaetigt','wahlperiode':21,
                'zuletzt_geprueft_utc':'2026-10-15T07:00:00+00:00'
            }),encoding='utf-8')
            self.assertEqual(inspect(d,now=self.now)['scan_21.json']['state'],'invalid')

    def test_no_timezone_is_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'scan_21.json').write_text(json.dumps({
                'status':'bereit','wahlperiode':21,
                'zuletzt_geprueft_utc':'2026-10-15T07:00:00'
            }),encoding='utf-8')
            self.assertEqual(inspect(d,now=self.now)['scan_21.json']['state'],'invalid')

if __name__=='__main__':
    unittest.main()
