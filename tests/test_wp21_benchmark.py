"""Source-grounded regression suite for actual 20/214 transcript fragments.

Not a representative precision estimate and not an WP21 approval gate.
"""
import copy
import unittest
from wp21_benchmark import load_fixture, calculate, build_small_xml


class OfficialExcerptBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = load_fixture()

    def test_verified_ledger_backs_all_nine_positive_people(self):
        results = calculate(self.meta)
        self.assertEqual(results['verified_person_sanctions_in_excerpts'],9)
        self.assertEqual(results['number_of_distinct_verified_events'],2)

    def test_original_phrases_have_no_regression(self):
        result = calculate(self.meta)
        self.assertEqual(result['number_of_source_excerpts'],4)
        self.assertEqual(result['text_positive_true'],3)
        self.assertEqual(result['text_negative_true'],1)
        self.assertEqual(result['text_positive_false'],0)
        self.assertEqual(result['text_positive_missed'],0)
        self.assertEqual(result['recipients_matched'],9)
        self.assertEqual(result['recipients_false'],0)
        self.assertEqual(result['recipients_missed'],0)
        self.assertTrue(result['regression_passed'])

    def test_group_notice_is_not_second_group_grant(self):
        item1,item2,item3,item4=self.meta['cases']
        self.assertEqual(item2['evidence'],item4['evidence'])
        self.assertEqual(item2['expected_people'],[])
        self.assertEqual(len(item4['expected_people']),8)
        self.assertFalse(item3['actionable'])
        root,lines=build_small_xml(self.meta)
        self.assertEqual(len(lines),4)

    def test_sample_can_be_mutated_to_detect_missed_identity(self):
        fixture=copy.deepcopy(self.meta)
        fixture['people_index']=[item for item in fixture['people_index']
                                 if item['name']!='Stephan Brandner']
        result=calculate(fixture)
        self.assertFalse(result['regression_passed'])
        self.assertGreater(result['recipients_missed'],0)

    def test_no_automatic_sanction_approval(self):
        self.assertEqual(calculate(self.meta)['automatically_verified_sanctions'],0)
        self.assertIn('keine Schätzung',calculate(self.meta)['limitations'])

if __name__=='__main__':
    unittest.main()
