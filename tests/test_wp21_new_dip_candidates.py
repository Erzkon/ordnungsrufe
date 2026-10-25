"""DIP discovery outside pinned WP21 parent IDs: read-only and fail closed."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wp21_dip_monitor import START, iso
from wp21_new_dip_candidates import (
    AUDIT_ROOT, build, corroborate_original_positions, classify,
    make_manual_review_batches, markdown, review_markdown, run, save,
)

NOW = datetime(2026,10,24,12,0,tzinfo=timezone.utc)
SINCE = NOW-timedelta(days=45)


def doc(ident, title, *, date='2026-10-23', updated=None):
    return {
        'id':str(ident),
        'wahlperiode':21,
        'titel':title,
        'abstract':'',
        'datum':date,
        'aktualisiert':updated or iso(NOW-timedelta(hours=3)),
    }


def position(parent, ident, session, date, step='Ordnungsruf'):
    return {
        'id':ident,'vorgang_id':int(parent),'wahlperiode':21,
        'vorgangsposition':step,'titel':step,
        'datum':date,'aktualisiert':iso(NOW-timedelta(hours=2)),
        'fundstelle':{
            'dokumentart':'Plenarprotokoll',
            'dokumentnummer':f'21/{session}',
            'datum':date,
            'pdf_url':f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf#P.1000',
            'xml_url':f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml',
        },
    }


class OutsidePinsDiscoveryTests(unittest.TestCase):
    def test_official_id_is_stronger_than_similar_names(self):
        docs=[
            doc(330133,'Erteilung eines Ordnungsrufes an Martin Hess'),
            doc(345001,'Erteilung eines Ordnungsrufes an Martin Hess'),
            doc(345002,'Erteilung eines Ordnungsrufes an andere Person'),
        ]
        report=build(docs,since=SINCE,now=NOW,pages=1)
        self.assertEqual(report['pinned_18_parents_seen_in_window'],1)
        self.assertEqual(report['possible_original_parent_ids_outside_18_pins'],2)
        self.assertEqual(
            {x['official_dip_parent_id'] for x in
             report['possible_originals_for_individual_review']},
            {'345001','345002'})
        self.assertEqual(report['automatically_confirmed_new_sanctions'],0)
        self.assertFalse(report['protected_counters_changed'])

    def test_full_dip_shadow_scans_procedures_without_ordnungsruf_vocabulary(self):
        records=[
            doc(348101,'Einspruch des Abgeordneten Martin Reichardt gegen eine Entscheidung'),
            doc(348102,'Beschwerde des Abgeordneten Stefan Keuter zur Plenarsitzung'),
            doc(348103,'Mitteilung über eine Abstimmung'),
            doc(348104,'Martin Reichardt: schriftliche Erklärung im Plenum'),
            doc(348105,'Ordnungsgeld gegen Martin Reichardt'),
            doc(348106,'Einspruch ohne Abgeordnetennamen'),
        ]
        report=build(records,since=SINCE,now=NOW,pages=2)
        self.assertEqual(report['total_dip_documents_in_update_window'],6)
        self.assertEqual(report['unfiltered_priority_procedure_parent_count'],2)
        self.assertEqual(
            {c['official_dip_parent_id'] for c in
             report['unfiltered_priority_procedure_parents']},
            {'348101','348102'})
        self.assertEqual(report['other_relevant_parent_ids_outside_18_pins'],1)
        self.assertTrue(all(not c['ordnungsruf_keyword_present_in_title_or_abstract']
                            and not c['original_measure_identity_verified']
                            and not c['appeal_or_legal_outcome_decided']
                            and c['automatically_approved_effective_sanctions']==0
                            for c in report['unfiltered_priority_procedure_parents']))
        self.assertIn('348102',markdown(report))

    def test_shadow_catches_description_only_procedure_not_surname_or_unrelated_topics(self):
        records=[
            {**doc(348201,'Nicht zugeordneter Vorgang'),
             'abstract':'Der Abgeordnete Stefan Keuter legt Einspruch ein'},
            doc(348202,'Widerspruch von Peter Reichardt zu einer Änderung'),
            doc(348203,'Einspruch einer anderen Person'),
            doc(348204,'Martin Reichardt beim Sportverein'),
            doc(348205,'Einspruch gegen einen Ordnungsruf an Martin Reichardt'),
        ]
        report=build(records,since=SINCE,now=NOW,pages=1)
        self.assertEqual(report['unfiltered_priority_procedure_parent_count'],1)
        self.assertEqual(
            report['unfiltered_priority_procedure_parents'][0]['official_dip_parent_id'],
            '348201')
        self.assertEqual(report['other_relevant_parent_ids_outside_18_pins'],1)

    def test_shadow_rejects_invalid_metadata_before_claiming_complete_report(self):
        item=doc(348301,'Einspruch des Abg Martin Reichardt')
        item['aktualisiert']='2024-01-01T00:00:00+00:00'
        with self.assertRaises(ValueError):
            build([item],since=SINCE,now=NOW,pages=1)
        item=doc(348302,'Beschwerde Stefan Keuter')
        item['datum']='not-a-day'
        with self.assertRaises(ValueError):
            build([item],since=SINCE,now=NOW,pages=1)
        item=doc(348303,'Einspruch Stefan Keuter')
        item['abstract']=None
        # None is a permissible empty optional field.
        self.assertEqual(
            build([item],since=SINCE,now=NOW,pages=1)
            ['unfiltered_priority_procedure_parent_count'],1)

    def test_appeal_and_penalty_not_confused_with_original(self):
        rows=[
            doc(345100,'Einspruch gegen die Erteilung eines Ordnungsrufes'),
            doc(345101,'Ordnungsgeld an einen Abgeordneten'),
            doc(345102,'Erteilung eines Ordnungsrufes an Abgeordneten A'),
            doc(345103,'Ordnungsruf im Bundestag'),
            doc(345104,'Abstimmung zur Zurückweisung eines Ordnungsrufes'),
        ]
        report=build(rows,since=SINCE,now=NOW,pages=1)
        self.assertEqual(report['possible_original_parent_ids_outside_18_pins'],1)
        self.assertEqual(report['other_relevant_parent_ids_outside_18_pins'],4)
        self.assertTrue(all(c['classification_for_manual_review']
                            != 'possible_original_grant_metadata'
                            for c in report['other_metadata_for_individual_review']))
        self.assertEqual(report['automatically_rescinded_sanctions'],0)

    def test_same_person_and_date_in_snapshot_is_flag_not_automatic_dedup(self):
        item=doc(345200,
                 'Erteilung eines Ordnungsrufes an Markus Frohnmaier',
                 date='2025-12-19')
        report=build([item],since=START,now=NOW,pages=1)
        cand=report['possible_originals_for_individual_review'][0]
        self.assertEqual(cand['possible_overlap_with_dated_positive_sample'],
                         [{'session':51,'person':'Markus Frohnmaier'}])
        self.assertFalse(cand['original_issue_individually_verified'])
        self.assertTrue(report['full_legislative_period_update_window'])

    def test_two_distinct_wording_variants_are_hints_not_two_approved_grants(self):
        variants=[
            'Erteilung von zwei Ordnungsrufen an die Abg Test',
            'Erteilung zweier Ordnungsrufe an den Abg Test',
            'Erteilung eines weiteren Ordnungsrufes an den Abg Test',
            'Erteilung von drei Ordnungsrufen an den Abg Test',
        ]
        for idx,title in enumerate(variants,start=1):
            with self.subTest(title=title):
                report=build([doc(347000+idx,title)],
                             since=SINCE,now=NOW,pages=1)
                self.assertEqual(report['possible_original_parent_ids_outside_18_pins'],1)
                self.assertEqual(report['automatically_confirmed_new_sanctions'],0)

    def test_title_absent_relevant_abstract_still_reviewed_not_grant(self):
        item=doc(345300,'Parlamentarischer Vorgang')
        item['abstract']='Erwähnung eines Ordnungsrufes'
        report=build([item],since=SINCE,now=NOW,pages=1)
        self.assertEqual(report['possible_original_parent_ids_outside_18_pins'],0)
        self.assertEqual(report['other_relevant_parent_ids_outside_18_pins'],1)

    def test_duplicate_wrong_term_and_bad_timestamp_rejected(self):
        item=doc(345400,'Ordnungsruf gegen Abgeordneten')
        with self.assertRaises(ValueError):
            build([item,item],since=SINCE,now=NOW,pages=1)
        foreign=copy.deepcopy(item)
        foreign['wahlperiode']=20
        with self.assertRaises(ValueError):
            build([foreign],since=SINCE,now=NOW,pages=1)
        invalid=copy.deepcopy(item)
        invalid['aktualisiert']='not-a-date'
        with self.assertRaises(ValueError):
            build([invalid],since=SINCE,now=NOW,pages=1)

    def test_cursor_pagination_and_solely_audit_outputs(self):
        AUDIT_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=AUDIT_ROOT) as temporary:
            dest=Path(temporary)/'discovery'
            seen=[]
            def load(params,key):
                seen.append(dict(params))
                if len(seen)==1:
                    return {'numFound':2,'cursor':'next','documents':[
                        doc(345500,'Erteilung eines Ordnungsrufes an A')]}
                return {'numFound':2,'cursor':None,'documents':[
                    doc(345501,'Einspruch gegen einen Ordnungsruf')]}
            ledger=Path('daten/wirksame_ordnungsrufe_21wp.csv').read_bytes()
            report=run(since=SINCE,now=NOW,key='test',load=load,output_dir=dest,
                       fetch=lambda parent,key:[position(parent,800001,90,'2026-07-10')])
            self.assertEqual(len(seen),2)
            self.assertEqual(seen[1]['cursor'],'next')
            self.assertEqual(report['api_pages_completely_fetched'],2)
            self.assertEqual(report['possible_original_parent_ids_outside_18_pins'],1)
            self.assertEqual(report['other_relevant_parent_ids_outside_18_pins'],1)
            self.assertEqual(Path('daten/wirksame_ordnungsrufe_21wp.csv').read_bytes(),ledger)
            stored=json.loads((dest/'outside_pins.json').read_text())
            self.assertEqual(stored['automatically_confirmed_new_sanctions'],0)
            self.assertIn('Keine bestätigten neuen Maßnahmen',
                          (dest/'outside_pins.md').read_text())
            self.assertTrue((dest/'review_queue.json').is_file())
            self.assertTrue((dest/'review_queue.md').is_file())

    def test_incomplete_api_pages_do_not_produce_report(self):
        AUDIT_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=AUDIT_ROOT) as temporary:
            folder=Path(temporary)/'incomplete'
            def incomplete(params,key):
                return {'numFound':2,'cursor':'loop','documents':[
                    doc(345600,'Erteilung eines Ordnungsrufes an A')]}
            with self.assertRaises(ValueError):
                run(since=SINCE,now=NOW,key='test',
                    load=incomplete,output_dir=folder,max_pages=2)
            self.assertFalse(folder.exists())

    def test_empty_complete_source_is_not_fabricated_coverage(self):
        AUDIT_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=AUDIT_ROOT) as temporary:
            report=run(since=SINCE,now=NOW,key='test',
                       load=lambda p,k:{'numFound':0,'cursor':None,'documents':[]},
                       output_dir=Path(temporary)/'empty')
            self.assertEqual(report['total_dip_documents_in_update_window'],0)
            self.assertFalse(report['full_legislative_period_update_window'])
            self.assertIn('weder',report['warning'])

    def test_later_parent_date_not_conflated_with_sichert_origin(self):
        item=doc(337160,'Erteilung eines Ordnungsrufes an den Abg Martin Sichert (AfD)',
                 date='2026-09-08')
        starting=build([item],since=SINCE,now=NOW,pages=1)
        linked=corroborate_original_positions(
            starting,key='test',fetch=lambda parent,key:[
                position(parent,801001,90,'2026-07-10'),
                position(parent,801002,91,'2026-09-08',step='Abstimmung')])
        case=linked['possible_originals_for_individual_review'][0]
        self.assertEqual(case['official_original_position_count'],1)
        self.assertTrue(case['parent_display_date_is_not_original_position_date'])
        self.assertEqual(case['matched_dated_positive_sample_by_original_position'],
                         [{'session':90,'person':'Martin Sichert',
                           'original_date':'2026-07-10',
                           'matching_official_position_id':'801001'}])
        self.assertEqual(len(case['other_position_sources_needing_legal_review']),1)
        self.assertEqual(linked['candidates_matched_to_existing_positive_sample'],1)
        self.assertEqual(linked['candidates_without_positive_sample_original_match'],0)
        self.assertEqual(linked['automatically_confirmed_new_sanctions'],0)

    def test_same_surname_other_original_session_not_false_dedup(self):
        item=doc(345777,'Erteilung eines Ordnungsrufes an den Abg Martin Sichert',
                 date='2026-09-08')
        base=build([item],since=SINCE,now=NOW,pages=1)
        linked=corroborate_original_positions(
            base,key='test',fetch=lambda p,k:[
                position(p,801003,95,'2026-09-17')])
        self.assertEqual(linked['candidates_matched_to_existing_positive_sample'],0)
        self.assertEqual(linked['candidates_without_positive_sample_original_match'],1)

    def test_crosswalk_rejects_wrong_parent_and_broken_official_fundstelle(self):
        item=doc(345778,'Erteilung eines Ordnungsrufes an den Abg Test')
        base=build([item],since=SINCE,now=NOW,pages=1)
        with self.assertRaises(ValueError):
            corroborate_original_positions(
                base,key='test',fetch=lambda p,k:[
                    position('999999',801004,90,'2026-07-10')])
        damaged=position('345778',801004,90,'2026-07-10')
        damaged['fundstelle']['pdf_url']='https://example.com/fake.pdf'
        with self.assertRaises(ValueError):
            corroborate_original_positions(
                base,key='test',fetch=lambda p,k:[damaged])

    def test_empty_or_incomplete_position_source_cannot_complete(self):
        item=doc(345779,'Erteilung eines Ordnungsrufes an den Abg Test')
        base=build([item],since=SINCE,now=NOW,pages=1)
        with self.assertRaises(ValueError):
            corroborate_original_positions(base,key='test',fetch=lambda p,k:[])
        with self.assertRaises(ValueError):
            corroborate_original_positions(
                {**base,'automatically_confirmed_new_sanctions':1},
                key='test',fetch=lambda p,k:[position(p,801005,90,'2026-07-10')])

    def test_only_unmatched_origins_go_into_manual_work_bundles(self):
        docs=[
            doc(337160,'Erteilung eines Ordnungsrufes an den Abg Martin Sichert',
                date='2026-09-08'),
            doc(345901,'Erteilung von zwei Ordnungsrufen an Abg Beispiel',
                date='2026-10-01'),
        ]
        base=build(docs,since=SINCE,now=NOW,pages=1)
        def fetch(parent,key):
            if parent=='337160':
                return [position(parent,802001,90,'2026-07-10')]
            return [
                position(parent,802002,102,'2026-10-01'),
                position(parent,802003,103,'2026-10-02',step='Abstimmung'),
            ]
        linked=corroborate_original_positions(base,key='test',fetch=fetch)
        queue=make_manual_review_batches(linked)
        self.assertEqual(queue['pending_parent_review_tasks'],1)
        self.assertEqual(len(queue['batches']),1)
        self.assertEqual(queue['batches'][0][0]['official_dip_parent_id'],'345901')
        self.assertEqual(queue['batches'][0][0]['priority'],'hoch')
        self.assertEqual(queue['automatic_counted_new_sanctions'],0)
        self.assertFalse(queue['protected_ledgers_changed'])
        self.assertIn('keine',review_markdown(queue).lower())
        with self.assertRaises(ValueError):
            review_markdown({**queue,'automatic_counted_new_sanctions':1})

    def test_zero_unmatched_queue_does_not_invent_manual_tasks(self):
        base=build([
            doc(337160,'Erteilung eines Ordnungsrufes an Martin Sichert',
                date='2026-09-08')],
            since=SINCE,now=NOW,pages=1)
        linked=corroborate_original_positions(
            base,key='test',fetch=lambda parent,key:[
                position(parent,802004,90,'2026-07-10')])
        q=make_manual_review_batches(linked)
        self.assertEqual(q['pending_parent_review_tasks'],0)
        self.assertEqual(q['batches'],[])
        self.assertEqual(q['automatic_counted_new_sanctions'],0)
        self.assertIn('Offene DIP-Elternvorgänge: 0',review_markdown(q))

    def test_outside_audit_and_unsafely_modified_count_rejected(self):
        report=build([],since=SINCE,now=NOW,pages=1)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                save(report,Path(tmp)/'public')
        with self.assertRaises(ValueError):
            markdown({**report,'automatically_confirmed_new_sanctions':1})

    def test_missing_timezone_and_future_start_rejected(self):
        with self.assertRaises(ValueError):
            build([],since=NOW.replace(tzinfo=None),now=NOW,pages=1)
        with self.assertRaises(ValueError):
            build([],since=NOW+timedelta(days=1),now=NOW,pages=1)
        with self.assertRaises(ValueError):
            build([],since=SINCE,now=NOW,pages=0)


if __name__=='__main__':
    unittest.main()
