"""Read-only DIP cross-entity queue: accurate ID linking, no legal inference."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from wp21_dip_monitor import iso
from wp21_pruefqueue import build_cases,run

NOW=datetime.now(timezone.utc)


def prepare(directory):
    root=Path(directory)
    primary=root/'primary.json'
    positions=root/'positions.json'
    stamp=iso(NOW)
    primary.write_text(json.dumps({
        'schema':'dip21-incremental-v1','last_success_utc':stamp,
        'items':{
            '330701':{'id':'330701','source':'https://dip.bundestag.de/vorgang/330701',
                      'title':'Ordnungsruf für Abgeordneten Kneller',
                      'kind':'ordnungsruf_bezug','updated':stamp,'active':True},
            '330702':{'id':'330702','source':'https://dip.bundestag.de/vorgang/330702',
                      'title':'Ordnungsruf - Einspruch',
                      'kind':'rechtsfolgen_hinweis','updated':stamp,'active':True},
        }
    }),encoding='utf-8')
    positions.write_text(json.dumps({
        'schema':'dip21-positionen-v1','last_success_utc':stamp,
        'items':{
            '100':{'id':'100','parent_id':'330701',
                   'source':'https://dip.bundestag.de/vorgang/330701',
                   'updated':stamp,'date':'2026-10-15','active':True,
                   'step':'Ordnungsruf erteilt','kind':'verfahrensschritt'},
            '101':{'id':'101','parent_id':'330702',
                   'source':'https://dip.bundestag.de/vorgang/330702',
                   'updated':stamp,'date':'2026-10-15','active':True,
                   'step':'Einspruch zurückgewiesen','kind':'moegliche_rechtsfolge'},
        }
    }),encoding='utf-8')
    return primary,positions


class TestReviewQueue(unittest.TestCase):
    def test_positions_join_only_by_official_parent_id(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=prepare(d)
            cases,report=build_cases(a,b)
        self.assertEqual(report['linked_dip_vorgaenge'],2)
        self.assertEqual(report['high_priority_cases'],1)
        self.assertEqual(cases[0]['id'],'330702')
        self.assertEqual(cases[0]['last_steps'][0]['id'],'101')
        self.assertEqual(cases[1]['last_steps'][0]['id'],'100')

    def test_no_confirmation_or_recission(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=prepare(d)
            cases,report=build_cases(a,b)
        self.assertEqual(report['automatically_confirmed_sanctions'],0)
        self.assertEqual(report['automatically_rescinded_sanctions'],0)
        self.assertEqual(cases[0]['review_status'],'nicht_unabhaengig_geprueft')

    def test_retired_parent_does_not_reappear(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=prepare(d)
            obj=json.loads(a.read_text())
            obj['items']['330702']['active']=False
            a.write_text(json.dumps(obj))
            cases,report=build_cases(a,b)
        self.assertEqual(len(cases),1)
        self.assertEqual(report['high_priority_cases'],0)

    def test_incomplete_position_state_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=prepare(d)
            obj=json.loads(b.read_text())
            obj['last_success_utc']=None
            b.write_text(json.dumps(obj))
            with self.assertRaises(ValueError):
                build_cases(a,b)

    def test_ensures_full_list_archived_separate_from_public_subset(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=prepare(d)
            report=run(a,b,Path(d)/'public.json',Path(d)/'full.json')
            self.assertEqual(report['shown'],2)
            self.assertEqual(len(json.loads((Path(d)/'full.json').read_text())),2)
            self.assertEqual(json.loads((Path(d)/'public.json').read_text())['status'],
                             'dip_verknuepfte_prueffalle_ohne_autozaehlung')

if __name__=='__main__': unittest.main()
