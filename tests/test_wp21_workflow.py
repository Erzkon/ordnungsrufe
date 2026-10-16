"""Static regression checks for unattended, main-only source monitoring."""
import unittest
from pathlib import Path


class WorkflowOperationalChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = Path('.github/workflows/pages.yml').read_text(encoding='utf-8')

    def test_main_only_and_no_pr_publication(self):
        self.assertIn("always() && github.event_name != 'pull_request'", self.workflow)
        self.assertIn("github.ref == 'refs/heads/main'", self.workflow)
        self.assertIn("if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'",
                      self.workflow)

    def test_anonymous_original_sources_are_daily_review_only(self):
        self.assertIn('id: anonymousDossier', self.workflow)
        self.assertIn('--cache .cache/wp21', self.workflow)
        self.assertIn('--output .audit/wp21_anonyme_quellen.json', self.workflow)
        self.assertIn("steps.anonymousDossier.outcome == 'success'", self.workflow)
        self.assertIn("steps.anonymousDossier.outcome == 'failure'", self.workflow)
        self.assertIn('wp21-anonyme-originalquellen-', self.workflow)
        self.assertIn("if: github.event_name != 'pull_request' && steps.scan.outcome == 'success'", self.workflow)

    def test_four_recipient_sources_run_only_after_successful_xml_scan(self):
        self.assertIn('id: fourRecipientEvidence', self.workflow)
        self.assertIn('--cache .cache/wp21', self.workflow)
        self.assertIn('--output .audit/four_source_recipient_hints.json', self.workflow)
        self.assertIn("steps.anonymousDossier.outcome == 'success'", self.workflow)
        self.assertIn("steps.fourRecipientEvidence.outcome == 'success'", self.workflow)
        self.assertIn("steps.fourRecipientEvidence.outcome == 'failure'", self.workflow)
        self.assertIn('wp21-vier-quellen-personenpruefung-', self.workflow)

    def test_eighteen_dossiers_use_complete_daily_xml_but_never_publish_count_changes(self):
        self.assertIn('id: eighteenDossiers',self.workflow)
        self.assertIn('python wp21_hochprioritaet_18.py',self.workflow)
        self.assertIn('--scan-summary docs/data/scan_21.json',self.workflow)
        self.assertIn('--output .audit/wp21_hochprioritaet_18.json',self.workflow)
        self.assertIn('--brief .audit/wp21_hochprioritaet_18_review.md',self.workflow)
        self.assertIn("steps.eighteenDossiers.outcome == 'success'",self.workflow)
        self.assertIn("steps.eighteenDossiers.outcome == 'failure'",self.workflow)
        self.assertIn("github.event_name != 'pull_request'",self.workflow)

    def test_dip_case_crosswalk_only_after_complete_position_pipeline(self):
        self.assertIn('id: eighteenDIP', self.workflow)
        self.assertIn("steps.dipqueue.outcome == 'success'", self.workflow)
        self.assertIn('python wp21_18_dip_verfahrenspositionen.py', self.workflow)
        self.assertIn('--vorgang-state .cache/dip21/state.json', self.workflow)
        self.assertIn('--position-state .cache/dip21/positionen.json', self.workflow)
        self.assertIn('wp21-18-dip-quellenverbund-', self.workflow)
        self.assertIn("steps.eighteenDIP.outcome == 'success'", self.workflow)
        self.assertIn("steps.eighteenDIP.outcome == 'failure'", self.workflow)

    def test_official_fundstelle_validation_fails_without_exact_eighteen_and_four(self):
        self.assertIn('id: eighteenSources', self.workflow)
        self.assertIn("steps.eighteenDIP.outcome == 'success'", self.workflow)
        self.assertIn("d['source_verified_original_grant_positions']!=18", self.workflow)
        self.assertIn("d['source_verified_independent_dip_rejected_appeals']!=4",
                      self.workflow)
        self.assertIn("steps.eighteenSources.outcome == 'failure'", self.workflow)
        self.assertIn("github.event_name != 'pull_request'", self.workflow)

    def test_original_document_source_survey_manual_only(self):
        wf=Path('.github/workflows/wp21_18_document_probe.yml').read_text(
            encoding='utf-8')
        self.assertIn('  workflow_dispatch:',wf)
        self.assertNotIn('  pull_request:',wf)
        self.assertNotIn('  schedule:',wf)
        self.assertIn('sha256sum --check',wf)
        self.assertIn('wp21_18_dip_original_beschluesse.py',wf)

    def test_full_dip_live_source_probe_is_manual_only(self):
        wf=Path('.github/workflows/wp21_18_dip_live_audit.yml').read_text(
            encoding='utf-8')
        self.assertIn('  workflow_dispatch:', wf)
        self.assertNotIn('  pull_request:', wf)
        self.assertNotIn('  schedule:', wf)
        self.assertIn('sha256sum --check', wf)
        self.assertIn('wp21_18_dip_verfahrenspositionen.py', wf)
        self.assertNotIn('export_wp21.py', wf)

    def test_targeted_eighteen_official_dip_ids_can_only_run_manually(self):
        wf=Path('.github/workflows/wp21_18_dip_targeted_confirm.yml').read_text(
            encoding='utf-8')
        self.assertIn('  workflow_dispatch:', wf)
        self.assertNotIn('  pull_request:', wf)
        self.assertNotIn('  schedule:', wf)
        self.assertIn('wp21_18_dip_verfahrenspositionen', wf)
        self.assertIn('sha256sum --check', wf)
        self.assertNotIn('export_wp21.py', wf)

    def test_expensive_full_xml_audit_is_manual_only(self):
        wf=Path('.github/workflows/wp21_full_audit.yml').read_text(
            encoding='utf-8')
        self.assertIn('  workflow_dispatch:',wf)
        self.assertNotIn('  pull_request:',wf)
        self.assertNotIn('  schedule:',wf)
        self.assertIn('sha256sum --check',wf)

    def test_full_followup_original_xml_scan_is_manual_only(self):
        full=Path('.github/workflows/wp21_18_vollstaendige_rechtsfolgen.yml').read_text(
            encoding='utf-8')
        self.assertIn('  workflow_dispatch:',full)
        self.assertNotIn('  pull_request:',full)
        self.assertNotIn('  schedule:',full)
        self.assertIn('sha256sum --check',full)
        self.assertIn('--scan-summary .audit/full_legal_scan.json',full)
        self.assertIn('source_session',full)

    def test_failure_watchdog_checks_all_upstream_failures(self):
        for term in ("needs.pruefen.result != 'success'",
                     "steps.dataartifact.outcome == 'failure'",
                     "steps.health.outcome == 'failure'",
                     "id: dataartifact", "id: health"):
            self.assertIn(term, self.workflow)

    def test_alert_idempotent_and_closes_after_recovery(self):
        self.assertGreaterEqual(
            self.workflow.count('<!-- ordnungsruf-wp21-data-sources -->'), 2)
        self.assertIn("state:'closed', state_reason:'completed'", self.workflow)
        self.assertIn("if ((existing.body || '') !== body)", self.workflow)


if __name__ == '__main__':
    unittest.main()
