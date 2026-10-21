"""Offline WP21 review batches remain non-counting and source bounded."""
import copy
import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wp21_autopruefung import norm, read_reviewed
from wp21_dip_kontrolle import reference
from wp21_batch_review import ROOT, POSITIVE, LEDGER, build, markdown, write

PROTECTED=[
    ROOT/'daten/wirksame_ordnungsrufe_20wp.csv',
    ROOT/'daten/wirksame_ordnungsrufe_21wp.csv',
    ROOT/'docs/data/ordnungsrufe.json',
    ROOT/'docs/data/ordnungsrufe_21.json',
]


class SourceBoundedBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot=reference(POSITIVE)
        cls.known,cls.count=read_reviewed(LEDGER)

    def result(self):
        return build(self.snapshot,self.known,self.count)

    def test_exact_sample_scope_and_no_approved_additions(self):
        report=self.result()
        self.assertEqual(report['dip_person_session_pairs_in_sample'],24)
        self.assertEqual(report['dip_original_grants_reported_in_sample'],25)
        self.assertEqual(report['confirmed_partial_ledger_measures'],8)
        self.assertEqual(report['pending_person_session_pairs'],17)
        self.assertEqual(report['reported_original_grants_not_in_confirmed_partial_ledger'],17)
        self.assertEqual(report['source_snapshot'],'2026-10-15')
        self.assertEqual(report['curated_original_wording_locations_across_18_cases'],21)
        self.assertEqual(report['curated_rejected_appeals_across_18_cases'],4)
        self.assertEqual([b['cases'] for b in report['batches']],[5,5,5,2])
        self.assertEqual(len({e['case_id'] for e in report['cases']}),17)
        self.assertEqual(report['automatic_approved_sanctions'],0)
        self.assertEqual(report['automatic_rescinded_sanctions'],0)
        self.assertFalse(report['protected_ledgers_changed'])
        self.assertIn('keine bestätigten wirksamen',report['warning'].lower())

    def test_priority_and_appeal_are_separate_facts(self):
        items={(e['session'],norm(e['person'])):e for e in self.result()['cases']}
        frohn=items[(51,norm('Markus Frohnmaier'))]
        self.assertEqual(frohn['original_xml_lines'],[3979,3981])
        self.assertEqual(frohn['priority'],'P0_mehrfachformulierung')
        self.assertIsNone(frohn['official_appeal_decision'])
        reich=items[(65,norm('Martin Reichardt'))]
        self.assertEqual(reich['original_xml_lines'],[2044,2046])
        self.assertEqual(reich['priority'],'P0_mehrfachformulierung')
        self.assertFalse(reich['official_appeal_decision']['confirms_effective_sanctions'])
        self.assertEqual(items[(52,norm('Martin Hess'))]['priority'],
                         'P1_einspruch_verknuepfen')
        self.assertEqual(len([c for c in items.values()
                              if c['official_appeal_decision']]),4)
        self.assertNotIn((94,norm('Cansin Köktürk')),items)
        self.assertEqual([x['session'] for x in self.result()['cases'][:2]],[51,65])

    def test_original_links_and_unreviewed_rows_consistent(self):
        for item in self.result()['cases']:
            self.assertTrue(item['source_pdf'].endswith(
                f"/21{item['session']:03d}.pdf"))
            self.assertTrue(item['source_xml'].endswith(
                f"/21{item['session']:03d}.xml"))
            self.assertGreater(len(item['original_xml_lines']),0)
            self.assertEqual(item['already_verified_measures'],0)
            self.assertEqual(item['reported_but_not_individually_verified'],1)

    def test_write_only_under_audit_and_protected_bytes_unchanged(self):
        before={str(f):hashlib.sha256(f.read_bytes()).hexdigest()
                for f in PROTECTED}
        audit=ROOT/'.audit'
        audit.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=audit) as folder:
            write(self.result(),folder)
            summary=(Path(folder)/'review_queue.md').read_text(encoding='utf-8')
            self.assertIn('Bündel 1',summary)
            self.assertIn('nicht 17 bestätigte',summary)
            self.assertIn('21/051',summary)
            self.assertIn('21/065',summary)
            self.assertEqual(len((Path(folder)/'review_queue.csv')
                                 .read_text(encoding='utf-8').splitlines()),18)
            self.assertIn('case_id',(Path(folder)/'review_queue.json')
                          .read_text(encoding='utf-8'))
        after={str(f):hashlib.sha256(f.read_bytes()).hexdigest()
               for f in PROTECTED}
        self.assertEqual(before,after)
        with TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'nur im Verzeichnis'):
                write(self.result(),folder)

    def test_two_first_batch_originals_keep_intervening_speaker_context_distinct(self):
        report=self.result()
        cases={(c['session'],norm(c['person'])):c for c in report['cases']}
        frohn=cases[(51,norm('Markus Frohnmaier'))]['manual_original_context_hint']
        reich=cases[(65,norm('Martin Reichardt'))]['manual_original_context_hint']
        self.assertEqual(
            frohn['preliminary_classification'],
            'two_phrases_with_intervening_new_interjection')
        self.assertEqual(
            reich['preliminary_classification'],
            'two_phrases_one_uninterrupted_chair_intervention')
        self.assertTrue(frohn['official_page'].endswith('21051.pdf#page=74'))
        self.assertTrue(reich['official_page'].endswith('21065.pdf#page=25'))
        self.assertFalse(frohn['separate_legal_grants_verified'])
        self.assertFalse(reich['separate_legal_grants_verified'])
        self.assertIn('mit',markdown(report))

    def test_three_official_original_vote_pairs_enrich_existing_queue(self):
        report=self.result()
        self.assertEqual(report['independently_crosschecked_original_and_vote_pairs'],3)
        rows=[c for c in report['cases']
              if c['independent_original_and_vote_crosscheck']]
        self.assertEqual([(c['session'],c['person']) for c in rows],
                         [(52,'Martin Hess'),(67,'Kerstin Przygodda'),
                          (69,'Fabian Fahl')])
        self.assertTrue(all(
            x['independent_original_and_vote_crosscheck']
             ['confirmed_parliamentary_rejection'] for x in rows))
        self.assertTrue(all(
            x['independent_original_and_vote_crosscheck']
             ['further_legal_outcome_review_required'] for x in rows))
        self.assertTrue(all(x['independent_original_and_vote_crosscheck']
                            ['new_effective_sanctions_automatically_approved']==0
                            for x in rows))
        self.assertEqual(report['automatic_approved_sanctions'],0)

    def test_next_five_original_pdfs_are_separately_verified_but_not_effective(self):
        report=self.result()
        self.assertEqual(report['independently_located_additional_original_pdfs'],5)
        rows=[c for c in report['cases'] if c['additional_original_pdf_crosscheck']]
        self.assertEqual(
            [(c['session'],c['person']) for c in rows],
            [(53,'Heidi Reichinnek'),(57,'Bernd Baumann'),
             (61,'Ulrich von Zons'),(65,'Luigi Pantisano'),
             (67,'Kathrin Gebel')])
        for row in rows:
            detail=row['additional_original_pdf_crosscheck']
            self.assertTrue(detail['original_individually_located'])
            self.assertTrue(detail['further_legal_outcome_review_required'])
            self.assertEqual(detail['new_effective_sanctions_automatically_approved'],0)
        self.assertEqual(report['automatic_approved_sanctions'],0)

    def test_five_originals_have_independent_noncounting_legal_followup_tasks(self):
        report=self.result()
        self.assertEqual(report['individual_later_effect_review_tasks_for_five_origins'],5)
        self.assertTrue(report['curated_objection_matches_not_global_no_appeal_proof'])
        rows=[c for c in report['cases'] if c['later_effects_review']]
        self.assertEqual(len(rows),5)
        for c in rows:
            self.assertFalse(c['later_effects_review']['legal_effects_proven'])
            self.assertFalse(c['later_effects_review']['historical_appeal_coverage_complete'])
            self.assertTrue(c['later_effects_review']['manual_review_pending'])
            self.assertEqual(c['later_effects_review']
                             ['new_effective_sanctions_automatically_approved'],0)
        self.assertEqual(report['automatic_approved_sanctions'],0)

    def test_new_official_penalty_is_not_misclassified_as_old_ordnungsruf(self):
        report=self.result()
        reich=next(c for c in report['cases']
                   if c['session']==65 and c['person']=='Martin Reichardt')
        different=reich['independent_unrelated_proceeding']
        self.assertEqual(different['sanction_type'],'ordnungsgeld_not_ordnungsruf')
        self.assertEqual(different['date_of_sanction'],'2026-10-15')
        self.assertFalse(different['counts_as_21_065_ordnungsruf'])
        self.assertFalse(different['changes_protected_ledger'])
        self.assertIn('kw42-de-einspruch-ordnungsgeld',different['source'])
        sichert=report['separate_preexisting_reviewed_case_appeal']
        self.assertEqual(sichert['session'],90)
        self.assertFalse(sichert['creates_another_ordnungsruf'])
        self.assertFalse(any(c['session']==90 for c in report['cases']))
        self.assertIn('Ordnungsgeld',markdown(report))
        self.assertEqual(report['automatic_approved_sanctions'],0)

    def test_corrupt_positive_control_and_ledger_fail_closed(self):
        sample=copy.deepcopy(self.snapshot)
        sample['entries'].pop()
        with self.assertRaises(ValueError):
            build(sample,self.known,self.count)
        sample=copy.deepcopy(self.snapshot)
        sample['entries'][0]['reported_grants']=2
        with self.assertRaises(ValueError):
            build(sample,self.known,self.count)
        sample=copy.deepcopy(self.snapshot)
        sample['entries'][0]['official_transcript']='https://example.com/counterfeit.pdf'
        with self.assertRaises(ValueError):
            build(sample,self.known,self.count)
        with self.assertRaises(ValueError):
            build(self.snapshot,self.known,self.count+1)
        with self.assertRaises(ValueError):
            build(self.snapshot,{**self.known,
                                 (51,norm('Markus Frohnmaier')):1},self.count)

    def test_false_approved_count_blocked_and_unknown_appeals_not_absent(self):
        report=self.result()
        with self.assertRaises(ValueError):
            markdown({**report,'automatic_approved_sanctions':1})
        self.assertEqual(len([c for c in report['cases']
                              if c['official_appeal_decision'] is None]),13)
        self.assertIn('nicht',report['warning'].lower())
        self.assertIn('Kein kuratierter Entscheidungsbeleg',markdown(report))


if __name__=='__main__':
    unittest.main()
