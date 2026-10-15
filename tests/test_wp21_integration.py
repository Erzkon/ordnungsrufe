"""Complete offline DIP workflow: initial sync, linked follow-up, later change.

All three stages use the REAL code, mocked network, and temp directories.
This deliberately never edits verified CSV files or approved web counters.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wp21_dip_monitor import run as sync_vorgaenge
from wp21_dip_positionen import run as sync_positionen
from wp21_pruefqueue import run as link_review

NOW=datetime.now(timezone.utc).replace(microsecond=0)


def vorgang(ident, title, abstract=''):
    return {'id':str(ident), 'wahlperiode':21, 'typ':'Vorgang',
            'titel':title,'abstract':abstract,
            'datum':'2026-09-10',
            'aktualisiert':(NOW-timedelta(hours=1)).isoformat()}


def position(ident, parent, text):
    return {'id':str(ident),'vorgang_id':str(parent), 'typ':'Vorgangsposition',
            'wahlperiode':21, 'titel':'Ordnungsruf',
            'datum':'2026-09-10','aktualisiert':NOW.isoformat(),
            'vorgangsposition':text}


class CompletePipelineTests(unittest.TestCase):
    def test_full_readonly_pipeline_and_followup_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            vstate=folder/'vorgang.json'
            vsum=folder/'vorgang_summary.json'
            vchanges=folder/'vorgang_changes.json'
            pstate=folder/'position.json'
            psum=folder/'position_summary.json'
            pchanges=folder/'position_changes.json'
            cases=folder/'cases.json'
            review=folder/'review_summary.json'
            # The grant is discovered; a different unrelated record is ignored.
            docs=[vorgang(330701,'Ordnungsruf für Frau Beispiel'),
                  vorgang(330702,'Versorgung und Infrastruktur')]
            def load(params,key):
                return {'numFound':len(docs),'documents':docs, 'cursor':None}
            original=(Path('daten/wirksame_ordnungsrufe_21wp.csv').read_bytes(),
                      Path('docs/data/ordnungsrufe_21.json').read_bytes())
            first=sync_vorgaenge(vstate,vsum,vchanges,now=NOW,key='test',load=load)
            self.assertEqual(first['tracked_relevant_vorgaenge'],1)
            self.assertEqual(first['new_vorgaenge'],1)
            followups=[position(331001,330701,'Der Ordnungsruf wurde erteilt')]
            def positions(parent,key):
                self.assertEqual(parent,'330701')
                return list(followups)
            second=sync_positionen(vstate,pstate,psum,pchanges,
                                   fetch=positions,now=NOW+timedelta(minutes=2),key='test')
            self.assertEqual(second['tracked_positions'],1)
            report=link_review(vstate,pstate,review,cases)
            self.assertEqual(report['linked_dip_vorgaenge'],1)
            self.assertEqual(report['high_priority_cases'],0)
            self.assertEqual(report['automatically_confirmed_sanctions'],0)
            self.assertEqual(json.loads(cases.read_text())[0]['last_steps'][0]['id'],'331001')
            # A subsequent procedural decision is a HIGH priority case,
            # not a legally certified rescission or newly counted grant.
            followups.append(position(331002,330701,
                                       'Einspruch gegen den Ordnungsruf zurückgewiesen'))
            second=sync_positionen(vstate,pstate,psum,pchanges,
                                   fetch=positions,now=NOW+timedelta(minutes=3),key='test')
            self.assertEqual(second['new_positions'],1)
            report=link_review(vstate,pstate,review,cases)
            self.assertEqual(report['high_priority_cases'],1)
            self.assertEqual(report['automatically_confirmed_sanctions'],0)
            self.assertEqual(report['automatically_rescinded_sanctions'],0)
            self.assertEqual(
                original,
                (Path('daten/wirksame_ordnungsrufe_21wp.csv').read_bytes(),
                 Path('docs/data/ordnungsrufe_21.json').read_bytes()))

    def test_fail_in_followup_preserves_previous_public_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            vstate=root/'vs.json'
            sync_vorgaenge(vstate,root/'vr.json',root/'vc.json',now=NOW,key='test',
                load=lambda p,k:{'numFound':1,'cursor':None,
                                  'documents':[vorgang(330701,'Ordnungsruf')]})
            def positions(parent,key):
                return [position(331001,330701,'Ordnungsruf')]
            paths=(vstate,root/'ps.json',root/'pr.json',root/'pc.json')
            sync_positionen(*paths,now=NOW+timedelta(minutes=2),key='test',
                            fetch=positions)
            raw=[x.read_bytes() for x in paths[1:]]
            def fail(parent,key):
                raise TimeoutError('DIP-Verfahrensdaten nicht erreichbar')
            with self.assertRaises(TimeoutError):
                sync_positionen(*paths,now=NOW+timedelta(minutes=3),
                                key='test',fetch=fail)
            self.assertEqual(raw,[x.read_bytes() for x in paths[1:]])

if __name__ == '__main__': unittest.main()
