"""Separate official objections outside the 18-priority source dossier."""
import json
import tempfile
import unittest
from pathlib import Path

from wp21_weitere_einspruchsberichte import (
    EVIDENCE, SOURCES, OTHER_MEASURE, OFFICIAL_ARTICLE_CASES, PROTOCOL40,
    validate, build_report, render_markdown, run)


class IndependentAdditionalObjectionTests(unittest.TestCase):
    def test_13_independent_objections_from_10_official_articles(self):
        cases=validate()
        self.assertEqual(len(cases),13)
        self.assertEqual(len(SOURCES),10)
        self.assertEqual(len(OFFICIAL_ARTICLE_CASES),10)
        self.assertEqual(len({row['source'] for row in EVIDENCE}),10)
        self.assertTrue(all(x['decision']=='einspruch_zurueckgewiesen'
                            and x['sanction_type']=='ordnungsruf'
                            for x in cases.values()))

    def test_four_november_25_votes_distinguish_two_janich_measures(self):
        rows=[r for r in EVIDENCE if r['source']==SOURCES['2025nov13']]
        self.assertEqual(len(rows),4)
        self.assertEqual(sorted(x['individual_objection_ordinal'] for x in rows
                         if x['person']=='Steffen Janich'),[1,2])
        self.assertEqual({x['original_date'] for x in rows},{'2025-11-13'})
        self.assertEqual({x['decision_date'] for x in rows},{'2025-11-25'})

    def test_five_original_grants_but_only_four_rejected_objections_in_40_42(self):
        original=PROTOCOL40['original_grants_by_person']
        votes=PROTOCOL40['rejected_objections_in_this_article_by_person']
        self.assertEqual(original,{'Martin Sichert':1,'Steffen Janich':2,
                                   'Kay Gottschalk':2})
        self.assertEqual(votes,{'Martin Sichert':1,'Steffen Janich':2,
                                'Kay Gottschalk':1})
        result=build_report()
        snap=result['original_40_and_vote_42_source_comparison']
        self.assertEqual(snap['five_originally_issued_calls'],5)
        self.assertEqual(snap['four_objections_rejected_in_vote_42'],4)
        self.assertTrue(snap['second_gottschalk_grant_not_resolved_by_this_article'])
        self.assertIsNone(snap['legally_effective_measure_count_from_these_sources'])
        local=[x for x in result['cases'] if x['original_session']==40]
        self.assertEqual(len(local),4)
        self.assertEqual({x['original_plenary_pdf_page_for_40'] for x in local},
                         {'https://dserver.bundestag.de/btp/21/21040.pdf#P.4626',
                          'https://dserver.bundestag.de/btp/21/21040.pdf#P.4635'})
        self.assertEqual({x['decision_plenary_pdf_page_for_40'] for x in local},
                         {'https://dserver.bundestag.de/btp/21/21042.pdf#P.4865'})

    def test_twice_brandner_and_multiple_reichardt_dates_are_not_same_case(self):
        june=[r for r in EVIDENCE if r['person']=='Stephan Brandner'
              and r['original_date'].startswith('2025-06')]
        self.assertEqual({x['original_date'] for x in june},
                         {'2025-06-05','2025-06-06'})
        self.assertEqual({x['decision_date'] for x in june},
                         {'2025-06-06','2025-06-24'})
        reichardt=[r for r in EVIDENCE if r['person']=='Martin Reichardt']
        self.assertEqual({r['original_date'] for r in reichardt},
                         {'2025-11-26','2025-12-18','2026-05-07'})
        self.assertEqual({r['original_session'] for r in reichardt},{None,77})

    def test_two_preverified_originals_are_not_recounted(self):
        result=build_report()
        self.assertEqual(result['additional_separately_rejected_objections'],13)
        self.assertEqual(result['previously_curated_priority_rejections'],4)
        self.assertEqual(result['documented_total_objections_in_both_corpus_snapshots'],17)
        self.assertEqual(result['already_individually_verified_originals_in_partial_ledger'],2)
        self.assertFalse(result['public_counters_modified'])
        self.assertFalse(result['historical_coverage_is_complete'])
        self.assertEqual(result['automatically_confirmed_additional_sanctions'],0)
        self.assertEqual(result['automatically_rescinded_sanctions'],0)
        known=[x for x in result['cases'] if x['original_session'] is not None]
        self.assertEqual({x['original_session'] for x in known},{40,77,90})
        self.assertEqual(sum(x['original_session']==40 for x in known),4)
        self.assertTrue(all(x['prior_verified_counter_reference_present']
                            and x['reviewed_effective_measures_in_existing_partial_ledger']==1
                            for x in known if x['original_session'] in (77,90)))
        self.assertTrue(all(x['reviewed_effective_measures_in_existing_partial_ledger']==0
                            for x in known if x['original_session']==40))
        self.assertTrue(all(not x['verified_individual_effective_sanction_from_this_appeal']
                            for x in result['cases']))

    def test_16_october_reichardt_ordnungsgeld_explicit_negative_control(self):
        other=build_report()['excluded_distinct_ordnungsgeld_appeal']
        self.assertEqual(other['sanction_type'],'ordnungsgeld')
        self.assertEqual(other['person'],'Martin Reichardt')
        self.assertEqual(other['original_date'],'2026-10-15')
        self.assertEqual(other['decision_date'],'2026-10-16')
        self.assertNotIn(other['source'],{r['source'] for r in EVIDENCE})
        with self.assertRaisesRegex(ValueError,'Negativkontrolle'):
            validate(other={**OTHER_MEASURE,'sanction_type':'ordnungsruf'})

    def test_source_specific_dates_names_ordinal_and_sitting_cannot_drift(self):
        changes=(
            (0,'original_date','2025-06-04'),
            (0,'decision_date','2025-06-07'),
            (0,'person','Martin Sichert'),
            (0,'source',SOURCES['2025jun06']),
            (5,'individual_objection_ordinal',3),
            (5,'original_session',52),
            (5,'sanction_type','ordnungsgeld'),
            (5,'decision','einspruch_aufgehoben'),
            (6,'person','Kay Gottschalk'),
            (11,'original_session',65),
        )
        for i,field,value in changes:
            with self.subTest(i=i,field=field):
                rows=[dict(x) for x in EVIDENCE]
                rows[i][field]=value
                with self.assertRaises(ValueError):
                    validate(rows)

    def test_missing_or_duplicate_janich_cannot_pass(self):
        with self.assertRaises(ValueError):
            validate(EVIDENCE[:-1])
        rows=[dict(x) for x in EVIDENCE]
        rows[6]['individual_objection_ordinal']=1
        with self.assertRaisesRegex(ValueError,'unterscheidbare'):
            validate(rows)

    def test_source_urls_must_retain_official_bundestag_domain(self):
        rows=[dict(x) for x in EVIDENCE]
        rows[0]['source']='https://bad.example/dokumente/textarchiv/2025/kw23-de-einspruch-ordnungsruf-1084838'
        with self.assertRaises(ValueError):
            validate(rows)

    def test_markdown_is_unambiguous_about_non_counts(self):
        md=render_markdown(build_report())
        self.assertIn('13 weitere eigenständig dokumentierte',md)
        self.assertIn('Steffen Janich',md)
        self.assertIn('fünf ursprünglich erteilte Ordnungsrufe',md)
        self.assertIn('Ordnungsgeld',md)
        self.assertIn('bereits bestätigt (keine Doppelzählung)',md)
        self.assertNotIn('13 neue wirksame Ordnungsrufe',md)

    def test_report_files_written_only_after_complete_validation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            r=run(root/'other.json',root/'other.md')
            self.assertEqual(r['automatically_confirmed_additional_sanctions'],0)
            self.assertEqual(json.loads((root/'other.json').read_text())
                             ['additional_official_articles'],10)
            self.assertIn('Kay Gottschalk',(root/'other.md').read_text())
            with self.assertRaises(FileNotFoundError):
                run(root/'bad.json',root/'bad.md',root/'missing.csv')
            self.assertFalse((root/'bad.json').exists())
            self.assertFalse((root/'bad.md').exists())

    def test_renderer_must_not_approve_measures_or_drop_four_previous_decisions(self):
        r=build_report()
        with self.assertRaises(ValueError):
            render_markdown({**r,'automatically_confirmed_additional_sanctions':1})
        with self.assertRaises(ValueError):
            render_markdown({**r,'documented_total_objections_in_both_corpus_snapshots':13})


if __name__=='__main__':
    unittest.main()
