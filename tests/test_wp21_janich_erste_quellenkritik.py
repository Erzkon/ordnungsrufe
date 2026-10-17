"""Explicit §39 2025 negative issuance source versus actual second grant."""
import unittest
from wp21_janich_erste_quellenkritik import LINES,inspect_rows,markdown


def examples():
    data={
        'sichert_first_grant':(
            'Herr Kollege, ich habe es gestern auch schon mal gesagt, und '
            'ich sage es Ihnen jetzt auch: Ich erteile Ihnen jetzt einen '
            'Ordnungsruf, weil Sie mit dem Finger auf Kollegen gezeigt haben; '
            'das ist unparlamentarisch.'),
        'janich_conditional_laughter_warning':(
            '– Und wenn Sie lachen – und ich weiß, wer gelacht hat –, '
            'erteile ich Ihnen gleich fürs Lachen den nächsten Ordnungsruf.'),
        'janich_explicit_second_issuance':(
            '– Ich erteile Ihnen auch für den Widerspruch gerade einen '
            'zweiten Ordnungsruf; das kann ich.'),
        'janich_first_objection_rejected':(
            'Wer stimmt für den Einspruch gegen den ersten Ordnungsruf '
            'gegen den Abgeordneten Steffen Janich? – Die AfD-Fraktion. '
            'Der Einspruch ist damit zurückgewiesen.'),
        'janich_second_objection_rejected':(
            'Wer stimmt für den Einspruch gegen den zweiten Ordnungsruf '
            'gegen den Abgeordneten Steffen Janich? – Die AfD-Fraktion. '
            'Der Einspruch ist damit zurückgewiesen.'),
    }
    return {
        session:[(line,data[name])
                 for name,(s,line,pattern) in LINES.items()
                 if s==session]
        for session in (40,42)
    }


class FirstJanichConditionalNotGrant(unittest.TestCase):
    def test_full_five_original_wordings_not_reinterpret_first_issuance(self):
        r=inspect_rows(examples())
        self.assertIsNone(r['first_independent_unconditional_issuance_xml_line'])
        self.assertTrue(r['conditional_notice_is_not_unconditional_issuance_proof'])
        self.assertTrue(r['do_not_map_conditional_warning_to_first_issuance'])
        self.assertEqual(r['documented_distinct_original_measures'],2)
        self.assertEqual(r['documented_separately_rejected_objections'],2)
        self.assertEqual(r['explicit_second_xml_line'],8719)
        self.assertEqual(r['public_counter_delta'],0)
        self.assertIn('bedingte Formulierung',markdown(r))
        self.assertIn('Widerspruch',markdown(r))

    def test_original_conditional_warning_must_be_present_and_ordered(self):
        p=examples()
        p[40]=[(line,text) for line,text in p[40] if line!=8717]
        with self.assertRaisesRegex(ValueError,'janich_conditional'):
            inspect_rows(p)
        p=examples()
        p[40]=[(8716 if line==8717 else line,text) for line,text in p[40]]
        with self.assertRaisesRegex(ValueError,'janich_conditional'):
            inspect_rows(p)

    def test_future_warning_cannot_become_unconditional_first_issuance(self):
        p=examples()
        p[40]=[(line,('Ich erteile Ihnen jetzt einen ersten Ordnungsruf '
                      'für das Lachen.' if line==8717 else text))
               for line,text in p[40]]
        with self.assertRaisesRegex(ValueError,'janich_conditional'):
            inspect_rows(p)

    def test_second_issuance_needs_exact_verb_and_explicit_second_number(self):
        p=examples()
        p[40]=[(line,('Ich werde Ihnen für den Widerspruch gleich einen '
                      'zweiten Ordnungsruf erteilen.'
                      if line==8719 else text)) for line,text in p[40]]
        with self.assertRaisesRegex(ValueError,'janich_explicit_second'):
            inspect_rows(p)

    def test_both_vote_records_must_be_separate_by_ordinal_and_line(self):
        p=examples()
        p[42]=[(line,('Wer stimmt für den Einspruch gegen den zweiten '
                      'Ordnungsruf gegen den Abgeordneten Steffen Janich? '
                      'Der Einspruch ist damit zurückgewiesen.'
                      if line==1513 else text)) for line,text in p[42]]
        with self.assertRaisesRegex(ValueError,'janich_first_objection'):
            inspect_rows(p)
        p=examples()
        p[42]=[(1513 if line==1517 else line,text) for line,text in p[42]]
        with self.assertRaises(ValueError):
            inspect_rows(p)

    def test_duplicate_first_warning_causes_failure_not_an_extra_sanction(self):
        p=examples()
        original=next(text for line,text in p[40] if line==8717)
        p[40].append((8723,original))
        with self.assertRaisesRegex(ValueError,'janich_conditional'):
            inspect_rows(p)

    def test_rendering_cannot_confirm_measures_from_text(self):
        r=inspect_rows(examples())
        with self.assertRaises(ValueError):
            markdown({**r,'public_counter_delta':2})
        with self.assertRaises(ValueError):
            markdown({**r,'first_independent_unconditional_issuance_xml_line':8717})


if __name__=='__main__':
    unittest.main()
