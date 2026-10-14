"""Conservative, source-reviewed additions missing from the original XML candidate register.

Maintains a separate, manually documented decision file. The original 123
verified measures are never modified. Additions are subject to exact DIP
metadata fingerprints, Bundestag IDs, session dates, multiplicity consistency,
and duplicate guards; the source PDF still requires expert review.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from dip_abgleich import clean

FIELDS = ['dip_id','dip_fingerabdruck','sitzung','person_id','person',
          'fraktion_zur_sitzung','nachtrag_anzahl','beleg_pdf','begruendung']
EXPECTED_VERIFIED = ['ereignis_id','datum','wahlperiode','sitzung','person_id',
                     'person','fraktion_zur_sitzung','quell_url','beleg']


class NachtragError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise NachtragError(reason)


def read(path, expected):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        require(reader.fieldnames is not None and set(expected) <= set(reader.fieldnames),
                f'{path}: Spalten fehlen')
        return [{k: (v or '').strip() for k,v in row.items()} for row in reader]


def digest(row):
    fields = ['dip_id','dip_titel','dip_datum','sitzungen_aus_dip','mehrfachvergabe_hinweis']
    return 'sha256:' + hashlib.sha256(json.dumps(
        {k:row[k] for k in fields}, ensure_ascii=False,sort_keys=True,separators=(',', ':')
    ).encode()).hexdigest()


def official_qty(title):
    if re.search(r'\b(?:je eines|acht|mehrere|drei|vier|fünf)\b',title,re.I):
        raise NachtragError('Gruppen- oder Mengenangabe noch nicht unterstützt: '+title)
    if re.search(r'\bzwei\s+ordnungsrufen\b',title,re.I): return 2
    if re.search(r'\b(?:eines|einen)\s+ordnungsrufes?\b',title,re.I): return 1
    raise NachtragError('Erteilungsmengenangabe unbekannt: '+title)


def reconcile(verified, dip_rows, sessions, decisions):
    require(len({r['ereignis_id']+':'+r['person_id'] for r in verified})==len(verified),
            'Ausgangsdaten enthalten dieselbe Person im selben Ereignis doppelt')
    by_dip = {}
    for d in dip_rows:
        require(d['dip_id'] not in by_dip, 'Doppelte DIP ID in Abgleich')
        by_dip[d['dip_id']] = d
    by_session = {}
    for s in sessions:
        require(s['sitzung'] not in by_session,'Sitzung doppelt')
        by_session[s['sitzung']] = s
    approved = []
    seen_dip = set();seen_person_session = set()
    base_person_counts = Counter((r['person_id'],r['sitzung']) for r in verified)
    new_eids = {r['ereignis_id'] for r in verified}
    for decision in decisions:
        pid=decision['person_id']; dip_id=decision['dip_id'];sn=decision['sitzung']
        require(re.fullmatch(r'\d{8}',pid) is not None,'Ungültige Bundestag-Person-ID')
        require(dip_id in by_dip, f'{dip_id}: DIP-Vorgang fehlt')
        require(dip_id not in seen_dip, f'{dip_id}: DIP Entscheidung doppelt')
        seen_dip.add(dip_id)
        require((pid,sn) not in seen_person_session,'Nachtrag für Person und Sitzung mehrfach')
        seen_person_session.add((pid,sn))
        dp=by_dip[dip_id]
        require(decision['dip_fingerabdruck']==digest(dp),f'{dip_id}: DIP-QUELLENDRIFT')
        require(sn in dp['sitzungen_aus_dip'].split(';'),f'{dip_id}: Sitzung nicht in DIP genannt')
        require(sn in by_session, f'{sn}: Sitzung nicht im Protokollregister')
        require(clean(decision['person']) in clean(dp['dip_titel']),f'{dip_id}: DIP-Titel nennt andere Person')
        require(decision['person'] and decision['fraktion_zur_sitzung'] and decision['begruendung'],
                f'{dip_id}: Identität oder Begründung fehlt')
        url=f'https://dserver.bundestag.de/btp/20/20{int(sn):03d}.pdf#page='
        require(decision['beleg_pdf'].startswith(url) and
                re.fullmatch(r'\d+',decision['beleg_pdf'][len(url):]),f'{dip_id}: PDF-Seite fehlt')
        qty=official_qty(dp['dip_titel'])
        require(decision['nachtrag_anzahl'].isdigit(), 'Nachtragsanzahl muss ganze Zahl sein')
        extra=int(decision['nachtrag_anzahl'])
        require(0<extra<=2,'Zusätzliche Menge außer Reichweite')
        previously=base_person_counts[(pid,sn)]
        require(previously+extra==qty,
                f'{dip_id}: DIP-Menge={qty}, bereits erfasst={previously}, Nachtrag={extra} – Widerspruch')
        require(dp['dip_datum']==f'{by_session[sn]["datum"][6:]}-{by_session[sn]["datum"][3:5]}-{by_session[sn]["datum"][:2]}',
                f'{dip_id}: Datum nicht zum amtlichen Sitzungsprotokoll passend')
        for k in range(extra):
            eid=f'DIP20-{dip_id}-N{k+1:02d}'
            require(eid not in new_eids,'Nachtragsereignis doppelt')
            new_eids.add(eid)
            approved.append({
                'ereignis_id':eid,
                'datum':by_session[sn]['datum'],
                'wahlperiode':'20',
                'sitzung':sn,
                'person_id':pid,
                'person':decision['person'],
                'fraktion_zur_sitzung':decision['fraktion_zur_sitzung'],
                'quell_url':decision['beleg_pdf'],
                'beleg':f"{decision['beleg_pdf']} | DIP: https://dip.bundestag.de/vorgang/{dip_id}",
            })
    return approved


def write_csv(path,rows,fields):
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def run(verified_path,dip_path,sessions_path,decisions_path,out_folder):
    verified=read(verified_path,EXPECTED_VERIFIED)
    dips=read(dip_path,['dip_id','dip_titel','dip_datum','sitzungen_aus_dip','mehrfachvergabe_hinweis'])
    sessions=read(sessions_path,['wahlperiode','sitzung','datum'])
    decisions=read(decisions_path,FIELDS)
    require(len(verified)==123, 'Sicherheitsstopp: Ausgangsmenge weicht von Prüfrunde 6 ab; Nachträge neu prüfen')
    require(len(sessions)==214, 'Nicht alle Sitzungsprotokolle vorhanden')
    new=reconcile(verified,dips,sessions,decisions)
    all_rows=sorted(verified+new,key=lambda r:(int(r['sitzung']),r['ereignis_id'],r['person']))
    require(len(all_rows)==len(verified)+len(new),'Fehler beim Zusammenführen')
    dest=Path(out_folder);dest.mkdir(parents=True,exist_ok=True)
    write_csv(dest/'bestaetigte_ordnungsrufe_mit_nachtraegen.csv',all_rows,EXPECTED_VERIFIED)
    stat={
        'wahlperiode':20,'pruefstatus':'Quellengeprüfte Teilmenge, kein amtlich finaler Gesamtstand',
        'bisherige_massnahmen_unveraendert':len(verified),
        'gepruefte_nachtraege':len(new),
        'zusammen_personenmassnahmen':len(all_rows),
        'zusammen_ereignis_ids':len({r['ereignis_id'] for r in all_rows}),
        'nachtrags_dip_ids':[d['dip_id'] for d in decisions],
        'fraktionen':dict(sorted(Counter(r['fraktion_zur_sitzung'] for r in all_rows).items())),
        'noch_kein_vollstaendigkeitsnachweis': True,
        'fehlende_ruecknahmenpruefung': True,
    }
    (dest/'nachtragsbericht.json').write_text(json.dumps(stat,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Do not mislabel other DIP metadata alerts as missing sanctions.
    print(f'Nachtraege erfolgreich: {len(verified)} + {len(new)} = {len(all_rows)}; Quellendrift und Dubletten kontrolliert')
    return stat


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verified',type=Path,default=Path('bestaetigte_ordnungsrufe.csv'))
    p.add_argument('--dip',type=Path,default=Path('dip_alle_ordnungsrufbezuege.csv'))
    p.add_argument('--sessions',type=Path,default=Path('sitzungen.csv'))
    p.add_argument('--decisions',type=Path,default=Path('pruefentscheidungen/dip_nachtraege.csv'))
    p.add_argument('--out-folder',type=Path,default=Path('.'))
    a=p.parse_args()
    run(a.verified,a.dip,a.sessions,a.decisions,a.out_folder)

if __name__=='__main__':main()
