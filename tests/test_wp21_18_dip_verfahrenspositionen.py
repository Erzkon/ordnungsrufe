"""Conservative independent DIP parent/position crosswalk to 18 original cases."""
import json
import tempfile
import unittest
from pathlib import Path
from wp21_autopruefung import norm
from wp21_18_dip_verfahrenspositionen import (
    mentioned_sittings, named, control_dates, crosswalk, render_markdown, run,
)


def parent(ident,title,date,kind='ordnungsruf_bezug',abstract=''):
    return {'id':str(ident),'source':f'https://dip.bundestag.de/vorgang/{ident}',
            'active':True,'title':title,'abstract_excerpt':abstract,
            'date':date,'updated':'2026-10-15T09:00:00+00:00','kind':kind}


def position(ident,parent_id,kind='moegliche_rechtsfolge',step='Einspruch zurückgewiesen'):
    return {'id':str(ident),'parent_id':str(parent_id),
            'source':f'https://dip.bundestag.de/vorgang/{parent_id}',
            'active':True,'kind':kind,'step':step,'title':'Einspruch gegen Ordnungsruf',
            'signal_fields':['titel'],
            'updated':'2026-10-16T08:30:00+00:00','date':'2026-10-16'}


def state(parents=None, positions=None):
    return (
        {'last_success_utc':'2026-10-15T09:00:00+00:00',
         'items':{str(x['id']):x for x in (parents or [])}},
        {'last_success_utc':'2026-10-16T08:30:00+00:00',
         'items':{str(x['id']):x for x in (positions or [])}},
    )


class OriginalDIPCrosswalkTests(unittest.TestCase):
    def test_full_name_is_not_a_prefix_and_protocol_sitting_is_explicit(self):
        self.assertTrue(named('Ordnungsruf für den Abg Martin Hess (AfD)', 'Martin Hess'))
        self.assertFalse(named('Ordnungsruf für Martin Hesseling', 'Martin Hess'))
        self.assertFalse(named('Ordnungsruf für Martin Hesse', 'Martin Hess'))
        self.assertEqual(mentioned_sittings('BT-Plenarprotokoll 21/065 S. 12'),{65})
        self.assertEqual(mentioned_sittings('aus der 65. Sitzung'),{65})
        self.assertEqual(mentioned_sittings('BT-PlPr 21/065 und 21/077'),{65,77})
        self.assertEqual(mentioned_sittings('Sitzung 65 im September 2026'),set())

    def test_all_18_curated_original_grant_dates_must_be_present(self):
        dates=control_dates(__import__('wp21_dip_kontrolle').reference())
        self.assertEqual(len(dates),18)
        self.assertEqual(dates[(52,norm('Martin Hess'))],'2026-01-14')
        self.assertEqual(dates[(65,norm('Martin Reichardt'))],'2026-03-19')
        self.assertEqual(dates[(94,norm('Cansin Köktürk'))],'2026-09-11')

    def test_name_and_date_links_only_one_original_session(self):
        parents=[
            parent(331001,'Erteilung eines Ordnungsrufes an Martin Hess','2026-01-14'),
            parent(331002,'Erteilung eines Ordnungsrufes an Martin Reichardt '
                          'im BT-Plenarprotokoll 21/077','2026-05-07'),
            parent(331003,'Erteilung eines Ordnungsrufes an Martin Reichardt '
                          'in der 65. Sitzung','2026-03-20'),
            parent(331004,'Verhängung eines Ordnungsgeldes gegen Cansin Köktürk; '
                          'zuvor Ordnungsruf','2026-09-11'),
            parent(331005,'Zwei Ordnungsrufe für Cansin Köktürk','2026-09-11'),
            parent(331006,'Ordnungsruf gegen Martin Reichardt','2026-08-20'),
            parent(331007,'Erteilung eines Ordnungsrufes an Martin Hesseling','2026-01-14'),
        ]
        a,b=state(parents,[position(5001,331001),position(5002,331003),
                           position(5003,331005)])
        r=crosswalk(a,b)
        self.assertEqual(r['original_cases'],18)
        self.assertEqual(r['bound_vorgang_candidates'],3)
        self.assertEqual(r['bound_position_hints'],3)
        self.assertEqual(r['unbound_same_name_vorgaenge'],2)
        self.assertEqual(r['different_measures_safely_excluded'],1)
        self.assertEqual(r['automatically_confirmed_sanctions'],0)
        self.assertEqual(r['automatically_rescinded_sanctions'],0)
        row=lambda s,p:next(x for x in r['cases'] if (x['session'],x['person'])==(s,p))
        self.assertEqual(row(52,'Martin Hess')['candidate_vorgaenge'][0]['parent_id'],'331001')
        self.assertEqual(row(65,'Martin Reichardt')['candidate_vorgaenge'][0]['parent_id'],'331003')
        self.assertEqual(row(94,'Cansin Köktürk')['candidate_vorgaenge'][0]['parent_id'],'331005')
        self.assertEqual(row(65,'Martin Reichardt')['candidate_vorgaenge'][0]
                         ['original_source_link_type'],'explicit_original_sitting_candidate')
        self.assertFalse(row(65,'Martin Reichardt')['candidate_vorgaenge'][0]
                         ['procedural_position_hints'][0]['is_individual_appeal_outcome_legally_confirmed'])
        self.assertTrue(all(x['manual_appeal_and_legal_effect_review_required']
                            for x in r['cases']))
        rendered=render_markdown(r)
        self.assertIn('Keine bestätigte Rechtswirksamkeit',rendered)
        self.assertIn('331003',rendered)
        self.assertIn('331002',rendered)
        self.assertNotIn('331004',rendered)

    def test_same_named_multiple_sittings_are_not_assigned_without_date_or_sitting(self):
        a,b=state([parent(551,'Ordnungsruf an Martin Reichardt','')])
        r=crosswalk(a,b)
        self.assertEqual(r['bound_vorgang_candidates'],0)
        self.assertEqual(r['unbound_same_name_vorgaenge'],1)
        self.assertEqual(r['cases_with_bound_parent_candidates'],0)
        self.assertEqual(r['unbound_same_name_review_candidates'][0]
                         ['candidate_original_keys'],
                         ['21/065:martin reichardt'])
        # The explicit other sitting is excluded, not inferred from surname.
        a,b=state([parent(552,'Ordnungsruf an Martin Reichardt, '
                                'Protokoll 21/077','')])
        self.assertEqual(crosswalk(a,b)['bound_vorgang_candidates'],0)

    def test_competing_sitting_references_are_not_linked(self):
        a,b=state([parent(551,'Ordnungsruf an Martin Reichardt '
                                'in der 65. Sitzung und im BT-PlPr 21/77',
                                '2026-03-19')])
        r=crosswalk(a,b)
        self.assertEqual(r['bound_vorgang_candidates'],0)
        self.assertEqual(r['unbound_same_name_vorgaenge'],1)

    def test_position_snapshot_must_be_at_least_as_recent_as_vorgang(self):
        a,b=state([parent(551,'Ordnungsruf an Martin Hess','2026-01-14')])
        b['last_success_utc']='2026-10-14T09:00:00+00:00'
        with self.assertRaisesRegex(ValueError,'älter'):
            crosswalk(a,b)
        a['last_success_utc']=None
        with self.assertRaisesRegex(ValueError,'zwei|Zwei'):
            crosswalk(a,b)

    def test_wrong_parent_source_and_unsafe_status_are_rejected(self):
        a,b=state([parent(551,'Ordnungsruf an Martin Hess','2026-01-14')],
                  [position(701,551)])
        b['items']['701']['source']='https://example.org/fake'
        with self.assertRaisesRegex(ValueError,'Beschädigte'):
            crosswalk(a,b)
        a['items']['551']['source']='https://example.org/fake'
        with self.assertRaisesRegex(ValueError,'Nichtamtlicher'):
            crosswalk(a,{'last_success_utc':'2026-10-16T08:30:00+00:00','items':{}})

    def test_file_readiness_is_required_and_never_overwrites_on_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            vorgang=root/'vorgang.json'
            positions=root/'positions.json'
            output=root/'report.json'; brief=root/'review.md'
            output.write_bytes(b'unchanged')
            brief.write_bytes(b'also unchanged')
            with self.assertRaises(ValueError):
                run(vorgang,positions,output,brief)
            self.assertEqual(output.read_bytes(),b'unchanged')
            self.assertEqual(brief.read_bytes(),b'also unchanged')
            p=parent(551,'Erteilung eines Ordnungsrufes an Martin Hess','2026-01-14')
            vorgang.write_text(json.dumps({
                'schema':'dip21-incremental-v1',
                'last_success_utc':'2026-10-15T09:00:00+00:00',
                'last_full_refresh_utc':'2026-10-15T09:00:00+00:00',
                'items':{'551':p}}),encoding='utf-8')
            positions.write_text(json.dumps({
                'schema':'dip21-positionen-v1',
                'last_success_utc':'2026-10-16T08:30:00+00:00',
                'items':{'701':position(701,551)}}),encoding='utf-8')
            report=run(vorgang,positions,output,brief)
            self.assertEqual(report['bound_vorgang_candidates'],1)
            self.assertEqual(json.loads(output.read_text())['bound_position_hints'],1)
            self.assertIn('Martin Hess',brief.read_text())
            self.assertFalse(report['protected_statistics_changed'])

    def test_unknown_legal_outcome_cannot_be_inserted_into_renderer(self):
        a,b=state([parent(551,'Ordnungsruf an Martin Hess','2026-01-14')],
                  [position(701,551)])
        report=crosswalk(a,b)
        with self.assertRaises(ValueError):
            render_markdown({**report,'automatically_confirmed_sanctions':1})
        with self.assertRaises(ValueError):
            render_markdown({**report,'protected_statistics_changed':True})


if __name__=='__main__':
    unittest.main()
