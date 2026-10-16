"""Eighteen original WP21 person/sitting dossiers are never sanctions."""
from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
from lxml import etree
from wp21_hochprioritaet_18 import (
    EXPECTED_KEYS, TARGETS, assemble, legal_hints, original_entry, validate_scope)
from wp21_dip_kontrolle import reference
from wp21_autopruefung import norm


def fixture(session, text='Ich erteile einen Ordnungsruf.'):
    return etree.fromstring((
        f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{session}">'
        '<sitzungsverlauf><tagesordnungspunkt><rede>'
        '<name>Vizepräsidentin Andrea Lindholz</name>'
        f'<p>{text}</p></rede></tagesordnungspunkt></sitzungsverlauf>'
        '</dbtplenarprotokoll>').encode())


class EighteenIndividualSourceTests(TestCase):
    def test_exact_18_person_session_targets_are_in_official_positive_snapshot(self):
        validate_scope()
        self.assertEqual(len(TARGETS),14)
        self.assertEqual(len(EXPECTED_KEYS),18)
        dip={(x['session'],norm(x['person'])) for x in reference()['entries']}
        self.assertTrue(EXPECTED_KEYS.issubset(dip))

    def test_one_original_paragraph_is_not_a_confirmed_sanction(self):
        ev={'line':3,'evidence_type':'possible_grant','status':'review_required',
            'text':'Ich erteile einen Ordnungsruf.',
            'zuordnungsmethode':'direkte_anrede',
            'identity_status':'matched_xml_person','person_id':'123',
            'issuer':'Vizepräsidentin Andrea Lindholz',
            'issuer_evidence':'chair_marker'}
        original=original_entry(ev,{3:ev['text']})
        self.assertEqual(len(original['text_sha256']),64)
        self.assertFalse(original['is_separately_confirmed_effective_sanction'])
        with self.assertRaises(ValueError):
            original_entry({**ev,'status':'confirmed'},{3:ev['text']})
        with self.assertRaises(ValueError):
            original_entry(ev,{3:'Unerwarteter Text'})
        with self.assertRaises(ValueError):
            original_entry({**ev,'evidence_type':'warning_or_conditional'},
                           {3:ev['text']})

    def test_keyword_hits_are_not_person_or_outcome_proof(self):
        root=fixture(71,'Gegen den Ordnungsruf wurde Einspruch eingelegt.')
        signals=legal_hints(root,71)
        self.assertEqual(len(signals),1)
        self.assertTrue(signals[0]['person_and_legal_outcome_not_verified'])
        self.assertEqual(legal_hints(root,71,subject='Mirze Edis'),[])
        self.assertNotIn('person',signals[0])

    def test_later_original_session_cites_full_person_not_assumed_decision(self):
        roots={s:fixture(s) for s in TARGETS}
        roots[53]=fixture(53,
            'Martin Hess hat Einspruch gegen den ihm in der 52. Sitzung '
            'erteilten Ordnungsruf eingelegt.')
        roots[68]=fixture(68,
            'Kerstin Przygodda hat Einspruch gegen den ihr in der 67. Sitzung '
            'erteilten Ordnungsruf eingelegt.')
        # Check textual extraction independently; no effective measure.
        self.assertEqual(len(legal_hints(roots[53],53,subject='Martin Hess')),1)
        self.assertEqual(len(legal_hints(roots[68],68,subject='Kerstin Przygodda')),1)
        self.assertEqual(legal_hints(roots[53],53,subject='Heidi Reichinnek'),[])

    def test_missing_originals_and_incomplete_followups_fail(self):
        roots={s:fixture(s) for s in TARGETS}
        with self.assertRaisesRegex(ValueError,'14'):
            assemble({94:roots[94]},reference(),{})
        with self.assertRaisesRegex(ValueError,'Unvollständiger'):
            assemble(roots,reference(),{},
                     later_roots={94:roots[94]},last_scanned=101)
        with self.assertRaisesRegex(ValueError,'DIP'):
            assemble(roots,{'entries':[]},{})

    def test_synthetic_all_18_remain_unverified_even_with_two_ledger_entries(self):
        roots={s:fixture(s) for s in TARGETS}
        def fake_events(path,index=None,root=None):
            session=int(root.get('sitzung-nr'))
            node=root.xpath('.//rede/p')[-1]
            for person in TARGETS[session]:
                yield {'person':person,'line':node.sourceline,
                       'text':'Ich erteile einen Ordnungsruf.',
                       'status':'review_required','evidence_type':'possible_grant',
                       'zuordnungsmethode':'direkte_anrede',
                       'identity_status':'matched_xml_person','person_id':'123',
                       'issuer':'Vizepräsidentin Andrea Lindholz',
                       'issuer_evidence':'chair_marker'}
        with patch('wp21_hochprioritaet_18.events',side_effect=fake_events):
            report=assemble(roots,reference(),
                            {(94,norm('Cansin Köktürk')):2})
        self.assertEqual(report['person_session_cases'],18)
        self.assertEqual(report['official_protocols_reviewed'],14)
        self.assertEqual(report['automatically_confirmed_effective_sanctions'],0)
        self.assertEqual(report['automatically_rescinded_sanctions'],0)
        self.assertFalse(report['protected_public_counters_changed'])
        row=next(x for x in report['cases'] if x['session']==94)
        self.assertEqual(row['verified_effective_measures_in_preexisting_partial_ledger'],2)
        self.assertEqual(row['dip_original_grants_reference'],2)
        self.assertEqual(row['distinct_parser_issuance_wordings'],1)
        self.assertTrue(row['requires_independent_individual_issuance_review'])
        self.assertEqual(row['later_sittings_search_scope'],
                         'only_14_selected_original_sessions_not_exhaustive')
