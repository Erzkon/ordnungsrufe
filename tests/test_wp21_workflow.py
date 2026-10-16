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
