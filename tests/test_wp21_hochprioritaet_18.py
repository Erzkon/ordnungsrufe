"""Eighteen original WP21 person/sitting dossiers are never sanctions."""
from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
from lxml import etree
from wp21_hochprioritaet_18 import (
    EXPECTED_KEYS, ORIGINAL_LINES, TARGETS, assemble, legal_hints,
    original_entry, render_manual_review_brief, validate_scope,
    explicit_original_sitting_refs)
from wp21_dip_kontrolle import reference
from wp21_einspruchsbelege import EVIDENCE
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
        self.assertEqual(set(ORIGINAL_LINES),EXPECTED_KEYS)
        self.assertEqual(sum(map(len,ORIGINAL_LINES.values())),21)
        self.assertEqual(len(EVIDENCE),4)
        dip={(x['session'],norm(x['person'])) for x in reference()['entries']}
        self.assertTrue(EXPECTED_KEYS.issubset(dip))

    def test_official_appeals_match_exactly_four_individual_source_cases(self):
        from wp21_einspruchsbelege import validated_index
        idx=validated_index()
        self.assertEqual(set(idx),{
            (52,norm('Martin Hess')),(65,norm('Martin Reichardt')),
            (67,norm('Kerstin Przygodda')),(69,norm('Fabian Fahl'))})
        self.assertNotIn((67,norm('Kathrin Gebel')),idx)
        self.assertNotIn((69,norm('Timon Dzienus')),idx)
        self.assertNotIn((51,norm('Markus Frohnmaier')),idx)

    def test_original_episodes_are_two_phrases_not_two_legal_measures(self):
        from wp21_hochprioritaet_18 import MULTI_PHRASE_EPISODES
        self.assertEqual(set(MULTI_PHRASE_EPISODES),{
            (51,norm('Markus Frohnmaier')),
            (65,norm('Martin Reichardt')),
            (94,norm('Cansin Köktürk'))})
        self.assertIn('repetition_possible',
                      MULTI_PHRASE_EPISODES[(65,norm('Martin Reichardt'))])

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
        found_hess=legal_hints(
            roots[53],53,subject='Martin Hess',origin_session=52)
        found_przy=legal_hints(
            roots[68],68,subject='Kerstin Przygodda',origin_session=67)
        self.assertEqual(len(found_hess),1)
        self.assertEqual(len(found_przy),1)
        self.assertTrue(found_hess[0]['explicit_original_session_reference_in_same_paragraph'])
        self.assertTrue(found_przy[0]['explicit_original_session_reference_in_same_paragraph'])
        self.assertEqual(legal_hints(
            roots[53],53,subject='Martin Hess',origin_session=67),[])
        self.assertEqual(legal_hints(roots[53],53,subject='Heidi Reichinnek'),[])

    def test_other_original_sitting_must_not_borrow_the_same_politicians_appeal(self):
        # Real official 21/078 discusses Reichardt's *other* 21/077
        # original grant. Previous generic full-name matching wrongly put
        # this in the 21/065 high-priority case's follow-up dossier.
        later=fixture(78,
            'Der Abgeordnete Martin Reichardt hat Einspruch gegen den '
            'ihm in der 77. Sitzung erteilten Ordnungsruf eingelegt.')
        self.assertEqual(explicit_original_sitting_refs(
            'Dem Abgeordneten wurde in der 77. Sitzung ein Ordnungsruf erteilt.'),
            {77})
        self.assertEqual(legal_hints(
            later,78,subject='Martin Reichardt',origin_session=65),[])
        self.assertEqual(len(legal_hints(
            later,78,subject='Martin Reichardt',origin_session=77)),1)
        self.assertEqual(explicit_original_sitting_refs(
            'Martin Reichardt und der Ordnungsruf aus der 65. Sitzung '
            'sowie der 77. Sitzung waren Gegenstand eines Einspruchs.'),{65,77})
        ambiguous=fixture(78,
            'Martin Reichardt und der Ordnungsruf aus der 65. Sitzung '
            'sowie der 77. Sitzung waren Gegenstand eines Einspruchs.')
        self.assertEqual(legal_hints(
            ambiguous,78,subject='Martin Reichardt',origin_session=65),[])
        # Generic same-name keyword mentions without an original sitting
        # remain unverified review hints, NOT outcome determinations.
        vague=fixture(66,
            'Martin Reichardt hat fristgerecht Einspruch gegen den '
            'Ordnungsruf der vergangenen Sitzung eingelegt.')
        hints=legal_hints(vague,66,subject='Martin Reichardt',origin_session=65)
        self.assertEqual(len(hints),1)
        self.assertFalse(hints[0]['explicit_original_session_reference_in_same_paragraph'])
        self.assertTrue(hints[0]['cross_sitting_identity_and_legal_outcome_unverified'])

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
        # Synthetic fixtures have one XML phrase; keep the production
        # 21-line source anchors intact and test only the procedural linking.
        fake_lines={key:(1,) for key in EXPECTED_KEYS}
        with patch('wp21_hochprioritaet_18.events',side_effect=fake_events):
            with patch.dict('wp21_hochprioritaet_18.ORIGINAL_LINES',
                            fake_lines,clear=True):
                with patch.dict('wp21_hochprioritaet_18.MULTI_PHRASE_EPISODES',
                                {},clear=True):
                    with patch('wp21_hochprioritaet_18.validate_scope',
                               return_value=None):
                        report=assemble(roots,reference(),
                                        {(94,norm('Cansin Köktürk')):2})
        self.assertEqual(report['person_session_cases'],18)
        self.assertEqual(report['official_protocols_reviewed'],14)
        self.assertEqual(report['automatically_confirmed_effective_sanctions'],0)
        self.assertEqual(report['automatically_rescinded_sanctions'],0)
        self.assertFalse(report['protected_public_counters_changed'])
        self.assertEqual(report['separately_officially_documented_rejected_appeals'],4)
        self.assertTrue(report['appeal_decisions_are_not_automatic_sanction_confirmations'])
        with patch.dict('wp21_hochprioritaet_18.ORIGINAL_LINES',
                        fake_lines,clear=True):
            matrix=render_manual_review_brief(report)
            self.assertEqual(matrix.count('Keine Einzelentscheidung in kuratierter Vierer-Auswahl'),14)
            self.assertEqual(matrix.count('[zurückgewiesen '),4)
            self.assertIn('Martin Hess',matrix)
            self.assertIn('Kerstin Przygodda',matrix)
            self.assertIn('Frohnmaier',matrix)
            self.assertIn('**Keine automatische Veröffentlichung',matrix)
            self.assertIn('Nur die 14 ausgewählten Originalprotokolle',matrix)
            self.assertIn('Spätere namentliche XML-Textstellen:',matrix)
            with self.assertRaises(ValueError):
                render_manual_review_brief({**report,
                    'automatically_confirmed_effective_sanctions':1})
        decisions=[e for e in report['cases'] if e['official_bundestag_appeal_decision']]
        self.assertEqual(len(decisions),4)
        self.assertTrue(all(x['official_bundestag_appeal_decision']['outcome']==
                            'einspruch_zurueckgewiesen' for x in decisions))
        self.assertTrue(all(x['official_bundestag_appeal_decision']['confirms_number_of_effective_sanctions']
                            is False for x in decisions))
        self.assertTrue(all(x['official_bundestag_appeal_decision']['changes_protected_ledger']
                            is False for x in decisions))
        for e in report['cases']:
            if e['person_for_review'] in ('Kathrin Gebel','Timon Dzienus'):
                self.assertIsNone(e['official_bundestag_appeal_decision'])
        row=next(x for x in report['cases'] if x['session']==94)
        self.assertEqual(row['verified_effective_measures_in_preexisting_partial_ledger'],2)
        self.assertEqual(row['dip_original_grants_reference'],2)
        self.assertEqual(row['distinct_parser_issuance_wordings'],1)
        self.assertTrue(row['requires_independent_individual_issuance_review'])
        self.assertEqual(row['later_sittings_search_scope'],
                         'only_14_selected_original_sessions_not_exhaustive')
