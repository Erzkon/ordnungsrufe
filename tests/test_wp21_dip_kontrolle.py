"""Official DIP positive control sample and non-destructive shadow cross-check."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from wp21_dip_kontrolle import (reference,compare,proposal_keys,run,REVIEWED)
from wp21_autopruefung import read_reviewed, norm


class TestDIPSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref=reference()
        cls.reviewed,cls.verified_count=read_reviewed(REVIEWED)

    def test_official_partial_sample_larger_than_manual_selection(self):
        self.assertEqual(len(self.ref['entries']),24)
        self.assertEqual(sum(r['reported_grants'] for r in self.ref['entries']),25)
        _,status=compare(self.ref,self.reviewed)
        self.assertEqual(status['davon_in_teilbestand_einzeln_belegt'],8)
        self.assertEqual(status['noch_nicht_in_teilbestand_belegt'],17)
        self.assertFalse(status['parser_geprueft'])
        self.assertEqual(status['automatisch_freigegebene_ordnungsrufe'],0)

    def test_two_kokturk_sanctions_are_one_dip_person_session_key(self):
        matching=[r for r in self.ref['entries']
                  if r['session']==94 and r['person']=='Cansin Köktürk']
        self.assertEqual(len(matching),1)
        self.assertEqual(matching[0]['reported_grants'],2)
        _,status=compare(self.ref,self.reviewed)
        self.assertEqual(status['dip_protokoll_personen_kombinationen'],24)
        self.assertEqual(status['dip_dokumentierte_urspruengliche_rufe_in_stichprobe'],25)

    def test_person_match_not_promoted_to_a_grant(self):
        parser_keys={(x['session'],norm(x['person']))
                     for x in self.ref['entries']}
        _,status=compare(self.ref,self.reviewed,parser_keys)
        self.assertEqual(status['dip_person_sitzung_per_parser_gefunden'],24)
        self.assertEqual(status['automatisch_freigegebene_ordnungsrufe'],0)

    def test_ambiguous_or_missing_parser_is_measured_not_approved(self):
        _,status=compare(self.ref,self.reviewed,set())
        self.assertEqual(status['dip_person_sitzung_vom_parser_verpasst'],24)
        self.assertEqual(status['automatisch_freigegebene_ordnungsrufe'],0)

    def test_detects_duplicate_reference_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'duplicate.json'
            fixture=dict(self.ref)
            fixture['entries']=self.ref['entries']+[self.ref['entries'][0]]
            path.write_text(json.dumps(fixture),encoding='utf-8')
            with self.assertRaises(ValueError):
                reference(path)

    def test_csv_roundtrip_and_confirmed_data_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            unchanged=REVIEWED.read_bytes()
            report=run(output_csv=p/'dip.csv',output_json=p/'dip.json')
            self.assertEqual(REVIEWED.read_bytes(),unchanged)
            self.assertEqual(report['automatisch_freigegebene_ordnungsrufe'],0)
            with (p/'dip.csv').open(encoding='utf-8',newline='') as handle:
                rows=list(csv.DictReader(handle))
            self.assertEqual(len(rows),24)
            self.assertTrue(all(x['amtlicher_index'].startswith('https://dip.bundestag.de')
                                for x in rows))

    def test_snapshot_does_not_claim_all_positive_cases(self):
        _,report=compare(self.ref,self.reviewed)
        self.assertIn('Keine vollständige DIP-Inventur',report['hinweis'])
        self.assertIn('ohne_gesamtzahl',report['status'])

if __name__=='__main__':
    unittest.main()
