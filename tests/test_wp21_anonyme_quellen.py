"""Safety and source invariants for anonymous WP21 review dossiers."""
import unittest

from lxml import etree
from wp21_anonyme_quellen import (
    ORIGINAL_ANCHORS, TARGETS, inspect, speaker_provenance,
    validate_original_anchor, nearby_original_reactions,
)


def fixture(chair=True,sentences=None):
    text=sentences or [
        'Bitte unterlassen Sie das.',
        'Ich erteile Ihnen einen Ordnungsruf.',
        'Wir fahren mit der Tagesordnung fort.'
    ]
    marker='<name>Vizepräsidentin Andrea Lindholz</name>' if chair else (
        '<p klasse="redner"><redner id="77"><name><vorname>Erika</vorname>'
        '<nachname>Beispiel</nachname></name></redner></p>')
    parts='\n'.join('<p>'+t+'</p>' for t in text)
    xml=('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="8">\n'
         '<sitzungsverlauf><tagesordnungspunkt><rede>\n'+marker+'\n'+parts+
         '\n</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
    root=etree.fromstring(xml.encode())
    target=[p for p in root.iter('p') if p.text and 'Ordnungsruf' in p.text]
    return root, int(target[0].sourceline)


class AnonymousSourceDossierTests(unittest.TestCase):
    def test_4_remaining_original_high_priority_locations(self):
        self.assertEqual(len(TARGETS),4)
        self.assertEqual(sum(map(len,TARGETS.values())),4)
        self.assertEqual(len({(session,line) for session,items in TARGETS.items()
                             for line in items}),4)

    def test_verified_wp21_040_pairs_have_separate_source_linked_dossier(self):
        self.assertNotIn(40,TARGETS)
        self.assertNotIn(26,TARGETS)
        self.assertNotIn(43,TARGETS)
        self.assertNotIn(49,TARGETS)
        self.assertNotIn(51,TARGETS)
        self.assertNotIn(65,TARGETS)

    def test_linked_exact_xml_sources_no_longer_treated_as_anonymous(self):
        self.assertNotIn(14,TARGETS)
        self.assertNotIn(37,TARGETS)
        self.assertNotIn(39,TARGETS)

    def test_anonymous_grant_context_keeps_source_line_not_a_person(self):
        root,line=fixture()
        rows=inspect(root,8,(line,))
        self.assertEqual(len(rows),1)
        row=rows[0]
        self.assertEqual(row['case_id'],f'xml-008-L{line}')
        self.assertEqual(row['original_grant']['line'],line)
        self.assertTrue(row['needs_manual_recipient_review'])
        self.assertFalse(row['recipient_automatically_identified'])
        self.assertFalse(row['legally_effective_sanction_automatically_confirmed'])
        self.assertEqual(len(row['previous_paragraphs']),1)
        self.assertEqual(len(row['following_paragraphs']),1)
        self.assertEqual(len(row['text_sha256']),64)
        self.assertFalse(row['original_wording_anchor_checked'])
        self.assertEqual(row['original_pdf'],
                         'https://dserver.bundestag.de/btp/21/21008.pdf')

    def test_original_comments_are_evidence_not_recipient_claims(self):
        root,line=fixture()
        previous=next(p for p in root.iter('p') if p.sourceline==line).getprevious()
        previous.addnext(etree.fromstring(
            '<kommentar>(Franz Beispiel [AfD]: Das ist falsch!)</kommentar>'))
        node=next(p for p in root.iter('p') if p.sourceline==line)
        rows=nearby_original_reactions(root,int(node.sourceline),node)
        self.assertEqual(len(rows),1)
        self.assertFalse(rows[0]['recipient_proved'])
        self.assertTrue(rows[0]['same_xml_rede_as_grant'])
        self.assertIn('Franz Beispiel',rows[0]['original_text'])
        self.assertEqual(len(rows[0]['text_sha256']),64)

    def test_context_comment_from_other_speech_has_no_rede_link(self):
        root,line=fixture()
        course=root.find('sitzungsverlauf/tagesordnungspunkt')
        preceding=etree.fromstring(
            '<rede><kommentar>(Jemand: Zuruf!)</kommentar></rede>')
        course.insert(0,preceding)
        node=next(p for p in root.iter('p') if 'Ordnungsruf' in ''.join(p.itertext()))
        comments=nearby_original_reactions(root,int(node.sourceline),node)
        self.assertEqual(len(comments),1)
        self.assertFalse(comments[0]['same_xml_rede_as_grant'])
        self.assertFalse(comments[0]['recipient_proved'])

    def test_existing_named_grant_fails_closed(self):
        root,line=fixture(sentences=[
            'Der Abgeordnete Franz Beispiel kommt zu Wort.',
            'Herr Beispiel, ich erteile Ihnen einen Ordnungsruf.'])
        # Even if name parsing is incomplete in a synthetic speaker index,
        # a missing name must never be silently claimed as "resolved."
        # Adding the known speaker ID makes this a matched person.
        marker=root.xpath('.//rede/name')[0]
        marker.addnext(etree.fromstring(
            '<p klasse="redner"><redner id="41"><name>'
            '<vorname>Franz</vorname><nachname>Beispiel</nachname>'
            '</name></redner></p>'))
        with self.assertRaisesRegex(ValueError,
                                    'schon einer Person zugeordnet'):
            inspect(root,8,(line,))

    def test_missing_official_xml_line_is_error(self):
        root,line=fixture()
        with self.assertRaisesRegex(ValueError,'Originalfundstelle fehlt'):
            inspect(root,8,(line+100,))

    def test_duplicate_target_line_is_error(self):
        root,line=fixture()
        with self.assertRaisesRegex(ValueError,'Doppeltes Prüfziel'):
            inspect(root,8,(line,line))

    def test_non_grant_paragraph_is_error(self):
        root,line=fixture()
        other=int(root.xpath('.//rede/p')[0].sourceline)
        with self.assertRaisesRegex(ValueError,'nicht mehr als Prüffall erkannt'):
            inspect(root,8,(other,))

    def test_wrong_election_period_is_error(self):
        root,line=fixture()
        root.set('wahlperiode','20')
        with self.assertRaisesRegex(ValueError,'Fremdes'):
            inspect(root,8,(line,))

    def test_chairless_offence_cannot_be_claimed_as_chair_sanction(self):
        root,line=fixture(chair=False)
        with self.assertRaisesRegex(ValueError,'Ohne präsidialen'):
            inspect(root,8,(line,))

    def test_presiding_chair_is_not_a_named_interjector(self):
        root,line=fixture()
        node=next(p for p in root.iter('p') if p.sourceline==line)
        marker=speaker_provenance(node)
        self.assertEqual(marker['speaker_type'],'presiding_chair')
        self.assertIsNone(marker['speaker_id'])
        self.assertIsNone(marker['speaker_name'])

    def test_original_anchor_set_matches_all_four_unresolved_locations(self):
        targets={(session,line) for session,lines in TARGETS.items() for line in lines}
        self.assertEqual(set(ORIGINAL_ANCHORS),targets)

    def test_original_anchor_works_only_with_matching_original_wording(self):
        validate_original_anchor(8,1419,
            'Es ist verboten, im Hohen Hause Zeichen hochzuhalten. '
            'Ich erteile Ihnen dafür einen Ordnungsruf.')
        with self.assertRaisesRegex(ValueError,'Originalwortlaut/Quellenanker'):
            validate_original_anchor(8,1419,'Ich erteile Ihnen keinen Ordnungsruf.')
        with self.assertRaisesRegex(ValueError,'Nicht geprüfter Quellenanker'):
            validate_original_anchor(8,1420,'Ich erteile Ihnen dafür einen Ordnungsruf.')

    def test_strict_original_inspection_rejects_unanchored_synthetic_text(self):
        root,line=fixture()
        with self.assertRaisesRegex(ValueError,'Nicht geprüfter Quellenanker'):
            inspect(root,8,(line,),require_original_anchors=True)

    def test_speaker_provenance_must_not_assume_target_recipient(self):
        root,line=fixture(chair=False)
        node=next(p for p in root.iter('p') if p.sourceline==line)
        mark=speaker_provenance(node)
        self.assertEqual(mark['speaker_type'],'redner_id')
        self.assertEqual(mark['speaker_id'],'77')
        self.assertEqual(mark['speaker_name'],'Erika Beispiel')
        self.assertNotIn('recipient',mark)


if __name__=='__main__':
    unittest.main()
