"""Original-XML Janich/Sichert/Gottschalk grant and appeals evidence: no auto count."""
import copy
import unittest

from parser import normal
from wp21_mehrfach_40 import inspect
from tests.test_wp21_mehrfach_40 import (
    build,CHAIR,S_FIRST,S_WARNING,S_SECOND,G_FIRST,G_SECOND,
    JANICH_INTERJECTION,
)


def original_evidence_fixture():
    root,_=build([
        ('11004892','Martin','Sichert',[
            (None,'Eine parlamentarische Debatte wird fortgesetzt.'),
            (CHAIR,S_FIRST),(CHAIR,S_WARNING),
            ('comment',JANICH_INTERJECTION),(CHAIR,S_SECOND)
        ]),
        ('11004731','Kay','Gottschalk',[
            (None,'Meine Damen und Herren, die Banken.'),
            (CHAIR,G_FIRST),(CHAIR,G_SECOND)
        ]),
    ])
    lines={}
    for node in root.iter():
        text=normal(''.join(node.itertext()))
        if node.tag=='p':
            for target in (S_FIRST,S_WARNING,S_SECOND,G_FIRST,G_SECOND):
                if text==target:
                    lines[target]=int(node.sourceline)
        if node.tag=='kommentar' and 'Steffen Janich [AfD]:' in text:
            lines[JANICH_INTERJECTION]=int(node.sourceline)
    if len(lines)!=6:
        raise ValueError('Test fixture missing source lines')
    expected={
        lines[S_FIRST]:('Martin Sichert','mit dem Finger auf Kollegen gezeigt',False),
        lines[S_SECOND]:('Steffen Janich','für den Widerspruch gerade',True),
        lines[G_FIRST]:('Kay Gottschalk','für die Verwendung des Wortes',False),
        lines[G_SECOND]:('Kay Gottschalk','Gleichsetzung mit dem Nationalsozialismus',True),
    }
    return root,expected,lines[S_WARNING],lines[JANICH_INTERJECTION]


class OfficialTwentyFirstTermAppealAndSourceTests(unittest.TestCase):
    def test_three_people_four_located_grants_four_separate_appeal_decisions(self):
        root,ref,warning,comment=original_evidence_fixture()
        data=inspect(root,ref,warning,comment)
        self.assertEqual(data['source_grant_passages_located'],4)
        self.assertEqual(data['different_recipient_review_hints'],3)
        self.assertEqual(data['automatically_confirmed_effective_sanctions'],0)
        self.assertEqual(data['automatically_rescinded_sanctions'],0)
        self.assertEqual(data['conditional_warning_not_granted'],warning)
        self.assertEqual(data['janich_named_interjection_xml_line'],comment)
        self.assertEqual([e['recipient_review_hint'] for e in data['source_passages']],
                         ['Martin Sichert','Steffen Janich',
                          'Kay Gottschalk','Kay Gottschalk'])
        self.assertEqual(len({e['xml_line'] for e in data['source_passages']}),4)
        self.assertEqual(data['official_appeals']['appeals_rejected'],4)
        appeals=data['official_appeals']['individual_appeals']
        self.assertEqual([r['person'] for r in appeals].count('Steffen Janich'),2)
        self.assertIsNone(appeals[1]['linked_original_xml_line'])
        self.assertEqual(appeals[2]['linked_original_xml_line'],8719)
        self.assertEqual(appeals[3]['linked_original_xml_line'],8990)
        self.assertNotIn(8992,[r['linked_original_xml_line'] for r in appeals])

    def test_janich_comment_missing_fails_closed(self):
        root,ref,warning,comment=original_evidence_fixture()
        with self.assertRaisesRegex(ValueError,'Benannter Janich'):
            inspect(root,ref,warning,comment+1000)

    def test_nearby_mp_speech_does_not_replace_named_interjection(self):
        root,ref,warning,comment=original_evidence_fixture()
        for node in root.iter('kommentar'):
            if 'Steffen Janich' in normal(''.join(node.itertext())):
                node.text='(Beifall bei den Abgeordneten der AfD)'
        with self.assertRaisesRegex(ValueError,'Benannter Janich'):
            inspect(root,ref,warning,comment)

    def test_unissued_conditional_laughter_warning_is_not_a_grant(self):
        root,ref,warning,comment=original_evidence_fixture()
        with self.assertRaisesRegex(ValueError,'Warnung fürs Lachen'):
            inspect(root,ref,warning+123,comment)

    def test_original_source_wording_drift_fails_closed(self):
        root,ref,warning,comment=original_evidence_fixture()
        invalid=copy.deepcopy(ref)
        janich_line=next(line for line,(who,_,_) in invalid.items()
                         if who=='Steffen Janich')
        invalid[janich_line]=('Steffen Janich','ein anderer Vorwurf',True)
        with self.assertRaisesRegex(ValueError,'Prüfwortlaut'):
            inspect(root,invalid,warning,comment)

    def test_second_grant_cannot_be_relabelled_first(self):
        root,ref,warning,comment=original_evidence_fixture()
        invalid=copy.deepcopy(ref)
        janich_line=next(line for line,(who,_,_) in invalid.items()
                         if who=='Steffen Janich')
        invalid[janich_line]=('Steffen Janich','für den Widerspruch gerade',False)
        with self.assertRaisesRegex(ValueError,'Prüfwortlaut'):
            inspect(root,invalid,warning,comment)

    def test_misassign_janich_to_sichert_is_rejected(self):
        root,ref,warning,comment=original_evidence_fixture()
        invalid=copy.deepcopy(ref)
        janich_line=next(line for line,(who,_,_) in invalid.items()
                         if who=='Steffen Janich')
        invalid[janich_line]=('Martin Sichert','für den Widerspruch gerade',True)
        with self.assertRaisesRegex(ValueError,'Original|Personen|Vier'):
            inspect(root,invalid,warning,comment)

    def test_misassign_gottschalk_second_to_someone_else_rejected(self):
        root,ref,warning,comment=original_evidence_fixture()
        invalid=copy.deepcopy(ref)
        got_second=next(line for line,(who,_,second) in invalid.items()
                        if who=='Kay Gottschalk' and second)
        invalid[got_second]=('Steffen Janich',
                             'Gleichsetzung mit dem Nationalsozialismus',True)
        with self.assertRaisesRegex(ValueError,'Personen|Sprecher|Vier'):
            inspect(root,invalid,warning,comment)

    def test_missing_original_line_not_accepted(self):
        root,ref,warning,comment=original_evidence_fixture()
        invalid=copy.deepcopy(ref)
        old=next(line for line,(who,_,_) in invalid.items() if who=='Martin Sichert')
        invalid[old+300]=invalid.pop(old)
        with self.assertRaisesRegex(ValueError,'Erteilungsstelle'):
            inspect(root,invalid,warning,comment)

    def test_wrong_election_period_not_accepted(self):
        root,ref,warning,comment=original_evidence_fixture()
        root.set('wahlperiode','20')
        with self.assertRaisesRegex(ValueError,'Fremdes'):
            inspect(root,ref,warning,comment)


if __name__=='__main__':
    unittest.main()
