"""Resolve pending DIP source decisions to official Bundestag person IDs.

Identity must match exactly and unambiguously in the official Bundestag
MdB-Stammdaten ZIP and must belong to the requested Bundestag legislature.
Never guess or fabricate IDs. Existing manually reviewed person IDs are kept.
"""
import argparse
import csv
import io
import json
import re
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MDB_URL = 'https://www.bundestag.de/resource/blob/472878/MdB-Stammdaten.zip'
MAX_ZIP_BYTES = 40_000_000
MAX_XML_BYTES = 110_000_000
COLUMNS = ('dip_id','dip_fingerabdruck','sitzung','person_id','person',
           'fraktion_zur_sitzung','nachtrag_anzahl','beleg_pdf','begruendung')

class IdentityError(ValueError): pass


def canonical(s):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s).casefold()).strip()


def _name_candidates(mdb):
    out = set()
    for name in mdb.findall('./NAMEN/NAME'):
        last=(name.findtext('NACHNAME') or '').strip()
        first=(name.findtext('VORNAME') or '').strip()
        if first and last:
            out.add(canonical(first + ' ' + last))
    return out


def parse_official_ids(source, legislature=20):
    """Parse official MDB_STAMMDATEN.XML; return name -> unique ID or set of IDs."""
    index = {}
    wanted=str(legislature)
    # At end(MDB), everything beneath that member is available while streaming.
    for _, elem in ET.iterparse(source, events=('end',)):
        if elem.tag.rsplit('}',1)[-1] != 'MDB':
            continue
        ids=(elem.findtext('./ID') or '').strip()
        wps={ (x.text or '').strip() for x in elem.findall('./WAHLPERIODEN/WAHLPERIODE/WP') }
        if re.fullmatch(r'\d{8}', ids) and wanted in wps:
            for name in _name_candidates(elem):
                index.setdefault(name,set()).add(ids)
        elem.clear()
    return index


def extract_xml(zipped_bytes):
    if len(zipped_bytes) > MAX_ZIP_BYTES:raise IdentityError('Amtliches ZIP ist zu gross')
    with zipfile.ZipFile(io.BytesIO(zipped_bytes)) as z:
        files=[p for p in z.infolist() if not p.is_dir() and p.filename.lower().endswith('.xml')]
        preferred=[p for p in files if 'stamm' in p.filename.lower() or 'mdb' in p.filename.lower()]
        if len(preferred)==1: entry=preferred[0]
        elif len(files)==1: entry=files[0]
        else:raise IdentityError('Amtliche Stammdaten-XML nicht eindeutig im ZIP')
        if entry.file_size > MAX_XML_BYTES or entry.file_size < 100:
            raise IdentityError('Amtliche XML unerwartet gross oder ungueltig')
        return z.read(entry)


def get_zip(url=MDB_URL):
    req=urllib.request.Request(url, headers={'User-Agent':'Ordnungsruf-Counter/10 (+public research)'})
    with urllib.request.urlopen(req,timeout=90) as response:
        data=response.read(MAX_ZIP_BYTES+1)
    if len(data)>MAX_ZIP_BYTES: raise IdentityError('ZIP-Download ist zu gross')
    return data


def resolve_rows(decisions, people, require_new=True):
    resolved=[]
    new=[]
    for row in decisions:
        row=row.copy(); name=canonical(row['person']); pid=row['person_id'].strip()
        if not name: raise IdentityError('Leerer Personenname')
        if not pid:
            matches=people.get(name,set())
            if len(matches)!=1:
                raise IdentityError(f'Person nicht eindeutig im amtlichen MdB-Stamm (20. WP): {row["person"]} ({len(matches)} Treffer)')
            pid=next(iter(matches));row['person_id']=pid
            new.append({'dip_id':row['dip_id'],'person':row['person'],'person_id':pid})
        if re.fullmatch(r'\d{8}',pid) is None:
            raise IdentityError(f'Ungueltige Bundestag-Personenkennung: {row["person"]}')
        # Names for existing source-reviewed IDs need not be revalidated here;
        # their manual decisions and fingerprints are checked by dip_nachtraege.py.
        resolved.append(row)
    if require_new and not new:raise IdentityError('Keine neuen Personenkennungen aufgeloest')
    return resolved,new


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--decisions',type=Path,default=Path('pruefentscheidungen/dip_nachtraege.csv'))
    p.add_argument('--output',type=Path,default=Path('dip_nachtraege_mit_personen_ids.csv'))
    p.add_argument('--report',type=Path,default=Path('mdb_id_abgleich_bericht.json'))
    p.add_argument('--zip-file',type=Path,help='Optional local copy of official MdB-Stammdaten.zip')
    a=p.parse_args()
    with a.decisions.open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f)
        if not rd.fieldnames or not set(COLUMNS)<=set(rd.fieldnames):
            raise IdentityError('Entscheidungsdatei enthaelt nicht alle erforderlichen Felder')
        decisions=list(rd)
    data=a.zip_file.read_bytes() if a.zip_file else get_zip()
    people=parse_official_ids(io.BytesIO(extract_xml(data)))
    resolved,new=resolve_rows(decisions,people)
    with a.output.open('w',encoding='utf-8',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=COLUMNS)
        wr.writeheader();wr.writerows({col:row[col] for col in COLUMNS} for row in resolved)
    report={'quelle':MDB_URL, 'wahlperiode':20,'personen_im_stammdaten_index':len(people),
            'bestehende_nachtraege':len(decisions)-len(new),'neu_aufgeloest':len(new),
            'neue_personen':new, 'keine_automatische_freigabe': True}
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Amtliche Personenkennungen: {len(new)} eindeutig aufgeloest; {len(decisions)-len(new)} bestehende Nachtraege erhalten.')

if __name__=='__main__':main()
