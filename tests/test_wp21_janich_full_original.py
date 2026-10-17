"""Complete 21/040 Janich source scrutiny: no inferred first issuance."""
import copy
import unittest

from tests.test_wp21_janich_erste_quellenkritik import examples
from wp21_janich_erste_quellenkritik import inspect_rows
from wp21_janich_full_original import inspect_all_rows, markdown


def sample():
    anchors = dict(examples()[40])
    anchors[8627] = (
        'Steffen Janich wurde im Parlament angesprochen; '
        'der Ordnungsruf ist eine Worterwähnung, keine neue Erteilung.')
    anchors[8607] = (
        'Frau Kollegin, ich erteile Ihnen jetzt einen Ordnungsruf. '
        'Wir setzen die Debatte danach fort.')
    anchors[8650] = (
        'Ein Ordnungsruf wurde heute erwähnt, '
        'nicht als zusätzliche Maßnahme beschlossen.')
    return [(n, anchors.get(n, 'Weitere Plenardebatte ohne Ordnungsruf.'))
            for n in range(8580, 8771)]


class FullOriginal(unittest.TestCase):
    def test_complete_sitting_has_separate_hard_anchors(self):
        result = inspect_all_rows(sample(), inspect_rows(examples()))
        self.assertEqual(result['known_other_person_sichert_line'], 8715)
        self.assertEqual(result['known_janich_conditional_warning_line'], 8717)
        self.assertEqual(result['known_janich_explicit_second_grant_line'], 8719)
        self.assertIsNone(result['original_janich_first_issuance_literal_line'])
        self.assertEqual(result['independently_rejected_first_and_second_appeals_in_21_042'], 2)
        self.assertEqual(result['verified_spoken_paragraphs_in_original'], 191)
        self.assertEqual(result['public_counter_delta'], 0)
        self.assertIn('kein automatischer Empfängerbeleg', markdown(result))

    def test_unattributed_other_person_grant_does_not_map_to_janich(self):
        result = inspect_all_rows(sample(), inspect_rows(examples()))
        hits = result['unattributed_explicit_issuance_wordings_for_manual_review']
        self.assertEqual([x['xml_line'] for x in hits], [8607])
        self.assertTrue(all(x['automatic_janich_first_grant_attribution'] is False
                            for x in hits))
        self.assertEqual(result['original_janich_first_issuance_literal_line'], None)
        self.assertEqual(result['automatic_effective_ordinal_count'], 0)

    def test_historical_name_without_issuing_verb_not_a_first_grant(self):
        result = inspect_all_rows(sample(), inspect_rows(examples()))
        a = next(x for x in result['unattributed_janich_named_wordings_for_manual_review']
                 if x['xml_line'] == 8627)
        self.assertFalse(a['literal_issuance_verb_detected'])
        self.assertTrue(a['requires_independent_recipient_and_speaker_review'])

    def test_8717_and_8719_not_manually_reassigned(self):
        r = inspect_all_rows(sample(),inspect_rows(examples()))
        unknown = {x['xml_line'] for x in r['unattributed_contexts_for_manual_review']}
        self.assertFalse({8715,8717,8719} & unknown)
        all_rows = {x['xml_line']:x for x in r['source_text_locations']}
        self.assertTrue(all_rows[8717]['conditional_wording_detected'])
        self.assertEqual(all_rows[8715]['source_class'],
                         'known_other_person_sichert_issuance')
        self.assertEqual(all_rows[8719]['source_class'],
                         'known_janich_explicit_second_issuance')

    def test_missing_early_part_of_sitting_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unvollständige'):
            inspect_all_rows(sample()[:85], inspect_rows(examples()))

    def test_duplicate_or_unsorted_full_original_fails(self):
        rows=sample()
        with self.assertRaisesRegex(ValueError,'doppelt'):
            inspect_all_rows(rows[:91]+rows[90:],inspect_rows(examples()))
        with self.assertRaisesRegex(ValueError,'unsortiert'):
            inspect_all_rows(list(reversed(rows)),inspect_rows(examples()))

    def test_mutated_first_source_or_missing_second_fails_closed(self):
        rows = sample()
        mutated=[(line,('Herr Kollege, kein Ordnungsruf.' if line==8715 else text))
                 for line,text in rows]
        with self.assertRaisesRegex(ValueError, 'Originalzeile'):
            inspect_all_rows(mutated,inspect_rows(examples()))
        with self.assertRaisesRegex(ValueError, 'Originalzeile'):
            inspect_all_rows([x for x in rows if x[0]!=8719],
                             inspect_rows(examples()))

    def test_fake_external_evidence_cannot_establish_first_original(self):
        ev=inspect_rows(examples())
        ev['first_independent_unconditional_issuance_xml_line']=8607
        with self.assertRaisesRegex(ValueError,'Unvollständige'):
            inspect_all_rows(sample(),ev)

    def test_report_cannot_enable_counting_or_legal_attribution(self):
        report=inspect_all_rows(sample(),inspect_rows(examples()))
        for change in ({'original_janich_first_issuance_literal_line':8607},
                       {'automatic_effective_ordinal_count':1},
                       {'public_counter_delta':1},
                       {'no_person_attribution_by_keyword_proximity':False},
                       {'explicit_other_sources_not_attributed_to_janich':False},
                       {'source_scope_is_all_spoken_paragraphs_not_appendices':False}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                markdown({**report,**change})


if __name__=='__main__':
    unittest.main()
