"""Strictly non-counting 2025 Bundestag DIP grouped grants versus objections."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from wp21_autopruefung import norm
from wp21_2025_dip_einzelakten import CASES,inspect,render_markdown,run,survey_from_complete_cache
from wp21_weitere_einspruchsberichte import EVIDENCE


def example_source_snapshot():
    records=[]
    for case_ordinal,(day,name,pid,sit,decision_sit,grants,votes) in enumerate(CASES,1):
        source=f'https://dserver.bundestag.de/btp/21/21{sit:03d}'
        result=f'https://dserver.bundestag.de/btp/21/21{decision_sit:03d}'
        decision_date=next(x['decision_date'] for x in EVIDENCE
                           if x['original_date']==day and x['person']==name)
        first={
            'id':str(700000+10*case_ordinal),'date':day,'step':'Ordnungsruf',
            'plenary_session':sit,'plenary_pdf':source+'.pdf#P.120',
            'plenary_xml':source+'.xml','decision_tenors':[],
            'abstract_excerpt':'','signal_fields':[],
        }
        positions=[first]
        for index in range(votes):
            title=(f'Einspruch des Abg {name} '
                   + (f'gegen die {index+1}. Ordnungsmaßnahme'
                      if votes==2 else
                      'gegen die erste Ordnungsmaßnahme'
                      if name=='Kay Gottschalk'
                      else 'gegen die Ordnungsmaßnahme'))
            positions.append({
                'id':str(800000+10*case_ordinal+index),'date':decision_date,
                'step':'Abstimmung','plenary_session':decision_sit,
                'plenary_pdf':result+'.pdf#P.250','plenary_xml':result+'.xml',
                'decision_tenors':['Zurückweisung des Einspruchs'],
                'abstract_excerpt':title,'signal_fields':['beschlussfassung'],
            })
        article='von zwei Ordnungsrufen' if grants==2 else 'eines Ordnungsrufes'
        parent={
            'id':pid,'source':'https://dip.bundestag.de/vorgang/'+pid,
            'title':f'Erteilung {article} an den Abg {name}',
            'date':decision_date,'matching_person_names':[name],
            'original_positions':positions,'original_grant_positions':[first],
        }
        records.append({
            'original_date':day,'person':name,
            'matching_parent_ids':[pid],
            'candidate_parent_count':1,
            'sources':[parent],
        })
    return {
        'schema':'wp21-2025-targeted-official-dip-source-survey-v1',
        'status':'noncounting_complete_filtered_api_inventory',
        'complete_filtered_parent_count':36,
        'selected_named_parent_count':22,
        'official_2025_originals_targeted':10,
        'ten_original_person_date_cases':records,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'protected_statistics_changed':False,
    }


class TenOfficial2025DIPCases(unittest.TestCase):
    def test_all_ten_case_sources_twelve_originals_eleven_votes(self):
        doc=inspect(example_source_snapshot())
        self.assertEqual(doc['official_parent_ids'],10)
        self.assertEqual(doc['source_original_grant_positions'],10)
        self.assertEqual(doc['official_position_records'],21)
        self.assertEqual(doc['original_issuance_events_review_only'],12)
        self.assertEqual(doc['separate_rejected_objections'],11)
        self.assertTrue(doc['gottschalk_two_initial_grants_one_first_objection_decision'])
        self.assertTrue(doc['janich_two_initial_grants_two_independent_decisions'])
        self.assertTrue(doc['other_gottschalk_outcome_unknown_outside_examined_parent'])
        self.assertEqual(doc['automatically_confirmed_effective_measures'],0)
        self.assertEqual(doc['automatically_rescinded_measures'],0)
        self.assertFalse(doc['public_statistics_modified'])
        self.assertIn('nicht',render_markdown(doc).lower())

    def test_all_official_2025_original_sittings_are_individually_specific(self):
        doc=inspect(example_source_snapshot())
        expected={
            ('2025-06-05','Stephan Brandner'):(10,11),
            ('2025-06-06','Stephan Brandner'):(11,12),
            ('2025-06-27','Luigi Pantisano'):(15,16),
            ('2025-09-18','Mirze Edis'):(25,26),
            ('2025-11-13','Kay Gottschalk'):(40,42),
            ('2025-11-13','Martin Sichert'):(40,42),
            ('2025-11-13','Steffen Janich'):(40,42),
            ('2025-11-26','Martin Reichardt'):(43,45),
            ('2025-12-17','Stephan Brandner'):(49,50),
            ('2025-12-18','Martin Reichardt'):(50,51),
        }
        self.assertEqual({
            (c['original_date'],c['person']):
                (c['original_sitting'],c['decision_sitting'])
            for c in doc['cases']}, expected)

    def test_gottschalk_first_explicit_vote_not_second(self):
        result=inspect(example_source_snapshot())
        kay=next(x for x in result['cases'] if x['person']=='Kay Gottschalk')
        self.assertEqual(kay['official_dip_parent_id'],'328225')
        self.assertEqual(kay['independently_sourced_original_issuance_count_review_only'],2)
        self.assertEqual(kay['independently_sourced_rejected_objection_count'],1)
        self.assertIn('erste Ordnungsmaßnahme',
                      kay['decision_dip_positions'][0]['abstract_excerpt'])
        self.assertIn('second_original_measured',kay['review_status'])
        self.assertTrue(kay['unseen_future_or_other_parent_procedures_not_excluded'])

    def test_janich_two_explicit_appeals_with_one_grant_position(self):
        result=inspect(example_source_snapshot())
        janich=next(x for x in result['cases'] if x['person']=='Steffen Janich')
        self.assertEqual(janich['official_dip_parent_id'],'328224')
        self.assertEqual(len(janich['decision_dip_positions']),2)
        self.assertEqual(janich['independently_sourced_original_issuance_count_review_only'],2)
        self.assertEqual(janich['review_status'],'both_separate_appeals_rejected')
        self.assertIn('1. Ordnungsmaßnahme',
                      janich['decision_dip_positions'][0]['abstract_excerpt'])
        self.assertIn('2. Ordnungsmaßnahme',
                      janich['decision_dip_positions'][1]['abstract_excerpt'])

    def test_source_grant_title_cannot_hide_two_real_measures(self):
        s=example_source_snapshot()
        kay=next(x for x in s['ten_original_person_date_cases'] if x['person']=='Kay Gottschalk')
        kay['sources'][0]['title']='Erteilung eines Ordnungsrufes an den Abg Kay Gottschalk'
        with self.assertRaisesRegex(ValueError,'Mehrfacherteilung'):
            inspect(s)

    def test_official_person_identity_parent_id_day_and_sitting_are_required(self):
        mutations=(
            ('person','Steffen Janich'),
            ('matching_parent_ids',['328224']),
            ('original_date','2025-11-12'),
        )
        for field,value in mutations:
            s=example_source_snapshot()
            kay=next(x for x in s['ten_original_person_date_cases'] if x['person']=='Kay Gottschalk')
            kay[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                inspect(s)
        s=example_source_snapshot()
        kay=next(x for x in s['ten_original_person_date_cases'] if x['person']=='Kay Gottschalk')
        kay['sources'][0]['original_positions'][0]['plenary_session']=49
        with self.assertRaisesRegex(ValueError,'Originalerteilungsposition'):
            inspect(s)

    def test_changed_abstract_gottschalk_first_to_second_rejected(self):
        s=example_source_snapshot()
        kay=next(x for x in s['ten_original_person_date_cases'] if x['person']=='Kay Gottschalk')
        kay['sources'][0]['original_positions'][1]['abstract_excerpt']='Einspruch des Abg Kay Gottschalk gegen die zweite Ordnungsmaßnahme'
        with self.assertRaisesRegex(ValueError,'erste/zweite Maßnahme'):
            inspect(s)

    def test_corrupt_vote_tenor_or_pdf_url_not_legal_conclusions(self):
        for field,value in (
                ('decision_tenors',['Aufhebung des Ordnungsrufes']),
                ('plenary_pdf','https://fake.example/21042.pdf#P.250'),
                ('date','2025-11-26'),
        ):
            s=example_source_snapshot()
            kay=next(x for x in s['ten_original_person_date_cases'] if x['person']=='Kay Gottschalk')
            kay['sources'][0]['original_positions'][1][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(
                    ValueError,'Einspruchsentscheidung'):
                inspect(s)

    def test_missing_or_extra_position_or_duplicate_parent_fails_closed(self):
        s=example_source_snapshot()
        kay=next(x for x in s['ten_original_person_date_cases'] if x['person']=='Kay Gottschalk')
        kay['sources'][0]['original_positions'].pop()
        with self.assertRaises(ValueError):
            inspect(s)
        s=example_source_snapshot()
        s['ten_original_person_date_cases'][0]['sources'][0]['id']='328225'
        with self.assertRaises(ValueError):
            inspect(s)
        s=example_source_snapshot()
        janich=next(x for x in s['ten_original_person_date_cases'] if x['person']=='Steffen Janich')
        janich['sources'][0]['original_positions'][2]['id']=janich['sources'][0]['original_positions'][1]['id']
        with self.assertRaises(ValueError):
            inspect(s)

    def test_successful_parent_position_cache_same_evidence_no_extra_counting(self):
        source=example_source_snapshot()
        parents={'last_success_utc':'2026-10-17T08:00:00+00:00','items':{}}
        positions={'last_success_utc':'2026-10-17T09:00:00+00:00','items':{}}
        for item in source['ten_original_person_date_cases']:
            parent=item['sources'][0]
            ident=parent['id']
            parents['items'][ident]={
                'id':ident,'title':parent['title'],'date':parent['date'],
                'source':parent['source'],'active':True}
            for p in parent['original_positions']:
                positions['items'][p['id']]={
                    'id':p['id'],'parent_id':ident,'active':True,
                    'source':parent['source'],'date':p['date'],'step':p['step'],
                    'official_plenary_session':p['plenary_session'],
                    'official_plenary_pdf_url':p['plenary_pdf'],
                    'official_plenary_xml_url':p['plenary_xml'],
                    'official_decision_tenors':p['decision_tenors'],
                    'official_position_abstract_excerpt':p['abstract_excerpt'],
                    'signal_fields':p['signal_fields']}
        cached=survey_from_complete_cache(parents,positions)
        result=inspect(cached)
        self.assertEqual(result['official_parent_ids'],10)
        self.assertEqual(result['official_position_records'],21)
        self.assertEqual(result['original_issuance_events_review_only'],12)
        self.assertEqual(result['separate_rejected_objections'],11)
        self.assertIn('incremental_dip',result['source_scope'])
        self.assertFalse(result['public_statistics_modified'])
        return parents,positions

    def test_stale_or_missing_cache_never_silently_approves_2025(self):
        parents,positions=self.test_successful_parent_position_cache_same_evidence_no_extra_counting()
        stale=copy.deepcopy(positions)
        stale['last_success_utc']='2026-10-17T07:59:00+00:00'
        with self.assertRaisesRegex(ValueError,'veraltet'):
            survey_from_complete_cache(parents,stale)
        broken=copy.deepcopy(positions)
        broken['items'].pop(next(iter(broken['items'])))
        with self.assertRaises(ValueError):
            inspect(survey_from_complete_cache(parents,broken))
        tampered=copy.deepcopy(parents)
        tampered['items']['328225']['source']='https://fake.example/vorgang/328225'
        with self.assertRaisesRegex(ValueError,'Elternvorgänge'):
            survey_from_complete_cache(tampered,positions)

    def test_new_unexpected_vote_is_a_review_alarm_never_a_twelfth_assumed_appeal(self):
        parents,positions=self.test_successful_parent_position_cache_same_evidence_no_extra_counting()
        extra=copy.deepcopy(positions)
        extra['items']['999991']={
            **next(p for p in extra['items'].values()
                   if p['parent_id']=='328225' and p['step']=='Abstimmung'),
            'id':'999991',
        }
        with self.assertRaisesRegex(ValueError,'Original.*Einspruchspositionen'):
            inspect(survey_from_complete_cache(parents,extra))

    def test_safe_write_and_fail_closed_on_untrusted_or_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            source=root/'source.json'
            source.write_text(json.dumps(example_source_snapshot()),encoding='utf-8')
            result=run(source,root/'result.json',root/'brief.md')
            self.assertEqual(result['official_position_records'],21)
            self.assertIn('328225',(root/'brief.md').read_text())
            self.assertEqual(json.loads((root/'result.json').read_text())
                             ['automatically_confirmed_effective_measures'],0)
            sample=example_source_snapshot()
            sample['ten_original_person_date_cases'].pop()
            source.write_text(json.dumps(sample))
            with self.assertRaisesRegex(ValueError,'zehn Original'):
                run(source,root/'should_not_exist.json',root/'should_not_exist.md')
            self.assertFalse((root/'should_not_exist.json').exists())

    def test_renderer_never_converts_rejected_objections_to_approved_counter(self):
        doc=inspect(example_source_snapshot())
        with self.assertRaises(ValueError):
            render_markdown({**doc,'automatically_confirmed_effective_measures':11})
        with self.assertRaises(ValueError):
            render_markdown({**doc,'public_statistics_modified':True})


if __name__=='__main__':
    unittest.main()
