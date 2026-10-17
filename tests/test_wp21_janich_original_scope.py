"""Source-bounded manual examination of Janich's elusive first issuance."""
import copy
import unittest

from tests.test_wp21_janich_erste_quellenkritik import examples
from wp21_janich_erste_quellenkritik import inspect_rows
from wp21_janich_original_scope import review, markdown


def fixture():
    source = examples()[40]
    p = {line:text for line,text in source}
    p[8713] = 'Abgeordneter Steffen Janich reagiert auf die Aussprache.'
    p[8714] = 'Ich behalte mir vor, Ihnen einen Ordnungsruf zu erteilen.'
    p[8716] = 'Steffen Janich spricht vom Ordnungsruf; keine neue Erteilung.'
    # A previously documented unambiguous grant to Sichert must NEVER
    # become Janich's independent first issuance.
    return [(s,p.get(s,f'Fortsetzung der parlamentarischen Beratung {s}.'))
            for s in range(8650,8737)]


class JanichOriginalScope(unittest.TestCase):
    def test_neighbourhood_preserves_both_known_original_anchors(self):
        r = review(fixture(),inspect_rows(examples()))
        self.assertEqual(r['known_conditional_warning_xml_line'],8717)
        self.assertEqual(r['known_second_grant_xml_line'],8719)
        self.assertIsNone(r['first_original_unconditional_issuance_xml_line'])
        self.assertTrue(r['first_measure_documented_only_in_later_decision'])
        self.assertTrue(r['separate_first_and_second_appeals_rejected'])
        self.assertEqual(r['public_counter_delta'],0)
        self.assertIn('unbedingte Erteilung',markdown(r))

    def test_other_people_and_conditional_words_remain_unattributed(self):
        r = review(fixture(),inspect_rows(examples()))
        manual = r['potential_manual_review_paragraphs']
        self.assertTrue(any(x['xml_line']==8715 for x in manual))
        self.assertTrue(any(x['xml_line']==8714 for x in manual))
        self.assertFalse(any(x['xml_line'] in (8717,8719) for x in manual))
        self.assertTrue(all(x['automatic_first_issuance_attribution'] is False
                            for x in r['source_paragraphs']))
        self.assertTrue(all(x['requires_manual_recipient_check']
                            for x in manual))

    def test_duplicate_anchor_or_missing_second_fails(self):
        p=fixture()
        p.append((8717,p[67][1]))
        with self.assertRaisesRegex(ValueError,'nicht eindeutig'):
            review(p,inspect_rows(examples()))
        p=[x for x in fixture() if x[0]!=8719]
        with self.assertRaisesRegex(ValueError,'fehlt'):
            review(p,inspect_rows(examples()))

    def test_tampered_conditional_text_or_line_sha_fails(self):
        p=fixture()
        p=[(line,('Ich erteile Ihnen jetzt den ersten Ordnungsruf!'
                  if line==8717 else t)) for line,t in p]
        with self.assertRaisesRegex(ValueError,'stimmt nicht'):
            review(p,inspect_rows(examples()))

    def test_foreign_or_weakened_prior_decision_is_rejected(self):
        ev=inspect_rows(examples())
        ev['documented_separately_rejected_objections']=1
        with self.assertRaisesRegex(ValueError,'Unverifizierte'):
            review(fixture(),ev)
        ev=inspect_rows(examples())
        ev['first_independent_unconditional_issuance_xml_line']=8717
        with self.assertRaisesRegex(ValueError,'Unverifizierte'):
            review(fixture(),ev)

    def test_cannot_expand_scope_without_explicit_tested_bounds(self):
        with self.assertRaisesRegex(ValueError,'Unerlaubte'):
            review(fixture(),inspect_rows(examples()),before=10000)

    def test_report_cannot_infer_legal_status(self):
        r=review(fixture(),inspect_rows(examples()))
        for changes in (
            {'first_original_unconditional_issuance_xml_line':8717},
            {'first_measure_documented_only_in_later_decision':False},
            {'speaker_recipient_not_automatically_inferred':False},
            {'automatic_legal_measure_count':1},
            {'public_counter_delta':1}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                markdown({**r,**changes})


if __name__=='__main__':
    unittest.main()
