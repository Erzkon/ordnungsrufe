"""Read-only title-independent DIP procedure position search regressions."""
import tempfile
import unittest
from pathlib import Path

from wp21_gottschalk_unkategorisierte_positionen import (
    pages, inspect, interval, markdown, run,
)

START, END = '2025-11-13', '2025-12-12'


def position(id, parent='328225', title='', *, day='2025-11-25',
             step='Abstimmung', abstract='', activities=None, tenor=None):
    return {
        'id': str(id), 'vorgang_id': parent, 'wahlperiode': 21,
        'datum': day, 'aktualisiert': '2026-10-17T12:00:00+00:00',
        'titel': title, 'vorgangsposition': step, 'abstract': abstract,
        'aktivitaet_anzeige': activities or [],
        'beschlussfassung': [{'beschlusstenor': tenor}] if tenor else [],
    }


def first():
    return position(
        '681803', title='Einspruch Kay Gottschalk gegen erste Ordnungsmaßnahme',
        tenor='Zurückweisung des Einspruchs')


class UnfilteredPositions(unittest.TestCase):
    def test_known_vote_anchor_and_strict_noncounting(self):
        report = inspect([first()], START, END, 1)
        self.assertTrue(report['known_first_appeal_verified'])
        self.assertFalse(report['manual_review_required'])
        self.assertTrue(report['absence_of_second_appeal_not_established'])
        self.assertEqual(report['public_counter_delta'], 0)
        self.assertIn('keine', markdown(report).lower())

    def test_other_title_candidate_in_abstract_or_activity(self):
        alternative = position(
            '699991', parent='337777', title='Beratung und Entscheidung',
            abstract='Einspruch Kay Gottschalk gegen die zweite Ordnungsmaßnahme')
        activity = position(
            '699992', parent='337778', title='Sonstiger Vorgang',
            activities=[{'titel': 'Einspruch von Kay Gottschalk'}])
        r = inspect([first(), alternative, activity], START, END, 1)
        self.assertEqual(r['other_candidate_positions'], 2)
        self.assertEqual(r['candidates'][1]['name_fields'], ['abstract'])
        self.assertTrue(r['candidates'][1]['potential_second_measure'])
        self.assertEqual(r['candidates'][2]['name_fields'],
                         ['aktivitaet_anzeige.titel'])
        self.assertEqual(r['automatically_confirmed_effective_sanctions'], 0)

    def test_historical_original_position_is_baseline_not_new_appeal(self):
        historical = position('681046', title='Zwei Ordnungsrufe an Kay Gottschalk',
                              day='2025-11-13', step='Ordnungsruf')
        report = inspect([first(), historical], START, END, 1)
        self.assertFalse(report['manual_review_required'])
        self.assertEqual(report['other_candidate_positions'], 0)
        self.assertEqual(report['known_baseline_position_ids'],
                         ['681046', '681803'])
        origin = next(row for row in report['candidates']
                      if row['position_id'] == '681046')
        self.assertTrue(origin['known_original_position'])
        altered = historical.copy()
        altered['datum'] = '2025-12-01'
        with self.assertRaisesRegex(ValueError, 'ursprüngliche'):
            inspect([first(), altered], START, END, 1)

    def test_related_parent_without_name_is_safely_discovered(self):
        other = position('699999', title='Weitere Position')
        r = inspect([first(), other], START, END, 1)
        self.assertTrue(r['manual_review_required'])
        self.assertTrue(r['candidates'][1]['known_parent'])

    def test_person_without_appeal_context_not_a_found_appeal(self):
        nonlegal = position('699997', parent='339999', title='Rede von Kay Gottschalk')
        self.assertEqual(len(inspect([first(), nonlegal], START, END, 1)
                             ['candidates']), 1)

    def test_known_vote_cannot_be_missing_or_relabelled(self):
        with self.assertRaisesRegex(ValueError, '681803'):
            inspect([], START, END, 1)
        tampered = first()
        tampered['beschlussfassung'] = []
        with self.assertRaisesRegex(ValueError, 'verändert'):
            inspect([tampered], START, END, 1)

    def test_complete_pagination_date_only_no_title_filter(self):
        docs = [position(str(700000+i), '339999', 'Haushaltsdebatte')
                for i in range(101)] + [first()]
        seen = []
        def load(params, key):
            seen.append(params.copy())
            self.assertEqual(key, 'test')
            self.assertEqual(params['f.wahlperiode'], '21')
            self.assertEqual(params['f.datum.start'], START)
            self.assertEqual(params['f.datum.end'], END)
            self.assertNotIn('f.titel', params)
            if 'cursor' in params:
                return {'documents': docs[100:], 'numFound': len(docs),
                        'cursor': None}
            return {'documents': docs[:100], 'numFound': len(docs),
                    'cursor': 'next'}
        rows, count = pages(START, END, 'test', load)
        self.assertEqual((len(rows), count, len(seen)), (102, 2, 2))
        self.assertTrue(inspect(rows, START, END, count)
                        ['known_first_appeal_verified'])

    def test_cursor_drift_duplicates_and_mismatched_dates_fail(self):
        for mode in ('missing', 'duplicate', 'changing_total'):
            calls = []
            def loader(params, key):
                calls.append(params)
                if len(calls) == 1:
                    return {'documents': [first()], 'numFound': 2, 'cursor': 'next'}
                if mode == 'missing':
                    return {'documents': [], 'numFound': 2, 'cursor': None}
                if mode == 'duplicate':
                    return {'documents': [first()], 'numFound': 2, 'cursor': None}
                return {'documents': [position('699998')],
                        'numFound': 3, 'cursor': None}
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                pages(START, END, 'test', loader)
        too_late = position('699998', day='2026-01-01')
        with self.assertRaises(ValueError):
            pages(START, END, 'test',
                  lambda p,k: {'documents': [too_late], 'numFound': 1,
                               'cursor': None})

    def test_atomic_absence_on_bad_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'report.json'
            with self.assertRaisesRegex(ValueError, '681803'):
                run(START, END, output, Path(tmp)/'report.md',
                    key='test', load=lambda p,k: {
                        'documents': [], 'numFound': 0, 'cursor': None})
            self.assertFalse(output.exists())

    def test_invalid_time_windows_and_positive_guard(self):
        for a,b in [('2025-11-12', END), (START,'2026-10-17'),
                    ('2025-12-30','2025-11-25'), (START,'2099-01-01')]:
            with self.subTest(a=a,b=b), self.assertRaises(ValueError):
                interval(a,b)
        with self.assertRaises(ValueError):
            pages(START, END, 'test', max_pages=161)

    def test_publishing_legal_outcome_and_absence_forbidden(self):
        r = inspect([first()], START, END, 1)
        for changes in (
                {'public_counter_delta': 1},
                {'automatically_confirmed_effective_sanctions': 1},
                {'absence_of_second_appeal_not_established': False},
                {'unsearched_dates_and_source_types_remain_open': False},
                {'second_measure_legal_effectiveness_unresolved': False}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                markdown({**r, **changes})


if __name__ == '__main__':
    unittest.main()
