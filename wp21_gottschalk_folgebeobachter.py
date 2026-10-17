#!/usr/bin/env python3
"""Read-only Gottschalk second-appeal watch on existing incremental DIP caches.

The full bounded official search is a separately archived historical
snapshot. This daily check only detects newly tracked Gottschalk
Ordnungsruf parents/positions in the CURRENT successful incremental
cache. It MUST NOT claim the cache is a complete register or infer
a second measure's legal effectiveness from missing positions.
"""
import argparse
import json
import re
from pathlib import Path

from wp21_autopruefung import norm
from wp21_18_dip_verfahrenspositionen import named
from wp21_dip_monitor import load_state,utc
from wp21_dip_positionen import read_position_state

PARENT='328225'
ORIGIN='681046'
VOTE='681803'
SOURCE='https://dip.bundestag.de/vorgang/'+PARENT
FIRST='Einspruch des Abg Kay Gottschalk (AfD) gegen die erste Ordnungsmaßnahme'


def inspect(parent_state,position_state):
    if (not isinstance(parent_state,dict) or not isinstance(position_state,dict)
            or not parent_state.get('last_success_utc')
            or not position_state.get('last_success_utc')):
        raise ValueError('Keine vollständig abgeschlossenen DIP-Quellensnapshots')
    if utc(position_state['last_success_utc'])<utc(parent_state['last_success_utc']):
        raise ValueError('DIP-Positionen älter als amtliche Elternquelle')
    parents=parent_state.get('items')
    positions=position_state.get('items')
    if (not isinstance(parents,dict) or not isinstance(positions,dict)
            or len(parents)>15000 or len(positions)>5000):
        raise ValueError('Ungültiger inkrementeller DIP-Quellencache')
    original=parents.get(PARENT)
    if (not isinstance(original,dict) or original.get('active',True) is not True
            or original.get('id')!=PARENT or original.get('source')!=SOURCE
            or not named(original.get('title',''),'Kay Gottschalk')
            or not re.search(r'\bvon\s+zwei\s+Ordnungsrufen\b',
                             original.get('title',''),re.I)):
        raise ValueError('Bekannter amtlicher Gottschalk-Sammelvorgang fehlt')
    bound={}
    for ident,row in positions.items():
        if not isinstance(row,dict) or row.get('parent_id')!=PARENT:
            continue
        if (ident in bound or row.get('id')!=ident
                or row.get('source')!=SOURCE
                or row.get('active',True) is not True):
            raise ValueError('Bekannte DIP-Position inaktiv oder fremd')
        bound[ident]=row
    if ORIGIN not in bound or VOTE not in bound:
        raise ValueError('Erste Gottschalk-Original-/Abstimmungsposition fehlt')
    first=bound[ORIGIN]
    vote=bound[VOTE]
    if (first.get('date')!='2025-11-13'
            or first.get('step')!='Ordnungsruf'
            or first.get('official_plenary_session')!=40
            or vote.get('date')!='2025-11-25'
            or vote.get('step')!='Abstimmung'
            or vote.get('official_plenary_session')!=42
            or vote.get('official_position_abstract_excerpt')!=FIRST
            or vote.get('official_decision_tenors')!=['Zurückweisung des Einspruchs']):
        raise ValueError('Bekannte Gottschalk-Erteilung/Einspruch nicht mehr quellengleich')
    extras=[]
    for ident,row in bound.items():
        if ident not in (ORIGIN,VOTE):
            extras.append({
                'parent_id':PARENT,'position_id':ident,
                'step':row.get('step'),
                'abstract_excerpt':row.get('official_position_abstract_excerpt'),
                'source':SOURCE,
            })
    other_parents=[]
    for ident,row in parents.items():
        if ident==PARENT:
            continue
        if not isinstance(row,dict):
            raise ValueError('DIP-Elternobjekt ungültig')
        title=row.get('title') or ''
        abstract=row.get('abstract_excerpt') or ''
        if (not isinstance(title,str) or not isinstance(abstract,str)
                or not isinstance(row.get('date') or '',str)):
            raise ValueError('DIP-Eltern-Metadatenfeld ungültig')
        if (not re.search(r'\bordnungsruf\w*\b',title,re.I)
                or not (named(title,'Kay Gottschalk') or named(abstract,'Kay Gottschalk'))):
            continue
        date=row.get('date') or ''
        if date and date<'2025-11-13':
            continue  # older unrelated original, NOT evidence for second 21/040
        if (not re.fullmatch(r'[1-9]\d{0,11}',ident)
                or row.get('id')!=ident
                or row.get('source')!='https://dip.bundestag.de/vorgang/'+ident):
            raise ValueError('Neuer Gottschalk-Elternvorgang ohne amtliche Identität')
        other_parents.append({
            'parent_id':ident,'title':title,'date':date,
            'active':row.get('active',True),
            'source':row['source'],
            'potentially_related_not_verified':True,
        })
    manual=bool(extras or other_parents)
    return {
        'schema':'wp21-gottschalk-incremental-secondary-appeal-watch-v1',
        'status':('changed_procedure_requires_manual_source_review'
                  if manual else 'no_additional_candidate_in_current_tracked_cache'),
        'cache_scope':'successful_incremental_DIP_parent_and_position_snapshots_only',
        'parent_cache_utc':parent_state['last_success_utc'],
        'position_cache_utc':position_state['last_success_utc'],
        'original_parent_id':PARENT,
        'two_original_calls_single_parent_documented':2,
        'first_appeal_rejection_position_id':VOTE,
        'new_positions_in_same_parent':extras,
        'other_potential_gottschalk_parents':sorted(other_parents,key=lambda x:x['parent_id']),
        'manual_review_required':manual,
        'absent_other_cache_candidates_is_not_appeal_absence_proof':True,
        'eventual_effectiveness_of_second_measure_unresolved':True,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'public_counter_delta':0,
    }


def markdown(r):
    if (r.get('schema')!='wp21-gottschalk-incremental-secondary-appeal-watch-v1'
            or r.get('original_parent_id')!=PARENT
            or r.get('absent_other_cache_candidates_is_not_appeal_absence_proof') is not True
            or r.get('eventual_effectiveness_of_second_measure_unresolved') is not True
            or r.get('automatically_confirmed_effective_sanctions')!=0
            or r.get('public_counter_delta')!=0):
        raise ValueError('Inkremetaler Gottschalk-Bericht ohne Beweisgrenzen')
    lines=[
        '# Gottschalks zweite Erteilung: tägliche DIP-Metadaten-Folgekontrolle',
        '',
        'Bekannter [DIP-Sammelvorgang 328225]'
        '(https://dip.bundestag.de/vorgang/328225): '
        'zwei ursprüngliche Ordnungsrufe, nur erster Einspruch '
        'im derzeit beobachteten Vorgang mit Zurückweisung belegt.',
        '',
        f"Beobachtungsstatus: **{r['status']}**.",
        f"Neue Positionskandidaten: {len(r['new_positions_in_same_parent'])}.",
        f"Weitere mögliche Elternvorgänge: {len(r['other_potential_gottschalk_parents'])}.",
        '',
    ]
    for row in r['new_positions_in_same_parent']:
        lines.append(f"- Neue Position **{row['position_id']}** im DIP-Vorgang 328225: "
                     f"{row['abstract_excerpt']}.")
    for row in r['other_potential_gottschalk_parents']:
        lines.append(f"- Neuer möglicherweise relevanter [DIP-Vorgang "
                     f"{row['parent_id']}]({row['source']}): {row['title']}.")
    lines.extend([
        '',
        '**Nur ein inkrementeller Ausschnitt:** Das Fehlen neuer Metadaten',
        'beweist weder die Abwesenheit anderer oder späterer Verfahren',
        'noch die endgültige rechtliche Wirksamkeit der zweiten Erteilung.',
        'Alle neuen Quellenhinweise verlangen fachliche Einzelprüfung;',
        '**keine automatische Zähleränderung.**','',
    ])
    return '\n'.join(lines)


def run(vorgang_state,position_state,output,brief):
    report=inspect(load_state(vorgang_state),read_position_state(position_state))
    body=markdown(report)
    for path,contents in (
            (Path(output),json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
            (Path(brief),body)):
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(path.suffix+'.tmp')
        tmp.write_text(contents,encoding='utf-8')
        tmp.replace(path)
    if report['manual_review_required']:
        print('::warning::Weitere Gottschalk-DIP-Position oder -Elternquelle: '
              'manuelle Prüfung, KEINE neue öffentliche Zählfreigabe')
    print('WP21_GOTTSCHALK_WATCH_OK: '
          f"{len(report['new_positions_in_same_parent'])} extra positions, "
          f"{len(report['other_potential_gottschalk_parents'])} other parents, "
          'zero automatic legal conclusions')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vorgang-state',type=Path,required=True)
    parser.add_argument('--position-state',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--brief',type=Path,required=True)
    args=parser.parse_args()
    run(args.vorgang_state,args.position_state,args.output,args.brief)
