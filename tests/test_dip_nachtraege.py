from copy import deepcopy
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dip_nachtraege import reconcile, digest, official_qty, NachtragError


def sample():
    dip = {'dip_id':'765432','dip_titel':'Erteilung von zwei Ordnungsrufen an den Abg Dietmar Nietan (SPD)',
           'dip_datum':'2023-01-26','sitzungen_aus_dip':'82','mehrfachvergabe_hinweis':'ja'}
    prev = [{'ereignis_id':'20-082-1','datum':'26.01.2023','wahlperiode':'20','sitzung':'82',
             'person_id':'11003199','person':'Dietmar Nietan','fraktion_zur_sitzung':'SPD',
             'quell_url':'https://example.org','beleg':'https://example.org'}]
    sess=[{'sitzung':'82','datum':'26.01.2023','wahlperiode':'20'}]
    dec={'dip_id':dip['dip_id'],'dip_fingerabdruck':digest(dip),'sitzung':'82',
         'person_id':'11003199','person':'Dietmar Nietan','fraktion_zur_sitzung':'SPD',
         'nachtrag_anzahl':'1', 'beleg_pdf':'https://dserver.bundestag.de/btp/20/20082.pdf#page=82',
         'begruendung':'2. Vergabe nach Volltext'}
    return prev,[dip],sess,[dec]


def test_one_safe_second_measure():
    v,d,s,r=sample()
    x=reconcile(v,d,s,r)
    assert len(x)==1
    assert x[0]['ereignis_id']=='DIP20-765432-N01'
    assert x[0]['person_id']=='11003199'


def test_new_single_sanction():
    v,d,s,r=sample()
    v=[];d[0]['dip_titel']='Erteilung eines Ordnungsrufes an den Abg Dietmar Nietan (SPD)';d[0]['mehrfachvergabe_hinweis']='nein'
    r[0]['dip_fingerabdruck']=digest(d[0])
    assert len(reconcile(v,d,s,r))==1


def test_tampered_title_rejected():
    v,d,s,r=sample();d[0]['dip_titel']='Erteilung von zwei Ordnungsrufen an die Abg Beatrix von Storch (AfD)'
    with pytest.raises(NachtragError,match='QUELLENDRIFT'):reconcile(v,d,s,r)


def test_wrong_name_rejected():
    v,d,s,r=sample();r[0]['person']='Beatrix von Storch'
    with pytest.raises(NachtragError,match='andere Person'):reconcile(v,d,s,r)


def test_invalid_identity_rejected():
    v,d,s,r=sample();r[0]['person_id']='XXX'
    with pytest.raises(NachtragError,match='Person-ID'):reconcile(v,d,s,r)


def test_wrong_quantity_rejected():
    v,d,s,r=sample();r[0]['nachtrag_anzahl']='2'
    with pytest.raises(NachtragError,match='Widerspruch'):reconcile(v,d,s,r)


def test_duplicate_decision_rejected():
    v,d,s,r=sample()
    with pytest.raises(NachtragError,match='doppelt'):reconcile(v,d,s,r+r)


def test_wrong_source_page_rejected():
    v,d,s,r=sample();r[0]['beleg_pdf']='https://evil.test/20082.pdf#page=82'
    with pytest.raises(NachtragError,match='PDF-Seite'):reconcile(v,d,s,r)


def test_mismatched_session_rejected():
    v,d,s,r=sample();r[0]['sitzung']='81'
    with pytest.raises(NachtragError,match='Sitzung nicht in DIP'):reconcile(v,d,s,r)


def test_session_date_rejected():
    v,d,s,r=sample();s[0]['datum']='27.01.2023'
    with pytest.raises(NachtragError,match='Datum'):reconcile(v,d,s,r)


def test_cannot_infer_group_count():
    with pytest.raises(NachtragError):official_qty('Erteilung je eines Ordnungsrufes an acht Abgeordnete (Gruppe BSW)')


def test_count_one_and_two():
    assert official_qty('Erteilung eines Ordnungsrufes an die Abg X')==1
    assert official_qty('Erteilung von zwei Ordnungsrufen an die Abg X')==2


def test_ambiguous_quantity_rejected():
    with pytest.raises(NachtragError):official_qty('Ordnungsruf oder Einspruch gegen Abgeordneten X')
