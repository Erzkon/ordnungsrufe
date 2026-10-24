"""17-parent DIP evidence: 12 new + 5 already refreshed, never counter updates."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wp21_all17_followups import ROOT, sources, combine, markdown, save
from wp21_five_rechtsfolgen import (
    historical_crosscheck, combine as five_combine, assess_dip,
)

BASE_DATE='2026-10-24T12:00:00+00:00'


def fake_parent(case):
    return {
        'id':int(case['official_dip_parent_id']), 'wahlperiode':21,
        'titel':'Erteilung eines Ordnungsrufes an den Abg '+case['person'],
        'abstract':'Ordnungsruf in Plenarsitzung',
        'datum':case['original_date'],
        'aktualisiert':'2026-10-24T11:00:00Z',
    }


def fake_original_position(case,idx=1):
    session=case['session']
    day=case['original_date']
    return {
        'id':100000+idx,
        'vorgang_id':int(case['official_dip_parent_id']),
        'wahlperiode':21,
        'vorgangsposition':'Ordnungsruf',
        'titel':'Erteilung des Ordnungsrufes',
        'datum':day,'aktualisiert':'2026-10-24T11:00:00Z',
        'fundstelle':{
            'dokumentart':'Plenarprotokoll',
            'dokumentnummer':f'21/{session}',
            'datum':day,
            'pdf_url':f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf#P.7000',
            'xml_url':f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml',
        },
    }


class SeventeenCasesLegalHints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.basis=sources()

    @classmethod
    def make_live(cls):
        twelve={}
        for idx,c in enumerate(cls.basis['twelve_cases'],start=1):
            twelve[c['official_dip_parent_id']]=assess_dip(
                c,fake_parent(c),[fake_original_position(c,idx)])
        older=historical_crosscheck()
        five={}
        for idx,c in enumerate(older['cases'],start=51):
            five[c['official_dip_parent_id']]=assess_dip(
                c,fake_parent(c),[fake_original_position(c,idx)])
        five_report=five_combine(older,five,BASE_DATE)
        return twelve,five_report

    def test_remaining_twelve_are_disjoint_from_five_and_cover_17(self):
        b=self.basis
        self.assertEqual(len(b['twelve_cases']),12)
        self.assertEqual(len(b['already_refreshed_five']),5)
        self.assertEqual(len(set(b['already_refreshed_five'])),5)
        self.assertFalse(set(b['already_refreshed_five'])&
                         {c['official_dip_parent_id'] for c in b['twelve_cases']})
        self.assertEqual(sum(bool(c['individually_curated_appeal_decision'])
                             for c in b['twelve_cases']),4)
        self.assertEqual(b['automatically_approved_new_sanctions'],0)
        self.assertEqual(b['protected_public_counter_changes'],0)
        self.assertEqual(b['scope'],'dated_original_sample_17_cases_not_the_entire_term')
        for c in b['twelve_cases']:
            self.assertTrue(c['original_xml_lines'])
            self.assertFalse(c['case_has_conclusive_individual_legal_effect_review'])
            self.assertEqual(c['additional_approved_sanctions'],0)

    def test_integrates_seventeen_only_after_both_live_source_sets(self):
        other,five=self.make_live()
        report=combine(self.basis,other,five,BASE_DATE)
        self.assertEqual(report['live_status'],'all_17_pinned_parents_refreshed')
        self.assertTrue(report['all_17_pinned_parents_refreshed'])
        self.assertEqual(report['total_dip_parent_originals_covered'],17)
        self.assertEqual(report['total_dip_positions_in_17_parents'],17)
        self.assertEqual(report['total_additional_position_review_hints'],0)
        self.assertEqual(report['automatically_approved_new_sanctions'],0)
        self.assertEqual(report['fully_reviewed_legal_effects'],0)
        self.assertIn('keine Vollerhebung',markdown(report))

    def test_live_missing_or_duplicate_origin_proof_rejected(self):
        other,five=self.make_live()
        truncated=dict(other)
        truncated.pop(next(iter(truncated)))
        with self.assertRaisesRegex(ValueError,'zwölf'):
            combine(self.basis,truncated,five,BASE_DATE)
        alt=copy.deepcopy(five)
        alt['cases'][0]['official_dip_parent_id']=self.basis['twelve_cases'][0][
            'official_dip_parent_id']
        with self.assertRaisesRegex(ValueError,'Doppelte'):
            combine(self.basis,other,alt,BASE_DATE)

    def test_legal_effect_and_position_guard(self):
        other,five=self.make_live()
        bad=copy.deepcopy(other)
        key=next(iter(bad))
        bad[key]['automatic_count_change']=1
        with self.assertRaises(ValueError):
            combine(self.basis,bad,five,BASE_DATE)
        notsafe=copy.deepcopy(self.basis)
        notsafe['automatically_approved_new_sanctions']=1
        with self.assertRaises(ValueError):
            combine(notsafe)
        with self.assertRaises(ValueError):
            markdown({**self.basis,'protected_public_counter_changes':1})

    def test_stale_independent_five_run_refused(self):
        other,five=self.make_live()
        stale=(datetime.fromisoformat(BASE_DATE)-timedelta(hours=3)).isoformat()
        five['last_five_parent_probe_utc']=stale
        with self.assertRaisesRegex(ValueError,'zeitnah'):
            combine(self.basis,other,five,BASE_DATE)

    def test_weekly_alert_reads_all17_and_skips_already_curated_votes(self):
        workflow=(ROOT/'.github/workflows/wp21_batch_review.yml').read_text(
            encoding='utf-8')
        self.assertIn("if: github.event_name == 'schedule'",workflow)
        self.assertIn(".audit/wp21_all17_live/all17.json",workflow)
        self.assertIn("p.needs_new_manual_source_review===true",workflow)
        self.assertIn("p.already_independently_curated_vote_metadata===false",workflow)
        self.assertIn("if(hints.length===0)",workflow)
        self.assertIn("const marker='<!-- wp21-five-procedure-digest:",workflow)
        self.assertIn("data.total_dip_parent_originals_covered!==17",workflow)
        self.assertIn("issues: write",workflow)

    def test_outside_workspace_forbidden_and_offline_no_guess(self):
        report=combine(self.basis)
        self.assertFalse(report['all_17_pinned_parents_refreshed'])
        self.assertEqual(report['live_status'],'not_checked')
        self.assertIsNone(report['total_additional_position_review_hints'])
        self.assertIn('weitere',report['warning'])
        (ROOT/'.audit').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.audit') as tmp:
            save(report,tmp)
            x=json.loads(Path(tmp,'all17.json').read_text(encoding='utf-8'))
            self.assertEqual(x['automatically_approved_new_sanctions'],0)
            self.assertEqual(len(x['twelve_cases']),12)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'privatem'):
                save(report,tmp)


if __name__=='__main__':
    unittest.main()
