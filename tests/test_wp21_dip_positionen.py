"""DIP procedural-position monitor: genuine API-field schemas with fake responses."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from wp21_dip_monitor import iso
from wp21_dip_positionen import (fetch_positions,normalize_position,read_position_state,
                                  evaluate,run,MAX_PARENTS,position_document_evidence)

NOW=datetime.now(timezone.utc)


def position(ident, parent='330701', step='Einspruch gegen den Ordnungsruf eingelegt'):
    return {'id':str(ident),'vorgang_id':str(parent),'typ':'Vorgangsposition',
            'vorgangsposition':step,'titel':'Ordnungsruf wegen Zwischenrufs',
            'aktualisiert':'2026-10-15T08:30:00+00:00','datum':'2026-10-15',
            'nachtrag':False}


def source(path, parents=('330701',)):
    path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps({
        'schema':'dip21-incremental-v1',
        'last_success_utc':iso(NOW),
        'items':{ident:{'id':ident,'source':'https://dip.bundestag.de/vorgang/'+ident,
            'title':'Ordnungsruf'} for ident in parents}
    }),encoding='utf-8')


class DIPPositions(unittest.TestCase):
    def test_fetch_by_official_filter_and_cursor(self):
        queries=[]
        def fake(params,key):
            queries.append(dict(params))
            if 'cursor' not in params:
                return {'numFound':2,'cursor':'next',
                        'documents':[position(1)]}
            return {'numFound':2,'cursor':'next',
                    'documents':[position(2)]}
        found=fetch_positions('330701','test',load=fake)
        self.assertEqual(len(found),2)
        self.assertEqual(queries[0]['f.vorgang'],'330701')
        self.assertEqual(queries[0]['f.wahlperiode'],'21')
        self.assertEqual(queries[1]['cursor'],'next')

    def test_empty_parent_is_valid(self):
        self.assertEqual(fetch_positions('330701','test',
            load=lambda q,k:{'documents':[],'numFound':0,'cursor':None}),[])

    def test_wrong_parent_fails(self):
        with self.assertRaises(ValueError):
            fetch_positions('330701','test',
                load=lambda q,k:{'documents':[position(1,parent='999')],
                                 'numFound':1,'cursor':'z'})

    def test_duplicate_position_rejected(self):
        with self.assertRaises(ValueError):
            fetch_positions('330701','test',load=lambda q,k:{
                'documents':[position(1),position(1)],'numFound':2,'cursor':'z'})

    def test_incomplete_cursor_is_error(self):
        with self.assertRaises(ValueError):
            fetch_positions('330701','test',load=lambda q,k:{
                'documents':[position(1)],'numFound':2,'cursor':'same'})

    def test_legal_rejection_is_not_a_retraction(self):
        item=normalize_position(position(1,step='Einspruch gegen den Ordnungsruf zurückgewiesen'))
        self.assertEqual(item['kind'],'moegliche_rechtsfolge')
        a,b,c=evaluate({'items':{}},[position(1)],{'330701'},NOW)
        self.assertEqual(b['automatically_rescinded_sanctions'],0)
        self.assertEqual(b['automatically_confirmed_sanctions'],0)
        self.assertEqual(b['new_positions'],1)
        self.assertEqual(len(c),1)

    def test_official_title_can_flag_appeal_even_when_step_only_says_ordnungsruf(self):
        raw=position(12,step='Ordnungsruf')
        raw['titel']='Einspruch gegen einen erteilten Ordnungsruf'
        item=normalize_position(raw)
        self.assertEqual(item['kind'],'moegliche_rechtsfolge')
        self.assertEqual(item['signal_fields'],['titel'])

    def test_nested_activity_mention_is_review_hint_never_automatic_retraction(self):
        raw=position(12,step='Ordnungsruf')
        raw['titel']='Erteilung eines Ordnungsrufes'
        raw['aktivitaet_anzeige']=[
            {'titel':'Prüfung eines Einspruchs gegen den Ordnungsruf',
             'aktivitaetsart':'Zur Geschäftsordnung BT'}]
        item=normalize_position(raw)
        self.assertEqual(item['kind'],'moegliche_rechtsfolge')
        self.assertEqual(item['signal_fields'],['aktivitaet_anzeige'])
        _,report,_=evaluate({'items':{}},[raw],{'330701'},NOW)
        self.assertEqual(report['automatically_rescinded_sanctions'],0)

    def test_unexpected_activity_metadata_fails_closed(self):
        raw=position(12)
        raw['aktivitaet_anzeige']=[{'titel':{'incorrect':'object'}}]
        with self.assertRaises(ValueError):
            normalize_position(raw)

    def test_actual_bundesrat_fundstellen_are_read_only_and_not_bundestag_sittings(self):
        # Official DIP records confirmed in the live 17 October 2026 probe.
        for pid, parent, number, page, day in (
                ('670644','321963','1054','130','2025-05-23'),
                ('678924','325401','1058','366','2025-10-17'),
                ('678887','325513','1058','354','2025-10-17')):
            with self.subTest(position_id=pid):
                raw=position(pid,parent=parent)
                raw['datum']=day
                raw['fundstelle']={
                    'dokumentart':'Plenarprotokoll',
                    'dokumentnummer':number,'datum':day,
                    'pdf_url':f'https://dserver.bundestag.de/brp/{number}.pdf#P.{page}',
                }
                evidence=position_document_evidence(raw)
                self.assertEqual(evidence['official_plenary_chamber'],'Bundesrat')
                self.assertEqual(evidence['official_bundesrat_session'],int(number))
                self.assertIsNone(evidence['official_plenary_session'])
                self.assertIsNone(evidence['official_plenary_xml_url'])
                self.assertTrue(evidence['source_metadata_is_only_a_review_hint'])
                normalized=normalize_position(raw)
                self.assertEqual(normalized['official_plenary_chamber'],'Bundesrat')
                _, report, _=evaluate({'items':{}},[raw],{parent},NOW)
                self.assertEqual(report['automatically_confirmed_sanctions'],0)
                self.assertEqual(report['automatically_rescinded_sanctions'],0)

    def test_bundesrat_pdf_provenance_and_date_must_match(self):
        from copy import deepcopy
        raw=position(670644,parent='321963')
        raw['datum']='2025-05-23'
        raw['fundstelle']={
            'dokumentart':'Plenarprotokoll','dokumentnummer':'1054',
            'datum':'2025-05-23',
            'pdf_url':'https://dserver.bundestag.de/brp/1054.pdf#P.130',
        }
        for field,value in (
                ('dokumentnummer','0'),
                ('dokumentnummer','21/1054'),
                ('dokumentnummer','20/104'),
                ('pdf_url','https://evil.example/brp/1054.pdf#P.130'),
                ('pdf_url','https://dserver.bundestag.de/brp/1058.pdf#P.130'),
                ('pdf_url','https://dserver.bundestag.de/btp/21/211054.pdf#P.130'),
                ('pdf_url','https://dserver.bundestag.de/brp/1054.pdf'),
                ('pdf_url','https://dserver.bundestag.de/brp/1054.pdf#P.0'),
                ('xml_url','https://dserver.bundestag.de/btp/21/21054.xml'),
                ('datum','2025-05-24'),
        ):
            with self.subTest(field=field,value=value):
                altered=deepcopy(raw)
                altered['fundstelle'][field]=value
                with self.assertRaises(ValueError):
                    position_document_evidence(altered)
        altered=deepcopy(raw)
        altered['datum']='2025-05-24'
        with self.assertRaisesRegex(ValueError,'widersprechen'):
            position_document_evidence(altered)

    def test_bundestag_plenary_strict_url_check_still_applies(self):
        raw=position(700001)
        raw['fundstelle']={
            'dokumentart':'Plenarprotokoll','dokumentnummer':'21/40',
            'datum':raw['datum'],
            'pdf_url':'https://dserver.bundestag.de/btp/21/21040.pdf#P.130',
            'xml_url':'https://dserver.bundestag.de/btp/21/21040.xml',
        }
        doc=position_document_evidence(raw)
        self.assertEqual(doc['official_plenary_chamber'],'Bundestag')
        self.assertEqual(doc['official_plenary_session'],40)
        self.assertIsNone(doc['official_bundesrat_session'])
        raw['fundstelle']['xml_url']='https://dserver.bundestag.de/brp/1054.xml'
        with self.assertRaisesRegex(ValueError,'nichtamtliche'):
            position_document_evidence(raw)

    def test_second_identical_run_is_idempotent(self):
        current,new_report,_=evaluate({'items':{}},[position(1)],{'330701'},NOW)
        later,report,changes=evaluate(current,[position(1)],{'330701'},NOW)
        self.assertEqual(changes,[])
        self.assertEqual(report['new_positions'],0)
        self.assertEqual(report['tracked_positions'],1)

    def test_removed_position_is_retained_in_history(self):
        old,_,_=evaluate({'items':{}},[position(1)],{'330701'},NOW)
        new,report,changes=evaluate(old,[],{'330701'},NOW)
        self.assertEqual(report['missing_positions'],1)
        self.assertFalse(new['items']['1']['active'])
        self.assertEqual(changes[0]['change'],'nicht_mehr_gefunden')

    def test_no_partial_state_writes_when_second_parent_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            src=root/'vorgang_state.json'
            target=root/'position_state.json'
            report=root/'report.json'
            changes=root/'changes.json'
            source(src,parents=('330701','330702'))
            def fail_on_second(parent,key):
                if parent=='330702':
                    raise OSError('API nicht erreichbar')
                return [position(1)]
            with self.assertRaises(OSError):
                run(src,target,report,changes,fetch=fail_on_second,now=NOW,key='test')
            self.assertFalse(target.exists())
            self.assertFalse(report.exists())

    def test_completed_multi_parent_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            src=root/'vorgang.json'
            source(src,parents=('330701','330702'))
            result=run(src,root/'positions.json',root/'report.json',root/'changes.json',
                fetch=lambda p,k:[position(int(p)-330690,p)],now=NOW,key='test')
            self.assertEqual(result['tracked_positions'],2)
            self.assertEqual(result['monitored_parent_vorgaenge'],2)
            self.assertEqual(result['legal_wording_positions'],2)
            self.assertEqual(len(read_position_state(root/'positions.json')['items']),2)

    def test_bad_state_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'positions.json'
            p.write_text(json.dumps({'schema':'dip21-positionen-v1',
                'items':{'100':{'id':'100','parent_id':'110',
                'source':'http://evil.test/'}}}))
            with self.assertRaises(ValueError):
                read_position_state(p)

    def test_report_is_not_sanction_count(self):
        snap,r,_=evaluate({'items':{}},[position(1),position(2,
            step='Der Einspruch gegen den Ordnungsruf wurde zurückgewiesen')],
            {'330701'},NOW)
        self.assertEqual(r['tracked_positions'],2)
        self.assertEqual(r['automatically_rescinded_sanctions'],0)

if __name__=='__main__':unittest.main()
