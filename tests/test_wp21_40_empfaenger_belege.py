"""Regressions: source speaker continuity is not a legal sanction decision."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from tests.test_wp21_janich_erste_quellenkritik import examples
from wp21_janich_erste_quellenkritik import inspect_rows
from wp21_40_empfaenger_belege import review, markdown


def original():
    # Exact genuine official spoken wording for the 3 hard-pinned
    # issuance paragraphs. Other nodes are stenographic source markers.
    text={
        8989:'Vizepräsidentin Andrea Lindholz:',
        8990:'Herr Kollege Gottschalk, ich erteile Ihnen jetzt einen Ordnungsruf für die Verwendung des Wortes „pfui“.',
        8991:'(Lachen bei der AfD)',
        8992:'Denn das ist unparlamentarisches Verhalten. Und ich erteile Ihnen einen zweiten Ordnungsruf dafür, dass Sie vorhin eine Gleichsetzung mit dem Nationalsozialismus vorgenommen haben.',
        8994:'KayGottschalkAfDKay Gottschalk (AfD):',
        9002:'(Reinhard Mixl [AfD]: Pfui!)',
        9004:'Vizepräsidentin Andrea Lindholz:',
        9005:'Herr Kollege Gottschalk, würden Sie bitte Ihre Rede unterbrechen. Ich habe das Wort „pfui“ gerade auch aus den Reihen der AfD gehört. Ich weiß nicht, wer es war; aber ich erteile auch dafür einen Ordnungsruf.',
        9006:'(Reinhard Mixl [AfD]: Ich war’s!)',
        9007:'KayGottschalkAfDKay Gottschalk (AfD):',
    }
    comments={8991,9002,9006}
    names={8989,9004}
    return [{
        'xml_line':line,'tag':('kommentar' if line in comments
                              else 'name' if line in names else 'p'),
        'class':('redner' if line in (8994,9007) else None),
        'speech_id':'ID214014100',
        'redner_id':'11004731' if line in (8994,9007) else None,
        'text':value,
    } for line,value in sorted(text.items())]


class OriginalRecipientMarkers(unittest.TestCase):
    def evidence(self):
        return inspect_rows(examples())

    def test_explicit_gottschalk_and_immediate_second_source_continuity(self):
        r=review(original(),self.evidence())
        g=r['gottschalk_immediate_second_issuance']
        self.assertEqual(g['context_supported_recipient'],'Kay Gottschalk')
        self.assertEqual(g['initial_explicit_recipient']['xml_line'],8990)
        self.assertEqual(g['same_chair_second_issuance']['xml_line'],8992)
        self.assertEqual(g['immediate_recipient_reply']['xml_line'],8994)
        self.assertTrue(g['speech_continuity_and_reply_verified'])
        self.assertFalse(g['second_sentence_names_recipient_explicitly'])
        self.assertFalse(g['appeal_or_legal_effect_confirmed'])
        self.assertEqual(r['public_counter_delta'],0)

    def test_named_mixl_interjection_and_post_grant_self_admission(self):
        r=review(original(),self.evidence())
        m=r['mixl_anonymous_interjection_and_admission']
        self.assertEqual(m['context_supported_speaker'],'Reinhard Mixl')
        self.assertEqual(m['original_interjection_name_and_word']['xml_line'],9002)
        self.assertEqual(m['chair_warning_did_not_identify_person']['xml_line'],9005)
        self.assertEqual(m['immediate_self_admission']['xml_line'],9006)
        self.assertTrue(m['speaker_attribution_from_official_comments'])
        self.assertFalse(m['formal_recipient_named_at_issuance'])
        self.assertFalse(m['separate_appeal_or_legal_effect_confirmed'])
        self.assertTrue(r['no_attribution_of_9005_to_gottschalk_or_janich'])

    def test_three_sanction_wordings_sha_originals_are_stable(self):
        r=review(original(),self.evidence())
        for obj in (r['gottschalk_immediate_second_issuance']['initial_explicit_recipient'],
                    r['gottschalk_immediate_second_issuance']['same_chair_second_issuance'],
                    r['mixl_anonymous_interjection_and_admission']['chair_warning_did_not_identify_person']):
            self.assertRegex(obj['source_sha256'],r'^[0-9a-f]{64}$')
            self.assertEqual(obj['source_speech_id'],'ID214014100')
            self.assertTrue(obj['original_source'].endswith('/21040.xml'))

    def test_missing_comment_or_self_admission_fails_closed(self):
        for missing in (9002,9006):
            with self.subTest(missing=missing),self.assertRaisesRegex(
                    ValueError,'fehlt'):
                review([r for r in original() if r['xml_line']!=missing],
                       self.evidence())

    def test_wrong_comment_identity_and_unknown_chair_fail(self):
        for line,replacement in (
                (9002,'(Kay Gottschalk [AfD]: Pfui!)'),
                (9006,'(Martin Sichert [AfD]: Ich war’s!)'),
                (9005,'Ich weiß genau, wer es war; ich erteile einen Ordnungsruf.'),
                (9004,'Präsidentin einer anderen Sitzung:')):
            with self.subTest(line=line),self.assertRaises(ValueError):
                fake=original()
                next(r for r in fake if r['xml_line']==line)['text']=replacement
                review(fake,self.evidence())

    def test_speaker_switch_before_second_would_prevent_attribution(self):
        fake=original()
        fake.insert(3,{
            'xml_line':8991,'tag':'name','text':'Ein anderer Redner:',
            'class':None,'speech_id':'ID214014100','redner_id':None,
        })
        with self.assertRaisesRegex(ValueError,'Sprecherwechsel'):
            review(fake,self.evidence())

    def test_owning_rede_id_and_gottschalk_reply_must_be_consistent(self):
        for line in (8990,8992,8994,9002,9005,9006):
            with self.subTest(line=line),self.assertRaisesRegex(ValueError,'Rede-'):
                fake=original()
                next(x for x in fake if x['xml_line']==line)['speech_id']='other'
                review(fake,self.evidence())
        fake=original()
        next(x for x in fake if x['xml_line']==8994)['redner_id']='0000'
        with self.assertRaisesRegex(ValueError,'Gottschalk'):
            review(fake,self.evidence())

    def test_issuance_sentence_still_cannot_name_new_legal_recipient(self):
        r=review(original(),self.evidence())
        self.assertTrue(r['all_attributions_require_manual_legal_review'])
        self.assertTrue(r['janich_first_unconditional_issuance_not_found_here'])
        self.assertEqual(r['automatically_confirmed_effective_sanctions'],0)
        self.assertIn('Keine neue automatisch',markdown(r))

    def test_all_legal_overrides_forbidden(self):
        r=review(original(),self.evidence())
        for change in (
                {'public_counter_delta':1},
                {'automatically_confirmed_effective_sanctions':1},
                {'no_attribution_of_9005_to_gottschalk_or_janich':False},
                {'all_attributions_require_manual_legal_review':False},
                {'janich_first_unconditional_issuance_not_found_here':False},
        ):
            with self.subTest(change=change),self.assertRaises(ValueError):
                markdown({**r,**change})
        t=copy.deepcopy(r)
        t['mixl_anonymous_interjection_and_admission'][
            'separate_appeal_or_legal_effect_confirmed']=True
        with self.assertRaises(ValueError):
            markdown(t)

    def test_source_evidence_not_weakened(self):
        other=self.evidence()
        other['documented_separately_rejected_objections']=1
        with self.assertRaisesRegex(ValueError,'Ungeprüfte'):
            review(original(),other)

    def test_unexpected_extra_source_duplicate_prevented(self):
        fake=original()
        fake.append(copy.deepcopy(fake[-1]))
        with self.assertRaises(ValueError):
            review(fake,self.evidence())


if __name__=='__main__':
    unittest.main()
