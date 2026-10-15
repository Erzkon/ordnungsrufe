"""WP21 original-PDF-language regression examples (not complete XML transcripts).

Primary sources: official Bundestag PDF protocols 21/57 p.48, 21/86 p.29,
21/93 p.87 and 21/94 p.24. Some utterances are abbreviated to the minimal
clause because PDF layout does not define XML paragraph boundaries.
"""
import unittest
from pathlib import Path

from lxml import etree
from parser import candidates, events, speaker_index


def sample_xml(sentence, name=None, number=94):
    names=''
    if name:
        first,last=name.split(' ',1)
        names=(f'<redner id="11005499"><name><vorname>{first}</vorname>'
               f'<nachname>{last}</nachname><fraktion>Test</fraktion>'
               f'</name></redner>')
    from html import escape
    data=(f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{number}" '
          f'sitzung-datum="11.09.2026"><vorspann>{names}</vorspann>'
          f'<sitzungsverlauf><tagesordnungspunkt>'
          f'<p>{escape(sentence)}</p></tagesordnungspunkt>'
          f'</sitzungsverlauf></dbtplenarprotokoll>')
    return etree.fromstring(data.encode('utf-8'))


def observed(text, name=None, session=94):
    root=sample_xml(text,name=name,number=session)
    idx=speaker_index([root])
    return (list(candidates(Path(f'21{session:03d}.xml'),root=root)),
            list(events(Path(f'21{session:03d}.xml'),index=idx,root=root)))


class OriginalWording(unittest.TestCase):
    def test_21094_first_grant_confirmation_is_a_candidate(self):
        hints, persons=observed('So, bitte schön, dann haben Sie jetzt Ihren Ordnungsruf.')
        self.assertEqual(hints[0]['classification'],'possible_grant')
        self.assertEqual(persons,[])  # Pronoun alone cannot prove identity.

    def test_21094_second_grant_is_a_candidate_without_guessed_identity(self):
        hints, persons=observed('Dafür gibt es den nächsten Ordnungsruf.')
        self.assertEqual(hints[0]['classification'],'possible_grant')
        self.assertEqual(persons,[])

    def test_21094_conditional_warning_not_confused_with_actual_grant(self):
        hints, persons=observed('Nein, jetzt ist Schluss, ansonsten gibt es einen Ordnungsruf.')
        self.assertNotEqual(hints[0]['classification'],'possible_grant')
        self.assertEqual(persons,[])

    def test_21057_named_subject_is_actual_person_proposal(self):
        hints, persons=observed('Der Abgeordnete Kneller erhält von mir einen Ordnungsruf.',
                                 name='Maximilian Kneller',session=57)
        self.assertEqual(hints[0]['classification'],'possible_grant')
        self.assertEqual(len(persons),1)
        self.assertEqual(persons[0]['person'],'Maximilian Kneller')
        self.assertEqual(persons[0]['zuordnungsmethode'],'explizites_empfaenger_subjekt')
        self.assertEqual(persons[0]['status'],'review_required')

    def test_21086_explicit_recipient_as_person_proposal(self):
        hints, persons=observed(
            'Wegen der Wortwahl erteile ich der Abgeordneten Köktürk einen Ordnungsruf.',
            name='Cansin Köktürk',session=86)
        self.assertEqual(hints[0]['classification'],'possible_grant')
        self.assertEqual(len(persons),1)
        self.assertEqual(persons[0]['person'],'Cansin Köktürk')

    def test_21093_pronoun_does_not_invent_bessin_from_utterance_alone(self):
        hints, persons=observed('Dafür erteile ich Ihnen einen Ordnungsruf.',
                                name='Birgit Bessin',session=93)
        self.assertEqual(hints[0]['classification'],'possible_grant')
        self.assertEqual(persons,[])

    def test_rescission_is_not_a_fresh_grant(self):
        hints, persons=observed('Der Ordnungsruf wurde aufgehoben.')
        self.assertNotEqual(hints[0]['classification'],'possible_grant')
        self.assertEqual(persons,[])

if __name__=='__main__':
    unittest.main()
