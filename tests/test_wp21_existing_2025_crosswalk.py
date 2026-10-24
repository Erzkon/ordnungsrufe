"""Offline safeguards for joining new DIP parents to old 2025 dossiers."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from wp21_2025_dip_einzelakten import CASES
from wp21_weitere_einspruchsberichte import EVIDENCE
from wp21_new_dip_candidates import (
    AUDIT_ROOT, START, build, corroborate_original_positions,
    make_manual_review_batches,
)
from wp21_existing_2025_crosswalk import (crosswalk, markdown, next_review_queue,
                                         next_review_markdown, run)

NOW=datetime(2026,10,24,15,0,tzinfo=timezone.utc)


def document(parent,name,day,grants=1):
    grant=('von zwei Ordnungsrufen' if grants==2 else 'eines Ordnungsrufes')
    return {'id':str(parent),'wahlperiode':21,
            'titel':f'Erteilung {grant} an den Abg {name}',
            'abstract':'','datum':day,
            'aktualisiert':'2026-10-23T13:00:00+00:00'}


def position(parent,ident,session,day,step='Ordnungsruf'):
    return {
        'id':int(ident),'vorgang_id':int(parent),'wahlperiode':21,
        'vorgangsposition':step,'titel':step,
        'datum':day,'aktualisiert':'2026-10-23T14:00:00+00:00',
        'fundstelle':{
            'dokumentart':'Plenarprotokoll',
            'dokumentnummer':f'21/{session}',
            'datum':day,
            'pdf_url':f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf#P.1000',
            'xml_url':f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml',
        },
    }


def fixture(include_unknown=True):
    docs=[]
    positions={}
    for idx,(day,person,parent,session,decision_session,grants,votes) in enumerate(CASES):
        docs.append(document(parent,person,day,grants))
        later=sorted((e for e in EVIDENCE if e['original_date']==day
                      and e['person']==person),
                     key=lambda e:e['individual_objection_ordinal'])
        assert len(later)==votes
        positions[parent]=[position(parent,880000+idx,session,day)]+[
            position(parent,890000+idx*10+n,decision_session,e['decision_date'],
                     'Abstimmung') for n,e in enumerate(later,1)]
    if include_unknown:
        docs.append(document('328596','Stefan Keuter','2025-11-26',2))
        positions['328596']=[
            position('328596',899999,43,'2025-11-26'),
            position('328596',899998,43,'2025-11-26'),
        ]
    base=build(docs,since=START,now=NOW,pages=1)
    enriched=corroborate_original_positions(
        base,key='testing',fetch=lambda parent,key:positions[parent])
    return enriched,make_manual_review_batches(enriched)


class PreviousDossiersCrosswalkTests(unittest.TestCase):
    def test_exact_ten_dossiers_are_reused_not_recounted(self):
        discovery,queue=fixture()
        report=crosswalk(discovery,queue)
        self.assertEqual(report['all_unmatched_dip_parent_tasks'],11)
        self.assertEqual(report['previously_curated_ten_parent_dossier_matches'],10)
        self.assertEqual(report['remaining_outside_ten_parent_dossier_tasks'],1)
        self.assertEqual(report['independently_reported_initial_grants_in_matched_dossiers'],12)
        self.assertEqual(report['independently_reported_rejected_appeals_in_matched_dossiers'],11)
        self.assertEqual(set(report['special_prior_cases_still_open']),{'328224','328225'})
        self.assertEqual(report['automatically_confirmed_new_measures'],0)
        self.assertEqual(report['automatically_rescinded_measures'],0)
        self.assertEqual(report['protected_counter_changes'],0)
        self.assertIn('keine zehn neuen',report['warning'])
        self.assertIn('Steffen Janich',markdown(report))

    def test_janich_and_gottschalk_different_procedural_limits(self):
        report=crosswalk(*fixture())
        rows={r['official_dip_parent_id']:r
              for r in report['previously_curated_parent_cases']}
        janich=rows['328224']
        gottschalk=rows['328225']
        self.assertEqual(janich['reported_initial_grants_from_independent_dossier'],2)
        self.assertEqual(janich['source_grant_dip_position_count'],1)
        self.assertEqual(janich['independently_documented_rejected_objections'],2)
        self.assertIsNone(janich['original_xml_line_from_seven_case_dossier'])
        self.assertIn('unlocated',janich['original_xml_status'])
        self.assertEqual(gottschalk['reported_initial_grants_from_independent_dossier'],2)
        self.assertEqual(gottschalk['independently_documented_rejected_objections'],1)
        self.assertIn('unresolved',gottschalk['original_xml_status'])
        self.assertEqual(len(janich['official_objection_reports']),2)

    def test_keuter_multiple_dip_grant_steps_do_not_prove_two_effective_calls(self):
        report=crosswalk(*fixture())
        keuter=report['remaining_parent_cases_for_individual_review'][0]
        self.assertEqual(keuter['official_dip_parent_id'],'328596')
        self.assertEqual(len(keuter['original_sources']),2)
        self.assertEqual(keuter['review_priority'],'hoch')
        self.assertIn('do_not_prove',keuter['remaining_source_problem'])
        self.assertEqual(keuter['newly_approved_sanctions'],0)

    def test_mismatched_official_identity_is_blocked(self):
        d,q=fixture()
        bad=copy.deepcopy(d)
        case=next(c for c in bad['possible_originals_for_individual_review']
                  if c['official_dip_parent_id']=='328225')
        case['title']='Erteilung von zwei Ordnungsrufen an den Abg Steffen Janich'
        with self.assertRaises(ValueError):
            crosswalk(bad,q)
        bad=copy.deepcopy(d)
        case=next(c for c in bad['possible_originals_for_individual_review']
                  if c['official_dip_parent_id']=='328225')
        case['original_position_sources'][0]['date']='2025-11-14'
        with self.assertRaises(ValueError):
            crosswalk(bad,q)

    def test_missing_independent_appeal_vote_is_not_silently_accepted(self):
        d,q=fixture()
        bad=copy.deepcopy(d)
        case=next(c for c in bad['possible_originals_for_individual_review']
                  if c['official_dip_parent_id']=='328224')
        case['other_position_sources_needing_legal_review']=[]
        case['official_parent_position_count']-=2
        with self.assertRaisesRegex(ValueError,'Einspruchsquelle'):
            crosswalk(bad,q)

    def test_appeal_position_wrong_plenary_session_is_not_taken_as_vote(self):
        d,q=fixture()
        bad=copy.deepcopy(d)
        c=next(c for c in bad['possible_originals_for_individual_review']
               if c['official_dip_parent_id']=='328224')
        c['other_position_sources_needing_legal_review'][0]['official_plenary_session']=99
        with self.assertRaisesRegex(ValueError,'Einspruchspositionen'):
            crosswalk(bad,q)

    def test_prior_study_is_not_required_for_recent_zero_case_window(self):
        d,q=fixture(include_unknown=False)
        d={**d,'possible_originals_for_individual_review':[],
           'possible_original_parent_ids_outside_18_pins':0,
           'candidates_without_positive_sample_original_match':0}
        q={**q,'batches':[],'pending_parent_review_tasks':0}
        report=crosswalk(d,q)
        self.assertEqual(report['all_unmatched_dip_parent_tasks'],0)
        self.assertEqual(report['previously_curated_ten_parent_dossier_matches'],0)

    def test_two_official_parents_same_person_sitting_remain_two_review_tasks(self):
        d,q=fixture()
        # Both IDs were historically present in the DIP snapshot for
        # Reichardt 21/014; their common title is NOT proof of two
        # independent legally effective sanctions.
        same_title='Erteilung eines Ordnungsrufes an den Abg Martin Reichardt (AfD)'
        for ident,pid in (('322921',882021),('322922',882022)):
            c={
                'official_dip_parent_id':ident,
                'official_dip_parent_url':'https://dip.bundestag.de/vorgang/'+ident,
                'title':same_title,
                'all_official_parent_positions_fetched':True,
                'official_original_position_count':1,
                'official_parent_position_count':1,
                'original_position_sources':[{
                    'official_position_id':str(pid),
                    'official_position_api':
                        'https://search.dip.bundestag.de/api/v1/vorgangsposition/'+str(pid),
                    'official_plenary_session':14,'date':'2025-06-26',
                    'official_plenary_pdf_url':
                        'https://dserver.bundestag.de/btp/21/21014.pdf#P.1500',
                }],
                'other_position_sources_needing_legal_review':[],
                'matched_dated_positive_sample_by_original_position':[],
                'confirmed_additional_sanctions':0,
            }
            d['possible_originals_for_individual_review'].append(c)
            q['batches'].append([{'official_dip_parent_id':ident}])
        d['possible_original_parent_ids_outside_18_pins']+=2
        d['candidates_without_positive_sample_original_match']+=2
        q['pending_parent_review_tasks']+=2
        r=crosswalk(d,q)
        self.assertEqual(r['parents_needing_collision_review'],2)
        self.assertEqual(len(r['possible_cross_parent_original_context_collisions']),1)
        group=r['possible_cross_parent_original_context_collisions'][0]
        self.assertEqual(group['distinct_official_parent_ids'],['322921','322922'])
        names={c['official_dip_parent_id']:c for c in
               r['remaining_parent_cases_for_individual_review']}
        self.assertEqual(names['322921']['other_dip_parents_same_original_context'],['322922'])
        self.assertEqual(names['322922']['other_dip_parents_same_original_context'],['322921'])
        self.assertEqual(names['322921']['review_priority'],'hoch')
        self.assertEqual(r['automatically_confirmed_new_measures'],0)
        self.assertIn('Getrennte DIP-Eltern',markdown(r))

    def test_deduplicated_next_bundles_do_not_repeat_old_dossiers(self):
        report=crosswalk(*fixture())
        batches=next_review_queue(report)
        self.assertEqual(batches['total_parent_tasks'],1)
        self.assertEqual(batches['batch_size'],5)
        self.assertEqual(len(batches['batches']),1)
        self.assertEqual(batches['batches'][0][0]['official_dip_parent_id'],'328596')
        self.assertTrue(batches['previous_ten_parent_dossiers_are_not_repeated_as_new_tasks'])
        self.assertEqual(batches['automatic_counter_change'],0)
        self.assertIn('328596',next_review_markdown(batches))
        with self.assertRaises(ValueError):
            next_review_markdown({**batches,'automatic_counter_change':1})
        with self.assertRaises(ValueError):
            next_review_queue(report,batch_size=0)

    def test_capped_bundles_never_mix_previous_and_uncurated_parents(self):
        report=crosswalk(*fixture())
        # Build many distinct, *synthetic* new sources to test pagination.
        rows=report['remaining_parent_cases_for_individual_review']
        for idx in range(1,13):
            clone=copy.deepcopy(rows[0])
            clone['official_dip_parent_id']=str(345800+idx)
            clone['official_parent_url']='https://dip.bundestag.de/vorgang/'+clone['official_dip_parent_id']
            clone['review_priority']='mittel'
            rows.append(clone)
        report['remaining_outside_ten_parent_dossier_tasks']=len(rows)
        q=next_review_queue(report)
        self.assertEqual(q['total_parent_tasks'],13)
        self.assertEqual([len(batch) for batch in q['batches']],[5,5,3])
        self.assertEqual(sum(len(b) for b in q['batches']),13)
        ids={x['official_dip_parent_id'] for b in q['batches'] for x in b}
        self.assertNotIn('328224',ids)
        self.assertNotIn('328225',ids)

    def test_queue_mutation_or_public_count_delta_rejected(self):
        d,q=fixture()
        corrupted=copy.deepcopy(q)
        corrupted['batches'][0][0]['official_dip_parent_id']='999888'
        with self.assertRaises(ValueError):
            crosswalk(d,corrupted)
        with self.assertRaises(ValueError):
            crosswalk({**d,'automatically_confirmed_new_sanctions':1},q)
        with self.assertRaises(ValueError):
            markdown({**crosswalk(d,q),'protected_counter_changes':1})

    def test_files_only_in_audit_and_no_source_ledger_mutation(self):
        d,q=fixture()
        AUDIT_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=AUDIT_ROOT) as td:
            folder=Path(td)
            inputs=folder/'sources'
            inputs.mkdir()
            (inputs/'outside_pins.json').write_text(json.dumps(d),encoding='utf-8')
            (inputs/'review_queue.json').write_text(json.dumps(q),encoding='utf-8')
            dest=folder/'matched'
            protected=Path('daten/wirksame_ordnungsrufe_21wp.csv').read_bytes()
            r=run(inputs/'outside_pins.json',inputs/'review_queue.json',dest)
            self.assertEqual(r['previously_curated_ten_parent_dossier_matches'],10)
            self.assertTrue((dest/'dossier_overlap.json').exists())
            self.assertTrue((dest/'next_review_queue.json').exists())
            self.assertTrue((dest/'next_review_queue.md').exists())
            self.assertIn('2025', (dest/'dossier_overlap.md').read_text())
            self.assertEqual(protected,Path('daten/wirksame_ordnungsrufe_21wp.csv').read_bytes())
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                run('does-not-exist','does-not-exist',Path(td)/'elsewhere')


if __name__=='__main__':
    unittest.main()
