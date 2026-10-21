"""Case-specific five-candidate follow-up without inferred absence of objections."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from wp21_five_rechtsfolgen import (
    ROOT,EXPECTED,historical_crosscheck,assess_dip,combine,render,save,
)


class FiveLegalFollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=historical_crosscheck()

    def case(self,person):
        return next(c for c in self.base['cases'] if c['person']==person)

    @staticmethod
    def parent(case,person=None):
        return {
            'id':int(case['official_dip_parent_id']),
            'wahlperiode':21,
            'titel':'Erteilung eines Ordnungsrufes an den Abg '+(
                person or case['person']),
            'abstract':'In der Plenarsitzung erteilter Ordnungsruf',
            'datum':case['original_date'],
            'aktualisiert':'2026-10-19T09:00:00Z',
        }

    @staticmethod
    def position(case,position_id=888):
        s=case['session'];day=case['original_date']
        return {
            'id':position_id,
            'vorgang_id':int(case['official_dip_parent_id']),
            'wahlperiode':21,
            'vorgangsposition':'Ordnungsruf',
            'titel':'Erteilung des Ordnungsrufes',
            'datum':day,
            'aktualisiert':'2026-10-19T09:00:00Z',
            'fundstelle':{
                'dokumentart':'Plenarprotokoll',
                'dokumentnummer':f'21/{s}',
                'datum':day,
                'pdf_url':f'https://dserver.bundestag.de/btp/21/21{s:03d}.pdf#P.7000',
                'xml_url':f'https://dserver.bundestag.de/btp/21/21{s:03d}.xml',
            },
        }

    def test_all_five_originals_bound_to_unique_official_dip_parent_id(self):
        self.assertEqual(
            [(c['session'],c['person'],c['official_dip_parent_id'])
             for c in self.base['cases']],
            [(53,'Heidi Reichinnek','330237'),
             (57,'Bernd Baumann','330700'),
             (61,'Ulrich von Zons','332078'),
             (65,'Luigi Pantisano','332778'),
             (67,'Kathrin Gebel','333090')])
        self.assertEqual(self.base['curated_rejected_objections_scanned'],17)
        self.assertEqual(self.base['definitively_closed_legal_effects'],0)
        self.assertEqual(self.base['automatically_approved_new_sanctions'],0)
        self.assertFalse(self.base['protected_ledger_changed'])
        self.assertFalse(any(c['no_appeal_has_been_proven'] for c in self.base['cases']))

    def test_pantisano_2025_appeal_not_attributed_to_march_2026(self):
        p=self.case('Luigi Pantisano')
        self.assertEqual(p['original_date'],'2026-03-19')
        other=p['same_name_other_date_reports_excluded']
        self.assertEqual(len(other),1)
        self.assertEqual(other[0]['original_date'],'2025-06-27')
        self.assertTrue(other[0]['NOT_this_grant'])
        self.assertEqual(p['bounded_curated_rejected_objection_matches'],[])

    def test_bernd_baumann_2018_and_gebel_as_target_do_not_link(self):
        baumann=self.case('Bernd Baumann')
        gebel=self.case('Kathrin Gebel')
        self.assertEqual(baumann['bounded_curated_rejected_objection_matches'],[])
        self.assertEqual(gebel['bounded_curated_rejected_objection_matches'],[])
        self.assertTrue(gebel['other_person_mentioned_in_report_not_recipient'])
        self.assertIn('KEIN Nachweis',self.base['warning'])

    def test_five_complete_dip_parents_preserve_no_legal_certainty(self):
        checks={}
        for case in self.base['cases']:
            checks[case['official_dip_parent_id']]=assess_dip(
                case,self.parent(case),[self.position(case)])
        report=combine(self.base,checks,'2026-10-21T18:20:00+00:00')
        self.assertTrue(report['live_dip_complete_for_exact_five_parents'])
        self.assertEqual(report['live_dip_parent_status'],'all_five_refreshed')
        self.assertTrue(all(
            x['dip_parent_metadata_review']['automatic_count_change']==0
            for x in report['cases']))
        self.assertFalse(all(
            x['dip_parent_metadata_review']['legal_effect_conclusively_verified']
            for x in report['cases']))
        self.assertEqual(report['automatically_approved_new_sanctions'],0)

    def test_appeal_position_remains_review_hint_even_with_rejection_tenor(self):
        c=self.case('Heidi Reichinnek')
        vote=self.position(c,889)
        vote.update({
            'vorgangsposition':'Abstimmung','datum':'2026-01-16',
            'fundstelle':{
                'dokumentart':'Plenarprotokoll',
                'dokumentnummer':'21/54',
                'datum':'2026-01-16',
                'pdf_url':'https://dserver.bundestag.de/btp/21/21054.pdf#P.6450',
                'xml_url':'https://dserver.bundestag.de/btp/21/21054.xml',
            },
            'beschlussfassung':[{'beschlusstenor':'Zurückweisung des Einspruchs'}],
        })
        result=assess_dip(c,self.parent(c),[self.position(c),vote])
        self.assertEqual(result['position_count'],2)
        self.assertEqual(result['other_step_review_hints'],1)
        self.assertEqual(result['positions'][1]['role_for_review'],
                         'unadjudicated_appeal_vote_metadata_candidate')
        self.assertFalse(result['positions'][1]['legal_effect_conclusively_verified'])
        self.assertFalse(result['legal_effect_conclusively_verified'])
        self.assertEqual(result['automatic_count_change'],0)

    def test_same_name_wrong_origination_date_or_parent_is_rejected(self):
        c=self.case('Heidi Reichinnek')
        bad=self.parent(c,person='Bernd Baumann')
        with self.assertRaisesRegex(ValueError,'anderer Empfänger'):
            assess_dip(c,bad,[self.position(c)])
        bad=self.parent(c)
        bad['id']=999
        with self.assertRaisesRegex(ValueError,'Fremder'):
            assess_dip(c,bad,[self.position(c)])
        pos=self.position(c)
        pos['vorgang_id']=999
        with self.assertRaisesRegex(ValueError,'fremden Vorgangs'):
            assess_dip(c,self.parent(c),[pos])
        pos=self.position(c)
        pos['datum']='2026-01-16'
        pos['fundstelle']['datum']='2026-01-16'
        with self.assertRaisesRegex(ValueError,'Originalerteilungsposition'):
            assess_dip(c,self.parent(c),[pos])

    def test_wrong_chamber_and_missing_origin_position_fail_closed(self):
        c=self.case('Kathrin Gebel')
        position=self.position(c)
        position['fundstelle']={
            'dokumentart':'Plenarprotokoll','dokumentnummer':'1054',
            'datum':position['datum'],
            'pdf_url':'https://dserver.bundestag.de/brp/1054.pdf#P.1',
            'xml_url':None,
        }
        with self.assertRaisesRegex(ValueError,'Originalprotokoll'):
            assess_dip(c,self.parent(c),[position])
        with self.assertRaises(ValueError):
            assess_dip(c,self.parent(c),[])
        with self.assertRaises(ValueError):
            assess_dip(c,self.parent(c),[self.position(c),self.position(c)])

    def test_dip_probe_fails_if_one_of_five_parent_records_missing(self):
        case=self.base['cases'][0]
        validated=assess_dip(case,self.parent(case),[self.position(case)])
        with self.assertRaisesRegex(ValueError,'fünf'):
            combine(self.base,{case['official_dip_parent_id']:validated},
                    '2026-10-21T18:20:00+00:00')
        raw=copy.deepcopy(self.base)
        raw['automatically_approved_new_sanctions']=1
        with self.assertRaises(ValueError):
            combine(raw)

    def test_offline_report_has_explicit_unknown_followup_status(self):
        report=combine(self.base)
        self.assertFalse(report['live_dip_complete_for_exact_five_parents'])
        self.assertEqual(report['live_dip_parent_status'],'not_checked')
        self.assertIn('kein Beweis',render(report))
        self.assertIn('noch nicht frisch abgefragt',render(report))
        self.assertIn('17er-Auswahl',render(report))

    def test_weekly_issue_notification_never_executes_on_pull_request(self):
        workflow=(ROOT/'.github/workflows/wp21_batch_review.yml').read_text(
            encoding='utf-8')
        self.assertIn("if: github.event_name == 'schedule'",workflow)
        self.assertIn('new-procedure-alert:',workflow)
        self.assertIn('issues: write',workflow)
        self.assertIn('wp21-five-procedure-digest:',workflow)
        self.assertIn("if(hints.length===0)",workflow)
        self.assertIn('actions/download-artifact@v7',workflow)
        self.assertIn("path: .audit",workflow)
        self.assertIn('automatic_count_change',workflow)
        self.assertNotIn('github.rest.issues.create({owner,repo,title,body,labels:',workflow)

    def test_save_only_nonpublic_artifacts_no_counters(self):
        report=combine(self.base)
        (ROOT/'.audit').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'.audit') as tmp:
            save(report,tmp)
            artifact=json.loads(Path(tmp,'later_effects.json').read_text(encoding='utf-8'))
            self.assertEqual(artifact['automatically_approved_new_sanctions'],0)
            self.assertEqual(len(artifact['cases']),5)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'private'):
                save(report,tmp)
        with self.assertRaises(ValueError):
            render({**report,'protected_ledger_changed':True})


if __name__=='__main__':
    unittest.main()
