#!/usr/bin/env python3
"""Verbindliche Nachpruefung: Ruecknahmen, Fehlzuordnungen und DIP-Nachtraege.

Erhaelt alle urspruenglichen Daten unveraendert. Vergleicht Quellenfingerabdruecke
und stoppt bei abweichender Ausgangslage; 135 bleibt als Arbeitswert markiert.
"""
import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

FIELDS = ('ereignis_id','datum','wahlperiode','sitzung','person_id','person',
          'fraktion_zur_sitzung','quell_url','beleg')
DECISIONS = ('aktion','ereignis_id','person_id','person','sitzung','fraktion_zur_sitzung',
             'dip_id','quellenfingerabdruck','beleg','begruendung')
CORR_FIELDS = (*DECISIONS,'status')
EXPECTED_REMOVALS = {'20-107-2983-01','20-163-4303-01','20-204-3164-01'}
EXPECTED_ADDITIONS = {
    '287211':('31','11004905','Beatrix von Storch','AfD'),
    '306052':('136','11005079','Matthias Helferich','fraktionslos'),
    '306511':('141','11005079','Matthias Helferich','fraktionslos'),
    '308052':('147','11004905','Beatrix von Storch','AfD'),
    '316468':('191','11005053','Robert Farle','fraktionslos'),
}
OFFICIAL_TOTAL = 135

class CheckError(ValueError):
    pass

def check(ok, why):
    if not ok: raise CheckError(why)

def read(path, required):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        check(reader.fieldnames is not None and set(required)<=set(reader.fieldnames),
              f'{path}: benoetigte Spalten fehlen')
        rows=list(reader)
    check(all(None not in r for r in rows),f'{path}: CSV-Zeile unvollstaendig')
    return [{k:(v or '').strip() for k,v in r.items()} for r in rows]

def fingerprint_record(r):
    return 'sha256:'+hashlib.sha256(json.dumps(
        {k:r[k] for k in FIELDS},ensure_ascii=False,sort_keys=True,
        separators=(',',':')).encode('utf-8')).hexdigest()

def fingerprint_dip(r):
    cols=('dip_id','dip_titel','dip_datum','sitzungen_aus_dip','mehrfachvergabe_hinweis')
    return 'sha256:'+hashlib.sha256(json.dumps(
        {k:r[k] for k in cols},ensure_ascii=False,sort_keys=True,
        separators=(',',':')).encode('utf-8')).hexdigest()

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if not unicodedata.combining(c))

def pdf_for_sitzung(s):
    return f'https://dserver.bundestag.de/btp/20/20{int(s):03d}.pdf#page='

def as_date(d):
    return datetime.strptime(d,'%d.%m.%Y').strftime('%Y-%m-%d')

def correct(original, dip, sessions, decisions):
    check(len({(r['ereignis_id'],r['person_id']) for r in original})==len(original),
          'Ausgangsdatei hat doppelte Personen-Ereignisse')
    check(len({r['ereignis_id'] for r in original})>=1,'Keine Ausgangsdaten')
    by_sid = {r['sitzung']:r for r in sessions}
    check(len(by_sid)==len(sessions),'Doppelte Sitzungen')
    by_dip = {r['dip_id']:r for r in dip}
    check(len(by_dip)==len(dip),'Doppelte DIP-IDs')
    by_event = {(r['ereignis_id'],r['person_id']):r for r in original}
    by_id = {}
    for r in original:
        if r['person_id']:
            by_id.setdefault(r['person_id'],set()).add(norm(r['person']))
    check({d['ereignis_id'] for d in decisions if d['aktion']!='hinzufuegen'}==EXPECTED_REMOVALS,
          'Sicherheitsstopp: bekannte Ruecknahme-/Fehlzuordnungs-IDs fehlen oder weichen ab')
    check({d['dip_id'] for d in decisions if d['aktion']=='hinzufuegen'}==set(EXPECTED_ADDITIONS),
          'Sicherheitsstopp: erwartete neue DIP-Faelle fehlen oder weichen ab')
    check(len(decisions)==8,'Es muessen genau acht nachvollziehbare Korrekturentscheidungen vorliegen')
    dismissed=[];new=[];changed=set();added_dips=set()
    for d in decisions:
        typ=d['aktion']
        check(typ in ('zurueckgenommen','fehlzuordnung','hinzufuegen'),
              f'Unerlaubte Aktion {typ}')
        check(d['sitzung'] in by_sid, f'{d["sitzung"]}: unbekannte Sitzung')
        check(re.fullmatch(r'\d{8}',d['person_id']) is not None, 'ungueltige Person-ID')
        check(norm(d['person']) in by_id.get(d['person_id'], set()),
              f'{d["person"]}: Personen-ID nicht durch bisherige Daten gesichert')
        check(bool(d['begruendung']) and bool(d['beleg']), 'Begruendung/Beleg fehlt')
        if typ in ('zurueckgenommen','fehlzuordnung'):
            check(not d['dip_id'], 'Entfernungsentscheidung darf keine neue DIP-ID haben')
            key=(d['ereignis_id'],d['person_id'])
            check(key not in changed and key in by_event,
                  f'{key}: nicht eindeutig in 133 Ausgangseintraegen')
            changed.add(key)
            row=by_event[key]
            for k in ('person','sitzung','fraktion_zur_sitzung'):
                check(d[k]==row[k], f'{d["ereignis_id"]}: {k} stimmt nicht')
            check(d['quellenfingerabdruck']==fingerprint_record(row),
                  f'{d["ereignis_id"]}: QUELLENDRIFT, Korrektur gesperrt')
            expected={
                '20-107-2983-01':'zurueckgenommen',
                '20-163-4303-01':'zurueckgenommen',
                '20-204-3164-01':'fehlzuordnung',
            }
            check(typ==expected[d['ereignis_id']], 'Ruecknahme-/Fehlzuordnungsart stimmt nicht')
            # Bei einer Ruecknahme muss der Beleg die nachfolgende Sitzung zeigen.
            ref_sitzung = {'20-107-2983-01':'108', '20-163-4303-01':'164',
                           '20-204-3164-01':'204'}[d['ereignis_id']]
            check(d['beleg'].startswith(pdf_for_sitzung(ref_sitzung)),
                  'Ruecknahme/Fehlzuordnung braucht PDF der belegenden Sitzung')
            dismissed.append({**d,'status':typ})
        else:
            did=d['dip_id']
            check(not d['ereignis_id'],'Bei DIP-Nachtrag Ereignis-ID leer lassen')
            check(did not in added_dips and did in by_dip,'DIP ID doppelt oder unbekannt')
            added_dips.add(did)
            source=by_dip[did]
            check(d['quellenfingerabdruck']==fingerprint_dip(source),
                  f'{did}: DIP-QUELLENDRIFT')
            check(d['sitzung'] in source['sitzungen_aus_dip'].split(';'),
                  f'{did}: Sitzung nicht im DIP-Vorgang')
            check((d['sitzung'],d['person_id'],d['person'],d['fraktion_zur_sitzung'])==EXPECTED_ADDITIONS[did],
                  f'{did}: Gesicherte Person, Fraktion oder Sitzung veraendert')
            check(norm(d['person']) in norm(source['dip_titel']),
                  f'{did}: Andere Person im DIP-Vorgang')
            check(d['beleg'].startswith(pdf_for_sitzung(d['sitzung'])),
                  f'{did}: Sitzungs-PDF-Beleg falsch')
            page=d['beleg'][len(pdf_for_sitzung(d['sitzung'])):]
            check(page.isdigit(), f'{did}: PDF-Seite fehlt')
            # Bei den Einspruchsvorgaengen 287211 (20/032) und 306511 (20/142)
            # entspricht das DIP-Datum dem Folgetag der Erteilung.
            if did in ('287211','306511'):
                orig,follow={'287211':('31','32'),'306511':('141','142')}[did]
                check(d['sitzung']==orig and source['dip_datum']==as_date(by_sid[follow]['datum']),
                      f'Nachtraeglicher DIP-Vorgang {did} nicht mehr passend')
            else:
                check(source['dip_datum']==as_date(by_sid[d['sitzung']]['datum']),
                      f'{did}: Datum weicht ab')
            check((d['person_id'],d['sitzung']) not in
                  {(r['person_id'],r['sitzung']) for r in original},
                  f'{did}: Person in Sitzung bereits erfasst')
            event_id=f'DIP20-{did}-K01'
            check(event_id not in {r['ereignis_id'] for r in original},'Doppelte neue Ereignis-ID')
            new.append({
                'ereignis_id':event_id,
                'datum':by_sid[d['sitzung']]['datum'],
                'wahlperiode':'20',
                'sitzung':d['sitzung'],
                'person_id':d['person_id'],
                'person':d['person'],
                'fraktion_zur_sitzung':d['fraktion_zur_sitzung'],
                'quell_url':d['beleg'],
                'beleg':d['beleg']+f' | DIP: https://dip.bundestag.de/vorgang/{did}',
            })
    result=sorted([r for r in original if (r['ereignis_id'],r['person_id']) not in changed]+new,
                  key=lambda r:(int(r['sitzung']),r['ereignis_id'],r['person']))
    check(len(new)==5 and len(dismissed)==3,'Sicherheitsstopp: erwartete 5+3 nicht erreicht')
    check(len(result)==len(original)+2,'Unerwartete Änderung der Personenmaßnahmen')
    check(len({(r['ereignis_id'],r['person_id']) for r in result})==len(result),
          'Dubletten nach Korrektur')
    return result,dismissed,new

def write_csv(path,rows,columns):
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)

def run(input_path,dip_path,sessions_path,decisions_path,dest_path):
    source=read(input_path,FIELDS)
    check(len(source)==133,'133er-Basis hat sich geaendert: erst Quellen neu vergleichen')
    dips=read(dip_path,('dip_id','dip_titel','dip_datum','sitzungen_aus_dip','mehrfachvergabe_hinweis'))
    sessions=read(sessions_path,('sitzung','datum'))
    check(len(sessions)==214,'Nicht alle 214 Protokolle verarbeitet')
    decisions=read(decisions_path,DECISIONS)
    final,dismissed,added=correct(source,dips,sessions,decisions)
    check(len(final)==135,'Abweichende wirksame Gesamtzahl – Sicherheitsstopp')
    dest=Path(dest_path);dest.mkdir(parents=True,exist_ok=True)
    write_csv(dest/'wirksame_ordnungsrufe.csv',final,FIELDS)
    write_csv(dest/'ausgenommene_ordnungsrufe.csv',dismissed,CORR_FIELDS)
    write_csv(dest/'ergaenzte_ordnungsrufe.csv',added,FIELDS)
    people=Counter(r['person'] for r in final)
    report={
        'wahlperiode':20,
        'original_bestaetigt_mit_nachtraegen':len(source),
        'zurueckgenommen':sum(x['status']=='zurueckgenommen' for x in dismissed),
        'fehlzugeordnet':sum(x['status']=='fehlzuordnung' for x in dismissed),
        'zusaetzlich_belegt':len(added),
        'wirksame_massnahmen_in_arbeitsliste':len(final),
        'amtliche_statistik_wirksame_massnahmen':OFFICIAL_TOTAL,
        'offene_differenz':OFFICIAL_TOTAL-len(final),
        'bestaetigte_ereignis_ids':len({r['ereignis_id'] for r in final}),
        'stephan_brandner':people['Stephan Brandner'],
        'beatrix_von_storch':people['Beatrix von Storch'],
        'amtliche_personenzahl_beatrix_von_storch':19,
        'abweichung_personenzahl_beatrix_von_storch':19-people['Beatrix von Storch'],
        'identifizierter_offener_dip_konflikt':'DIP 298177 Sitzung 20/094 vs DIP 298160 Sitzung 20/095: Vorbehalt am Vortag, Erteilung am Folgetag. In Arbeitsliste einmal gezaehlt.',
        'dip_306511_einspruch_zurueckgewiesen':'20/142, PDF Seiten 15 und 61',
        'methodik':'Nur per Quellenabgleich einzeln belegte Massnahmen, keine automatische Auffuellung zur amtlichen Zahl.',
        'status':'Vorlaeufig. Gesamtwert 135 stimmt numerisch, aber Einzelabgleich (von Storch 18 statt amtlich 19) und DIP-Konflikte sind offen.',
    }
    (dest/'korrekturbericht.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Korrigiert: {len(source)} - 2 Ruecknahmen - 1 Fehlzuordnung + 5 belegte = {len(final)}; Einzelabgleich bleibt offen.')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verified',default='bestaetigte_ordnungsrufe_mit_nachtraegen.csv')
    p.add_argument('--dip',default='dip_alle_ordnungsrufbezuege.csv')
    p.add_argument('--sessions',default='sitzungen.csv')
    p.add_argument('--decisions',default='pruefentscheidungen/abschlusskorrekturen.csv')
    p.add_argument('--out-folder',default='.')
    a=p.parse_args()
    run(a.verified,a.dip,a.sessions,a.decisions,a.out_folder)

if __name__=='__main__': main()
