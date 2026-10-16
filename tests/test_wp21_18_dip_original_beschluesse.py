"""Fail-closed direct official DIP original-PDF and appeal-tenor dossier tests."""
import copy
import unittest

from wp21_18_dip_original_beschluesse import PINS,assemble,render_markdown
from wp21_18_dip_verfahrenspositionen import control_dates
from wp21_dip_kontrolle import reference
from wp21_einspruchsbelege import validated_index
from wp21_hochprioritaet_18 import TARGETS
from wp21_autopruefung import norm

NEXT_SITTING={52:53,65:66,67:68,69:70}


def position(identifier,parent,session,date,step,person='',is_appeal=False):
    pdf=f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf#P.100'
    url=f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml'
    raw={
        'id':str(identifier),'vorgang_id':parent,'wahlperiode':21,
        'datum':date,'aktualisiert':'2026-10-16T08:00:00+00:00',
        'vorgangsposition':step,'titel':f'Ordnungsruf {person}',
        'fundstelle':{
            'dokumentart':'Plenarprotokoll',
            'dokumentnummer':f'21/{session}',
            'datum':date,'pdf_url':pdf,'xml_url':url},
    }
    if is_appeal:
        raw['abstract']=f'Einspruch des Abg {person} gegen die Ordnungsmaßnahme'
        raw['beschlussfassung']=[{'beschlusstenor':'Zurückweisung des Einspruchs',
                                 'seite':'100A'}]
    return {'id':str(identifier),
            'source_api':'https://search.dip.bundestag.de/api/v1/vorgangsposition/'+str(identifier),
            'official_raw_metadata':raw}


def snapshot():
    dates=control_dates(reference())
    decisions=validated_index()
    cases=[]
    for n,(session,person) in enumerate(
            ((s,name) for s,names in sorted(TARGETS.items()) for name in names),1):
        key=(session,norm(person))
        parent=PINS[key]
        current=[
            position(600000+n,parent,session,dates[key],'Ordnungsruf',person)]
        if key in decisions:
            current.append(position(700000+n,parent,NEXT_SITTING[session],
                                    decisions[key]['decision_date'],'Abstimmung',
                                    person,is_appeal=True))
        cases.append({
            'session':session,'person':person,'vorgang_id':parent,
            'vorgang_source':'https://dip.bundestag.de/vorgang/'+parent,
            'positions':current,
        })
    return {'status':'official_position_source_reference_inventory',
            'original_cases':18,'positions':22,
            'no_automated_sanction_decisions':True,'cases':cases}


class StructuredDIPOriginalEvidenceTests(unittest.TestCase):
    def test_all_eighteen_full_sources_and_four_rejected_appeals(self):
        r=assemble(snapshot())
        self.assertEqual(r['case_count'],18)
        self.assertEqual(r['position_count'],22)
        self.assertEqual(r['grant_source_position_count'],18)
        self.assertEqual(r['appeal_decision_tenor_count'],4)
        self.assertEqual(r['automatically_confirmed_effective_sanctions'],0)
        self.assertEqual(r['automatically_rescinded_sanctions'],0)
        self.assertFalse(r['protected_public_counters_changed'])
        self.assertEqual(sum(bool(c['separate_appeal_decision_source'])
                             for c in r['cases']),4)
        self.assertIn('Zurückweisung',render_markdown(r))

    def test_alien_vorgang_id_fails(self):
        s=snapshot()
        s['cases'][0]['vorgang_id']='334727' # different original Reichardt
        with self.assertRaisesRegex(ValueError,'Falscher amtlicher'):
            assemble(s)

    def test_two_original_grants_are_not_inferred_from_two_phrases(self):
        r=assemble(snapshot())
        c=next(x for x in r['cases']
               if x['session']==94 and x['person']=='Cansin Köktürk')
        self.assertEqual(c['original_grant_source']['position_type'],'Ordnungsruf')
        self.assertTrue(c['legal_effect_and_distinct_issuance_count_not_inferred'])
        self.assertNotIn('number_of_legally_effective_grants',r)

    def test_wrong_appeal_identity_or_tenor_fails_closed(self):
        s=snapshot()
        c=next(x for x in s['cases'] if x['session']==52)
        vote=c['positions'][1]['official_raw_metadata']
        vote['abstract']='Einspruch des Abg Martin Reichardt'
        with self.assertRaisesRegex(ValueError,'Einspruchsbeschluss'):
            assemble(s)
        s=snapshot()
        c=next(x for x in s['cases'] if x['session']==52)
        vote=c['positions'][1]['official_raw_metadata']
        vote['beschlussfassung'][0]['beschlusstenor']='Offene Abstimmung'
        with self.assertRaisesRegex(ValueError,'Einspruchsbeschluss'):
            assemble(s)

    def test_wrong_sitting_fundstelle_or_duplicated_position_fails(self):
        s=snapshot()
        c=next(x for x in s['cases'] if x['session']==65
               and x['person']=='Martin Reichardt')
        orig=c['positions'][0]['official_raw_metadata']
        orig['fundstelle']['dokumentnummer']='21/77'
        orig['fundstelle']['pdf_url']='https://dserver.bundestag.de/btp/21/21077.pdf#P.100'
        orig['fundstelle']['xml_url']='https://dserver.bundestag.de/btp/21/21077.xml'
        with self.assertRaisesRegex(ValueError,'Originalerteilung'):
            assemble(s)
        s=snapshot()
        s['cases'][1]['positions'][0]['id']=s['cases'][0]['positions'][0]['id']
        with self.assertRaisesRegex(ValueError,'Position ohne amtlichen'):
            assemble(s)

    def test_missing_original_or_missing_appeal_must_not_look_complete(self):
        s=snapshot()
        s['cases']=s['cases'][:-1]
        with self.assertRaisesRegex(ValueError,'Nicht alle 22'):
            assemble(s)
        s=snapshot()
        next(x for x in s['cases'] if x['session']==52)['positions'].pop()
        with self.assertRaisesRegex(ValueError,'Erteilung/Einspruch in Originalakte unvollständig'):
            assemble(s)
        s=snapshot()
        s['positions']=23
        with self.assertRaisesRegex(ValueError,'18/22'):
            assemble(s)


if __name__=='__main__':
    unittest.main()
