"""Four original grant paragraphs, two MPs; no effective sanction inference."""
import copy
import unittest

from parser import normal
from wp21_mehrfach_40 import inspect
from tests.test_wp21_mehrfach_40 import (
    build,CHAIR,OTHER,S_FIRST,S_WARNING,S_SECOND,G_FIRST,G_SECOND
)


def original_pairs():
    root,_=build([
        ('11004892','Martin','Sichert',[
            (None,'Sichern wir die Rechte von Menschen.'),
            (CHAIR,S_FIRST),(CHAIR,S_WARNING),(CHAIR,S_SECOND)]),
        ('11004731','Kay','Gottschalk',[
            (None,'Wir sprechen über politisches Verhalten.'),
            (CHAIR,G_FIRST),(CHAIR,G_SECOND)]),
    ])
    look={}
    for p in root.iter('p'):
        text=normal(''.join(p.itertext()))
        for marker in (S_FIRST,S_WARNING,S_SECOND,G_FIRST,G_SECOND):
            if text==marker:
                look[marker]=int(p.sourceline)
    if len(look)!=5:
        raise ValueError('Synthetic source lines are not unique')
    reference={
        'Martin Sichert':{
            'person_id':'11004892','first':look[S_FIRST],'second':look[S_SECOND],
            'first_phrase':'mit dem Finger auf Kollegen gezeigt',
            'second_phrase':'für den Widerspruch gerade',
        },
        'Kay Gottschalk':{
            'person_id':'11004731','first':look[G_FIRST],'second':look[G_SECOND],
            'first_phrase':'für die Verwendung des Wortes',
            'second_phrase':'Gleichsetzung mit dem Nationalsozialismus',
        },
    }
    return root,reference,look[S_WARNING]


class ExactMultipleOriginalSourceTests(unittest.TestCase):
    def test_keeps_two_separate_pairs_with_all_four_origin_lines(self):
        root,ref,warning=original_pairs()
        result=inspect(root,ref,warning)
        self.assertEqual(result['paired_speaker_references'],2)
        self.assertEqual(result['original_issuing_passages'],4)
        self.assertEqual(result['automatically_confirmed_effective_sanctions'],0)
        self.assertEqual(result['automatically_rescinded_sanctions'],0)
        self.assertEqual(result['conditional_warning_not_issued']['xml_line'],warning)
        self.assertEqual({p['recipient_review_hint'] for p in result['pairs']},
                         {'Martin Sichert','Kay Gottschalk'})
        for item in result['pairs']:
            self.assertTrue(item['separate_event_and_legal_effect_review_required'])
            self.assertNotEqual(item['first']['source']['line'],
                                item['second']['source']['line'])
            self.assertEqual(len(item['first']['sha256']),64)
            self.assertEqual(len(item['second']['sha256']),64)
            self.assertTrue(item['second']['method'].startswith(
                            ('zweites_ordnungsrufpaar_', 'zweiter_ordnungsruf_')))

    def test_conditional_warning_cannot_be_omitted(self):
        root,reference,warning=original_pairs()
        with self.assertRaisesRegex(ValueError,'Bedingte Lachandrohung'):
            inspect(root,reference,warning+100)

    def test_swapping_first_and_second_is_not_accepted(self):
        root,reference,warning=original_pairs()
        invalid=copy.deepcopy(reference)
        invalid['Martin Sichert']['first']=reference['Martin Sichert']['second']
        invalid['Martin Sichert']['second']=reference['Martin Sichert']['first']
        with self.assertRaisesRegex(ValueError,'Erst-/Zweiterteilung ungültig'):
            inspect(root,invalid,warning)

    def test_fake_ordinal_source_text_fails_closed(self):
        root,ref,warning=original_pairs()
        for p in root.iter('p'):
            if 'für den Widerspruch' in normal(''.join(p.itertext())):
                p.text='Ich erteile Ihnen einen Ordnungsruf, nicht einen zweiten.'
                break
        with self.assertRaisesRegex(ValueError,'Originaltext keine sichere'):
            inspect(root,ref,warning)

    def test_changed_xml_grant_text_rejected_even_with_existing_hint(self):
        root,reference,warning=original_pairs()
        invalid=copy.deepcopy(reference)
        invalid['Kay Gottschalk']['second_phrase']='völlig anderer Vorwurf'
        with self.assertRaisesRegex(ValueError,'Originaltext keine sichere'):
            inspect(root,invalid,warning)

    def test_mismatched_speaker_id_is_not_allowed(self):
        root,reference,warning=original_pairs()
        invalid=copy.deepcopy(reference)
        invalid['Kay Gottschalk']['person_id']='99999999'
        with self.assertRaisesRegex(ValueError,'XML-Sprecher nicht eindeutig'):
            inspect(root,invalid,warning)

    def test_no_pair_across_different_presiding_chairs(self):
        root,ref,warning=original_pairs()
        for node in root.iter('name'):
            if node.text==CHAIR and node.getparent().tag=='rede':
                node.text=OTHER
                break
        with self.assertRaisesRegex(ValueError,'XML-Sprecher nicht eindeutig'):
            inspect(root,ref,warning)

    def test_duplicate_or_missing_original_line_is_rejected(self):
        root,ref,warning=original_pairs()
        invalid=copy.deepcopy(ref)
        invalid['Kay Gottschalk']['second']=invalid['Kay Gottschalk']['first']
        with self.assertRaisesRegex(ValueError,'Erst-/Zweiterteilung ungültig'):
            inspect(root,invalid,warning)
        invalid=copy.deepcopy(ref)
        invalid['Kay Gottschalk']['second']=invalid['Kay Gottschalk']['first']+8
        with self.assertRaisesRegex(ValueError,'Originalfundstelle'):
            inspect(root,invalid,warning)

    def test_original_other_election_period_is_rejected(self):
        root,ref,warning=original_pairs()
        root.set('wahlperiode','20')
        with self.assertRaisesRegex(ValueError,'Fremdes'):
            inspect(root,ref,warning)


if __name__=='__main__':
    unittest.main()
