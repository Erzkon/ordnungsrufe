"""Regression tests for seven independently verified 2025 grant utterances."""
import unittest

from wp21_2025_sieben_originalzeilen import DAYS,LOCATIONS,exact_match,markdown


class SevenOriginalXMLGrants(unittest.TestCase):
    EXAMPLES={
        10:('Stephan Brandner',
            'Herr Brandner, ich erteile Ihnen dafür, dass Sie „Syndikat“ gegenüber allen anderen Abgeordneten hier im Haus jetzt wiederholt benutzt haben, einen Ordnungsruf.'),
        11:('Stephan Brandner',
            'Bevor ich den nächsten Tagesordnungspunkt aufrufe, möchte ich dem Abgeordneten Brandner von der AfD einen Ordnungsruf erteilen. Deshalb erteile ich ihm einen Ordnungsruf.'),
        15:('Luigi Pantisano',
            'Ich erteile einen Ordnungsruf an den Abgeordneten der Linksfraktion, Herrn Pantisano.'),
        25:('Mirze Edis',
            'Während der Rede des Abgeordneten Sascha Lensing rief der Abgeordnete Mirze Edis ihm etwas zu: Ich erteile einen Ordnungsruf für diese Äußerung.'),
        43:('Martin Reichardt',
            'Ich erteile Ihnen hiermit einen Ordnungsruf, Herr Reichardt. Sie kennen anscheinend die Geschäftsordnung nicht.'),
        49:('Stephan Brandner',
            'Bevor wir die Debatte fortsetzen, möchte ich dem Abgeordneten Stephan Brandner von der AfD einen Ordnungsruf erteilen für den Zwischenruf „Heul doch!“.'),
        50:('Martin Reichardt',
            'Ich erteile dem Bundestagsabgeordneten Martin Reichardt einen Ordnungsruf.'),
    }

    def test_all_seven_original_sittings_have_one_exact_line_and_issuer_utterance(self):
        self.assertEqual(len(DAYS),7)
        self.assertEqual(len(LOCATIONS),7)
        for session,(person,spoken) in self.EXAMPLES.items():
            line=LOCATIONS[(session,person.casefold())][0]
            with self.subTest(session=session):
                row=exact_match([(line,spoken)],session,person)
                self.assertEqual(row['original_xml_line'],line)
                self.assertEqual(row['session'],session)
                self.assertEqual(len(row['paragraph_sha256']),64)
                self.assertFalse(row['legally_effective_individual_sanction_confirmed'])
                self.assertEqual(row['automatic_public_counter_delta'],0)

    def test_same_text_on_two_xml_lines_is_ambiguous(self):
        person,text=self.EXAMPLES[10]
        line=LOCATIONS[(10,person.casefold())][0]
        with self.assertRaisesRegex(ValueError,'duplicated'):
            exact_match([(line,text),(line+5,text)],10,person)

    def test_source_shift_is_not_silently_accepted(self):
        person,text=self.EXAMPLES[49]
        line=LOCATIONS[(49,person.casefold())][0]
        with self.assertRaisesRegex(ValueError,'shifted'):
            exact_match([(line+1,text)],49,person)

    def test_historical_mention_without_current_issuer_not_approved(self):
        with self.assertRaisesRegex(ValueError,'missing'):
            exact_match([(5850,'Über den Ordnungsruf des Herrn Brandner wurde abgestimmt.')],
                        10,'Stephan Brandner')

    def test_other_person_or_session_is_not_borrowed(self):
        person,text=self.EXAMPLES[10]
        with self.assertRaisesRegex(ValueError,'Unreviewed'):
            exact_match([(5850,text)],10,'Martin Reichardt')
        with self.assertRaisesRegex(ValueError,'Unreviewed'):
            exact_match([(5850,text)],40,person)

    def test_renderer_will_not_publish_measure_numbers(self):
        with self.assertRaisesRegex(ValueError,'Untrusted'):
            markdown({
                'schema':'wp21-2025-seven-verified-original-xml-loci-v1',
                'individually_sourced_original_xml_lines':7,
                'automatically_confirmed_effective_sanctions':1,
                'public_counter_delta':1,
                'cases':[{} for _ in range(7)],
            })


if __name__=='__main__':
    unittest.main()
