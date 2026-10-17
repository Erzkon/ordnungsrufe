"""Bounded official Gottschalk source survey must not infer universal absence."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from wp21_gottschalk_bounded_review import inspect,markdown,run


def source():
    return {
        'schema':'wp21-gottschalk-later-procedure-bounded-review-v1',
        'search_start':'2025-11-13','search_end':'2026-10-17',
        'search_query':'official_21wp_title_ordnungsruf_and_vorgang_datum',
        'fully_traversed_filtered_dip_parent_count':36,
        'official_dip_api_pages_checked':1,
        'named_gottschalk_parent_count':1,
        'known_original_dip_id':'328225',
        'other_parliamentary_procedures_outside_this_title_date_filter_not_excluded':True,
        'missing_second_vote_is_not_proof_of_final_effectiveness':True,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'public_counters_changed':False,
        'second_appeal_explicitly_worded_candidates':[],
        'gottschalk_named_source_parents':[{
            'id':'328225',
            'title':'Erteilung von zwei Ordnungsrufen an den Abg Kay Gottschalk (AfD)',
            'date':'2025-11-25',
            'source':'https://dip.bundestag.de/vorgang/328225',
            'abstract_excerpt':'',
            'official_position_count':2,
            'complete_parent_positions':[{
                'id':'681046','date':'2025-11-13',
                'title':'Erteilung von zwei Ordnungsrufen an den Abg Kay Gottschalk (AfD)',
                'step':'Ordnungsruf','abstract_excerpt':'',
                'plenary_session':40,
                'plenary_pdf':'https://dserver.bundestag.de/btp/21/21040.pdf#P.4635',
                'decision_tenors':[],'signal_fields':[],
            },{
                'id':'681803','date':'2025-11-25',
                'title':'Erteilung von zwei Ordnungsrufen an den Abg Kay Gottschalk (AfD)',
                'step':'Abstimmung',
                'abstract_excerpt':'Einspruch des Abg Kay Gottschalk (AfD) gegen die erste Ordnungsmaßnahme',
                'plenary_session':42,
                'plenary_pdf':'https://dserver.bundestag.de/btp/21/21042.pdf#P.4865',
                'decision_tenors':['Zurückweisung des Einspruchs'],
                'signal_fields':['beschlussfassung','abstract'],
            }],
        }],
    }


class GottschalkBoundedSourceScope(unittest.TestCase):
    def test_actual_expected_one_parent_two_measures_one_first_objection(self):
        report=inspect(source())
        self.assertEqual(report['official_title_filtered_dip_parent_count'],36)
        self.assertEqual(report['named_gottschalk_parents_within_scope'],1)
        self.assertEqual(report['original_two_separate_issuances_confirmed'],2)
        self.assertEqual(report['first_appeal_rejection_position_id'],'681803')
        self.assertEqual(report['second_individually_decided_appeal_in_this_scoped_source_count'],0)
        self.assertTrue(report['other_procedures_outside_title_date_filter_unchecked'])
        self.assertTrue(report['absence_of_appeal_anywhere_not_established'])
        self.assertTrue(report['effectiveness_of_second_call_not_established'])
        self.assertEqual(report['public_counter_delta'],0)
        self.assertIn('Kein Vollständigkeitsbeweis',markdown(report))

    def test_first_appeal_swapped_to_second_must_fail(self):
        p=source()
        p['gottschalk_named_source_parents'][0]['complete_parent_positions'][1]['abstract_excerpt']=(
            'Einspruch des Abg Kay Gottschalk (AfD) gegen die zweite Ordnungsmaßnahme')
        with self.assertRaisesRegex(ValueError,'erste und zweite|Erste und zweite'):
            inspect(p)

    def test_unknown_new_parent_triggers_manual_not_auto_count(self):
        p=source()
        new=copy.deepcopy(p['gottschalk_named_source_parents'][0])
        new['id']='339555'
        new['source']='https://dip.bundestag.de/vorgang/339555'
        new['complete_parent_positions']=[]
        new['official_position_count']=0
        p['gottschalk_named_source_parents'].append(new)
        p['named_gottschalk_parent_count']=2
        with self.assertRaisesRegex(ValueError,'Neues mögliches'):
            inspect(p)

    def test_new_second_appeal_candidate_is_not_silent_zero(self):
        p=source()
        p['second_appeal_explicitly_worded_candidates']=[{
            'id':'699999','step':'Abstimmung',
            'abstract_excerpt':'gegen die zweite Ordnungsmaßnahme'}]
        with self.assertRaisesRegex(ValueError,'Neues mögliches'):
            inspect(p)

    def test_missing_or_extra_parent_position_fails_closed(self):
        p=source()
        p['gottschalk_named_source_parents'][0]['complete_parent_positions'].pop()
        p['gottschalk_named_source_parents'][0]['official_position_count']=1
        with self.assertRaisesRegex(ValueError,'Position'):
            inspect(p)
        p=source()
        p['gottschalk_named_source_parents'][0]['complete_parent_positions'][1]['id']='681046'
        with self.assertRaisesRegex(ValueError,'doppelt'):
            inspect(p)

    def test_outside_scope_cannot_be_transformed_into_universal_absence(self):
        for field,value in (
                ('other_parliamentary_procedures_outside_this_title_date_filter_not_excluded',False),
                ('missing_second_vote_is_not_proof_of_final_effectiveness',False),
                ('public_counters_changed',True),
                ('search_start','2026-01-01'),
                ('official_dip_api_pages_checked',0),
        ):
            p=source()
            p[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                inspect(p)

    def test_source_file_outputs_only_after_validation(self):
        with tempfile.TemporaryDirectory() as td:
            directory=Path(td)
            original=directory/'original.json'
            original.write_text(json.dumps(source()),encoding='utf-8')
            report=run(original,directory/'report.json',directory/'report.md')
            self.assertEqual(report['public_counter_delta'],0)
            self.assertEqual(json.loads((directory/'report.json').read_text())
                             ['official_parent_id'],'328225')
            original.write_text(json.dumps({**source(),'public_counters_changed':True}),
                                encoding='utf-8')
            with self.assertRaises(ValueError):
                run(original,directory/'should_not_exist.json',
                    directory/'should_not_exist.md')
            self.assertFalse((directory/'should_not_exist.json').exists())

    def test_report_cannot_launder_second_legally_effective_sanction(self):
        r=inspect(source())
        with self.assertRaises(ValueError):
            markdown({**r,'effectiveness_of_second_call_not_established':False})
        with self.assertRaises(ValueError):
            markdown({**r,'public_counter_delta':1})


if __name__=='__main__':
    unittest.main()
