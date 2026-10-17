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

    def test_gottschalk_new_parent_watch_is_read_only_after_successful_dip_cache(self):
        self.assertIn('id: gottschalkWatch',self.workflow)
        self.assertIn('wp21_gottschalk_folgebeobachter.py',self.workflow)
        self.assertIn("steps.dippositions.outcome == 'success'",self.workflow)
        self.assertIn("steps.gottschalkWatch.outcome == 'success'",self.workflow)
        self.assertIn("steps.gottschalkWatch.outcome == 'failure'",self.workflow)
        self.assertIn('wp21-gottschalk-folgebeobachter-',self.workflow)
        source=Path('.github/workflows/wp21_gottschalk_folgeverfahren_probe.yml').read_text(
            encoding='utf-8')
        self.assertIn('  workflow_dispatch:',source)
        self.assertNotIn('  pull_request:',source)
        self.assertNotIn('  schedule:',source)
        self.assertIn('wp21_gottschalk_bounded_review.py',source)
        self.assertIn('sha256sum --check',source)

    def test_title_independent_dip_position_probe_does_not_publish_counts(self):
        source=Path('.github/workflows/wp21_18_einzelakten.yml').read_text(
            encoding='utf-8')
        self.assertIn('gottschalk-position-first:',source)
        self.assertIn('wp21_gottschalk_unkategorisierte_positionen.py',source)
        self.assertIn('tests.test_wp21_gottschalk_unkategorisierte_positionen',source)
        self.assertIn('sha256sum --check',source)
        self.assertIn('wp21_gottschalk_historischer_backfill.py',source)
        self.assertIn("      - name: Alle späteren Gottschalk-DIP-Positionen in begrenzten historischen Teilfenstern prüfen\n        if: github.event_name == 'workflow_dispatch'",source)
        self.assertIn('tests.test_wp21_gottschalk_historischer_backfill',source)
        self.assertIn('--start "$WINDOW_START" --end "$WINDOW_END"',source)

    def test_title_independent_gottschalk_positions_watch_uses_recent_window_only(self):
        self.assertIn('id: gottschalkPositionWide', self.workflow)
        self.assertIn('wp21_gottschalk_unkategorisierte_positionen.py', self.workflow)
        self.assertIn("steps.dippositions.outcome == 'success'", self.workflow)
        self.assertIn("steps.gottschalkPositionWide.outcome == 'success'", self.workflow)
        self.assertIn("steps.gottschalkPositionWide.outcome == 'failure'", self.workflow)
        self.assertIn("date -u -d '13 days ago'", self.workflow)
        self.assertIn('wp21-gottschalk-positions-current-', self.workflow)

    def test_janich_conditional_original_wording_is_review_only(self):
        self.assertIn('id: janichContext',self.workflow)
        self.assertIn('wp21_janich_erste_quellenkritik.py',self.workflow)
        self.assertIn("steps.janichContext.outcome == 'failure'",self.workflow)
        self.assertIn("steps.fortyDossier.outcome == 'success'",self.workflow)

    def test_two_real_plenary_xmls_for_november_multigrants_are_isolated_review_only(self):
        self.assertIn('id: fortyDossier',self.workflow)
        self.assertIn('python wp21_40_mehrfach_akte.py',self.workflow)
        self.assertIn('--cache .cache/wp21',self.workflow)
        self.assertIn('wp21-sitzungen-40-42-mehrfachakte-',self.workflow)
        self.assertIn("steps.fortyDossier.outcome == 'success'",self.workflow)
        self.assertIn("steps.fortyDossier.outcome == 'failure'",self.workflow)
        self.assertIn("github.event_name != 'pull_request'",self.workflow)

    def test_ten_2025_dip_sources_have_isolated_failclosed_original_crosswalk(self):
        wf=Path('.github/workflows/wp21_2025_original_case_probe.yml').read_text(
            encoding='utf-8')
        self.assertIn('wp21_2025_dip_einzelakten.py',wf)
        self.assertIn('tests.test_wp21_2025_dip_einzelakten',wf)
        self.assertIn('verified_individual_cases.json',wf)
        self.assertIn('wp21_2025_massnahmen_lifecycle.py',wf)
        self.assertIn('original_40_42.xml_review.json',wf)
        self.assertIn('measure_lifecycle_review.md',wf)
        self.assertIn('sha256sum --check',wf)

    def test_seven_more_original_xml_sittings_are_reviewed_without_counts(self):
        self.assertIn('id: sevenOriginals',self.workflow)
        self.assertIn('python wp21_2025_sieben_originalzeilen.py',self.workflow)
        self.assertIn('--cache .cache/wp21',self.workflow)
        self.assertIn("steps.sevenOriginals.outcome == 'failure'",self.workflow)
        probe=Path('.github/workflows/wp21_2025_original_xml_probe.yml').read_text(
            encoding='utf-8')
        self.assertIn('  workflow_dispatch:',probe)
        self.assertNotIn('  pull_request:',probe)
        self.assertNotIn('  schedule:',probe)

    def test_all_eleven_identified_original_sources_are_required_before_lifecycle_daily_review(self):
        self.assertIn("steps.sevenOriginals.outcome == 'success'",self.workflow)
        self.assertIn('--seven-original-report .audit/wp21_2025_7_original_lines.json',
                      self.workflow)
        self.assertIn('wp21_2025_sieben_originalzeilen.py',self.workflow)

    def test_one_person_one_measures_not_objections_dossier_is_independently_queued(self):
        self.assertIn('id: individual2025',self.workflow)
        self.assertIn("steps.original2025.outcome == 'success'",self.workflow)
        self.assertIn("steps.fortyDossier.outcome == 'success'",self.workflow)
        self.assertIn('python wp21_2025_massnahmen_lifecycle.py',self.workflow)
        self.assertIn('wp21-2025-einzelmassnahmen-quelle-',self.workflow)
        self.assertIn("steps.individual2025.outcome == 'failure'",self.workflow)
        self.assertIn("github.event_name != 'pull_request'",self.workflow)

    def test_complete_2025_twelve_measure_official_source_live_probe_is_manual_only(self):
        source=Path('.github/workflows/wp21_2025_lifecycle_live_validation.yml').read_text(
            encoding='utf-8')
        self.assertIn('  workflow_dispatch:',source)
        self.assertNotIn('  pull_request:',source)
        self.assertNotIn('  schedule:',source)
        self.assertIn('wp21_2025_massnahmen_lifecycle.py',source)
        self.assertIn('wp21_2025_sieben_originalzeilen.py',source)
        self.assertIn('identified_original_xml_issuance_lines',source)
        self.assertIn('sha256sum --check',source)
        self.assertNotIn('export_wp21.py',source)

    def test_2025_case_review_uses_completed_dip_cache_and_full_survey_is_manual(self):
        self.assertIn('id: original2025',self.workflow)
        self.assertIn("steps.dippositions.outcome == 'success'",self.workflow)
        self.assertIn('python wp21_2025_dip_einzelakten.py',self.workflow)
        self.assertIn('--vorgang-state .cache/dip21/state.json',self.workflow)
        self.assertIn('--position-state .cache/dip21/positionen.json',self.workflow)
        self.assertIn('wp21-2025-dip-origins-and-appeals-',self.workflow)
        self.assertIn("steps.original2025.outcome == 'failure'",self.workflow)
        survey=Path('.github/workflows/wp21_2025_original_case_probe.yml').read_text(
            encoding='utf-8')
        self.assertIn('  workflow_dispatch:',survey)
        self.assertNotIn('  pull_request:',survey)
        self.assertNotIn('  schedule:',survey)

    def test_additional_official_appeal_decisions_remain_readonly_and_not_double_counted(self):
        self.assertIn('id: additionalAppeals', self.workflow)
        self.assertIn('python wp21_weitere_einspruchsberichte.py',self.workflow)
        self.assertIn('--ledger daten/wirksame_ordnungsrufe_21wp.csv',self.workflow)
        self.assertIn('wp21-weitere-einspruchsberichte-',self.workflow)
        self.assertIn("steps.additionalAppeals.outcome == 'success'",self.workflow)
        self.assertIn("steps.additionalAppeals.outcome == 'failure'",self.workflow)
        self.assertIn("github.event_name != 'pull_request'",self.workflow)

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
