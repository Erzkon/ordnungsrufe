#!/usr/bin/env python3
"""Read-only priority queue linking DIP Vorgang IDs and their positions.

The linking key is the official vorgang_id, not guessed name similarity.
No metadata may change any verified sanction count or legal status.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from wp21_dip_monitor import load_state, utc
from wp21_dip_positionen import read_position_state

MAX_PUBLIC = 30
MAX_CANDIDATES = 350


def build_cases(vorgang_state, positions_state):
    original = load_state(vorgang_state)
    procedural = read_position_state(positions_state)
    if not original['last_success_utc'] or not procedural['last_success_utc']:
        raise ValueError('DIP-Auswertung benötigt beide erfolgreichen Quellenscans')
    original_time = utc(original['last_success_utc'])
    procedural_time = utc(procedural['last_success_utc'])
    if procedural_time < original_time:
        raise ValueError('Positionsquellen sind älter als DIP-Vorgangs-Abruf')
    items = original['items']
    if len(items) > MAX_CANDIDATES:
        raise ValueError('Mehr Vorgänge als sicher automatisch auswertbar')
    by_parent = {}
    for row in procedural['items'].values():
        if row.get('active',True):
            by_parent.setdefault(row['parent_id'],[]).append(row)
    cases = []
    for id_, item in items.items():
        if not item.get('active', True):
            continue
        if not re.fullmatch(r'[1-9]\d{0,11}', id_):
            raise ValueError('Ungültige DIP-Vorgang-ID')
        positions = by_parent.get(id_,[])
        legal = [p for p in positions if p['kind']=='moegliche_rechtsfolge']
        if item.get('kind') == 'rechtsfolgen_hinweis' or legal:
            priority = 'hoch'
            reason = 'Rechtsfolgen-Schlagwörter in amtlichen Metadaten: Ausgang und betroffene Maßnahme zu prüfen'
        elif not positions:
            priority = 'mittel'
            reason = 'Vorgang ohne beobachtete Verfahrenspositionen; keine Aussage zur Wirksamkeit'
        else:
            priority = 'normal'
            reason = 'Ordnungsruf-bezogener Vorgang; Vollständigkeit und spätere Beschlüsse bleiben ungeprüft'
        cases.append({
            'id': id_,
            'source':'https://dip.bundestag.de/vorgang/' + id_,
            'title':item['title'][:240],
            'updated':item['updated'],
            'priority':priority,
            'reason':reason,
            'position_count':len(positions),
            'legal_wording_positions':len(legal),
            'last_steps':[{'id':p['id'], 'date':p['date'],
                           'step':p['step'][:190], 'kind':p['kind']}
                          for p in sorted(positions,key=lambda p:p['updated'],reverse=True)[:3]],
            'review_status':'nicht_unabhaengig_geprueft',
        })
    order={'hoch':0,'mittel':1,'normal':2}
    cases.sort(key=lambda c:(order[c['priority']],-utc(c['updated']).timestamp(),int(c['id'])))
    report={
        'wahlperiode':21,
        'status':'dip_verknuepfte_prueffalle_ohne_autozaehlung',
        'last_success_utc':procedural['last_success_utc'],
        'linked_dip_vorgaenge':len(cases),
        'high_priority_cases':sum(c['priority']=='hoch' for c in cases),
        'medium_priority_cases':sum(c['priority']=='mittel' for c in cases),
        'items':cases[:MAX_PUBLIC],
        'shown':min(len(cases),MAX_PUBLIC),
        'automatically_confirmed_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'warning':('Vorgänge und Positionen sind über amtliche IDs verknüpft. '
                   'Keine Zuordnung zu einzelnen wirksamen Ordnungsrufen. '
                   'Fallpriorität ist keine rechtsverbindliche Bewertung.'),
    }
    return cases,report


def write_json(target,data):
    path=Path(target)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)


def run(vorgang_state, position_state, report_out, full_out):
    cases,report=build_cases(vorgang_state,position_state)
    write_json(full_out,cases)
    write_json(report_out,report)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vorgang-state',type=Path,default=Path('.cache/dip21/state.json'))
    ap.add_argument('--position-state',type=Path,default=Path('.cache/dip21/positionen.json'))
    ap.add_argument('--report',type=Path,default=Path('docs/data/dip_prueffalle_21.json'))
    ap.add_argument('--full',type=Path,default=Path('wp21_dip_verknuepfte_faelle.json'))
    a=ap.parse_args()
    report=run(a.vorgang_state,a.position_state,a.report,a.full)
    print(f"DIP-Quellenverbund: {report['linked_dip_vorgaenge']} Vorgänge, "
          f"{report['high_priority_cases']} hohe Priorität; "
          "keine bestätigten oder zurückgenommenen Maßnahmen.")


if __name__=='__main__':
    main()
