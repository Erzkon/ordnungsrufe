"""Tests for manual verified ledger and scan candidate separation."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from export_wp21 import build, valid_21_pdf
from wp21_scan import safe_parse, review_rows, scan

BASE=Path(__file__).resolve().parents[1]

class TestWP21(unittest.TestCase):
    def test_seed_is_explicitly_incomplete(self):
        payload=build(BASE/'daten/wirksame_ordnungsrufe_21wp.csv')
        self.assertEqual(payload['meta']['count'],8)
        self.assertTrue(payload['meta']['incomplete'])
        self.assertEqual(sum(x['person']=='Cansin Köktürk' for x in payload['records']),2)
        self.assertEqual(len({x['event_id'] for x in payload['records']}),8)

    def test_valid_pdf_strict(self):
        self.assertTrue(valid_21_pdf('https://dserver.bundestag.de/btp/21/21094.pdf#page=24',94))
        self.assertFalse(valid_21_pdf('https://dserver.bundestag.de/btp/20/21094.pdf#page=24',94))
        self.assertFalse(valid_21_pdf('https://dserver.bundestag.de/btp/21/21099.pdf#page=24',94))
        self.assertFalse(valid_21_pdf('https://other.net/btp/21/21094.pdf#page=24',94))

    def test_ledger_rejects_duplicates(self):
        path=BASE/'daten/wirksame_ordnungsrufe_21wp.csv'
        with path.open(encoding='utf-8',newline='') as h:
            rows=list(csv.DictReader(h))
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'duplicate.csv'
            with p.open('w',encoding='utf-8',newline='') as h:
                w=csv.DictWriter(h,fieldnames=rows[0].keys())
                w.writeheader();w.writerows(rows+[rows[0]])
            with self.assertRaises(ValueError):build(p)

    def test_xml_candidate_is_never_a_confirmed_measure(self):
        xml=b'''<dbtplenarprotokoll wahlperiode="21" sitzung-nr="2" sitzung-datum="01.04.2025">
<sitzungsverlauf><tagesordnungspunkt><p>Ich erteile Herrn Test einen Ordnungsruf.</p>
<p>Ich drohe Ihnen im naechsten Fall einen Ordnungsruf an.</p></tagesordnungspunkt></sitzungsverlauf>
</dbtplenarprotokoll>'''
        root=safe_parse(xml,2)
        rows=review_rows(root,2)
        self.assertGreaterEqual(len(rows),1)
        self.assertTrue(all(r['status']=='manuelle_pruefung_erforderlich' for r in rows))
        with self.assertRaises(ValueError):safe_parse(xml.replace(b'wahlperiode="21"',b'wahlperiode="20"'),2)

    def test_scan_does_not_translate_hints_to_measures(self):
        xml=b'''<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1" sitzung-datum="25.03.2025"><sitzungsverlauf><tagesordnungspunkt><p>Ich erteile Ihnen einen Ordnungsruf.</p></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>'''
        with tempfile.TemporaryDirectory() as td:
            with patch('wp21_scan.fetch', side_effect=lambda n,*args,**kw:xml if n==1 else None):
                rows,status=scan(Path(td),max_session=10)
        self.assertEqual(status['untersuchte_sitzungen'],1)
        self.assertEqual(status['automatisch_bestaetigte_ordnungsrufe'],0)
        self.assertTrue(len(rows)>=1)

if __name__=='__main__':unittest.main()
