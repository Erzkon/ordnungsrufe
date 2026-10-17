"""Conservative diff of newly published or edited official Bundestag PDFs."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from wp21_minuten_delta import compare, markdown, run, validate

BASELINE_PATH = Path('daten/wp21_amtliche_protokolle_baseline.json')


def baseline():
    return json.loads(BASELINE_PATH.read_text(encoding='utf-8'))


def current(b=None):
    b = b or baseline()
    rows = []
    for sid in range(100, 41, -1):
        record = b['records'][str(sid)]
        hits = []
        if sid == 42:
            hits.append({
                'session': sid, 'source': record['url'], 'pdf_page': 2,
                'known_first_objection_only': True,
                'automatic_legal_conclusion': False, 'public_count_delta': 0,
                'context_excerpt': 'Kay Gottschalk Einspruch erster Ordnungsruf'
            })
        rows.append({
            'session': sid, 'official_url': record['url'],
            'pdf_sha256': record['sha256'], 'pages_checked': 3,
            'name_appeal_contexts': hits,
            'possible_later_context_count': 0,
        })
    return {
        'schema': 'wp21-all-published-official-resolution-minutes-v1',
        'official_catalogue': {
            'latest_published_official_minute': rows[0]['session']
        },
        'minutes_checked': len(rows),
        'pages_checked': sum(x['pages_checked'] for x in rows),
        'source_reports': rows,
        'later_review_context_count': 0,
        'no_publication_after_latest_does_not_prove_legal_absence': True,
        'second_gottschalk_measure_legality_unresolved': True,
        'public_counter_delta': 0,
        'automatically_confirmed_effective_sanctions': 0,
        'automatically_rescinded_sanctions': 0,
    }


class OfficialMinutesDelta(unittest.TestCase):
    def test_provenance_is_real_successful_complete_historical_audit(self):
        b = baseline()
        self.assertEqual(len(b['records']), 59)
        self.assertEqual(b['source_report_sha256'],
                         'ceb870a52658b46993f468433abcb722be3d4a78cb5d672e0301064a14fa207d')
        self.assertIn('/actions/runs/39055803206', b['source_run'])
        self.assertTrue(validate(b, current(b)))

    def test_unchanged_historical_record_does_not_trigger_daily_alert(self):
        r = compare(baseline(), current())
        self.assertFalse(r['manual_review_required'])
        self.assertEqual(r['new_official_minutes'], [])
        self.assertEqual(r['revised_historical_pdf_sources'], [])
        self.assertEqual(r['later_named_appeal_contexts'], [])
        self.assertEqual(r['protected_public_counter_delta'], 0)
        self.assertIn('Kein Zählerupdate', markdown(r))

    def test_new_publication_is_a_manual_review_not_a_legal_decision(self):
        now = current()
        row = {
            'session': 101,
            'official_url': 'https://www.bundestag.de/resource/blob/1234567/amtpr21101.pdf',
            'pdf_sha256': 'a' * 64, 'pages_checked': 5,
            'name_appeal_contexts': [], 'possible_later_context_count': 0,
        }
        now['source_reports'].insert(0, row)
        now['minutes_checked'] += 1
        now['pages_checked'] += 5
        now['official_catalogue']['latest_published_official_minute'] = 101
        report = compare(baseline(), now)
        self.assertTrue(report['manual_review_required'])
        self.assertEqual(len(report['new_official_minutes']), 1)
        self.assertEqual(report['new_official_minutes'][0]['session'], 101)
        self.assertTrue(report['no_automatic_legal_outcome'])
        self.assertEqual(report['automatically_confirmed_effective_sanctions'], 0)

    def test_revised_historical_source_sha_or_url_detected_individually(self):
        for kind in ('bytes', 'url'):
            now = current()
            row = next(x for x in now['source_reports'] if x['session'] == 77)
            if kind == 'bytes':
                row['pdf_sha256'] = 'f' * 64
            else:
                row['official_url'] = (
                    'https://www.bundestag.de/resource/blob/7654321/amtpr21077.pdf')
            r = compare(baseline(), now)
            self.assertEqual([x['session'] for x in r['revised_historical_pdf_sources']], [77])
            self.assertEqual(r['revised_historical_pdf_sources'][0]['bytes_changed'],
                             kind == 'bytes')
            self.assertEqual(r['revised_historical_pdf_sources'][0]['url_changed'],
                             kind == 'url')

    def test_named_second_objection_is_unverified_even_when_wording_direct(self):
        now = current()
        row = next(x for x in now['source_reports'] if x['session'] == 85)
        row['name_appeal_contexts'] = [{
            'session': 85, 'source': row['official_url'], 'pdf_page': 2,
            'context_excerpt': 'Kay Gottschalk Einspruch gegen zweiten Ordnungsruf',
            'second_measure_explicitly_named': True,
            'known_first_objection_only': False,
            'automatic_legal_conclusion': False, 'public_count_delta': 0,
        }]
        row['possible_later_context_count'] = 1
        now['later_review_context_count'] += 1
        r = compare(baseline(), now)
        self.assertTrue(r['manual_review_required'])
        self.assertTrue(r['later_named_appeal_contexts'][0]['possible_second_in_named_section'])
        self.assertEqual(r['later_named_appeal_contexts'][0]['automatic_decision_status'],
                         'unverified')
        self.assertEqual(r['protected_public_counter_delta'], 0)

    def test_first_reference_cannot_be_reclassified_or_missing(self):
        now = current()
        row = next(x for x in now['source_reports'] if x['session'] == 42)
        row['name_appeal_contexts'] = []
        with self.assertRaisesRegex(ValueError, '21/042'):
            compare(baseline(), now)
        now = current()
        row = next(x for x in now['source_reports'] if x['session'] == 42)
        row['name_appeal_contexts'][0]['known_first_objection_only'] = False
        with self.assertRaisesRegex(ValueError, '21/042'):
            compare(baseline(), now)

    def test_missing_session_duplicate_or_wrong_pdf_cannot_be_ignored(self):
        for kind in ('missing', 'duplicate', 'mismatch'):
            now = current()
            if kind == 'missing':
                now['source_reports'] = [x for x in now['source_reports']
                                         if x['session'] != 73]
                now['minutes_checked'] -= 1
                now['pages_checked'] -= 3
            elif kind == 'duplicate':
                now['source_reports'][3] = copy.deepcopy(now['source_reports'][2])
            else:
                now['source_reports'][3]['official_url'] = (
                    'https://www.bundestag.de/resource/blob/1234567/amtpr21101.pdf')
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                compare(baseline(), now)

    def test_bad_baseline_provenance_and_published_count_fail(self):
        b = baseline()
        b['source_report_sha256'] = 'a'*64
        with self.assertRaisesRegex(ValueError, 'Referenz'):
            compare(b, current())
        now = current()
        now['later_review_context_count'] = 5
        with self.assertRaisesRegex(ValueError, 'vollständig'):
            compare(baseline(), now)

    def test_no_auto_count_or_false_negative_can_be_published(self):
        r = compare(baseline(), current())
        for mod in ({'protected_public_counter_delta': 1},
                    {'no_automatic_legal_outcome': False},
                    {'second_gottschalk_measure_legality_unresolved': False},
                    {'other_nonplenary_documents_and_unpublished_sessions_not_excluded': False},
                    {'reference_baseline_not_updated_by_this_scan': False}):
            with self.subTest(mod=mod), self.assertRaises(ValueError):
                markdown({**r, **mod})

    def test_failed_source_never_writes_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            now = current()
            now['public_counter_delta'] = 1
            (root/'current.json').write_text(json.dumps(now), encoding='utf-8')
            output = root/'delta.json'
            with self.assertRaises(ValueError):
                run(root/'current.json', BASELINE_PATH, output, root/'delta.md')
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
