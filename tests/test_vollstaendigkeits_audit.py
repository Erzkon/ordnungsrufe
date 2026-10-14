from pathlib import Path
from lxml import etree
import pytest
from vollstaendigkeits_audit import scan_xml, compare, official_comparison, audit


def write_xml(folder, session, speech, appendix=''):
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'20{session:03d}.xml'
    root=etree.Element('dbtplenarprotokoll', **{'wahlperiode':'20','sitzung-nr':str(session),'sitzung-datum':'01.01.2025'})
    sv=etree.SubElement(root, 'sitzungsverlauf');t=etree.SubElement(sv,'tagesordnungspunkt')
    for chunk in speech:
        etree.SubElement(t,'p').text=chunk
    an=etree.SubElement(root,'anlagen')
    if appendix: etree.SubElement(an,'p').text=appendix
    path.write_bytes(etree.tostring(root,xml_declaration=True,encoding='utf-8',pretty_print=True))
    return path


def test_independent_search_includes_phrase_without_ordnungsruf(tmp_path):
    f=write_xml(tmp_path,1,['Herr Kollege, ich rufe Sie zur Ordnung.'])
    rows=scan_xml(f)
    assert len(rows)==1 and 'zur_ordnung' in rows[0]['suchmuster']


def test_threat_remains_unconfirmed_finding(tmp_path):
    f=write_xml(tmp_path,2,['Ich werde Sie beim naechsten Mal zur Ordnung rufen.'])
    rows=scan_xml(f)
    assert len(rows)==1
    _,novel,_=compare(rows,[],[])
    assert len(novel)==1
    assert 'entscheidung' not in novel[0]


def test_appendix_low_priority(tmp_path):
    f=write_xml(tmp_path,3,[],appendix='Der Ordnungsruf wurde diskutiert.')
    _,new,_=compare(scan_xml(f),[],[])
    assert new[0]['bereich']=='ausserhalb_sitzungsverlauf'
    assert new[0]['pruefprioritaet']=='niedrig'


def test_match_by_xml_line_and_filename(tmp_path):
    f=write_xml(tmp_path,4,['Ich erteile einen Ordnungsruf.'])
    rows=scan_xml(f)
    candidates=[{'file':f.name,'line':rows[0]['xml_zeile']}]
    _,new,_=compare(rows,candidates,[])
    assert new==[]


def test_duplicate_phrase_in_second_xml_line_is_found(tmp_path):
    f=write_xml(tmp_path,5,['Es gibt Ordnungsrufe.', 'Das ist ein Ordnungsruf.'])
    rows=scan_xml(f)
    assert len(rows)==2
    _,new,_=compare(rows,[{'file':f.name,'line':rows[0]['xml_zeile']}],[])
    assert len(new)==1


def test_return_appeal_flagged_without_auto_reversing(tmp_path):
    f=write_xml(tmp_path,6,['Der Ordnungsruf wurde zurückgenommen.', 'Dem Einspruch gegen den Ordnungsruf wurde stattgegeben.'])
    rows=scan_xml(f)
    _,_,alerts=compare(rows,[],[])
    assert len(alerts)==2
    assert alerts[0]['ruecknahme_signal']=='ja'
    assert alerts[1]['einspruch_signal']=='ja'


def test_cross_session_retrospective_flag(tmp_path):
    f=write_xml(tmp_path,7,['Den Ordnungsruf habe ich gestern ausgesprochen.'])
    _,_,alerts=compare(scan_xml(f),[],[])
    assert alerts[0]['rueckbezug_signal']=='ja'


def test_official_counts_dont_declare_missing_12():
    rows=[{'person':'Stephan Brandner'}]*21+[{'person':'Beatrix von Storch'}]*16+[{'person':'Martin Reichardt'}]*7
    counts=official_comparison(rows)
    assert counts[1]['differenz_amtlich_minus_roh']==-1
    assert counts[2]['differenz_amtlich_minus_roh']==3
    assert 'Zaehlweisen' in counts[0]['hinweis']


def test_reject_incomplete_corpus(tmp_path):
    write_xml(tmp_path,214,['Das ist ein Ordnungsruf.'])
    with pytest.raises(ValueError,match='Nicht alle 214 Protokolle'):
        audit(tmp_path,[],[])
