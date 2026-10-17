"""Version-1.0 release candidate: only bounded and already verified counts."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from wp21_betriebsbericht import EXPECTED

from v1_release_gate import evaluate,markdown,run,PROTECTED,STATUS


class ReleaseGate(unittest.TestCase):
    def test_real_checked_snapshots_pass_without_write_to_ledger(self):
        original={p:(Path(p).read_bytes()) for p in PROTECTED}
        r=evaluate(Path('.'))
        self.assertEqual(r['status'],STATUS)
        self.assertEqual(r['verified_20th_term_measures'],135)
        self.assertEqual(r['verified_20th_term_events'],123)
        self.assertEqual(r['verified_21st_term_partial_items'],8)
        self.assertFalse(r['release_scope']['twenty_first_term_full_census_claim'])
        self.assertFalse(r['automatic_merge_or_publish_authorized'])
        self.assertEqual(r['automatically_imported_unverified_measures'],0)
        self.assertEqual(original,{p:Path(p).read_bytes() for p in PROTECTED})

    def test_release_summary_never_reframes_partial_21_as_complete(self):
        r=evaluate(Path('.'))
        md=markdown(r).lower()
        self.assertIn('keine vollständige gesamtstatistik',md)
        self.assertIn('ausdrückliche',md)
        for change in (
                {'automatic_merge_or_publish_authorized':True},
                {'automatically_imported_unverified_measures':1},
                {'requires_explicit_human_merging_decision':False},
                {'not_an_exhaustive_legal_effect_confirmation':False}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                markdown({**r,**change})

    def copy_minimal(self,root):
        for p in list(PROTECTED)+[
                'daten/korrekturbericht_20wp.json',
                'docs/index.html','docs/app.js','docs/verified_contract.js',
                'docs/source_health.js']:
            target=root/p
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,target)

    def add_health(self, root, *, ages=0, missing=(), contradictory=False):
        source={}
        now=datetime.now(timezone.utc)
        for name in EXPECTED:
            state='stale' if name in missing else 'fresh'
            source[name]={
                'state':state,
                'date':now.date().isoformat() if state=='fresh' else '2026-10-01',
                'reason':'' if state=='fresh' else 'Cached old report',
            }
        document={
            'schema':'wp21-health-v1',
            'all_sources_fresh':not missing,
            'sources':source,
            'generated_at_utc':(now-timedelta(hours=ages)).isoformat(),
        }
        if contradictory:
            document['all_sources_fresh']=not document['all_sources_fresh']
        path=root/'docs/data/quellenstatus_21.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(document),encoding='utf-8')
        return path

    def test_live_publication_requires_fresh_operational_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.copy_minimal(root)
            with self.assertRaisesRegex(ValueError,'Betriebsstatus fehlt'):
                evaluate(root,require_source_health=True)
            self.add_health(root)
            audited=evaluate(root,require_source_health=True)
            self.assertEqual(audited['public_source_health']['fresh_sources'],7)
            self.assertEqual(audited['public_source_health']['source_count'],7)
            self.assertEqual(audited['automatically_imported_unverified_measures'],0)

    def test_feed_outage_disclosed_not_misreported_as_zero_sanctions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.copy_minimal(root)
            self.add_health(root,missing=('scan_21.json','dip_live_21.json'))
            audited=evaluate(root,require_source_health=True)
            health=audited['public_source_health']
            self.assertEqual(health['fresh_sources'],5)
            self.assertEqual(len(health['missing_stale_or_invalid_sources']),2)
            self.assertTrue(health['source_outage_does_not_change_verified_counts'])
            self.assertEqual(audited['verified_21st_term_partial_items'],8)

    def test_outdated_or_contradictory_source_manifest_cannot_ship(self):
        for kwargs in ({'ages':72},{'contradictory':True}):
            with self.subTest(kwargs=kwargs),tempfile.TemporaryDirectory() as d:
                root=Path(d);self.copy_minimal(root)
                self.add_health(root,**kwargs)
                with self.assertRaises(ValueError):
                    evaluate(root,require_source_health=True)

    def test_partial_term_cannot_be_mislabeled_total(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.copy_minimal(root)
            f=root/'docs/data/ordnungsrufe_21.json'
            data=json.loads(f.read_text())
            data['meta']['incomplete']=False
            f.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                evaluate(root)

    def test_source_data_tamper_is_not_silently_published(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.copy_minimal(root)
            f=root/'docs/data/ordnungsrufe.json'
            data=json.loads(f.read_text())
            data['records'][0]['source']='https://not-bundestag.example/20/20001.pdf'
            f.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'CSV/JSON'):
                evaluate(root)

    def test_frontend_rejects_missing_warning_or_wrong_script_sequence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.copy_minimal(root)
            f=root/'docs/index.html'
            f.write_text(f.read_text().replace(
                '<script src="verified_contract.js" defer></script>',''))
            with self.assertRaisesRegex(ValueError,'Reihenfolge'):
                evaluate(root)

    def test_successful_gate_writes_only_temporary_report(self):
        with tempfile.TemporaryDirectory() as d:
            files_before={p:Path(p).read_bytes() for p in PROTECTED}
            json_path=Path(d)/'release.json'
            md_path=Path(d)/'release.md'
            report=run(Path('.'),json_path,md_path)
            self.assertEqual(json.loads(json_path.read_text())['status'],STATUS)
            self.assertIn('keine vollständige',md_path.read_text())
            self.assertTrue(report['requires_explicit_human_merging_decision'])
            self.assertEqual(files_before,{p:Path(p).read_bytes() for p in PROTECTED})


if __name__=='__main__':
    unittest.main()
