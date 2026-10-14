import io
import zipfile
import pytest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mdb_id_abgleich import canonical,parse_official_ids,extract_xml,resolve_rows,IdentityError


def member(pid,first,last,wp='20'):
    return f'<MDB><ID>{pid}</ID><NAMEN><NAME><NACHNAME>{last}</NACHNAME><VORNAME>{first}</VORNAME></NAME></NAMEN><WAHLPERIODEN><WAHLPERIODE><WP>{wp}</WP></WAHLPERIODE></WAHLPERIODEN></MDB>'


def fixture_xml():
    data='<DATEN>'+member('11000001','Jörn','König')+member('11000002','Tino','Sorge')+member('11000003','Heike','Engelhardt')+member('11000004','Kassem','Taher Saleh')+member('11000005','Falscher','Mensch','19')+'</DATEN>'
    return data.encode()


def test_four_unambiguous_names():
    a=parse_official_ids(io.BytesIO(fixture_xml()))
    assert a['jörn könig']=={'11000001'}
    assert a['kassem taher saleh']=={'11000004'}
    assert 'falscher mensch' not in a


def test_resolve_unknown_without_guessing():
    a=parse_official_ids(io.BytesIO(fixture_xml()))
    rows=[{'dip_id':'1','person':'Heike Engelhardt','person_id':''}, {'dip_id':'2','person':'Tino Sorge','person_id':''}]
    out,n=resolve_rows(rows,a)
    assert [r['person_id'] for r in out]==['11000003','11000002']
    assert len(n)==2


def test_ambiguous_name_stopped():
    a={'heike engelhardt':{'11000003','11000006'}}
    with pytest.raises(IdentityError,match='nicht eindeutig'):resolve_rows([{'person':'Heike Engelhardt','person_id':''}],a)


def test_missing_name_stopped():
    with pytest.raises(IdentityError,match='nicht eindeutig'):resolve_rows([{'person':'Heike Engelhardt','person_id':''}],{})


def test_existing_id_preserved():
    r=[{'dip_id':'1','person':'Dietmar Nietan','person_id':'11003199'}, {'dip_id':'2','person':'Heike Engelhardt','person_id':''}]
    out,ids=resolve_rows(r,{'heike engelhardt':{'11000003'}})
    assert out[0]['person_id']=='11003199' and len(ids)==1


def test_invalid_known_id_stopped():
    with pytest.raises(IdentityError,match='Ungueltige'):resolve_rows([{'person':'Someone','person_id':'abc'}],{},require_new=False)


def test_zip_has_xml_and_no_directory_extraction():
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        z.writestr('foo/MDB_STAMMDATEN.XML',fixture_xml())
    assert extract_xml(b.getvalue())==fixture_xml()


def test_zip_rejects_ambiguous_payload():
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        z.writestr('unknown.xml',fixture_xml())
        z.writestr('other.xml',fixture_xml())
    with pytest.raises(IdentityError,match='nicht eindeutig'):extract_xml(b.getvalue())


def test_missing_member_id_skipped():
    xml='<DATA>'+member('unknown','A','B')+member('11000001','Jörn','König')+'</DATA>'
    a=parse_official_ids(io.BytesIO(xml.encode()))
    assert len(a)==1


def test_canonical_preserves_umlaut():
    assert canonical('  JÖRN   König  ')=='jörn könig'
