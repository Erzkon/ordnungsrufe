"""Rotating cache refresh tests: old XML changes cannot remain forever hidden."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from wp21_scan import scan

def xml(n):
    return (f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{n}" '
            f'sitzung-datum="25.03.2025"><sitzungsverlauf><tagesordnungspunkt>'
            f'<p>Es wurde kein Ordnungsruf erteilt.</p>'
            f'</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>').encode()

class TestRefresh(unittest.TestCase):
    def test_old_transcripts_are_revalidated_in_rotating_weekly_buckets(self):
        with tempfile.TemporaryDirectory() as td:
            cache=Path(td)
            for session in range(1,11):
                (cache/f'21{session:03d}.xml').write_bytes(xml(session))
            calls=[]
            def fake_fetch(session, folder, refresh=False):
                calls.append((session,refresh))
                return xml(session) if session <= 10 else None
            with patch('wp21_scan.fetch',side_effect=fake_fetch):
                _,summary=scan(cache,max_session=15,refresh_last=1,refresh_older_bucket=2)
            self.assertEqual(summary['untersuchte_sitzungen'],10)
            self.assertEqual(summary['woechentlicher_quellenrefresh_bucket'],2)
            checked={n for n,flag in calls if flag}
            self.assertEqual(checked,{2,9,10})
            self.assertFalse(any(flag for n,flag in calls if n>10))

    def test_rejects_invalid_rotation_bucket(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                scan(Path(td),max_session=10,refresh_older_bucket=7)

if __name__=='__main__':
    unittest.main()
