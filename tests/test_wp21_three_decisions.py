"""Three source-bound original-issuance / parliamentary-vote crosswalks."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wp21_autopruefung import norm, read_reviewed
from wp21_dip_kontrolle import reference
from wp21_einspruchsbelege import validated_index
from wp21_three_decisions import (
    ROOT, SNAPSHOT, LEDGER, SOURCE_CASES, build, official_pdf, render, main,
)


class ThreeOfficialVotesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=reference(SNAPSHOT)
        cls.known,cls.total=read_reviewed(LEDGER)
        cls.appeals=validated_index()

    def crosswalk(self, cases=SOURCE_CASES, appeals=None, snapshot=None, known=None):
        return build(source_cases=cases,
                     appeals=self.appeals if appeals is None else appeals,
                     snapshot=self.snapshot if snapshot is None else snapshot,
                     known=self.known if known is None else known)

    def test_all_three_match_individual_origins_and_votes_without_counting(self):
        r=self.crosswalk()
        self.assertEqual(r['individual_origins_checked'],3)
        self.assertEqual(r['individually_linked_parliamentary_appeal_rejections'],3)
        self.assertEqual(r['independently_newly_approved_effective_sanctions'],0)
        self.assertFalse(r['protected_public_counters_changed'])
        self.assertEqual([(x['session'],x['person']) for x in r['cases']],[
            (52,'Martin Hess'),(67,'Kerstin Przygodda'),(69,'Fabian Fahl')])
        self.assertEqual([x['original_xml_lines'] for x in r['cases']],
                         [[3749],[3079],[2204]])
        self.assertTrue(all(x['appeal_rejection_supported_by_independent_plenary_vote']
                            for x in r['cases']))
        self.assertTrue(all(x['requires_independent_later_legal_outcome_review']
                            for x in r['cases']))
        self.assertFalse(any(x['no_later_reversal_proven'] for x in r['cases']))

    def test_specific_original_and_vote_pdfs_and_dates(self):
        rows=self.crosswalk()['cases']
        for x,session,page,decision_session,decision_page in [
            (rows[0],52,54,53,71),(rows[1],67,41,68,108),
            (rows[2],69,51,70,66),
        ]:
            self.assertEqual(x['original_pdf_url'],official_pdf(session,page))
            self.assertEqual(x['decision_pdf_url'],
                             official_pdf(decision_session,decision_page))
            self.assertEqual(x['additional_original_grants_approved'],0)
            self.assertIn('bundestag.de/dokumente/textarchiv/',
                          x['editorial_appeal_report_url'])

    def test_fahl_chair_restatement_must_not_count_as_another_grant(self):
        fahl=self.crosswalk()['cases'][2]
        self.assertIn('restatement',fahl['original_issuance_wording'])
        self.assertEqual(fahl['original_xml_lines'],[2204])
        self.assertEqual(fahl['additional_original_grants_approved'],0)

    def test_appeal_rejection_cannot_be_confused_with_original_date(self):
        for row in self.crosswalk()['cases']:
            self.assertLess(row['original_date'],row['decision_date'])
            self.assertGreater(row['decision_session'],row['session'])
        wrong=copy.deepcopy(SOURCE_CASES)
        wrong[1]['decision_date']='2026-03-27'
        with self.assertRaisesRegex(ValueError,'widersprüchlich'):
            self.crosswalk(wrong)
        wrong=copy.deepcopy(SOURCE_CASES)
        wrong[2]['decision_session']=69
        with self.assertRaisesRegex(ValueError,'widersprüchlich'):
            self.crosswalk(wrong)

    def test_missing_or_misattributed_appeal_fails_closed(self):
        appeals=dict(self.appeals)
        appeals.pop((67,norm('Kerstin Przygodda')))
        with self.assertRaises(ValueError):
            self.crosswalk(appeals=appeals)
        wrong=copy.deepcopy(SOURCE_CASES)
        wrong[0]['original_xml_lines']=(3079,)
        with self.assertRaises(ValueError):
            self.crosswalk(wrong)

    def test_fake_original_pdf_and_mutated_reference_fail_closed(self):
        wrong=copy.deepcopy(self.snapshot)
        wrong['entries'][0]['reported_grants']=2
        with self.assertRaises(ValueError):
            self.crosswalk(snapshot=wrong)
        wrong=copy.deepcopy(SOURCE_CASES)
        wrong[0]['original_pdf_page']='https://invalid.example'
        with self.assertRaises(ValueError):
            self.crosswalk(wrong)
        with self.assertRaises(ValueError):
            official_pdf(22,0)

    def test_original_votes_do_not_alter_verified_reference(self):
        report=self.crosswalk()
        content=render(report)
        for name in ('Martin Hess','Kerstin Przygodda','Fabian Fahl'):
            self.assertIn(name,content)
        self.assertIn('keine unabhängige Zählerfreigabe',content)
        with self.assertRaises(ValueError):
            render({**report,'independently_newly_approved_effective_sanctions':1})

    def test_output_restricted_to_nonpublic_audit_directory(self):
        (ROOT/'.audit').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.audit') as tmp:
            with patch('sys.argv',['crosswalk','--output-dir',tmp]):
                main()
            report=json.loads((Path(tmp)/'crosswalk.json').read_text(encoding='utf-8'))
            self.assertEqual(report['independently_newly_approved_effective_sanctions'],0)
            self.assertEqual(len(report['cases']),3)
        with tempfile.TemporaryDirectory() as tmp:
            with patch('sys.argv',['crosswalk','--output-dir',tmp]):
                with self.assertRaisesRegex(ValueError,'nur unter'):
                    main()

if __name__=='__main__':
    unittest.main()
