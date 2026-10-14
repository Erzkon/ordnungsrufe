"""Isolationstests fuer den GitHub-Pages-Export; kein Netzwerk erforderlich."""
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from export_webdaten import build, valid_proof

BASE = Path(__file__).resolve().parents[1]


class TestWebExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = BASE / 'daten/wirksame_ordnungsrufe_20wp.csv'
        cls.report = BASE / 'daten/korrekturbericht_20wp.json'

    def test_expected_record_counts_and_personalities(self):
        payload = build(self.data, self.report)
        rows = payload['records']
        self.assertEqual(len(rows), 135)
        self.assertEqual(payload['meta']['events'], 123)
        self.assertEqual(sum(r['person'] == 'Beatrix von Storch' for r in rows), 18)
        self.assertEqual(sum(r['person'] == 'Stephan Brandner' for r in rows), 20)
        self.assertEqual(payload['meta']['rescinded_excluded'], 2)
        self.assertEqual(sum(r['group'] == 'AfD' for r in rows), 84)

    def test_only_valid_original_pdf_links(self):
        for r in build(self.data, self.report)['records']:
            self.assertTrue(valid_proof(r['source']), r['source'])

    def test_pdf_source_rejects_external_hosts_and_missing_page(self):
        self.assertFalse(valid_proof('javascript:alert(1)'))
        self.assertFalse(valid_proof('https://evil.example/btp/20/20031.pdf#page=12'))
        self.assertFalse(valid_proof('https://dserver.bundestag.de/btp/20/20031.pdf'))
        self.assertFalse(valid_proof('https://dserver.bundestag.de/btp/20/20031.pdf#page=abc'))
        self.assertTrue(valid_proof('https://dserver.bundestag.de/btp/20/20031.pdf#page=78'))

    def test_duplicate_or_changed_counts_raise(self):
        with self.data.open(encoding='utf-8', newline='') as reader_file:
            rows = list(csv.DictReader(reader_file))
        fields = list(rows[0])
        rows.append(copy.deepcopy(rows[0]))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'wrong.csv'
            with path.open('w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(ValueError):
                build(path, self.report)

    def test_changed_report_is_rejected(self):
        report = json.loads(self.report.read_text(encoding='utf-8'))
        report['beatrix_von_storch'] = 19
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'wrong.json'
            path.write_text(json.dumps(report), encoding='utf-8')
            with self.assertRaises(ValueError):
                build(self.data, path)


if __name__ == '__main__':
    unittest.main()
