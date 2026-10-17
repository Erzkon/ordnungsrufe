"""Deterministic offline checks for the real multi-page 24h DIP smoke test."""
import unittest
from datetime import datetime, timezone

from wp21_dip_live_probe import recent_pagination_probe


NOW = datetime(2026, 10, 15, 9, tzinfo=timezone.utc)


def item(ident, title):
    return {'id': ident, 'wahlperiode': 21, 'titel': title, 'abstract': '',
            'datum': '2026-10-15', 'aktualisiert': NOW.isoformat()}


class LivePaginationTests(unittest.TestCase):
    def test_multpage_trial_uses_injected_api_and_finds_review_text(self):
        requests = []
        def load(params, key):
            requests.append(dict(params))
            self.assertEqual(key, 'test')
            if 'cursor' not in params:
                return {'numFound': 3, 'cursor': 'next',
                        'documents': [item(1, 'Ordnungsruf'), item(2, 'Haushalt')]}
            return {'numFound': 3, 'cursor': None,
                    'documents': [item(3, 'Einspruch gegen Ordnungsruf')]}
        report = recent_pagination_probe(load, 'test', NOW)
        self.assertEqual(report, {'documents': 3, 'pages': 2,
                                  'title_or_abstract_matches': 2})
        self.assertEqual(requests[0]['f.wahlperiode'], '21')
        self.assertEqual(requests[1]['cursor'], 'next')
        self.assertEqual(len(requests), 2)

    def test_truncated_result_must_fail_even_for_smoke_test(self):
        with self.assertRaises(ValueError):
            recent_pagination_probe(
                lambda p,k: {'numFound': 2, 'cursor': None,
                             'documents': [item(1, 'Ordnungsruf')]},
                'test', NOW)

    def test_unexpected_period_fails_closed(self):
        bad = item(1, 'Ordnungsruf')
        bad['wahlperiode'] = 20
        with self.assertRaises(ValueError):
            recent_pagination_probe(
                lambda p,k: {'numFound': 1, 'cursor': None, 'documents': [bad]},
                'test', NOW)


if __name__ == '__main__':
    unittest.main()
