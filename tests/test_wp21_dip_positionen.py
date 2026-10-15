"""DIP procedural-position monitor: genuine API-field schemas with fake responses."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from wp21_dip_monitor import iso
from wp21_dip_positionen import (fetch_positions,normalize_position,read_position_state,
                                  evaluate,run,MAX_PARENTS)

NOW=datetime(2026,10,15,9,tzinfo=timezone.utc)


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
                fetch=lambda p,k:[position(10,p)],now=NOW,key='test')
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
