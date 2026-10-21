"""Review-only source proofs for the second five-case WP21 batch."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wp21_five_origins import PRIMARY_PAGES, ROOT, build, markdown, main


class FiveOriginalProofsTests(unittest.TestCase):
    def test_exact_five_primary_pdf_sources_and_original_line_anchors(self):
        d=build()
        self.assertEqual(d['origin_issuances_individually_located_in_official_pdfs'],5)
        self.assertEqual(d['individual_effectiveness_reviews_completed'],0)
        self.assertEqual(d['newly_approved_effective_sanctions'],0)
        self.assertFalse(d['protected_counters_changed'])
        self.assertEqual(
            [(x['session'],x['person'],x['original_xml_line'])
             for x in d['cases']],
            [(53,'Heidi Reichinnek',6149),
             (57,'Bernd Baumann',1487),
             (61,'Ulrich von Zons',4557),
             (65,'Luigi Pantisano',5104),
             (67,'Kathrin Gebel',3164)])
        self.assertTrue(all(x['original_source_individually_located']
                            for x in d['cases']))
        self.assertTrue(all(not x['subsequent_effectiveness_and_appeals_independently_reviewed']
                            for x in d['cases']))
        self.assertTrue(all(x['curated_appeal_absence_is_no_evidence_of_no_appeal']
                            for x in d['cases']))

    def test_exact_pdf_page_links_and_no_transferring_chair_warning(self):
        d=build()
        self.assertEqual(
            [x['original_pdf_url'] for x in d['cases']],[
                'https://dserver.bundestag.de/btp/21/21053.pdf#page=159',
                'https://dserver.bundestag.de/btp/21/21057.pdf#page=31',
                'https://dserver.bundestag.de/btp/21/21061.pdf#page=76',
                'https://dserver.bundestag.de/btp/21/21065.pdf#page=114',
                'https://dserver.bundestag.de/btp/21/21067.pdf#page=44',
            ])
        zons=d['cases'][2]
        self.assertIn('Brosius-Gersdorf',zons['original_issuance_context'])
        self.assertIn('Bodo Ramelow',zons['presiding_officer'])
        self.assertEqual(zons['newly_approved_effective_sanctions'],0)

    def test_changed_source_identity_and_duplicate_rejected(self):
        wrong=list(copy.deepcopy(PRIMARY_PAGES))
        row=list(wrong[0])
        row[1]=54
        wrong[0]=tuple(row)
        with self.assertRaises(ValueError):
            build(sources=tuple(wrong))
        wrong=list(copy.deepcopy(PRIMARY_PAGES))
        wrong[1]=wrong[0]
        with self.assertRaises(ValueError):
            build(sources=tuple(wrong))
        wrong=list(copy.deepcopy(PRIMARY_PAGES))
        row=list(wrong[3])
        row[4]=0
        wrong[3]=tuple(row)
        with self.assertRaises(ValueError):
            build(sources=tuple(wrong))

    def test_never_conclude_absent_appeal_or_add_approved_counter(self):
        d=build()
        self.assertIn('kein Schluss',d['warning'].lower())
        self.assertEqual(d['newly_approved_effective_sanctions'],0)
        with self.assertRaises(ValueError):
            markdown({**d,'newly_approved_effective_sanctions':1})
        self.assertIn('noch offen',markdown(d))

    def test_outputs_only_to_non_public_audit_with_no_statistic_mutation(self):
        (ROOT/'.audit').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.audit') as tmp:
            with patch('sys.argv',['five','--output-dir',tmp]):
                main()
            payload=json.loads((Path(tmp)/'source_records.json').read_text(
                encoding='utf-8'))
            self.assertEqual(payload['newly_approved_effective_sanctions'],0)
            self.assertEqual(len(payload['cases']),5)
            self.assertIn('Luigi Pantisano',Path(tmp,'source_records.md')
                          .read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as tmp:
            with patch('sys.argv',['five','--output-dir',tmp]):
                with self.assertRaisesRegex(ValueError,'nichtöffentliche'):
                    main()

if __name__=='__main__':
    unittest.main()
