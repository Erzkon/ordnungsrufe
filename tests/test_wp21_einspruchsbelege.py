"""Official Bundestag appeal evidence never auto-approves a sanction."""
import unittest

from wp21_einspruchsbelege import EVIDENCE,find,validated_index
from wp21_pruefbericht import create_brief
from wp21_vollstaendigkeit import FIELDS


def case(session,person,priority='hoch'):
    row={name:'' for name in FIELDS}
    row.update(fall_id=f'person-{session:03d}-z',prioritaet=priority,
               typ='person_sitzung_ohne_einzelereignisabgleich',
               sitzung=str(session),person=person,
               protokoll=f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf',
               dip_urspruengliche_erteilungen_stichprobe='1',
               bestaetigte_massnahmen_teilbestand='0',
               parser_person_sitzung_vorhanden='ja',
               parser_fundstellen='1')
    return row


def report(high=1,total=1):
    return {'wahlperiode':21,'status':'quellenvollstaendigkeit_ohne_automatische_freigabe',
            'automatically_confirmed_sanctions':0,
            'automatically_rescinded_sanctions':0,
            'review_cases_total':total,'high_priority_cases':high,
            'last_success_utc':'2026-10-15T17:55:42+00:00',
            'sessions_scanned':100}


class OfficialAppealEvidenceTests(unittest.TestCase):
    def test_four_official_bundestag_decisions_are_distinct(self):
        index=validated_index()
        self.assertEqual(len(index),4)
        self.assertEqual({x['session'] for x in EVIDENCE},{52,65,67,69})
        self.assertTrue(all(x['outcome']=='einspruch_zurueckgewiesen'
                            for x in index.values()))

    def test_match_person_and_exact_session_not_some_other_same_name(self):
        self.assertEqual(find(65,'Martin Reichardt')['decision_date'],'2026-03-20')
        self.assertIsNone(find(77,'Martin Reichardt'))
        self.assertIsNone(find(67,'Kathrin Gebel'))
        self.assertIsNone(find(69,'Mirze Edis'))

    def test_reject_untrusted_domain(self):
        row={**EVIDENCE[0],'source':'https://evil.example/fake'}
        with self.assertRaisesRegex(ValueError,'Nichtamtliche'):
            validated_index((row,))

    def test_reject_invalid_legal_outcome(self):
        row={**EVIDENCE[0],'outcome':'ordnungsruf_wirksam'}
        with self.assertRaisesRegex(ValueError,'Rechtsausgang'):
            validated_index((row,))

    def test_reject_duplicate_independent_record(self):
        with self.assertRaisesRegex(ValueError,'doppelt'):
            validated_index((EVIDENCE[0],EVIDENCE[0]))

    def test_reject_duplicate_source_document_under_other_person(self):
        other={**EVIDENCE[0],'person':'Anderer Politiker','session':53}
        with self.assertRaisesRegex(ValueError,'doppelt'):
            validated_index((EVIDENCE[0],other))

    def test_reject_future_or_invalid_date(self):
        row={**EVIDENCE[0],'decision_date':'2028-10-15'}
        with self.assertRaisesRegex(ValueError,'Quellengrenze'):
            validated_index((row,))

    def test_high_priority_report_shows_appeal_but_still_manual(self):
        text=create_brief([case(52,'Martin Hess')],report())
        self.assertIn('Einspruch am 2026-01-15',text)
        self.assertIn('amtlicher Beschlussbericht',text)
        self.assertIn('**Manuelle Entscheidung:** offen',text)

    def test_non_matching_case_does_not_borrow_other_appeal(self):
        text=create_brief([case(67,'Kathrin Gebel')],report())
        self.assertNotIn('Separat nachgewiesene Einspruchsentscheidung',text)
        self.assertNotIn('1158042',text)

    def test_medium_priority_evidence_not_falsely_promoted(self):
        text=create_brief([case(52,'Martin Hess','mittel')],report(high=0))
        self.assertNotIn('Separat nachgewiesene Einspruchsentscheidung',text)
        self.assertIn('**Offene Hochprioritäts-Prüffälle:** 0',text)


if __name__=='__main__':
    unittest.main()
