"""Synthetic source-line regression for two distinct grant and appeal episodes."""
import unittest
from lxml import etree
from wp21_40_mehrfach_akte import (
    PHRASES_40,PHRASES_42,inspect,render_markdown)


def fixture(number,rewrites=None):
    orig=[
        'Ich erteile Ihnen jetzt einen Ordnungsruf, weil Sie mit dem Finger auf Kollegen gezeigt haben; das ist unparlamentarisch.',
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
    date='13.11.2025' if number==40 else '25.11.2025'
    src=(
        f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{number}" sitzung-datum="{date}">'
        '<sitzungsverlauf><tagesordnungspunkt><name>Vizepräsidentin Andrea Lindholz</name>'
        +''.join('<p>'+t+'</p>' for t in body)+
        '</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
    return etree.fromstring(src.encode())


class CaseFortySourceCrossChecks(unittest.TestCase):
    def test_four_issuance_and_four_appeal_text_anchors_are_not_counts(self):
        r=inspect({40:fixture(40),42:fixture(42)})
        self.assertEqual(r['distinct_original_issued_measures_from_independent_sources'],5)
        self.assertEqual(r['distinct_rejected_appeals_in_42'],4)
        self.assertEqual(r['four_separate_vote_rejection_wordings_checked'],4)
        self.assertEqual(len(r['source_issuance_paragraphs']),4)
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
        bad=fixture(40,{3:'Keine weitere Äußerung der Sitzungsleitung.'})
        with self.assertRaisesRegex(ValueError,'Gottschalk_second'):
            inspect({40:bad,42:fixture(42)})

    def test_conditional_only_or_ambiguous_source_cannot_replace_actual(self):
        bad=fixture(40,{1:'Wenn Sie widersprechen, erteile ich einen Ordnungsruf.'})
        with self.assertRaisesRegex(ValueError,'Janich_second'):
            inspect({40:bad,42:fixture(42)})

    def test_not_four_rejections_fails(self):
        bad=fixture(42,{3:'Wer stimmt für den Einspruch des Abgeordneten Kay Gottschalk? Der Antrag wird vertagt.'})
        with self.assertRaisesRegex(ValueError,'Vier getrennte'):
            inspect({40:fixture(40),42:bad})

    def test_same_paragraph_duplicate_fails_closed(self):
        bad=fixture(42)
        bad.find('.//tagesordnungspunkt').append(
            etree.Element('p'))
        bad.findall('.//p')[-1].text='Wer stimmt für den Einspruch des Abgeordneten Martin Sichert?'
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
