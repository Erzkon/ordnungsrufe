"""Offline regression tests for protected WP21 automatic triage."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from wp21_autopruefung import (extract_proposals, make_report, norm,
                                read_reviewed, roots_from_cache, run)

XML = '''<?xml version="1.0" encoding="UTF-8"?>
<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1" sitzung-datum="25.03.2025">
 <redner id="11012345"><name><vorname>Max</vorname><nachname>Beispiel</nachname>
 <fraktion>AfD</fraktion></name></redner>
 <sitzungsverlauf><tagesordnungspunkt>
 <p>Ich erteile dem Abgeordneten Max Beispiel einen Ordnungsruf.</p>
 <p>Ich werde dem Abgeordneten Max Beispiel möglicherweise einen Ordnungsruf erteilen.</p>
 </tagesordnungspunkt></sitzungsverlauf>
</dbtplenarprotokoll>'''.encode()

HEADER = ['ereignis_id','datum','wahlperiode','sitzung','person',
          'fraktion_zur_sitzung','beleg','pruefvermerk']


def write_reference(folder, person='Max Beispiel'):
    target=folder/'verified.csv'
    with target.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=HEADER)
        writer.writeheader()
        writer.writerow({'ereignis_id':'21-001-test-01',
                         'datum':'25.03.2025','wahlperiode':'21',
                         'sitzung':'1','person':person,
                         'fraktion_zur_sitzung':'AfD',
                         'beleg':'https://dserver.bundestag.de/btp/21/21001.pdf#page=2',
                         'pruefvermerk':'Manuell verifiziert'})
    return target


class TestTriage(unittest.TestCase):
    def test_normalisation(self):
        self.assertEqual(norm('  Cansin  KÖKTÜRK '), 'cansin kokturk')

    def test_scan_is_never_automatic_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'21001.xml'
            path.write_bytes(XML)
            rows=extract_proposals([path], {})
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['person_vorschlag'],'Max Beispiel')
            self.assertEqual(rows[0]['pruefstatus'],'offen')
            self.assertIn(rows[0]['prioritaet'],('hoch','mittel'))
            self.assertNotIn('bestaetigt',rows[0]['pruefstatus'])

    def test_exact_session_person_match_is_not_a_grant_count(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            path=folder/'21001.xml'
            path.write_bytes(XML)
            known,count=read_reviewed(write_reference(folder))
            rows=extract_proposals([path],known)
            self.assertEqual(rows[0]['pruefstatus'],'referenz_abgeglichen')
            report=make_report(rows,known,count,1,'2026-10-14T10:00:00+00:00')
            self.assertEqual(report['davon_referenz_person_sitzung_erkannt'],1)
            self.assertEqual(report['automatisch_freigegebene_ordnungsrufe'],0)

    def test_missed_reference_remains_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            path=folder/'21001.xml'
            path.write_bytes(XML)
            known,count=read_reviewed(write_reference(folder,'Jemand Anders'))
            report=make_report(extract_proposals([path],known),known,count,1,'2026-10-14T10:00:00+00:00')
            self.assertEqual(report['davon_referenz_person_sitzung_nicht_erkannt'],1)
            self.assertEqual(report['offene_personenhinweise'],1)

    def test_fail_closed_on_missing_protocol(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                roots_from_cache(Path(temp),1)

    def test_duplicate_reference_ids_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            target=write_reference(folder)
            lines=target.read_text(encoding='utf-8').splitlines()
            target.write_text('\n'.join(lines+[lines[1]])+'\n',encoding='utf-8')
            with self.assertRaises(ValueError):
                read_reviewed(target)

    def test_complete_offline_flow_never_changes_confirmed_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            cache=root/'cache';cache.mkdir()
            (cache/'21001.xml').write_bytes(XML)
            ref=write_reference(root)
            unchanged=ref.read_bytes()
            summary=root/'scan.json'
            summary.write_text(json.dumps({
                'status':'bereit', 'letzte_sitzung':1,
                'untersuchte_sitzungen':1,
                'zuletzt_geprueft_utc':'2026-10-14T10:00:00+00:00',
            }),encoding='utf-8')
            csv_out=root/'hints.csv'
            json_out=root/'audit.json'
            report=run(cache,summary,ref,csv_out,json_out)
            self.assertEqual(report['automatisch_freigegebene_ordnungsrufe'],0)
            self.assertEqual(ref.read_bytes(),unchanged)
            self.assertEqual(json.loads(json_out.read_text())['gescannte_sitzungen'],1)
            with csv_out.open(encoding='utf-8',newline='') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))),1)

    def test_twice_in_same_sitting_is_one_benchmark_key_not_two_grants(self):
        from wp21_autopruefung import norm
        key=(94, norm('Cansin Köktürk'))
        reviewed={key:2}
        proposals=[{'sitzung':'94','person_vorschlag':'Cansin Köktürk',
                    'pruefstatus':'referenz_abgeglichen', 'prioritaet':'niedrig'}]
        report=make_report(proposals,reviewed,2,94,'2026-10-15T06:00:00+00:00')
        self.assertEqual(report['bereits_einzeln_belegte_massnahmen'],2)
        self.assertEqual(report['referenz_person_sitzung_kombinationen'],1)
        self.assertEqual(report['referenz_mehrfachvergaben_ohne_parser_nachweis'],1)
        self.assertEqual(report['davon_referenz_person_sitzung_erkannt'],1)
        self.assertEqual(report['davon_referenz_person_sitzung_nicht_erkannt'],0)
        self.assertEqual(report['automatisch_freigegebene_ordnungsrufe'],0)

if __name__ == '__main__':
    unittest.main()
