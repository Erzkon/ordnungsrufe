"""Version-1.0 release candidate: only bounded and already verified counts."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

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
                'docs/index.html','docs/app.js','docs/verified_contract.js']:
            target=root/p
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,target)

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
