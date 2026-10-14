"""Isolationstests ohne Downloads, GitHub oder externe Dateien."""
import copy
import csv
import json
import hashlib
from pathlib import Path

import pytest
from abschlusskorrekturen import (FIELDS,DECISIONS,CheckError,correct,run,
    fingerprint_record,fingerprint_dip)


def example():
    source=[]
    def old(eid,pid,name,s,fr):
        item=dict(ereignis_id=eid, datum=f'01.01.2023',wahlperiode='20',sitzung=str(s),
                  person_id=pid,person=name,fraktion_zur_sitzung=fr,
                  quell_url='https://example.invalid/20.xml',beleg='https://example.invalid/20.pdf')
        source.append(item)
        return item
    # Original vor den Korrekturen (die Personen-IDs sind amtliche Nummern,
    # keine erfundenen Namen). Die vier bereits registrierten Identitaeten
    # werden in anderen Sitzungen referenziert.
    s=old('20-107-2983-01','11004892','Martin Sichert',107,'AfD')
    v=old('20-163-4303-01','11004905','Beatrix von Storch',163,'AfD')
    b=old('20-204-3164-01','11004678','Stephan Brandner',204,'AfD')
    old('20-020-7812-01','11004905','Beatrix von Storch',20,'AfD')
    old('20-060-5739-01','11005079','Matthias Helferich',60,'fraktionslos')
    old('20-085-5217-01','11005053','Robert Farle',85,'fraktionslos')
    dips={};sessions={}
    for sn in [20,31,32,60,85,107,136,147,163,191,204]:
        date={31:'28.04.2022',32:'29.04.2022',136:'15.11.2023',
              147:'18.01.2024',191:'10.10.2024'}.get(sn,'01.01.2023')
        sessions[str(sn)]=dict(sitzung=str(sn),datum=date)
    for did,sn,name,iso in [('287211','31','Beatrix von Storch','2022-04-29'),
                             ('306052','136','Matthias Helferich','2023-11-15'),
                             ('308052','147','Beatrix von Storch','2024-01-18'),
                             ('316468','191','Robert Farle','2024-10-10')]:
        dips[did]=dict(dip_id=did,dip_titel='Erteilung eines Ordnungsrufes an '+name,
                       dip_datum=iso,sitzungen_aus_dip='31;32' if did=='287211' else sn,
                       mehrfachvergabe_hinweis='nein')
    decisions=[]
    for row,typ,ref in [(s,'zurueckgenommen',108),(v,'zurueckgenommen',164),
                        (b,'fehlzuordnung',204)]:
        decisions.append(dict(aktion=typ,ereignis_id=row['ereignis_id'],person_id=row['person_id'],
            person=row['person'],sitzung=row['sitzung'],fraktion_zur_sitzung=row['fraktion_zur_sitzung'],
            dip_id='',quellenfingerabdruck=fingerprint_record(row),
            beleg=f'https://dserver.bundestag.de/btp/20/20{ref:03}.pdf#page=10',
            begruendung='Amtlich dokumentierte Begruendung'))
    for did,sn,pid,name,fr in [('287211','31','11004905','Beatrix von Storch','AfD'),
                               ('306052','136','11005079','Matthias Helferich','fraktionslos'),
                               ('308052','147','11004905','Beatrix von Storch','AfD'),
                               ('316468','191','11005053','Robert Farle','fraktionslos')]:
        decisions.append(dict(aktion='hinzufuegen',ereignis_id='',person_id=pid,person=name,
            sitzung=sn,fraktion_zur_sitzung=fr,dip_id=did,
            quellenfingerabdruck=fingerprint_dip(dips[did]),
            beleg=f'https://dserver.bundestag.de/btp/20/20{int(sn):03}.pdf#page=11',
            begruendung='Amtlich dokumentierte Erteilung'))
    return source,list(dips.values()),list(sessions.values()),decisions


def test_historical_corrections_are_separate_from_originals():
    original,dips,sessions,decisions=example()
    before=copy.deepcopy(original)
    result,excluded,added=correct(original,dips,sessions,decisions)
    assert len(result)==len(original)+1
    assert len(excluded)==3 and len(added)==4
    assert original==before
    assert {x['ereignis_id'] for x in original}-{x['ereignis_id'] for x in result}=={
        '20-107-2983-01','20-163-4303-01','20-204-3164-01'}
    assert sum(x['person']=='Beatrix von Storch' for x in result)==3

@pytest.mark.parametrize('position,field,new_value',[
    (0,'quellenfingerabdruck','sha256:invalid'),
    (3,'quellenfingerabdruck','sha256:invalid'),
    (0,'person_id','00000000'),
    (0,'aktion','fehlzuordnung'),
    (2,'aktion','zurueckgenommen'),
    (3,'fraktion_zur_sitzung','Sonstige'),
    (4,'person','Anderer Name'),
    (4,'sitzung','137'),
    (3,'dip_id','123456'),
    (3,'beleg','https://irrelevant.invalid/page'),
    (2,'beleg','https://dserver.bundestag.de/btp/20/20108.pdf#page=10'),
    (5,'begruendung',''),
])
def test_reject_wrong_decisions(position,field,new_value):
    source,dips,sessions,decisions=example()
    decisions[position][field]=new_value
    with pytest.raises(CheckError): correct(source,dips,sessions,decisions)

def test_reject_extra_decision():
    source,dips,sessions,decisions=example()
    decisions.append(copy.deepcopy(decisions[-1]))
    with pytest.raises(CheckError):correct(source,dips,sessions,decisions)

def test_source_change_blocks_previous_approval():
    source,dips,sessions,decisions=example()
    source[0]['beleg']='https://some-other-reference.invalid/'
    with pytest.raises(CheckError,match='QUELLENDRIFT'):
        correct(source,dips,sessions,decisions)

def test_dip_change_blocks_new_approval():
    source,dips,sessions,decisions=example()
    dips[0]['dip_datum']='2029-01-01'
    with pytest.raises(CheckError,match='QUELLENDRIFT'):
        correct(source,dips,sessions,decisions)

def test_no_duplicate_person_sitting():
    source,dips,sessions,decisions=example()
    source[3]['sitzung']='31'
    with pytest.raises(CheckError,match='bereits erfasst'):
        correct(source,dips,sessions,decisions)

def test_session_31_uses_subsequent_objection_date():
    source,dips,sessions,decisions=example()
    for row in sessions:
        if row['sitzung']=='32':row['datum']='30.04.2022'
    with pytest.raises(CheckError,match='287211'):
        correct(source,dips,sessions,decisions)

def test_can_reject_missing_evidence_page():
    source,dips,sessions,decisions=example()
    decisions[6]['beleg']='https://dserver.bundestag.de/btp/20/20191.pdf#page='
    with pytest.raises(CheckError):
        correct(source,dips,sessions,decisions)
