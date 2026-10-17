"""Synthetic source-line regression for two distinct grant and appeal episodes."""
import unittest
from lxml import etree
from wp21_40_mehrfach_akte import (
    PHRASES_40,PHRASES_42,inspect,render_markdown)


def fixture(number,rewrites=None,duplicate=None):
    orig=[
        'Ich erteile Ihnen jetzt einen Ordnungsruf, weil Sie mit dem Finger auf Kollegen gezeigt haben; das ist unparlamentarisch.',
        'Und wenn Sie lachen – und ich weiß, wer gelacht hat –, erteile ich Ihnen gleich fürs Lachen den nächsten Ordnungsruf.',
        'Ich erteile Ihnen auch für den Widerspruch gerade einen zweiten Ordnungsruf; das kann ich.',
        'Herr Kollege Gottschalk, ich erteile Ihnen jetzt einen Ordnungsruf für die Verwendung des Wortes pfui.',
        'Und ich erteile Ihnen einen zweiten Ordnungsruf dafür, dass Sie vorhin eine Gleichsetzung mit dem Nationalsozialismus vorgenommen haben.',
    ]
    later=[
        'Wer stimmt für den Einspruch des Abgeordneten Martin Sichert? Der Einspruch ist damit zurückgewiesen.',
        'Wer stimmt für den Einspruch gegen den ersten Ordnungsruf gegen den Abgeordneten Steffen Janich? Der Einspruch ist damit zurückgewiesen.',
        'Wer stimmt für den Einspruch gegen den zweiten Ordnungsruf gegen den Abgeordneten Steffen Janich? Der Einspruch ist damit zurückgewiesen.',
        'Wer stimmt für den Einspruch des Abgeordneten Kay Gottschalk? Der Einspruch ist damit zurückgewiesen.',
    ]
    body=list(orig if number==40 else later)
    if rewrites:
        for idx,value in rewrites.items():
            body[idx]=value
    if duplicate:
        body.append(duplicate)
    date='13.11.2025' if number==40 else '25.11.2025'
    src=(
        f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{number}" sitzung-datum="{date}">'
        '<sitzungsverlauf><tagesordnungspunkt><name>Vizepräsidentin Andrea Lindholz</name>'
        +'\n'.join('<p>'+t+'</p>' for t in body)+
        '</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
    return etree.fromstring(src.encode())


class CaseFortySourceCrossChecks(unittest.TestCase):
    def test_four_issuance_and_four_appeal_text_anchors_are_not_counts(self):
        r=inspect({40:fixture(40),42:fixture(42)})
        self.assertEqual(r['distinct_original_issued_measures_from_independent_sources'],5)
        self.assertEqual(r['distinct_rejected_appeals_in_42'],4)
        self.assertEqual(r['four_separate_vote_rejection_wordings_checked'],4)
        self.assertEqual(len(r['source_issuance_paragraphs']),4)
        self.assertEqual(r['original_issuance_phrases_explicitly_located'],4)
        self.assertIsNone(r['janich_first_original_unconditional_issuance_xml_line'])
        self.assertFalse(r['janich_first_warning_is_issuance'])
        self.assertEqual(r['janich_first_measure_basis'],
                         'separate_official_objection_decision_21_042')
        self.assertEqual(len(r['source_non_issuance_context_paragraphs']),1)
        self.assertIn('Bedingte Warnung',render_markdown(r))
        self.assertEqual(len(r['source_appeal_paragraphs']),4)
        self.assertEqual(r['gottschalk_original_issued_measures'],2)
        self.assertEqual(r['gottschalk_appeals_decided_in_42'],1)
        self.assertEqual(r['automatically_confirmed_effective_sanctions'],0)
        self.assertIn('nicht',render_markdown(r).lower())

    def test_missing_first_or_second_janich_vote_fails(self):
        bad=fixture(42,{1:'Ein anderer Tagesordnungspunkt.'})
        with self.assertRaisesRegex(ValueError,'Janich_first'):
            inspect({40:fixture(40),42:bad})
        bad=fixture(42,{2:'Ein anderer Tagesordnungspunkt.'})
        with self.assertRaisesRegex(ValueError,'Janich_second'):
            inspect({40:fixture(40),42:bad})

    def test_gottschalk_two_grants_not_derived_from_one_vote(self):
        bad=fixture(40,{4:'Keine weitere Äußerung der Sitzungsleitung.'})
        with self.assertRaisesRegex(ValueError,'Gottschalk_second'):
            inspect({40:bad,42:fixture(42)})

    def test_conditional_only_or_ambiguous_source_cannot_replace_actual(self):
        bad=fixture(40,{2:'Wenn Sie widersprechen, erteile ich einen Ordnungsruf.'})
        with self.assertRaisesRegex(ValueError,'Janich_second'):
            inspect({40:bad,42:fixture(42)})

    def test_conditional_context_missing_or_promoted_cannot_pass(self):
        missing=fixture(40,{1:'Ich erteile Ihnen jetzt den ersten Ordnungsruf.'})
        with self.assertRaisesRegex(ValueError,'Janich_first_conditional_warning'):
            inspect({40:missing,42:fixture(42)})
        wrongly_ordered=fixture(40)
        # Source-line order matters; the future threat must precede the second call.
        children=wrongly_ordered.xpath('.//p')
        children[1].text,children[2].text=children[2].text,children[1].text
        with self.assertRaises(ValueError):
            inspect({40:wrongly_ordered,42:fixture(42)})

    def test_report_never_accepts_a_fabricated_first_literal_grant(self):
        r=inspect({40:fixture(40),42:fixture(42)})
        with self.assertRaises(ValueError):
            render_markdown({**r,
                'janich_first_original_unconditional_issuance_xml_line':2})
        with self.assertRaises(ValueError):
            render_markdown({**r,'janich_first_warning_is_issuance':True})

    def test_not_four_rejections_fails(self):
        bad=fixture(42,{3:'Wer stimmt für den Einspruch des Abgeordneten Kay Gottschalk? Der Antrag wird vertagt.'})
        with self.assertRaisesRegex(ValueError,'Vier getrennte'):
            inspect({40:fixture(40),42:bad})

    def test_same_paragraph_duplicate_fails_closed(self):
        bad=fixture(42,duplicate=(
            'Wer stimmt für den Einspruch des Abgeordneten Martin Sichert?'))
        with self.assertRaisesRegex(ValueError,'Sichert_objection_vote'):
            inspect({40:fixture(40),42:bad})

    def test_wrong_original_sitting_and_date_fails(self):
        wrong=fixture(40)
        wrong.set('sitzung-datum','14.11.2025')
        with self.assertRaisesRegex(ValueError,'Falsche amtliche'):
            inspect({40:wrong,42:fixture(42)})
        with self.assertRaises(ValueError):
            inspect({40:fixture(40)})


if __name__=='__main__':
    unittest.main()
