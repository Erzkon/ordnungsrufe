"""Separate source-linked original issue #n from objection decision #n."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_wp21_2025_dip_einzelakten import example_source_snapshot
from wp21_2025_dip_einzelakten import inspect
from wp21_2025_massnahmen_lifecycle import (
    ORIGINAL_40,VOTES_42,review,markdown,run)


def plenary_example():
    def line(val):
        return {'original_xml_line':val,
                'paragraph_sha256':format(val,'064x'),
                'legal_measure_count_confirmed_by_this_paragraph':False}
    return {
        'schema':'wp21-40-42-source-episode-audit-v1',
        'distinct_original_issued_measures_from_independent_sources':5,
        'distinct_rejected_appeals_in_42':4,
        'gottschalk_original_issued_measures':2,
        'gottschalk_appeals_decided_in_42':1,
        'janich_appeals_distinguish_first_and_second':True,
        'four_separate_vote_rejection_wordings_checked':4,
        'automatically_confirmed_effective_sanctions':0,
        'protected_public_counters_changed':False,
        'original_protocol':'https://dserver.bundestag.de/btp/21/21040.xml',
        'appeal_protocol':'https://dserver.bundestag.de/btp/21/21042.xml',
        'source_issuance_paragraphs':{
            k:line(n) for k,n in ORIGINAL_40.values()},
        'source_appeal_paragraphs':{
            k:line(n) for k,n in VOTES_42.values()},
    }


def report_example():
    return inspect(example_source_snapshot())


class IndividualMeasureLifecycleTests(unittest.TestCase):
    def test_twelve_originals_eleven_separate_decided_objections(self):
        result=review(report_example(),plenary_example())
        self.assertEqual(len(result['measures']),12)
        self.assertEqual(result['official_dip_original_parents'],10)
        self.assertEqual(result['initially_issued_individual_grants_review_only'],12)
        self.assertEqual(result['separately_rejected_objections'],11)
        self.assertEqual(result['no_vote_in_examined_parent'],1)
        self.assertEqual(result['identified_original_xml_issuance_lines'],4)
        self.assertEqual(result['still_unlocated_original_xml_issuance_lines'],8)
        self.assertEqual(result['automatically_confirmed_legally_effective_measures'],0)
        self.assertEqual(result['automatically_rescinded_measures'],0)
        self.assertEqual(result['public_counter_delta'],0)
        self.assertFalse(any(x['individual_legally_effective_sanction_confirmed_here']
                             for x in result['measures']))
        self.assertEqual(sum(x['automatic_public_counter_delta'] for x in result['measures']),0)
        self.assertIn('nichtzählende',markdown(result).lower())

    def test_gottschalk_two_distinct_measures_only_first_has_a_vote(self):
        result=review(report_example(),plenary_example())
        kay=[r for r in result['measures'] if r['person']=='Kay Gottschalk']
        self.assertEqual([r['ordinal_within_official_parent'] for r in kay],[1,2])
        self.assertEqual([r['objection_rejection_in_examined_parent'] for r in kay],
                         [True,False])
        self.assertEqual([r['specific_original_issuance_xml_source']['line']
                          for r in kay],[8990,8992])
        self.assertEqual(kay[0]['objection_vote_xml_line']['line'],1521)
        self.assertIsNone(kay[1]['objection_vote_xml_line'])
        self.assertIsNone(kay[1]['objection_vote_dip_position_id'])
        self.assertFalse(kay[1]['missing_vote_means_no_appeal_anywhere'])
        self.assertTrue(result['Gottschalk_second_grant_status_not_exhaustively_established'])
        self.assertEqual(kay[0]['official_parent_id'],kay[1]['official_parent_id'])

    def test_janich_two_decisions_distinct_with_first_grant_line_unlocated(self):
        result=review(report_example(),plenary_example())
        janich=[r for r in result['measures'] if r['person']=='Steffen Janich']
        self.assertEqual(len(janich),2)
        self.assertTrue(janich[0]['first_janich_xml_original_line_still_unlocated'])
        self.assertIsNone(janich[0]['specific_original_issuance_xml_source'])
        self.assertEqual(janich[1]['specific_original_issuance_xml_source']['line'],8719)
        self.assertEqual([x['objection_vote_xml_line']['line'] for x in janich],
                         [1513,1517])
        self.assertEqual(len({x['objection_vote_dip_position_id'] for x in janich}),2)

    def test_sichert_original_xml_line_and_vote_line_stay_distinct(self):
        report=review(report_example(),plenary_example())
        p=next(r for r in report['measures'] if r['person']=='Martin Sichert'
               and r['original_sitting']==40)
        self.assertEqual(p['specific_original_issuance_xml_source']['line'],8715)
        self.assertEqual(p['objection_vote_xml_line']['line'],1507)

    def test_corrupt_original_hash_or_xml_line_must_fail(self):
        for field,val in (('paragraph_sha256','not-sha'),
                          ('original_xml_line',8992)):
            data=plenary_example()
            data['source_issuance_paragraphs'][
                'Gottschalk_first_original_issuance'][field]=val
            with self.subTest(field=field),self.assertRaises(ValueError):
                review(report_example(),data)

    def test_wrong_vote_source_or_missing_second_janich_decision_fails(self):
        data=plenary_example()
        data['source_appeal_paragraphs'].pop('Janich_second_objection_vote')
        with self.assertRaises(ValueError):
            review(report_example(),data)
        data=plenary_example()
        data['appeal_protocol']='https://fake.example/21042.xml'
        with self.assertRaises(ValueError):
            review(report_example(),data)

    def test_wrong_ordinal_vote_assignment_is_not_relabelled(self):
        official=report_example()
        kay=next(x for x in official['cases'] if x['person']=='Kay Gottschalk')
        kay['decision_dip_positions'][0]['abstract_excerpt']=(
            'Einspruch des Abg Kay Gottschalk gegen die zweite Ordnungsmaßnahme')
        with self.assertRaisesRegex(ValueError,'Erster/zweiter'):
            review(official,plenary_example())
        official=report_example()
        janich=next(x for x in official['cases'] if x['person']=='Steffen Janich')
        janich['decision_dip_positions'][0]['abstract_excerpt']=(
            janich['decision_dip_positions'][1]['abstract_excerpt'])
        with self.assertRaisesRegex(ValueError,'Erster/zweiter'):
            review(official,plenary_example())

    def test_bogus_parent_or_wrong_original_identity_fails(self):
        source=report_example()
        kay=next(x for x in source['cases'] if x['person']=='Kay Gottschalk')
        kay['official_dip_parent_id']='329551'
        with self.assertRaisesRegex(ValueError,'Person/Sitzung/Originalzahl'):
            review(source,plenary_example())
        source=report_example()
        source['cases'][0]['independently_sourced_original_issuance_count_review_only']=2
        with self.assertRaisesRegex(ValueError,'Person/Sitzung/Originalzahl'):
            review(source,plenary_example())

    def test_no_duplicate_vote_id_may_serve_two_individual_measures(self):
        source=report_example()
        janich=next(x for x in source['cases'] if x['person']=='Steffen Janich')
        janich['decision_dip_positions'][1]['id']=(
            janich['decision_dip_positions'][0]['id'])
        with self.assertRaisesRegex(ValueError,'Einzelner Einspruch'):
            review(source,plenary_example())

    def test_missing_case_is_never_interpreted_as_empty_original(self):
        source=report_example()
        source['cases'].pop()
        with self.assertRaisesRegex(ValueError,'Genau zehn'):
            review(source,plenary_example())

    def test_files_only_written_after_complete_review_and_not_public(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            (base/'dip.json').write_text(json.dumps(report_example()),encoding='utf-8')
            (base/'xml.json').write_text(json.dumps(plenary_example()),encoding='utf-8')
            product=run(base/'dip.json',base/'xml.json',
                        base/'output.json',base/'output.md')
            self.assertEqual(product['public_counter_delta'],0)
            self.assertEqual(json.loads((base/'output.json').read_text())
                             ['initially_issued_individual_grants_review_only'],12)
            self.assertIn('Gottschalk',(base/'output.md').read_text())
            bad=plenary_example()
            bad['four_separate_vote_rejection_wordings_checked']=3
            (base/'bad.json').write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                run(base/'dip.json',base/'bad.json',
                    base/'not-written.json',base/'not-written.md')
            self.assertFalse((base/'not-written.json').exists())

    def test_report_does_not_allow_automatic_legal_counts(self):
        r=review(report_example(),plenary_example())
        with self.assertRaisesRegex(ValueError,'Zählerleck'):
            markdown({**r,'public_counter_delta':11})


if __name__=='__main__':
    unittest.main()
