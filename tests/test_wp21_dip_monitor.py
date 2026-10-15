"""DIP public-API monitor tests with fake paginated official-schema responses.

No network or API key is required. Never derives validated sanction counts.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wp21_dip_monitor import (START, evolve, load_state, paginate, relevant_item,
                              run, iso, utc)

NOW=datetime(2026,10,15,7,0,tzinfo=timezone.utc)

def entry(id, title, abstract='', changed='2026-10-14T09:00:00+00:00'):
    return {'id':str(id),'wahlperiode':21,'typ':'Vorgang',
            'datum':'2026-10-13','aktualisiert':changed,
            'titel':title,'abstract':abstract}

class DIPMonitorTests(unittest.TestCase):
    def test_first_run_uses_full_wp21_lookback_without_history(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            requests=[]
            def load(params,key):
                requests.append(params)
                return {'numFound':2,'documents':[
                    entry(330701,'Ordnungsruf für Herrn Kneller'),
                    entry(330702,'Antrag zum Wasserschutz')], 'cursor':'x'}
            report=run(root/'cache.json',root/'report.json',root/'changes.json',
                       now=NOW,key='test',load=load)
            self.assertEqual(requests[0]['f.aktualisiert.start'],iso(START))
            self.assertEqual(report['tracked_relevant_vorgaenge'],1)
            self.assertEqual(report['new_vorgaenge'],1)
            self.assertEqual(report['automatically_confirmed_sanctions'],0)
            self.assertEqual(len(json.loads((root/'changes.json').read_text())),1)

    def test_paginated_cursor_fetches_all_without_truncation(self):
        calls=[]
        def load(params,key):
            calls.append(params.get('cursor'))
            return ({'numFound':3,'documents':[entry(11,'Ordnungsruf A'),
                                               entry(12,'Ordnungsruf B')],
                     'cursor':'page-2'}
                    if params.get('cursor') is None else
                    {'numFound':3,'documents':[entry(13,'Ordnungsruf C')],
                     'cursor':'page-2'})
        docs,pages=paginate(START,'test',load=load)
        self.assertEqual(pages,2)
        self.assertEqual(calls,[None,'page-2'])
        self.assertEqual(len(docs),3)

    def test_short_pagination_fails_not_falsely_complete(self):
        def load(params,key):
            return {'numFound':15,'documents':[entry(1,'Ordnungsruf')],
                    'cursor':params.get('cursor','same')}
        with self.assertRaises(ValueError):
            paginate(START,'test',load=load)

    def test_duplicate_page_ids_are_rejected(self):
        def load(params,key):
            return {'numFound':3,'documents':[entry(11,'Ordnungsruf'),
                                               entry(11,'Ordnungsruf')],
                    'cursor':'next'}
        with self.assertRaises(ValueError):
            paginate(START,'test',load=load)

    def test_wrong_legislature_is_rejected(self):
        wrong=entry(11,'Ordnungsruf')
        wrong['wahlperiode']=20
        with self.assertRaises(ValueError):
            paginate(START,'test',load=lambda p,k:{
                'numFound':1,'documents':[wrong],'cursor':'x'})

    def test_case_insensitive_legal_signals_are_metadata_only(self):
        item=relevant_item(entry(50,'Ordnungsruf gegen Test',
                                 'Einspruch gegen den Ordnungsruf wurde zurückgewiesen.'))
        self.assertEqual(item['kind'],'rechtsfolgen_hinweis')
        self.assertEqual(item['source'],'https://dip.bundestag.de/vorgang/50')
        self.assertIsNone(relevant_item(entry(51,'Wahlrecht und Gesundheit')))

    def test_incremental_overlap_and_idempotence(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            requests=[]
            def load(params,key):
                requests.append(params)
                return {'numFound':1,
                        'documents':[entry(330701,'Ordnungsruf für Herrn Kneller')],
                        'cursor':'x'}
            out=(folder/'state.json',folder/'report.json',folder/'changes.json')
            first=run(*out,now=NOW,key='test',load=load)
            second=run(*out,now=NOW+timedelta(hours=1),key='test',load=load)
            self.assertEqual(first['new_vorgaenge'],1)
            self.assertEqual(second['new_vorgaenge'],0)
            self.assertEqual(second['tracked_relevant_vorgaenge'],1)
            self.assertEqual(requests[1]['f.aktualisiert.start'],
                             iso(NOW-timedelta(days=30)))

    def test_monthly_full_refresh_recovers_backdated_updates(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            paths=(root/'state.json',root/'report.json',root/'changes.json')
            requests=[]
            def load(params,key):
                requests.append(dict(params))
                if len(requests)==1:
                    return {'numFound':1,'documents':[entry(330701,'Ordnungsruf alt')],
                            'cursor':None}
                return {'numFound':2,'documents':[
                    entry(330701,'Ordnungsruf alt'),
                    entry(330702,'Ordnungsruf nachträglich ergänzt',
                          changed='2026-05-01T10:00:00+00:00')],'cursor':None}
            first=run(*paths,now=NOW,key='test',load=load)
            monthly=run(*paths,now=datetime(2026,11,1,tzinfo=timezone.utc),
                        key='test',load=load)
            self.assertEqual(first['new_vorgaenge'],1)
            self.assertEqual(monthly['new_vorgaenge'],1)
            self.assertTrue(monthly['full_term_refresh'])
            self.assertEqual(monthly['request_since_utc'],iso(START))
            self.assertEqual(monthly['tracked_relevant_vorgaenge'],2)

    def test_regular_day_uses_rolling_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            params=[]
            def load(p,k):
                params.append(p)
                return {'numFound':0,'documents':[],'cursor':None}
            paths=(root/'state.json',root/'report.json',root/'changes.json')
            run(*paths,now=NOW,key='test',load=load)
            report=run(*paths,now=NOW+timedelta(days=1),key='test',load=load)
            self.assertFalse(report['full_term_refresh'])
            self.assertEqual(params[1]['f.aktualisiert.start'],
                             iso(NOW-timedelta(days=30)))

    def test_metadata_change_emits_alert_but_does_not_retract(self):
        original=relevant_item(entry(333,'Ordnungsruf für Frau Test'))
        earlier={'last_success_utc':iso(NOW-timedelta(days=1)),
                 'items':{'333':{**original,'active':True}}}
        docs=[entry(333,'Ordnungsruf für Frau Test',
                    'Einspruch gegen den Ordnungsruf wurde zurückgewiesen.')]
        newer,report,changes=evolve(earlier,docs,NOW)
        self.assertEqual(report['changed_vorgaenge'],1)
        self.assertEqual(report['legal_signals_total'],1)
        self.assertEqual(report['automatically_confirmed_sanctions'],0)
        self.assertEqual(changes[0]['change'],'aktualisiert')

    def test_incomplete_fetch_must_not_replace_successful_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            state=folder/'state.json'
            report=folder/'report.json'
            changes=folder/'changes.json'
            def fetch_ok(p,k):
                return {'numFound':1,'documents':[entry(99,'Ordnungsruf')],
                        'cursor':'x'}
            run(state,report,changes,now=NOW,key='test',load=fetch_ok)
            original=[x.read_bytes() for x in (state,report,changes)]
            def fetch_bad(p,k):
                return {'numFound':5,'documents':[entry(99,'Ordnungsruf')],
                        'cursor':'loop'}
            with self.assertRaises(ValueError):
                run(state,report,changes,now=NOW+timedelta(days=1),
                    key='test',load=fetch_bad)
            self.assertEqual(original,[x.read_bytes() for x in (state,report,changes)])

    def test_missing_from_full_term_retires_only_after_full_refresh(self):
        one=relevant_item(entry(900,'Ordnungsruf Herr Test'))
        original={'last_success_utc':iso(NOW-timedelta(days=1)),
                  'items':{'900':{**one,'active':True}}}
        rolling,report,_=evolve(original,[],NOW)
        self.assertTrue(rolling['items']['900']['active'])
        self.assertEqual(report['missing_from_complete_term'],0)
        full,report,changes=evolve(original,[],NOW,complete_term=True)
        self.assertFalse(full['items']['900']['active'])
        self.assertEqual(report['missing_from_complete_term'],1)
        self.assertEqual(changes[0]['change'],'nicht_mehr_im_gesamtbestand')

    def test_reclassification_keeps_history_not_silent_deletion(self):
        old=relevant_item(entry(900,'Ordnungsruf'))
        earlier={'last_success_utc':iso(NOW-timedelta(days=1)),
                 'items':{'900':{**old,'active':True}}}
        state,report,changes=evolve(earlier,[entry(900,'Anderes Thema')],NOW)
        self.assertFalse(state['items']['900']['active'])
        self.assertEqual(report['no_longer_matching'],1)
        self.assertEqual(changes[0]['change'],'nicht_mehr_treffend')

    def test_reject_tampered_cache(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'state.json'
            f.write_text(json.dumps({'schema':'dip21-incremental-v1',
              'last_success_utc':iso(NOW),
              'items':{'10':{'id':'10','source':'https://evil.net'}}}))
            with self.assertRaises(ValueError):
                load_state(f)

    def test_failing_network_does_not_mutate_existing_state(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            def fail(*args):
                raise OSError('DIP temporarily offline')
            with self.assertRaises(OSError):
                run(folder/'state.json',folder/'report.json',
                    folder/'changes.json',now=NOW,key='test',load=fail)
            self.assertFalse((folder/'state.json').exists())

if __name__=='__main__':
    unittest.main()
