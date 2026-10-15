"""Regression tests: retraction references are alerts, never state changes."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from wp21_rechtsfolgen import build_report, classify_signal, extract_signals, run

def xml(*paragraphs):
    inner = ''.join(f'<p>{p}</p>' for p in paragraphs)
    return (f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1" '
            f'sitzung-datum="25.03.2025"><sitzungsverlauf><tagesordnungspunkt>'
            f'{inner}</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>').encode()

class TestLegalSignals(unittest.TestCase):
    def test_appeals_not_automatically_retractions(self):
        kind = classify_signal('Gegen den Ordnungsruf liegt ein Einspruch vor.')
        self.assertEqual(kind,('einspruch','einspruch'))
        self.assertIsNone(classify_signal('Die Mitglieder legten Einspruch ein.'))

    def test_clear_retraction_is_still_only_a_candidate(self):
        kind = classify_signal('Der Ordnungsruf wurde zurückgenommen.')
        self.assertEqual(kind,('moegliche_ruecknahme','moegliche_ruecknahme'))
        self.assertEqual(build_report(
            [{'kategorie':kind[0]}],1,'2026-10-15T06:00:00+00:00'
        )['automatisch_zurueckgenommene_massnahmen'],0)

    def test_rejected_appeal_marked_ambiguous(self):
        kind = classify_signal('Der Einspruch gegen den Ordnungsruf wird zurückgewiesen.')
        self.assertEqual(kind[0],'mehrdeutig')
        self.assertIn('moegliche_zurueckweisung',kind[1])

    def test_ordinary_sanction_is_not_legal_followup(self):
        self.assertIsNone(classify_signal('Ich erteile Herrn Beispiel einen Ordnungsruf.'))

    def test_extract_signals_from_protocol_and_safe_source_links(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)/'21001.xml'
            target.write_bytes(xml(
                'Ich erteile einen Ordnungsruf.',
                'Gegen den Ordnungsruf wurde Einspruch eingelegt.',
                'Der Ordnungsruf wurde zurückgenommen.'))
            found = extract_signals([target])
            self.assertEqual(len(found),2)
            self.assertEqual(found[0]['sitzung'],'1')
            self.assertEqual(found[0]['protokoll_url'],
                'https://dserver.bundestag.de/btp/21/21001.pdf')
            self.assertNotEqual(found[0]['signal_id'],found[1]['signal_id'])

    def test_run_produces_report_but_no_sanction_changes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            cache=p/'cache'; cache.mkdir()
            (cache/'21001.xml').write_bytes(xml('Der Ordnungsruf wurde aufgehoben.'))
            summary=p/'scan.json'
            summary.write_text(json.dumps({
                'status':'bereit','letzte_sitzung':1,
                'untersuchte_sitzungen':1,
                'zuletzt_geprueft_utc':'2026-10-15T06:00:00+00:00'
            }),encoding='utf-8')
            report=run(cache,summary,p/'alerts.csv',p/'alerts.json')
            self.assertEqual(report['textstellen_gesamt'],1)
            self.assertEqual(report['automatisch_zurueckgenommene_massnahmen'],0)
            with (p/'alerts.csv').open(encoding='utf-8',newline='') as handle:
                self.assertEqual(len(list(csv.DictReader(handle))),1)
            self.assertEqual(json.loads((p/'alerts.json').read_text())['status'],
                             'ungepruefte_rechtsfolgen_hinweise')

    def test_missing_session_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            summary=p/'scan.json'
            summary.write_text(json.dumps({'status':'bereit','letzte_sitzung':1,
                'untersuchte_sitzungen':1,'zuletzt_geprueft_utc':'2026-10-15T06:00:00+00:00'}))
            with self.assertRaises(ValueError):
                run(p,summary,p/'alerts.csv',p/'alerts.json')

if __name__=='__main__':
    unittest.main()
