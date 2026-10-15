"""Independent source-coverage audit: don't confuse events, mentions and counts."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from wp21_vollstaendigkeit import (build_cases, inventory, run, scan_lines,
                                   person_hints, audited_summary)
from wp21_dip_kontrolle import REFERENCE
from wp21_autopruefung import norm

STAMP='2026-10-15T08:00:00+00:00'
PDF='https://dserver.bundestag.de/btp/21/21094.pdf'
XML='https://dserver.bundestag.de/btp/21/21094.xml'


def scanrow(line=12, classification='possible_grant'):
    return {'hinweis_id':f'21-094-L{line}-abcdef012345',
            'sitzung':'94','xml_zeile':str(line),
            'klasse':classification,'status':'manuelle_pruefung_erforderlich',
            'xml_quelle':XML,'pdf_quelle':PDF}


def parserrow(line=12, person='Cansin Köktürk'):
    return {'hinweis_id':f'21-094-L{line}-abcdef0123',
            'sitzung':'94','xml_zeile':str(line),
            'person_vorschlag':person,'klassifikation':'possible_grant',
            'pruefstatus':'offen','protokoll_21':PDF}


def write_csv(path,columns,rows):
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def make_data(folder, xml=None, parser=None):
    root=Path(folder)
    scan=root/'xml.csv'; proposed=root/'parser.csv'
    xml=[scanrow()] if xml is None else xml
    parser=[parserrow()] if parser is None else parser
    write_csv(scan,list(scanrow()),xml)
    write_csv(proposed,list(parserrow()),parser)
    summary={'status':'bereit','letzte_sitzung':94,
             'untersuchte_sitzungen':94,'textstellen_zur_pruefung':len(xml),
             'zuletzt_geprueft_utc':STAMP}
    parsed={'status':'automatische_vorpruefung_ohne_freigabe',
            'gescannte_sitzungen':94,'parser_personenhinweise':len(parser),
            'letzter_Quellenscan_utc':STAMP}
    (root/'scan.json').write_text(json.dumps(summary))
    (root/'parser.json').write_text(json.dumps(parsed))
    return scan,proposed,summary,parsed


class CrossSourceAuditTests(unittest.TestCase):
    def test_multiple_grants_are_not_proved_by_one_parser_mention(self):
        reviewed={(94,norm('Cansin Köktürk')):2}
        dip={'entries':[{'session':94,'person':'Cansin Köktürk',
                         'reported_grants':2}],
             'official_index':'https://dip.bundestag.de/suche?x=1'}
        parser={(94,norm('Cansin Köktürk')):[parserrow()]}
        cases,metric=build_cases(reviewed,dip,parser,{(94,12):[scanrow()]},94)
        self.assertEqual(metric['multiple_measure_person_session_keys'],1)
        self.assertEqual(cases[0]['bestaetigte_massnahmen_teilbestand'],'2')
        self.assertEqual(cases[0]['parser_fundstellen'],'1')
        self.assertEqual(cases[0]['prioritaet'],'hoch')
        self.assertEqual(cases[0]['typ'],'person_sitzung_ohne_einzelereignisabgleich')

    def test_future_sessions_are_excluded_from_missed_detection(self):
        reviewed={(100,norm('Test')):1,(90,norm('Andere')):1}
        dip={'entries':[{'session':101,'person':'Test','reported_grants':2}],
             'official_index':'https://dip.bundestag.de/suche?x=1'}
        cases,metrics=build_cases(reviewed,dip,{}, {},94)
        self.assertEqual(len(cases),1)
        self.assertEqual(metrics['confirmed_keys_without_parser'],1)
        self.assertEqual(metrics['dip_sample_keys_without_parser'],0)

    def test_xml_orphan_text_is_not_a_new_grant(self):
        dip={'entries':[],'official_index':'https://dip.bundestag.de/suche?x=1'}
        warnings={(94,12):[scanrow(classification='warning_or_conditional')]}
        cases,metric=build_cases({},dip,{},warnings,94)
        self.assertEqual(metric['xml_text_locations_without_person_parser'],1)
        self.assertEqual(len(cases),1)
        self.assertEqual(cases[0]['prioritaet'],'mittel')
        self.assertEqual(cases[0]['person'],'')
        self.assertEqual(cases[0]['dip_urspruengliche_erteilungen_stichprobe'],'')

    def test_unattributed_grant_text_needs_high_priority_review(self):
        dip={'entries':[],'official_index':'https://dip.bundestag.de/suche?x=1'}
        cases,_=build_cases({},dip,{}, {(94,12):[scanrow()]},94)
        self.assertEqual(cases[0]['prioritaet'],'hoch')

    def test_rejects_mismatched_parser_lines(self):
        with tempfile.TemporaryDirectory() as td:
            scan,proposed,_,_=make_data(td,parser=[parserrow(22)])
            with self.assertRaisesRegex(ValueError,'ohne XML-Quelle'):
                inventory(json.loads((Path(td)/'scan.json').read_text()),
                          json.loads((Path(td)/'parser.json').read_text()),
                          scan,proposed,Path('daten/wirksame_ordnungsrufe_21wp.csv'),REFERENCE)

    def test_rejects_tampered_xml_urls_and_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as td:
            src,_,_,_=make_data(td)
            bad=scanrow()
            bad['pdf_quelle']='https://example.com/bad'
            write_csv(src,list(bad),[bad])
            with self.assertRaises(ValueError):
                scan_lines(src,94)
            write_csv(src,list(scanrow()),[scanrow(),scanrow()])
            with self.assertRaises(ValueError):
                scan_lines(src,94)

    def test_rejects_stale_cross_source_run(self):
        with tempfile.TemporaryDirectory() as td:
            _,_,scan,parser=make_data(td)
            parser['letzter_Quellenscan_utc']='2026-10-14T08:00:00+00:00'
            with self.assertRaisesRegex(ValueError,'nicht synchron'):
                audited_summary(scan,parser,1,1)

    def test_rejects_duplicate_parser_ids(self):
        with tempfile.TemporaryDirectory() as td:
            _,src,_,_=make_data(td)
            write_csv(src,list(parserrow()),[parserrow(),parserrow()])
            with self.assertRaises(ValueError):
                person_hints(src,94)

    def test_real_ledger_and_curated_dip_stay_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            scan,parsed,_,_=make_data(root)
            ledger=Path('daten/wirksame_ordnungsrufe_21wp.csv')
            confirmed=Path('docs/data/ordnungsrufe_21.json')
            before=[p.read_bytes() for p in (ledger,confirmed,REFERENCE)]
            report=run(root/'scan.json',root/'parser.json',scan,parsed,
                       ledger,REFERENCE,root/'full.csv',root/'public.json')
            self.assertEqual([p.read_bytes() for p in (ledger,confirmed,REFERENCE)],before)
            self.assertEqual(report['automatically_confirmed_sanctions'],0)
            self.assertEqual(report['automatically_rescinded_sanctions'],0)
            self.assertEqual(report['sessions_scanned'],94)
            self.assertEqual(report['dip_sample_person_session_keys_outside_scan'],2)
            self.assertEqual(report['dip_sample_reported_original_grants_within_scan'],23)
            self.assertGreaterEqual(report['review_cases_total'],22)
            with (root/'full.csv').open(encoding='utf-8',newline='') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))),
                                 report['review_cases_total'])
            self.assertEqual(json.loads((root/'public.json').read_text())['shown'],
                             min(30,report['review_cases_total']))

    def test_truncated_or_stale_report_preserves_previous_results(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            xml,proposed,scan,parser=make_data(root)
            ledger=Path('daten/wirksame_ordnungsrufe_21wp.csv')
            outputs=(root/'full.csv',root/'public.json')
            for output in outputs:
                output.write_bytes(b'unchanged')
            scan['textstellen_zur_pruefung']=2
            (root/'scan.json').write_text(json.dumps(scan))
            with self.assertRaises(ValueError):
                run(root/'scan.json',root/'parser.json',xml,proposed,
                    ledger,REFERENCE,*outputs)
            self.assertEqual([o.read_bytes() for o in outputs],
                             [b'unchanged',b'unchanged'])


if __name__ == '__main__':
    unittest.main()
