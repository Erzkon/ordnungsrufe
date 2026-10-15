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

    def test_official_21053_quoted_exclamation_does_not_hide_named_dative(self):
        hints, persons=observed(
            'Bevor wir diesen Tagesordnungspunkt abschließen, möchte ich der '
            'Abgeordneten Reichinnek einen Ordnungsruf für den Zwischenruf '
            '„Lügnerin!“ erteilen.',
            name='Heidi Reichinnek',session=53)
        self.assertEqual(hints[0]['classification'],'possible_grant')
        self.assertEqual(len(persons),1)
        self.assertEqual(persons[0]['person'],'Heidi Reichinnek')
        self.assertEqual(persons[0]['zuordnungsmethode'],'expliziter_dativ')
        self.assertEqual(persons[0]['status'],'review_required')

    def test_official_21068_quoted_interruption_with_exclamation(self):
        hints, persons=observed(
            'Bevor wir die Debatte fortsetzen, möchte ich der Abgeordneten '
            'Dr. Paula Piechotta einen Ordnungsruf erteilen für den '
            'Zwischenruf „Feigling!“.',name='Paula Piechotta',session=68)
        self.assertEqual(hints[0]['classification'],'possible_grant')
        self.assertEqual(len(persons),1)
        self.assertEqual(persons[0]['person'],'Paula Piechotta')
        self.assertEqual(persons[0]['status'],'review_required')

    def test_quoted_mention_or_conditional_still_cannot_confirm_a_grant(self):
        for example in (
            'Die Formulierung „Ordnungsruf!“ allein ist noch keine Erteilung.',
            'Wenn Sie das wiederholen, möchte ich Ihnen für „Lügner!“ '
            'einen Ordnungsruf erteilen.'):
            hints, persons=observed(example)
            self.assertNotEqual(hints[0]['classification'],'possible_grant')
            self.assertEqual(persons,[])

    def test_rescission_is_not_a_fresh_grant(self):
        hints, persons=observed('Der Ordnungsruf wurde aufgehoben.')
        self.assertNotEqual(hints[0]['classification'],'possible_grant')
        self.assertEqual(persons,[])


    def test_21052_insulted_colleague_is_not_a_recipient(self):
        hints, persons = observed(
            'Herr Kollege, dafür, dass Sie der Kollegin Inkompetenz und noch '
            'mehr vorgeworfen haben, erteile ich Ihnen hiermit einen '
            'Ordnungsruf. Denn es war ein persönlicher Angriff direkt '
            'auf die Kollegin.', name='Martin Hess', session=52)
        self.assertEqual(hints[0]['classification'], 'possible_grant')
        self.assertEqual(persons, [])

    def test_21067_insulted_named_colleague_is_not_sanctioned(self):
        hints, persons = observed(
            'Frau Kollegin, dafür, dass Sie der Kollegin Gebel '
            '„pathologischen Männerhass“ vorgeworfen haben, '
            'erhalten Sie jetzt von mir einen Ordnungsruf.',
            name='Kathrin Gebel', session=67)
        self.assertEqual(hints[0]['classification'], 'possible_grant')
        self.assertEqual(persons, [])

    def test_21065_named_interruption_sanction_is_review_candidate(self):
        hints, persons = observed(
            'Ich muss, bevor ich die nächste Rednerin aufrufe, noch mal '
            'zurückkommen zu Tagesordnungspunkt 8. Da gab es bei der Rede '
            'des Abgeordneten Ronald Gläser einen Zwischenruf des '
            'Abgeordneten Pantisano aus der Linksfraktion mit klarem Bezug '
            'auf die AfD: „Faschisten seid ihr! Mehr nicht!“ '
            'Das belege ich jetzt hiermit mit einem Ordnungsruf.',
            name='Luigi Pantisano', session=65)
        self.assertEqual(hints[0]['classification'], 'possible_grant')
        self.assertEqual(len(persons), 1)
        self.assertEqual(persons[0]['person'], 'Luigi Pantisano')
        self.assertEqual(persons[0]['zuordnungsmethode'],
                         'benannter_zwischenruf_im_absatz')
        self.assertEqual(persons[0]['status'], 'review_required')

    def test_das_belege_ich_without_unique_quoted_actor_is_unassigned(self):
        hints, persons = observed(
            'Zwei Kollegen riefen dazwischen. Das belege ich jetzt hiermit '
            'mit einem Ordnungsruf.', session=65)
        self.assertEqual(hints[0]['classification'], 'possible_grant')
        self.assertEqual(persons, [])

    def test_two_named_interrupters_must_not_be_arbitrarily_attributed(self):
        _, persons = observed(
            'Da gab es einen Zwischenruf des Abgeordneten Pantisano und '
            'des Abgeordneten Gläser: „Faschisten!“ Das belege ich jetzt '
            'hiermit mit einem Ordnungsruf.',
            name='Luigi Pantisano', session=65)
        self.assertEqual(persons, [])

    def test_21061_future_possible_sanction_not_an_imposed_grant(self):
        hints, persons = observed(
            'Für das Lachen können Sie gleich auch einen Ordnungsruf bekommen.',
            session=61)
        self.assertEqual(hints[0]['classification'], 'warning_or_conditional')
        self.assertEqual(persons, [])


    def test_original_21015_name_after_issued_ordnungsruf(self):
        hints, people = observed(
            'Ich erteile einen Ordnungsruf an Herrn Lamely, der von einer '
            '„Lüge“ gesprochen hat.', name='Test Lamely', session=15)
        self.assertEqual(hints[0]['classification'], 'possible_grant')
        self.assertEqual([x['person'] for x in people], ['Test Lamely'])
        self.assertEqual(people[0]['zuordnungsmethode'],
                         'expliziter_empfaenger_nach_erteilung')

    def test_original_21023_postposed_dative_after_ordnungsruf(self):
        hints, people = observed(
            'Bevor wir jetzt mit der Rednerliste fortfahren, habe ich noch '
            'etwas aus letzter Woche nachzuholen. Ich erteile hier noch einen '
            'nachträglichen Ordnungsruf, in dem Fall dem Abgeordneten '
            'Karsten Hilse der Fraktion der AfD, für die herabwürdigenden '
            'Äußerungen gegenüber der Fraktion Bündnis 90/Die Grünen.',
            name='Karsten Hilse', session=23)
        self.assertEqual(hints[0]['classification'], 'possible_grant')
        self.assertEqual([x['person'] for x in people], ['Karsten Hilse'])

    def test_original_21043_fronted_herrn_frohnmaier(self):
        hints, people = observed(
            '– Herrn Frohnmaier erteile ich einen Ordnungsruf.',
            name='Markus Frohnmaier', session=43)
        self.assertEqual(hints[0]['classification'], 'possible_grant')
        self.assertEqual([x['person'] for x in people], ['Markus Frohnmaier'])
        self.assertEqual(people[0]['zuordnungsmethode'],
                         'expliziter_empfaenger_vorangestellt')

    def test_original_21050_bundestagsabgeordneten_dative(self):
        hints, people = observed(
            'Ich erteile dem Bundestagsabgeordneten Martin Reichardt '
            'einen Ordnungsruf. Er hat den Abgeordneten Ralf Stegner '
            'als Hetzer bezeichnet.',
            name='Martin Reichardt', session=50)
        self.assertEqual(hints[0]['classification'], 'possible_grant')
        self.assertEqual([x['person'] for x in people], ['Martin Reichardt'])

    def test_unsafe_generic_references_not_issued(self):
        examples = [
            ('Da ich es nicht zuordnen kann, kann ich keinen Ordnungsruf '
             'erteilen.', 75),
            ('Muss ich Ihnen dafür jetzt einen Ordnungsruf erteilen? '
             'Ich habe nichts verstanden.', 74),
            ('Ich müsste Ihnen theoretisch einen Ordnungsruf erteilen,', 43),
            ('Aber dann bekommt man ja einen Ordnungsruf, wie unsere '
             'Vorsitzende.', 25),
            ('Wer dreimal einen Ordnungsruf erhält, gegen den wird '
             'automatisch ein Ordnungsgeld verhängt.', 22),
            ('Ich weiß nicht, ob sie dafür auch schon einen Ordnungsruf '
             'oder ein Strafgeld bekommen hat.', 82)
        ]
        for text,session in examples:
            with self.subTest(session=session):
                hints, people = observed(text, session=session)
                self.assertNotEqual(hints[0]['classification'], 'possible_grant')
                self.assertEqual(people, [])

    def test_explicit_recipient_outside_issuing_clause_not_an_event(self):
        hints,people = observed(
            'An Herrn Lamely sollten Sie denken. Einen Ordnungsruf '
            'hätte man hier erteilen können.', name='Test Lamely',session=15)
        self.assertNotEqual(hints[0]['classification'], 'possible_grant')
        self.assertEqual(people, [])


if __name__=='__main__':
    unittest.main()
