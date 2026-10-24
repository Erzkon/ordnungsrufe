"""DIP discovery outside pinned WP21 parent IDs: read-only and fail closed."""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wp21_dip_monitor import START, iso
from wp21_new_dip_candidates import (
    AUDIT_ROOT, build, classify, markdown, run, save,
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
            report=run(since=SINCE,now=NOW,key='test',load=load,output_dir=dest)
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
