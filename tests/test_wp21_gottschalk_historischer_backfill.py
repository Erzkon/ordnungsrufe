"""Fail-closed historical, multi-window DIP discovery for Gottschalk."""
import tempfile
import unittest
from pathlib import Path

from wp21_gottschalk_historischer_backfill import (
    windows, review, markdown, run,
)


def first():
    return {
        'id': '681803', 'vorgang_id': '328225', 'wahlperiode': 21,
        'datum': '2025-11-25', 'aktualisiert': '2026-10-17T12:00:00+00:00',
        'titel': 'Einspruch Kay Gottschalk gegen erste Ordnungsmaßnahme',
        'abstract': '', 'vorgangsposition': 'Abstimmung',
        'beschlussfassung': [{
            'beschlusstenor': 'Zurückweisung des Einspruchs'}],
    }


def second():
    return {
        'id': '699999', 'vorgang_id': '338888', 'wahlperiode': 21,
        'datum': '2026-01-05', 'aktualisiert': '2026-10-17T12:00:00+00:00',
        'titel': 'Anderer Verfahrensname',
        'abstract': 'Einspruch Kay Gottschalk gegen zweite Ordnungsmaßnahme',
        'vorgangsposition': 'Abstimmung',
    }


class HistoricalBackfill(unittest.TestCase):
    def test_windows_are_nonoverlapping_and_bounded(self):
        result = windows('2025-11-13', '2026-01-15')
        self.assertEqual(result, [
            ('2025-11-13', '2025-12-27'),
            ('2025-12-28', '2026-01-15'),
        ])
        for left, right in zip(result, result[1:]):
            self.assertLess(left[1], right[0])
        self.assertEqual(len(windows('2025-11-13', '2026-10-17')), 8)

    def test_full_cross_window_search_surfaces_later_second_candidate(self):
        params_seen = []
        def load(params, key):
            params_seen.append(params)
            self.assertNotIn('f.titel', params)
            self.assertEqual(key, 'test')
            a,b = params['f.datum.start'],params['f.datum.end']
            documents = [
                p for p in (first(), second()) if a <= p['datum'] <= b]
            return {'documents': documents, 'numFound': len(documents),
                    'cursor': None}
        report = review('2025-11-13', '2026-01-15',
                        key='test', load=load)
        self.assertEqual(report['completed_windows'], 2)
        self.assertEqual(report['complete_position_count'], 2)
        self.assertTrue(report['known_first_vote_reference_checked'])
        self.assertTrue(report['manual_review_required'])
        self.assertEqual(
            [p['position_id'] for p in report['new_nonbaseline_candidates']],
            ['699999'])
        self.assertEqual(report['public_counter_delta'], 0)
        self.assertEqual(len(params_seen), 2)
        self.assertIn('Keine automatische Zählerfreigabe', markdown(report))

    def test_no_candidate_outside_known_is_not_legal_absence(self):
        def load(params, key):
            d = [p for p in (first(),)
                 if params['f.datum.start'] <= p['datum'] <= params['f.datum.end']]
            return {'documents': d, 'numFound': len(d), 'cursor': None}
        r = review('2025-11-13', '2026-01-15',
                   key='test', load=load)
        self.assertFalse(r['manual_review_required'])
        self.assertTrue(r['missing_second_vote_is_not_proven'])
        self.assertTrue(r['other_dates_source_types_or_non_named_positions_unchecked'])

    def test_failed_later_window_writes_no_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            def load(params, key):
                if params['f.datum.start'] > '2025-12-01':
                    raise ValueError('simulated DIP failure')
                return {'documents': [first()], 'numFound': 1,
                        'cursor': None}
            target = Path(tmp)/'history.json'
            with self.assertRaisesRegex(ValueError, 'simulated'):
                run('2025-11-13', '2026-01-15',
                    target, Path(tmp)/'history.md', key='test', load=load)
            self.assertFalse(target.exists())

    def test_forged_legal_inference_fails(self):
        def load(params, key):
            d = [p for p in (first(),)
                 if params['f.datum.start'] <= p['datum'] <= params['f.datum.end']]
            return {'documents': d, 'numFound': len(d), 'cursor': None}
        r = review('2025-11-13', '2025-12-01',
                   key='test', load=load)
        for changed in (
                {'public_counter_delta': 1},
                {'missing_second_vote_is_not_proven': False},
                {'title_filter_used': True},
                {'second_measure_legal_effectiveness_unresolved': False}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                markdown({**r, **changed})

    def test_span_limit_and_future_rejected(self):
        for args in [('2025-11-12','2026-01-15'),
                     ('2025-11-13','2026-12-31'),
                     ('2026-01-15','2025-12-01')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                windows(*args)


if __name__ == '__main__':
    unittest.main()
