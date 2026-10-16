"""Regression of the four strictly located independent official XML clues."""
import unittest
from html import escape
from lxml import etree
from wp21_vier_quellenbelege import SOURCES, verify_original

COMMENTS={
    8:'(Die Rednerin hält eine Plastikkarte hoch)',
    23:'(Beifall bei der CDU/CSU und der SPD – Carolin Bachmann [AfD]: Hätte das nicht warten können bis zum Ende der Debatte?)',
    28:'(Beifall bei der AfD – René Bochmann [AfD], an die Abg. Nicole Gohlke [Die Linke] gewandt: Ich würde jetzt sitzen bleiben und schweigen! – Heiterkeit bei der AfD)',
    46:'(Beifall bei der CDU/CSU – Mirze Edis [Die Linke]: Warum nicht?)',
}


def fixture(session,*,comment=None,speaker=None,chair=None,grant=None,
            comment_line=None,grant_line=None,other_rede=False):
    line,cl,name,president,anchor,_=SOURCES[session]
    line=grant_line or line
    cl=comment_line or cl
    president=chair or president
    contents={}
    if session==8:
        first,last=(speaker or name).split(' ',1)
        contents[1400]=('<p klasse="redner"><redner id="99"><name><vorname>'+
                        escape(first)+'</vorname><nachname>'+escape(last)+
                        '</nachname></name></redner></p>')
        contents[1417]='<kommentar>(Beifall bei der AfD)</kommentar>'
    contents[cl]='<kommentar>'+escape(COMMENTS[session] if comment is None else comment)+'</kommentar>'
    contents[line]='<p>'+escape(grant or anchor)+'</p>'
    marker=line-1 if session in (8,28) else cl-2
    contents[marker]='<name>'+escape(president)+'</name>'
    if other_rede:
        contents[cl]='</rede><rede>'+contents[cl]+'</rede><rede>'
    lines=[f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{session}">',
           '<sitzungsverlauf><tagesordnungspunkt><rede>']
    for at,tag in sorted(contents.items()):
        lines.extend(['']*(at-len(lines)-1))
        lines.append(tag)
    lines.append('</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
    return etree.fromstring('\n'.join(lines).encode())


class FixedOriginalEvidenceTests(unittest.TestCase):
    def test_all_four_expected_source_links_are_unverified(self):
        expected={8:'Carolin Bachmann',23:'Carolin Bachmann',
                  28:'René Bochmann',46:'Mirze Edis'}
        for session in SOURCES:
            with self.subTest(session=session):
                case=verify_original(fixture(session),session)
                self.assertEqual(case['person_for_manual_review'],expected[session])
                self.assertTrue(case['recipient_review_only'])
                self.assertFalse(case['individual_effective_sanction_confirmed'])
                self.assertEqual(len(case['original_comment_sha256']),64)
                self.assertEqual(len(case['original_grant_sha256']),64)
                self.assertEqual(bool(case['person_xml_id_when_originally_verified']),
                                 session==8)

    def test_wrong_interjector_does_not_identify_recipient(self):
        for session in (23,28,46):
            with self.subTest(session=session):
                remark=COMMENTS[session].replace(SOURCES[session][2],'Andere Person')
                with self.assertRaisesRegex(ValueError,'Zwischenruf'):
                    verify_original(fixture(session,comment=remark),session)

    def test_card_holder_needs_same_original_redner_id(self):
        with self.assertRaisesRegex(ValueError,'Rednerin'):
            verify_original(fixture(8,speaker='Andere Person'),8)

    def test_wrong_chair_is_rejected(self):
        for session in SOURCES:
            with self.assertRaisesRegex(ValueError,'Vorsitz'):
                verify_original(fixture(
                    session,chair='Vizepräsident Bodo Ramelow'),session)

    def test_wrong_original_grant_wording_is_rejected(self):
        for session in SOURCES:
            with self.assertRaisesRegex(ValueError,'Erteilung'):
                verify_original(fixture(
                    session,grant='Ich spreche keine Ordnungsrufe aus.'),session)

    def test_wrong_xml_source_line_is_rejected(self):
        for session in SOURCES:
            with self.assertRaisesRegex(ValueError,'Original'):
                verify_original(fixture(
                    session,grant_line=SOURCES[session][0]+6),session)

    def test_unrelated_rede_comments_are_not_recipient_proof(self):
        for session in SOURCES:
            with self.assertRaises(ValueError):
                verify_original(fixture(session,other_rede=True),session)

    def test_different_election_period_and_session_are_rejected(self):
        root=fixture(46)
        root.set('wahlperiode','20')
        with self.assertRaisesRegex(ValueError,'Falsches'):
            verify_original(root,46)
        root=fixture(23)
        with self.assertRaisesRegex(ValueError,'Falsches'):
            verify_original(root,28)


if __name__=='__main__':
    unittest.main()
