"""Original DIP Plenar-Fundstellen and independently documented appeal decisions.

These are source linkage checks, NOT confirmed sanctions or rescissions.
The fixtures replicate bounded official DIP field shapes from 2026-10-16.
"""
import unittest

from wp21_dip_positionen import normalize_position, position_document_evidence
from wp21_18_dip_verfahrenspositionen import crosswalk


def original_raw():
    return {
        'id':'684560','vorgang_id':'330133','wahlperiode':21,
        'aktualisiert':'2026-10-15T09:00:00+00:00',
        'datum':'2026-01-14','titel':'Ordnungsruf für Martin Hess',
        'vorgangsposition':'Ordnungsruf',
        'fundstelle':{
            'id':'5763','dokumentnummer':'21/52','datum':'2026-01-14',
            'dokumentart':'Plenarprotokoll',
            'xml_url':'https://dserver.bundestag.de/btp/21/21052.xml',
            'pdf_url':'https://dserver.bundestag.de/btp/21/21052.pdf#P.6222',
        },
    }


def decision_raw(tenor='Zurückweisung des Einspruchs',person='Martin Hess'):
    return {
        'id':'684717','vorgang_id':'330133','wahlperiode':21,
        'aktualisiert':'2026-10-15T09:00:00+00:00',
        'datum':'2026-01-15','titel':'Einspruch zur Ordnungsmaßnahme',
        'vorgangsposition':'Abstimmung',
        'abstract':f'Einspruch des Abg {person} (AfD) gegen die Ordnungsmaßnahme',
        'beschlussfassung':[{'beschlusstenor':tenor,'seite':'6329B'}],
        'fundstelle':{
            'id':'5764','dokumentnummer':'21/53','datum':'2026-01-15',
            'dokumentart':'Plenarprotokoll',
            'xml_url':'https://dserver.bundestag.de/btp/21/21053.xml',
            'pdf_url':'https://dserver.bundestag.de/btp/21/21053.pdf#P.6329',
        },
    }


def states(grant=None,vote=None):
    g=normalize_position(grant or original_raw())
    v=normalize_position(vote or decision_raw())
    parents={'last_success_utc':'2026-10-15T08:00:00+00:00',
             'items':{'330133':{
                 'id':'330133','source':'https://dip.bundestag.de/vorgang/330133',
                 'active':True,'date':'2026-01-15','title':'Ordnungsruf für Martin Hess',
                 'abstract_excerpt':'','kind':'ordnungsruf_bezug'}}}
    positions={'last_success_utc':'2026-10-15T09:00:00+00:00',
               'items':{g['id']:{**g,'active':True},v['id']:{**v,'active':True}}}
    return parents,positions


class OfficialDIPFundstelleTests(unittest.TestCase):
    def test_exact_original_pdf_and_xml_page_citations_survive_normalizing(self):
        p=normalize_position(original_raw())
        self.assertEqual(p['official_plenary_session'],52)
        self.assertEqual(p['official_plenary_date'],'2026-01-14')
        self.assertEqual(p['official_plenary_pdf_url'],
                         'https://dserver.bundestag.de/btp/21/21052.pdf#P.6222')
        self.assertEqual(p['official_plenary_xml_url'],
                         'https://dserver.bundestag.de/btp/21/21052.xml')
        self.assertTrue(p['source_metadata_is_only_a_review_hint'])
        self.assertEqual(p['official_decision_tenors'],[])

    def test_dip_vote_decision_wording_is_explicit_but_not_new_sanction(self):
        p=normalize_position(decision_raw())
        self.assertEqual(p['official_plenary_session'],53)
        self.assertEqual(p['official_decision_tenors'],['Zurückweisung des Einspruchs'])
        self.assertIn('beschlussfassung',p['signal_fields'])
        self.assertEqual(p['kind'],'moegliche_rechtsfolge')
        self.assertFalse('automatically_confirmed_sanctions' in p)
        result=crosswalk(*states())
        self.assertEqual(result['source_verified_original_grant_positions'],1)
        self.assertEqual(result['source_verified_independent_dip_rejected_appeals'],1)
        self.assertEqual(result['automatically_confirmed_sanctions'],0)
        self.assertEqual(result['automatically_rescinded_sanctions'],0)
        rows=next(x for x in result['cases']
                  if x['session']==52 and x['person']=='Martin Hess')
        steps=rows['candidate_vorgaenge'][0]['procedural_position_hints']
        self.assertTrue(steps[0]['official_original_grant_position_source_verified'])
        self.assertTrue(steps[1]['independent_dip_appeal_rejection_tenor_source_verified'])
        self.assertFalse(steps[1]['is_individual_appeal_outcome_legally_confirmed'])
        self.assertIsNone(steps[1]['legal_measure_count_from_metadata'])

    def test_person_identity_and_tenor_are_both_required(self):
        r=crosswalk(*states(vote=decision_raw(person='Martin Reichardt')))
        self.assertEqual(r['source_verified_independent_dip_rejected_appeals'],0)
        r=crosswalk(*states(vote=decision_raw(tenor='Vertagung des Einspruchs')))
        self.assertEqual(r['source_verified_independent_dip_rejected_appeals'],0)
        self.assertEqual(r['automatically_confirmed_sanctions'],0)

    def test_unsafe_pdf_link_or_foreign_session_is_never_source_verified(self):
        x=original_raw()
        x['fundstelle']['pdf_url']='https://evil.example/btp/21/21052.pdf#P.6222'
        with self.assertRaisesRegex(ValueError,'nichtamtliche'):
            normalize_position(x)
        x=original_raw()
        x['fundstelle']['xml_url']='https://dserver.bundestag.de/btp/21/21077.xml'
        with self.assertRaisesRegex(ValueError,'nichtamtliche'):
            normalize_position(x)
        x=original_raw()
        x['fundstelle']['datum']='2026-03-01'
        with self.assertRaisesRegex(ValueError,'widersprechen'):
            normalize_position(x)
        x=original_raw()
        x['fundstelle']['dokumentnummer']='21/77'
        x['fundstelle']['xml_url']='https://dserver.bundestag.de/btp/21/21077.xml'
        x['fundstelle']['pdf_url']='https://dserver.bundestag.de/btp/21/21077.pdf#P.6222'
        with self.assertRaisesRegex(ValueError,'Fremde ursprüngliche'):
            crosswalk(*states(grant=x))

    def test_tampered_cached_document_url_cannot_bypass_source_validation(self):
        a,b=states()
        b['items']['684717']['official_plenary_pdf_url']='https://evil.example/21053.pdf#P.6329'
        with self.assertRaisesRegex(ValueError,'manipuliert'):
            crosswalk(a,b)

    def test_beschluss_tenor_and_abstract_type_fail_closed(self):
        raw=decision_raw()
        raw['beschlussfassung']=[{'beschlusstenor':'A'},{'beschlusstenor':'A'}]
        with self.assertRaisesRegex(ValueError,'Doppelte'):
            position_document_evidence(raw)
        raw=decision_raw()
        raw['beschlussfassung']=[{'beschlusstenor':{'unsafe':'object'}}]
        with self.assertRaisesRegex(ValueError,'DIP-Beschlusstenor'):
            normalize_position(raw)
        raw=decision_raw()
        raw['abstract']=['not','text']
        with self.assertRaisesRegex(ValueError,'abstract'):
            normalize_position(raw)

    def test_no_fundstelle_is_not_a_false_positive(self):
        p=original_raw()
        p.pop('fundstelle')
        r=normalize_position(p)
        self.assertIsNone(r['official_plenary_session'])
        self.assertIsNone(r['official_plenary_pdf_url'])
        self.assertEqual(r['official_decision_tenors'],[])


if __name__=='__main__':
    unittest.main()
