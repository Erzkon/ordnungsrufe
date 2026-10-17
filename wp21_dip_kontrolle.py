#!/usr/bin/env python3
"""Independent partial DIP-anchored WP21 grant-discovery reference comparison.

Positive-only, curated snapshot: NEVER an overall count or effectiveness proof.
This output cannot modify the source-reviewed ledger or automatic website counts.
"""
import argparse
import csv
import json
import re
from datetime import date, datetime
from pathlib import Path

from wp21_autopruefung import norm, read_reviewed

ROOT=Path(__file__).resolve().parent
REFERENCE=ROOT/'tests/fixtures/official_dip_wp21_positive_snapshot.json'
REVIEWED=ROOT/'daten/wirksame_ordnungsrufe_21wp.csv'
FIELDS=('sitzung','person','dip_erwaehnte_urspruengliche_rufe',
        'belegte_rufe_in_teilmenge','parser_vorschlag_vorhanden',
        'status','quellenprotokoll','amtlicher_index')


def reference(path=REFERENCE):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if (data.get('$schema')!='ordnungsruf-dip-positive-control-v1'
            or not data.get('official_index','').startswith('https://dip.bundestag.de/suche?')
            or not 12 <= len(data.get('entries',[])) <= 200):
        raise ValueError('Ungültiger DIP-Referenzsnapshot')
    snapshot=datetime.strptime(data['last_manual_snapshot'],'%Y-%m-%d').date()
    if snapshot > date.today():
        raise ValueError('DIP-Referenz stammt aus der Zukunft')
    seen=set()
    for row in data['entries']:
        s=row['session']
        key=(s,norm(row['person']))
        if (type(s) is not int or not 1<=s<=450
                or not key[1] or key in seen
                or row['reported_grants'] not in (1,2,3)
                or row['official_transcript'] !=
                f'https://dserver.bundestag.de/btp/21/21{s:03d}.pdf'):
            raise ValueError(f'Doppelter oder ungültiger DIP-Eintrag: {row}')
        seen.add(key)
        datetime.strptime(row['date'],'%d.%m.%Y')
    return data


def proposal_keys(path):
    if not path:
        return None
    with Path(path).open(encoding='utf-8',newline='') as handle:
        reader=csv.DictReader(handle)
        if not reader.fieldnames or not {'sitzung','person_vorschlag','pruefstatus'}.issubset(reader.fieldnames):
            raise ValueError('Unerwartetes Schema der Parser-Prüfliste')
        return {(int(row['sitzung']),norm(row['person_vorschlag']))
                for row in reader if row['person_vorschlag'].strip()}


def compare(ref, known, detected=None):
    indexed=ref['entries']
    records=[]
    for entry in indexed:
        key=(entry['session'],norm(entry['person']))
        reviewed=known.get(key,0)
        if reviewed > entry['reported_grants']:
            raise ValueError('Manuelle Referenz und DIP-Ausschnitt widersprechen sich')
        # A parser presence means a person was mentioned, NOT one independently
        # identifiable and effective sanction.
        found = None if detected is None else key in detected
        status=('bereits_einzeln_belegt' if reviewed==entry['reported_grants']
                else 'teilweise_einzeln_belegt' if reviewed
                else 'noch_nicht_im_belegten_teilbestand')
        records.append({
            'sitzung':str(entry['session']), 'person':entry['person'],
            'dip_erwaehnte_urspruengliche_rufe':str(entry['reported_grants']),
            'belegte_rufe_in_teilmenge':str(reviewed),
            'parser_vorschlag_vorhanden':('nicht_ausgefuehrt' if found is None
                                          else 'ja' if found else 'nein'),
            'status':status, 'quellenprotokoll':entry['official_transcript'],
            'amtlicher_index':ref['official_index'],
        })
    grants=sum(x['reported_grants'] for x in indexed)
    covered=sum(known.get((x['session'],norm(x['person'])),0) for x in indexed)
    if covered > grants:
        raise ValueError('DIP-Teilstichprobe kann nicht übererfüllt sein')
    return records,{
        'wahlperiode':21,'status':'ausgewaehlte_dip_positivkontrollen_ohne_gesamtzahl',
        'dip_referenzstand':ref['last_manual_snapshot'],
        'dip_protokoll_personen_kombinationen':len(indexed),
        'dip_dokumentierte_urspruengliche_rufe_in_stichprobe':grants,
        'davon_in_teilbestand_einzeln_belegt':covered,
        'noch_nicht_in_teilbestand_belegt':grants-covered,
        'parser_geprueft':detected is not None,
        'dip_person_sitzung_per_parser_gefunden':(
            sum((x['session'],norm(x['person'])) in detected for x in indexed)
            if detected is not None else None),
        'dip_person_sitzung_vom_parser_verpasst':(
            sum((x['session'],norm(x['person'])) not in detected for x in indexed)
            if detected is not None else None),
        'automatisch_freigegebene_ordnungsrufe':0,
        'quelle':ref['official_index'],
        'hinweis': ('DIP-Stichprobe dokumentiert ursprüngliche Erteilungen, '
                   'nicht notwendigerweise rechtswirksame Maßnahmen. '
                   'Keine vollständige DIP-Inventur, keine negativen Kontrollen, '
                   'keine Trefferquote der Gesamtpopulation. Parser-Person/Sitzung '
                   'ist kein Nachweis einer einzeln zuordenbaren Sanktion.'),
    }


def run(path=REFERENCE, ledger=REVIEWED, proposals=None,
        output_csv=Path('wp21_dip_pruefliste.csv'),
        output_json=Path('docs/data/dip_kontrolle_21.json')):
    r=reference(path)
    known,_=read_reviewed(ledger)
    candidates=proposal_keys(proposals)
    rows,report=compare(r,known,candidates)
    out=Path(output_csv)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    target=Path(output_json)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,default=REFERENCE)
    parser.add_argument('--reviewed',type=Path,default=REVIEWED)
    parser.add_argument('--proposals',type=Path)
    parser.add_argument('--candidates',type=Path,default=Path('wp21_dip_pruefliste.csv'))
    parser.add_argument('--report',type=Path,default=Path('docs/data/dip_kontrolle_21.json'))
    opts=parser.parse_args()
    report=run(opts.reference,opts.reviewed,opts.proposals,opts.candidates,opts.report)
    print('DIP-Positivkontrollen:',report['dip_protokoll_personen_kombinationen'],
          'Person/Sitzung-Referenzen;',
          report['davon_in_teilbestand_einzeln_belegt'],'von',
          report['dip_dokumentierte_urspruengliche_rufe_in_stichprobe'],
          'Erteilungen in manuell geprüfter Auswahl (keine Gesamtzahl).')


if __name__=='__main__':
    main()
