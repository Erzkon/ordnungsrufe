"""Non-counting unit tests for three original DIP legal-followup parents."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from wp21_new_dip_candidates import AUDIT_ROOT
from wp21_priority_later_effects import (
    EXPECTED,inspect_parent,bounded_other_parent_hints,original_role_consistent,
    historical_appeal_exclusions,consolidate,review_alerts,render,save,run,
)
from tests.test_wp21_priority_xml_verify import fixture as original_scout


def parent(ident):
    meta=EXPECTED[ident]
    title=('Erteilung von zwei Ordnungsrufen an den Abg Stefan Keuter (AfD)'
           if ident=='328596' else
           'Erteilung eines Ordnungsrufes an den Abg Martin Reichardt (AfD)')
    return {'id':int(ident),'wahlperiode':21,
            'titel':title,'datum':meta['original_date'],
            'aktualisiert':'2026-10-24T10:00:00+00:00'}


def children(ident,extra=False):
    meta=EXPECTED[ident]
    day=meta['original_date']
    result=[]
    for pid,page in meta['original_position_pages'].items():
        session=meta['original_session']
        result.append({
            'id':int(pid),'vorgang_id':int(ident),'wahlperiode':21,
            'vorgangsposition':'Ordnungsruf',
            'titel':'Erteilung eines Ordnungsrufes',
            'datum':day,'aktualisiert':'2026-10-24T10:00:00+00:00',
            'fundstelle':{
                'dokumentart':'Plenarprotokoll',
                'dokumentnummer':f'21/{session}',
                'datum':day,
                'pdf_url':f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf#P.{page}',
                'xml_url':f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml',
            },
        })
    if extra and ident=='328596':
        result.append({
            'id':988801,'vorgang_id':int(ident),'wahlperiode':21,
            'vorgangsposition':'Abstimmung',
            'titel':'Zurückweisung des Einspruchs',
            'datum':'2025-11-28',
            'aktualisiert':'2026-10-24T10:00:00+00:00',
            'beschlussfassung':[{'beschlusstenor':'Zurückweisung des Einspruchs'}],
            'fundstelle':{
                'dokumentart':'Plenarprotokoll','dokumentnummer':'21/45',
                'datum':'2025-11-28',
                'pdf_url':'https://dserver.bundestag.de/btp/21/21045.pdf#P.5091',
                'xml_url':'https://dserver.bundestag.de/btp/21/21045.xml',
            },
        })
    return result


def inventory(include_related=True):
    other=[]
    if include_related:
        other=[
            {'official_dip_parent_id':'340550',
             'official_dip_parent_url':'https://dip.bundestag.de/vorgang/340550',
             'source_date':'2026-10-16',
             'title':'Verhängung eines Ordnungsgeldes gegen den Abg Martin Reichardt (AfD)'},
            {'official_dip_parent_id':'328595',
             'official_dip_parent_url':'https://dip.bundestag.de/vorgang/328595',
             'source_date':'2025-11-28',
             'title':'Erteilung eines Ordnungsrufes an den Abg Martin Reichardt (AfD)'},
            {'official_dip_parent_id':'999002',
             'official_dip_parent_url':'https://dip.bundestag.de/vorgang/999002',
             'source_date':'2026-10-24',
             'title':'Einspruch des Abg Stefan Keuter gegen einen Ordnungsruf'},
        ]
    return {
        'schema':'wp21-dip-outside-pins-discovery-v1',
        'status':'source_discovery_only_no_effectiveness_decision',
        'since_utc':'2025-03-25T00:00:00+00:00',
        'observed_until_utc':'2026-10-24T12:00:00+00:00',
        'full_legislative_period_update_window':True,
        'api_pages_completely_fetched':194,
        'possible_original_parent_ids_outside_18_pins':0,
        'other_relevant_parent_ids_outside_18_pins':len(other),
        'possible_originals_for_individual_review':[],
        'other_metadata_for_individual_review':other,
        'automatically_confirmed_new_sanctions':0,
        'protected_counters_changed':False,
    }


def pinned(with_vote=False):
    return {ident:inspect_parent(ident,parent(ident),children(ident,with_vote))
            for ident in EXPECTED}


class PriorityLegalFollowupTests(unittest.TestCase):
    def test_three_parents_four_pinned_positions_do_not_approve_four(self):
        cases=pinned()
        summary=consolidate(cases,original_scout(),inventory())
        self.assertEqual(summary['official_parents_refreshed'],3)
        self.assertEqual(summary['official_original_position_refs'],4)
        self.assertEqual(summary['individually_spoken_source_loci_previously_checked'],3)
        self.assertEqual(
            {c['official_dip_parent_id']:c['original_dip_position_count']
             for c in summary['pinned_parent_cases']},
            {'322921':1,'322922':1,'328596':2})
        self.assertTrue(summary['person_conflict_reichardt_title_vs_keuter_original'])
        self.assertTrue(summary['no_additional_parent_position_is_not_proof_of_no_appeal'])
        self.assertEqual(summary['automatically_approved_new_sanctions'],0)
        self.assertFalse(summary['protected_counter_files_modified'])
        self.assertIn('Keine',render(summary))

    def test_keuter_wrong_reichardt_parent_title_does_not_change_recipient(self):
        case=inspect_parent('322921',parent('322921'),children('322921'))
        self.assertEqual(case['displayed_dip_person_metadata_only'],'Martin Reichardt')
        self.assertEqual(case['original_recipient_from_official_plenary'],'Stefan Keuter')
        self.assertTrue(case['parent_title_recipient_conflicts_with_spoken_original'])
        self.assertFalse(case['legal_effect_of_each_grant_conclusively_verified'])

    def test_later_vote_metadata_is_not_an_established_rejection_or_effectiveness(self):
        case=inspect_parent('328596',parent('328596'),children('328596',True))
        self.assertEqual(case['original_dip_position_count'],2)
        self.assertEqual(case['additional_parent_procedure_position_count'],1)
        row=case['later_parent_positions_for_individual_review'][0]
        self.assertEqual(row['source_class'],'possible_appeal_or_later_legal_effect_metadata')
        self.assertIn('Zurückweisung des Einspruchs',
                      row['official_decision_tenors_metadata_only'])
        self.assertTrue(row['source_cannot_confirm_final_legal_effect'])
        self.assertEqual(row['newly_confirmed_effective_sanctions'],0)
        result=consolidate({**pinned(),'328596':case},original_scout(),inventory())
        self.assertEqual(result['automatically_approved_new_sanctions'],0)
        self.assertIn('Zusätzliche',render(result))

    def test_alerts_are_only_unresolved_parent_positions_or_relevant_keywords(self):
        report=consolidate(pinned(),original_scout(),inventory())
        alerts=review_alerts(report)
        # The separately regulated fine and unrelated original Reichardt
        # grant must not trigger a legal-effect alert for these three IDs.
        self.assertEqual(alerts['hint_count'],1)
        self.assertEqual(alerts['hints'][0]['official_parent_id'],'999002')
        self.assertEqual(
            alerts['hints'][0]['kind'],'other_parent_name_and_procedure_keyword_only')
        self.assertFalse(alerts['absence_of_hints_means_no_appeal'])
        self.assertEqual(alerts['automatically_approved_sanctions'],0)
        self.assertFalse(alerts['protected_counters_modified'])
        with_vote=consolidate(
            {**pinned(),'328596':inspect_parent(
                '328596',parent('328596'),children('328596',True))},
            original_scout(),inventory())
        alerts=review_alerts(with_vote)
        self.assertEqual(alerts['hint_count'],2)
        self.assertEqual(
            {x['kind'] for x in alerts['hints']},
            {'new_parent_procedure_position','other_parent_name_and_procedure_keyword_only'})
        self.assertTrue(all(x['automatic_count_delta']==0 for x in alerts['hints']))
        corrupt=copy.deepcopy(with_vote)
        idx=next(c for c in corrupt['pinned_parent_cases'] if c['official_dip_parent_id']=='328596')
        idx['later_parent_positions_for_individual_review'][0]['source_url']='https://evil.example'
        with self.assertRaises(ValueError):
            review_alerts(corrupt)

    def test_zero_alerts_is_not_silently_interpreted_as_no_appeals(self):
        report=consolidate(pinned(),original_scout(),inventory(False))
        alerts=review_alerts(report)
        self.assertEqual(alerts['hint_count'],0)
        self.assertEqual(alerts['hints'],[])
        self.assertFalse(alerts['absence_of_hints_means_no_appeal'])

    def test_missing_relabelled_or_foreign_official_position_fails_closed(self):
        with self.assertRaises(ValueError):
            inspect_parent('328596',parent('328596'),children('328596')[:1])
        bad=children('322921')
        bad[0]['fundstelle']['pdf_url']=(
            'https://dserver.bundestag.de/btp/21/21014.pdf#P.1133')
        with self.assertRaises(ValueError):
            inspect_parent('322921',parent('322921'),bad)
        bad=children('322922')
        bad[0]['vorgang_id']=328596
        with self.assertRaises(ValueError):
            inspect_parent('322922',parent('322922'),bad)
        bad=children('322922')
        bad[0]['vorgangsposition']='Abstimmung'
        with self.assertRaises(ValueError):
            inspect_parent('322922',parent('322922'),bad)
        bad=children('322922')*2
        with self.assertRaises(ValueError):
            inspect_parent('322922',parent('322922'),bad)

    def test_other_same_person_sources_are_unlinked_and_fine_is_separate(self):
        hints=bounded_other_parent_hints(inventory())
        self.assertEqual(len(hints['named_other_parent_metadata_candidates']),3)
        groups={x['official_parent_id']:x['source_class']
                for x in hints['named_other_parent_metadata_candidates']}
        self.assertEqual(groups['340550'],
                         'distinct_sanction_type_not_an_ordnungsruf_appeal')
        self.assertEqual(groups['328595'],
                         'same_name_different_or_unlinked_original_metadata')
        self.assertEqual(groups['999002'],'procedure_keyword_possible_related_metadata')
        self.assertEqual(hints['matched_to_any_of_four_individual_grants_automatically'],0)
        self.assertFalse(hints['absence_of_other_relevant_sources_proven'])

    def test_unfiltered_dip_procedure_without_ordnungsruf_word_flows_to_alerts(self):
        data=inventory()
        data['unfiltered_priority_procedure_parents']=[{
            'official_dip_parent_id':'348999',
            'official_dip_parent_url':'https://dip.bundestag.de/vorgang/348999',
            'title':'Einspruch des Abgeordneten Stefan Keuter gegen eine Entscheidung',
            'abstract_excerpt':'',
            'source_date':'2026-10-25',
            'updated_utc':'2026-10-25T08:00:00+00:00',
            'matched_full_person_names_metadata_only':['Stefan Keuter'],
            'matched_procedural_text_not_full_legal_decision':True,
            'ordnungsruf_keyword_present_in_title_or_abstract':False,
            'original_measure_identity_verified':False,
            'appeal_or_legal_outcome_decided':False,
            'automatically_approved_effective_sanctions':0,
        }]
        data['unfiltered_priority_procedure_parent_count']=1
        info=bounded_other_parent_hints(data)
        self.assertTrue(info['unfiltered_legal_shadow_evaluated'])
        self.assertEqual(info['unfiltered_procedure_keyword_parent_hints'],1)
        source=next(c for c in info['named_other_parent_metadata_candidates']
                    if c['official_parent_id']=='348999')
        self.assertEqual(source['source_class'],
                         'other_dip_parent_possible_procedure_without_ordnungsruf_keyword')
        self.assertFalse(source['exact_original_case_link_verified'])
        report=consolidate(pinned(),original_scout(),data)
        alerts=review_alerts(report)
        self.assertEqual(alerts['hint_count'],2)
        alert=next(a for a in alerts['hints'] if a['official_parent_id']=='348999')
        self.assertTrue(alert['case_link_and_legal_outcome_still_require_manual_review'])
        self.assertEqual(alert['automatic_count_delta'],0)
        self.assertFalse(alerts['absence_of_hints_means_no_appeal'])

    def test_shadow_wrong_full_name_or_duplicate_parent_refused(self):
        data=inventory(False)
        shadow={
            'official_dip_parent_id':'348998',
            'official_dip_parent_url':'https://dip.bundestag.de/vorgang/348998',
            'title':'Widerspruch von Martin Reichardt',
            'abstract_excerpt':'',
            'matched_full_person_names_metadata_only':['Martin Reichardt'],
            'matched_procedural_text_not_full_legal_decision':True,
            'ordnungsruf_keyword_present_in_title_or_abstract':False,
            'original_measure_identity_verified':False,
            'appeal_or_legal_outcome_decided':False,
            'automatically_approved_effective_sanctions':0,
            'source_date':'2026-10-25',
            'updated_utc':'2026-10-25T09:00:00+00:00',
        }
        data['unfiltered_priority_procedure_parents']=[shadow]
        data['unfiltered_priority_procedure_parent_count']=1
        self.assertEqual(bounded_other_parent_hints(data)
                         ['unfiltered_procedure_keyword_parent_hints'],1)
        for change in (
            {'matched_full_person_names_metadata_only':['Stefan Keuter']},
            {'official_dip_parent_url':'https://untrusted.example/348998'},
            {'appeal_or_legal_outcome_decided':True},
            {'automatically_approved_effective_sanctions':1},
        ):
            altered=copy.deepcopy(data)
            altered['unfiltered_priority_procedure_parents'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                bounded_other_parent_hints(altered)
        dup=copy.deepcopy(data)
        dup['unfiltered_priority_procedure_parents']=[shadow,copy.deepcopy(shadow)]
        dup['unfiltered_priority_procedure_parent_count']=2
        with self.assertRaises(ValueError):
            bounded_other_parent_hints(dup)

    def test_empty_bounded_other_parent_sources_is_not_negated_effects(self):
        data=inventory(False)
        data['full_legislative_period_update_window']=False
        info=bounded_other_parent_hints(data)
        self.assertEqual(info['named_other_parent_metadata_candidates'],[])
        self.assertFalse(info['full_term_update_filter_used'])
        self.assertFalse(info['absence_of_other_relevant_sources_proven'])
        report=consolidate(pinned(),original_scout(),data)
        self.assertTrue(report['no_complete_cross_document_legal_exhaustiveness_claim'])

    def test_bounded_objection_corpus_excludes_other_reichardt_originals(self):
        r=historical_appeal_exclusions()
        self.assertTrue(r['known_official_objections_to_other_originals_excluded'])
        self.assertTrue(all(x['original_cannot_be_one_of_three_checked_parents']
                            for x in r['known_official_objections_to_other_originals_excluded']))
        self.assertTrue(r['separately_curated_reichardt_ordnungsGELD_negative_control']
                        ['not_an_ordnungsruf'])
        self.assertFalse(r['no_bounded_objection_match_proves_no_appeal'])
        extra=[x for x in r['known_official_objections_to_other_originals_excluded']
               if x.get('source_collected_outside_fixed_thirteen_article_corpus')]
        self.assertEqual(len(extra),1)
        self.assertEqual(extra[0]['different_original_day'],'2026-03-19')
        self.assertEqual(extra[0]['decision_day'],'2026-03-20')
        self.assertEqual(extra[0]['independent_official_decision_protocol'],
                         'https://www.bundestag.de/resource/blob/1155780/amtpr21066.pdf')
        self.assertTrue(extra[0]['original_cannot_be_one_of_three_checked_parents'])


    def test_malformed_discovery_is_never_exhaustive_evidence(self):
        d=inventory()
        with self.assertRaises(ValueError):
            bounded_other_parent_hints({**d,'protected_counters_changed':True})
        with self.assertRaises(ValueError):
            bounded_other_parent_hints({**d,
                 'other_relevant_parent_ids_outside_18_pins':1})
        d=inventory()
        d['other_metadata_for_individual_review'].append(
            copy.deepcopy(d['other_metadata_for_individual_review'][0]))
        d['other_relevant_parent_ids_outside_18_pins']+=1
        with self.assertRaises(ValueError):
            bounded_other_parent_hints(d)

    def test_mutating_spoken_source_refuses_later_effect_report(self):
        d=original_scout()
        first=d['sessions'][0]['candidate_paragraphs'][0]
        first['text']='Irgendetwas anderes'
        with self.assertRaises(ValueError):
            original_role_consistent(d)
        cases=pinned()
        cases['322921']['legal_effect_of_each_grant_conclusively_verified']=True
        with self.assertRaises(ValueError):
            consolidate(cases,original_scout(),inventory())

    def test_only_audit_outputs_and_preserve_protected_ledgers(self):
        AUDIT_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=AUDIT_ROOT) as tmp:
            base=Path(tmp)
            source=base/'original_scout.json'
            window=base/'source_window.json'
            source.write_text(json.dumps(original_scout()),encoding='utf-8')
            window.write_text(json.dumps(inventory()),encoding='utf-8')
            ledger=Path('daten/wirksame_ordnungsrufe_21wp.csv').read_bytes()
            report=run(
                source=source,discovery=window,output=base/'results',
                key='mock',
                fetch_parent=lambda ident,key:parent(ident),
                fetch_children=lambda ident,key:children(ident))
            self.assertEqual(report['automatically_approved_new_sanctions'],0)
            self.assertTrue((base/'results/priority_later_effects.json').is_file())
            self.assertTrue((base/'results/priority_later_effects.md').is_file())
            self.assertTrue((base/'results/priority_review_alerts.json').is_file())
            self.assertEqual(ledger,Path('daten/wirksame_ordnungsrufe_21wp.csv').read_bytes())
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                save(consolidate(pinned(),original_scout(),inventory()),Path(td)/'public')


if __name__=='__main__':
    unittest.main()
