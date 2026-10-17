"""Gottschalk/Mixl chronology crosswalk from independently official sources."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_wp21_gottschalk_unkategorisierte_positionen import position,first
from tests.test_wp21_gottschalk_amtliche_beschluesse import pages as official_pdf_pages
from tests.test_wp21_janich_erste_quellenkritik import examples
from tests.test_wp21_40_empfaenger_belege import original
from wp21_janich_erste_quellenkritik import inspect_rows
from wp21_40_empfaenger_belege import review as speaker_review
from wp21_40_dip_rechtsfolgen_crosswalk import (
    inspect_dip_parent, extract_mixl_position_hints,
    validate_original, reconcile, markdown, run,
)

ORIGIN = position('681046',title='Erteilung von zwei Ordnungsrufen an Kay Gottschalk',
                  step='Ordnungsruf',day='2025-11-13')


def case():
    return speaker_review(original(),inspect_rows(examples()))


def dip(with_mixl=False):
    records=[ORIGIN,first()]
    if with_mixl:
        records.append(position(
            '699985',parent='331133',day='2025-11-27',
            title='Ordnungsruf wegen Zwischenruf von Reinhard Mixl',
            step='Weitere Unterrichtung',
        ))
    return records


def check(with_mixl=False):
    return reconcile(case(),[ORIGIN,first()],dip(with_mixl),
                     1,official_pdf_pages(42))


class CrosswalkTests(unittest.TestCase):
    def test_known_original_and_one_decision_are_distinct(self):
        r=check()
        g=r['gottschalk']
        self.assertTrue(g['two_original_calls_supported_by_21_040'])
        self.assertEqual(g['original_dip_parent']['known_issuance_position_id'],'681046')
        self.assertEqual(g['original_dip_parent']['known_vote_position_id'],'681803')
        self.assertTrue(g['original_dip_parent']['dip_vote_cannot_be_applied_to_both_calls'])
        self.assertEqual(g['one_formal_rejected_objection_in_21_042']
                         ['official_minutes_source'].split('/')[-1],'amtpr21042.pdf')
        self.assertFalse(g['one_formal_rejected_objection_in_21_042']
                         ['ordinal_named_in_resolution'])
        self.assertFalse(g['one_formal_rejected_objection_in_21_042']
                         ['automatically_proves_second_objection_or_outcome'])
        self.assertEqual(g['second_appeal_status'],'unverified_not_absence_proved')
        self.assertEqual(r['public_counter_delta'],0)

    def test_mixl_can_have_metadata_hint_but_never_a_new_decision(self):
        r=check(True)
        m=r['mixl']
        self.assertEqual(m['interjection_speaker_from_official_commented_xml'],
                         'Reinhard Mixl')
        self.assertTrue(m['original_chair_issuance_did_not_name_recipient'])
        self.assertEqual([x['position_id'] for x in m['candidate_dip_positions']],
                         ['699985'])
        self.assertTrue(m['candidate_dip_positions'][0]['requires_manual_source_review'])
        self.assertEqual(m['appeal_decision_status'],'unverified')
        self.assertEqual(r['automatically_confirmed_effective_sanctions'],0)
        self.assertIn('keine bestätigte rechtswirksamkeit',markdown(r).lower())

    def test_mixl_unrelated_legislation_and_missing_name_not_counted(self):
        unrelated=position('699984',parent='335824',
                           title='Gesetz zur Aufhebung der Steuer für Antragsteller',
                           abstract='Reinhard Mixl',step='Gesetzesentwurf')
        self.assertEqual(extract_mixl_position_hints([unrelated]),[])
        same=position('699983',parent='331135',
                      title='Einspruch gegen einen Ordnungsruf ohne Empfängernamen')
        self.assertEqual(extract_mixl_position_hints([same]),[])

    def test_mixed_name_and_source_words_only_produce_review_not_proof(self):
        x=position('699998',parent='331138',title='Einspruch gegen Ordnungsruf',
                   activities=[{'titel':'Reinhard Mixl sprach im Bundestag'}])
        r=extract_mixl_position_hints([x])
        self.assertEqual(len(r),1)
        self.assertTrue(r[0]['person_link_and_procedural_vocabulary_not_a_legal_decision'])

    def test_wrong_parent_vote_and_tenor_fail_closed(self):
        for issue in ('missing_vote','wrong_parent','wrong_tenor'):
            with self.subTest(issue=issue),self.assertRaises(ValueError):
                p=copy.deepcopy([ORIGIN,first()])
                if issue=='missing_vote':
                    p=p[:1]
                elif issue=='wrong_parent':
                    p[0]['vorgang_id']='321111'
                else:
                    p[1]['beschlussfassung']=[]
                inspect_dip_parent(p)

    def test_missing_separate_known_dip_vote_fails(self):
        with self.assertRaises(ValueError):
            reconcile(case(),[ORIGIN,first()],
                      [ORIGIN],1,official_pdf_pages(42))

    def test_drifted_minute_and_unverified_original_fail_closed(self):
        with self.assertRaises(ValueError):
            reconcile(case(),[ORIGIN,first()],dip(),1,
                      [official_pdf_pages(42)[0],'Einspruch fehlt hier vollständig',
                       official_pdf_pages(42)[2]])
        changed=case()
        changed['gottschalk_immediate_second_issuance'][
            'context_supported_recipient']='Steffen Janich'
        with self.assertRaisesRegex(ValueError,'Sprecher'):
            validate_original(changed)

    def test_duplicate_mixl_metadata_or_bad_date_fails(self):
        p=position('699999',title='Reinhard Mixl Einspruch gegen Ordnungsruf')
        with self.assertRaises(ValueError):
            extract_mixl_position_hints([p,p])
        p['datum']='2026-01-05'
        with self.assertRaises(ValueError):
            extract_mixl_position_hints([p])

    def test_full_run_mock_and_not_written_on_dip_failure(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);src=base/'speaker.json';src.write_text(json.dumps(case()))
            r=run(
                src,base/'case.json',base/'case.md',key='fake',
                get_parent=lambda parent,key:[ORIGIN,first()],
                get_pages=lambda start,end,key:(dip(True),1),
                pdf_load=lambda url,size:b'%PDF synthetic source',
                extract=lambda blob:official_pdf_pages(42),
            )
            self.assertEqual(r['complete_dip_pages_examined'],1)
            self.assertEqual(r['mixl']['candidate_dip_positions'][0]['position_id'],
                             '699985')
            self.assertTrue((base/'case.json').exists())
            self.assertEqual(json.loads((base/'case.json').read_text())
                             ['public_counter_delta'],0)
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);src=base/'speaker.json';src.write_text(json.dumps(case()))
            with self.assertRaisesRegex(ValueError,'DIP source failure'):
                run(src,base/'case.json',base/'case.md',key='fake',
                    get_parent=lambda parent,key:(_ for _ in ()).throw(
                        ValueError('DIP source failure')))
            self.assertFalse((base/'case.json').exists())

    def test_rendering_cannot_rewrite_legal_conclusions(self):
        r=check()
        for changed in (
                {'public_counter_delta':1},
                {'automatically_confirmed_effective_sanctions':2},
                {'no_automatic_recipient_or_legal_effect_decision':False},
                {'other_periods_and_documents_unchecked':False},
        ):
            with self.subTest(change=changed),self.assertRaises(ValueError):
                markdown({**r,**changed})
        a=copy.deepcopy(r)
        a['gottschalk']['second_appeal_status']='rechtswirksam'
        with self.assertRaises(ValueError):
            markdown(a)


if __name__=='__main__':
    unittest.main()
