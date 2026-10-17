#!/usr/bin/env python3
"""Exact official DIP source crosswalk for ten 2025 person/day original cases.

Ten *parents* with one origin-position each describe TWELVE originally
issued calls, whereas ELEVEN separately documented objections were
rejected. Gottschalk has two calls in one official parent but the one
available vote explicitly concerns his FIRST measure. This proves
nothing about the final legal effect of his second grant.

Neither the number of parents, origin-positions, or rejected objections
is a new public count of independently legally effective Ordnungsrufe.
"""
import argparse
import json
import re
from pathlib import Path

from wp21_autopruefung import norm
from wp21_18_dip_verfahrenspositionen import named
from wp21_weitere_einspruchsberichte import EVIDENCE

DIP='https://dip.bundestag.de/vorgang/'

# Official ten independent IDs/positions checked against the real DIP API:
# https://github.com/Erzkon/ordnungsrufe/actions/runs/39016255012
# Each tuple: original ISO day, full identity, official DIP ID,
# origin session, decision session, original grant count, decided appeals.
CASES=(
 ('2025-06-05','Stephan Brandner','322353',10,11,1,1),
 ('2025-06-06','Stephan Brandner','322377',11,12,1,1),
 ('2025-06-27','Luigi Pantisano','322932',15,16,1,1),
 ('2025-09-18','Mirze Edis','326010',25,26,1,1),
 ('2025-11-13','Kay Gottschalk','328225',40,42,2,1),
 ('2025-11-13','Martin Sichert','328523',40,42,1,1),
 ('2025-11-13','Steffen Janich','328224',40,42,2,2),
 ('2025-11-26','Martin Reichardt','328595',43,45,1,1),
 ('2025-12-17','Stephan Brandner','329445',49,50,1,1),
 ('2025-12-18','Martin Reichardt','329551',50,51,1,1),
)
# Explicit, person- and case-specific original procedural distinction.
SPECIAL_ABSTRACTS={
 ('2025-11-13',norm('Kay Gottschalk')):
     ('gegen die erste Ordnungsmaßnahme',),
 ('2025-11-13',norm('Steffen Janich')):
     ('gegen die 1. Ordnungsmaßnahme',
      'gegen die 2. Ordnungsmaßnahme'),
}


def verified_case_index():
    if len(CASES)!=10 or len({(d,norm(p)) for d,p,*_ in CASES})!=10:
        raise ValueError('Zehn einzigartige amtliche DIP-Originfälle fehlen')
    if len({ident for _,_,ident,*_ in CASES})!=10:
        raise ValueError('DIP-Vorgangs-ID eines Originals mehrfach verwendet')
    if sum(x[5] for x in CASES)!=12 or sum(x[6] for x in CASES)!=11:
        raise ValueError('Original- und Einspruchsgesamtmengen verwechselt')
    for d,name,ident,session,decision_session,grants,objections in CASES:
        if (not re.fullmatch(r'[1-9]\d{0,11}',ident)
                or not 1<=session<decision_session<=450
                or (grants,objections) not in ((1,1),(2,1),(2,2))
                or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',d)):
            raise ValueError('Beschädigter kuratierter DIP-Originalfall')
    independent={}
    for e in EVIDENCE:
        if e['original_date'].startswith('2025-'):
            key=(e['original_date'],norm(e['person']))
            independent.setdefault(key,[]).append(e)
    target={(d,norm(name)) for d,name,*_ in CASES}
    if set(independent)!=target:
        raise ValueError('DIP-Originalfälle stimmen nicht mit unabhängigen Einsprüchen überein')
    for day,name,_,session,_,_,count in CASES:
        objections=independent[(day,norm(name))]
        if (len(objections)!=count
                or sorted(x['individual_objection_ordinal']
                          for x in objections)!=list(range(1,count+1))):
            raise ValueError('Einspruchsanzahl und Einzelidentitäten passen nicht zum Original')
        existing={x['original_session'] for x in objections if x['original_session']}
        if existing and existing!={session}:
            raise ValueError('Unabhängig belegte Ursprungsnummer widerspricht DIP')
    return {(d,norm(n)):(n,ident,s,decision,g,v)
            for d,n,ident,s,decision,g,v in CASES}


def official_plenary_url(value,session):
    root=f'https://dserver.bundestag.de/btp/21/21{session:03d}'
    return (isinstance(value,str)
            and bool(re.fullmatch(re.escape(root)+r'\.pdf#P\.[1-9]\d{0,5}',value)))


def inspect(snapshot):
    targets=verified_case_index()
    if (not isinstance(snapshot,dict)
            or (snapshot.get('schema'),snapshot.get('status')) not in (
                ('wp21-2025-targeted-official-dip-source-survey-v1',
                 'noncounting_complete_filtered_api_inventory'),
                ('wp21-2025-source-bound-completed-dip-cache-v1',
                 'read_only_incremental_dip_positions_no_exhaustive_appeal_history'))
            or snapshot.get('official_2025_originals_targeted')!=10
            or snapshot.get('automatically_confirmed_effective_sanctions')!=0
            or snapshot.get('automatically_rescinded_sanctions')!=0
            or snapshot.get('protected_statistics_changed') is not False):
        raise ValueError('Amtlicher Vollfilter-Quellensnapshot nicht vertrauenswürdig')
    cases=snapshot.get('ten_original_person_date_cases')
    if not isinstance(cases,list) or len(cases)!=10:
        raise ValueError('Genau zehn Original-DIP-Fallprüfakten notwendig')
    seen=set()
    used_parents=set()
    used_positions=set()
    results=[]
    for raw in cases:
        if not isinstance(raw,dict):
            raise ValueError('Beschädigte 2025-DIP-Einzelakte')
        key=(raw.get('original_date'),norm(raw.get('person','')))
        if key not in targets or key in seen:
            raise ValueError('Unbekannter oder mehrfach zugeordneter Person/Datum-Fall')
        seen.add(key)
        fullname,ident,original_session,vote_session,original_grants,objections=targets[key]
        if (raw.get('person')!=fullname or raw.get('matching_parent_ids')!=[ident]
                or raw.get('candidate_parent_count')!=1):
            raise ValueError('Originaldatum/Person nicht eindeutig genau einem DIP-Vorgang zugeordnet')
        parents=raw.get('sources')
        if not isinstance(parents,list) or len(parents)!=1:
            raise ValueError('DIP-Originalquelle fehlend oder mehrdeutig')
        parent=parents[0]
        if (parent.get('id')!=ident or ident in used_parents
                or parent.get('source')!=DIP+ident
                or fullname not in parent.get('matching_person_names',[])
                or not named(parent.get('title',''),fullname)
                or not re.search(r'\bordnungsruf\w*\b',parent.get('title',''),re.I)):
            raise ValueError('Fremder DIP-Vorgang oder Personenname')
        used_parents.add(ident)
        title=' '.join(parent['title'].split())
        if original_grants==2:
            if not re.search(r'\bvon\s+zwei\s+Ordnungsrufen\b',title,re.I):
                raise ValueError('Amtliche Mehrfacherteilung nicht ausdrücklich belegt')
        elif re.search(r'\bvon\s+zwei\s+Ordnungsrufen\b',title,re.I):
            raise ValueError('Ausdrücklich doppelte Erteilung nicht als einzelne einstufen')
        positions=parent.get('original_positions')
        if not isinstance(positions,list) or len(positions)!=1+objections:
            raise ValueError('Nicht genau Original + individuell belegte Einspruchspositionen')
        if parent.get('original_grant_positions')!=[
                p for p in positions
                if p.get('step')=='Ordnungsruf' and p.get('date')==key[0]]:
            raise ValueError('Original-Erteilungsposition inkonsistent oder doppelt')
        grant=[]
        votes=[]
        decision_dates={r['decision_date'] for r in EVIDENCE
                        if r['original_date']==key[0]
                        and norm(r['person'])==key[1]}
        if len(decision_dates)!=1:
            raise ValueError('Widersprüchliche unabhängige Einspruchsdaten')
        decision_date=next(iter(decision_dates))
        for p in positions:
            if not isinstance(p,dict):
                raise ValueError('DIP-Vorgangsposition ist kein Objekt')
            pid=str(p.get('id',''))
            if not re.fullmatch(r'[1-9]\d{0,11}',pid) or pid in used_positions:
                raise ValueError('Mehrdeutige/ungültige DIP-Positions-ID')
            used_positions.add(pid)
            step=p.get('step')
            if step=='Ordnungsruf':
                if (grant or p.get('date')!=key[0]
                        or p.get('plenary_session')!=original_session
                        or not official_plenary_url(p.get('plenary_pdf'),original_session)
                        or p.get('plenary_xml')!=
                            f'https://dserver.bundestag.de/btp/21/21{original_session:03d}.xml'
                        or p.get('decision_tenors')!=[]):
                    raise ValueError('Amtliche Originalerteilungsposition falsch referenziert')
                grant.append(p)
            elif step=='Abstimmung':
                if (p.get('date')!=decision_date
                        or p.get('plenary_session')!=vote_session
                        or not official_plenary_url(p.get('plenary_pdf'),vote_session)
                        or p.get('plenary_xml')!=
                            f'https://dserver.bundestag.de/btp/21/21{vote_session:03d}.xml'
                        or p.get('decision_tenors')!=['Zurückweisung des Einspruchs']
                        or not named(p.get('abstract_excerpt',''),fullname)):
                    raise ValueError('Unbelegte DIP-Einspruchsentscheidung/Originalbezug')
                votes.append(p)
            else:
                raise ValueError('Nicht geprüfter zusätzlicher DIP-Rechtsfolgen-Schritt')
        if len(grant)!=1 or len(votes)!=objections:
            raise ValueError('Original/Abstimmung nicht getrennt nachgewiesen')
        fragments=SPECIAL_ABSTRACTS.get(key)
        if fragments:
            # Each verified first/second-appeal marker must occur in ONE
            # distinct DIP vote position. Merely mentioning both in the
            # same summary must not count as two different decisions.
            matched_positions=[]
            for phrase in fragments:
                matches=[index for index,vote in enumerate(votes)
                         if phrase.casefold() in vote['abstract_excerpt'].casefold()]
                if len(matches)!=1:
                    raise ValueError('Einspruch für die erste/zweite Maßnahme nicht unterscheidbar')
                matched_positions.extend(matches)
            if (len(fragments)!=len(votes)
                    or len(set(matched_positions))!=len(votes)):
                raise ValueError('Einspruch für die erste/zweite Maßnahme nicht unterscheidbar')
        status=(
            'second_original_measured_but_no_second_appeal_vote_in_this_parent'
            if (key==('2025-11-13',norm('Kay Gottschalk')))
            else 'both_separate_appeals_rejected'
            if (key==('2025-11-13',norm('Steffen Janich')))
            else 'one_original_and_one_rejected_appeal')
        results.append({
            'original_date':key[0], 'person':fullname,
            'original_sitting':original_session,
            'decision_sitting':vote_session,'decision_date':decision_date,
            'official_dip_parent_id':ident,'official_dip_parent':DIP+ident,
            'official_title':title,
            'independently_sourced_original_issuance_count_review_only':original_grants,
            'independently_sourced_rejected_objection_count':objections,
            'original_dip_position':{
                'id':grant[0]['id'],'plenary_pdf':grant[0]['plenary_pdf'],
                'plenary_xml':grant[0]['plenary_xml']},
            'decision_dip_positions':[{
                'id':p['id'],'plenary_pdf':p['plenary_pdf'],
                'decision_tenor':'Zurückweisung des Einspruchs',
                'abstract_excerpt':p['abstract_excerpt']} for p in votes],
            'review_status':status,
            'legal_effect_of_individual_measures_not_inferred':True,
            'unseen_future_or_other_parent_procedures_not_excluded':True,
        })
    if len(seen)!=10 or len(used_parents)!=10 or len(used_positions)!=21:
        raise ValueError('Unvollständige zehn Originalvorgänge/21 Positionen')
    results.sort(key=lambda x:(x['original_date'],norm(x['person'])))
    if (sum(x['independently_sourced_original_issuance_count_review_only']
            for x in results)!=12
            or sum(x['independently_sourced_rejected_objection_count']
                   for x in results)!=11):
        raise ValueError('Zwölf Originalerteilungen und elf belegte Einsprüche vermischt')
    return {
        'schema':'wp21-2025-ten-cases-original-votes-review-v1',
        'official_source_run':'https://github.com/Erzkon/ordnungsrufe/actions/runs/39016255012',
        'source_scope':(
            '2025-06-01_to_2026-01-05_dip_filtered_title_survey'
            if snapshot.get('schema')=='wp21-2025-targeted-official-dip-source-survey-v1'
            else 'latest_successfully_completed_incremental_dip_parent_and_position_snapshots'),
        'case_count':10,'official_parent_ids':10,
        'source_original_grant_positions':10,
        'original_issuance_events_review_only':12,
        'separate_rejected_objections':11,'official_position_records':21,
        'gottschalk_two_initial_grants_one_first_objection_decision':True,
        'janich_two_initial_grants_two_independent_decisions':True,
        'other_gottschalk_outcome_unknown_outside_examined_parent':True,
        'automatically_confirmed_effective_measures':0,
        'automatically_rescinded_measures':0,
        'public_statistics_modified':False,
        'warning':('Zehn amtliche DIP-Vorgänge beschreiben zwölf ursprünglich '
                   'erteilte Maßnahmen und elf später zurückgewiesene Einsprüche. '
                   'Diese Werte sind drei unterschiedliche Metriken; der '
                   'abschließende Bestand wirksamer Einzelmaßnahmen bleibt '
                   'bei fehlender unabhängiger Statusprüfung unbekannt.'),
        'cases':results,
    }


def survey_from_complete_cache(vorgang,positionen):
    """Build a 10-parent audit input only from two successful DIP snapshots.

    This does NOT imply the cached records cover every separate procedure.
    An unexpected later voting position breaks the frozen 2025 expectation
    and triggers a review warning, never an automatic count revision.
    """
    from wp21_dip_monitor import utc
    verified_case_index()
    if (not isinstance(vorgang,dict) or not isinstance(positionen,dict)
            or not vorgang.get('last_success_utc')
            or not positionen.get('last_success_utc')):
        raise ValueError('Zwei erfolgreich abgeschlossene DIP-Snapshots notwendig')
    if utc(positionen['last_success_utc'])<utc(vorgang['last_success_utc']):
        raise ValueError('DIP-Verfahrenspositionen gegenüber Vorgängen veraltet')
    parents=vorgang.get('items')
    positions=positionen.get('items')
    if not isinstance(parents,dict) or not isinstance(positions,dict):
        raise ValueError('Amtliche DIP-Cache-Struktur beschädigt')
    if len(parents)>15000 or len(positions)>5000:
        raise ValueError('DIP-Cache größer als erlaubter Originalquellenabgleich')
    records=[]
    used_position_ids=set()
    for day,person,ident,session,decision_session,grants,votes in CASES:
        parent=parents.get(ident)
        if (not isinstance(parent,dict) or parent.get('active',True) is not True
                or parent.get('id')!=ident or parent.get('source')!=DIP+ident
                or not named(parent.get('title',''),person)):
            raise ValueError('Einer der zehn amtlichen Elternvorgänge fehlt/ist nicht aktiv')
        source_positions=[]
        for key,p in positions.items():
            if p.get('parent_id')!=ident:
                continue
            # A tracked position disappearing from DIP is a change that
            # needs individual review; never discard it and present the
            # remaining source steps as an unchanged complete dossier.
            if p.get('active',True) is not True:
                raise ValueError('Eine DIP-Position des Originals wurde inaktiv/entfernt')
            if (key in used_position_ids or p.get('id')!=key
                    or p.get('source')!=DIP+ident):
                raise ValueError('Verwechslung/Dublette in amtlichen DIP-Positionen')
            used_position_ids.add(key)
            source_positions.append({
                'id':key,'date':p.get('date'),'step':p.get('step'),
                'plenary_session':p.get('official_plenary_session'),
                'plenary_pdf':p.get('official_plenary_pdf_url'),
                'plenary_xml':p.get('official_plenary_xml_url'),
                'decision_tenors':p.get('official_decision_tenors'),
                'abstract_excerpt':p.get('official_position_abstract_excerpt'),
                'signal_fields':p.get('signal_fields',[]),
            })
        source_positions.sort(key=lambda p:int(p['id']))
        original=[p for p in source_positions
                  if p['date']==day and p['step']=='Ordnungsruf']
        source={'id':ident,'source':DIP+ident,'title':parent['title'],
                'date':parent.get('date'),'matching_person_names':[person],
                'original_positions':source_positions,
                'original_grant_positions':original}
        records.append({
            'original_date':day,'person':person,
            'candidate_parent_count':1,'matching_parent_ids':[ident],
            'sources':[source],
        })
    return {
        'schema':'wp21-2025-source-bound-completed-dip-cache-v1',
        'status':'read_only_incremental_dip_positions_no_exhaustive_appeal_history',
        'official_2025_originals_targeted':10,
        'vorgang_snapshot_utc':vorgang['last_success_utc'],
        'position_snapshot_utc':positionen['last_success_utc'],
        'ten_original_person_date_cases':records,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'protected_statistics_changed':False,
    }


def run_from_cache(vorgang_state,position_state,output,brief):
    """Daily incremental evidence refresh, no API calls or public writes."""
    from wp21_dip_monitor import load_state
    from wp21_dip_positionen import read_position_state
    snapshot=survey_from_complete_cache(load_state(vorgang_state),
                                        read_position_state(position_state))
    return run_snapshot(snapshot,output,brief)


def render_markdown(report):
    if (report.get('schema')!='wp21-2025-ten-cases-original-votes-review-v1'
            or report.get('case_count')!=10
            or report.get('original_issuance_events_review_only')!=12
            or report.get('separate_rejected_objections')!=11
            or report.get('official_position_records')!=21
            or report.get('automatically_confirmed_effective_measures')!=0
            or report.get('public_statistics_modified')):
        raise ValueError('Unvollständige ursprüngliche Erteilung/Einspruchsprüfakte')
    lines=[
        '# Zehn amtliche DIP-Originalvorgänge (2025) und ihre Einspruchsentscheidungen',
        '',
        '**Zehn offiziell verifizierte DIP-Vorgänge; zwölf ursprünglich',
        'erteilte Ordnungsrufe; elf getrennt zurückgewiesene Einsprüche.**',
        '',
        '> Diese Angaben sind keine neue Summe rechtlich wirksamer Rufe.',
        '> DIP-Vorgang, ursprüngliche Erteilung und Einspruchsentscheidung',
        '> sind unterschiedliche Quelleneinheiten.',
        '',
        '| Originaltag | Person | Sitzung | Ursprüngliche Erteilungen | Zurückgewiesene Einsprüche | Originalbeleg |',
        '| --- | --- | --- | ---: | ---: | --- |',
    ]
    for r in report['cases']:
        lines.append(
            f"| {r['original_date']} | {r['person']} | "
            f"21/{r['original_sitting']:03d} | "
            f"{r['independently_sourced_original_issuance_count_review_only']} | "
            f"{r['independently_sourced_rejected_objection_count']} | "
            f"[DIP {r['official_dip_parent_id']}]({r['official_dip_parent']}) · "
            f"[amtliches PDF]({r['original_dip_position']['plenary_pdf']}) |")
    lines.extend(['','## Kritischer Gottschalk-Befund','',
        'Im Sammelvorgang **328225** stehen zwei ursprünglich erteilte',
        'Ordnungsrufe, aber nur **eine** Einspruchsabstimmung:',
        'Sie bezeichnet ausdrücklich die **erste Ordnungsmaßnahme**.',
        'Der andere ursprüngliche Ordnungsruf ist in diesem Vorgang',
        'nicht durch eine weitere Abstimmungsposition beantwortet.',
        'Ein weiteres Einspruchsverfahren außerhalb dieser konkret',
        'überprüften DIP-Positionen kann nicht ausgeschlossen werden.',
        '',
        'Bei **Steffen Janich (DIP 328224)** bezeichnen die beiden',
        'Abstimmungspositionen ausdrücklich die **erste** und',
        '**zweite** Ordnungsmaßnahme, die beide zurückgewiesen wurden.',
        '',
        'Keine öffentlich bestätigten Statistiken geändert und keine',
        'automatische Entscheidung über den Rechtsbestand getroffen.',
        ''])
    return '\n'.join(lines)


def run(source,output,brief):
    raw=json.loads(Path(source).read_text(encoding='utf-8'))
    return run_snapshot(raw,output,brief)


def run_snapshot(raw,output,brief):
    report=inspect(raw)
    markdown=render_markdown(report)
    for target,data in ((Path(output),json.dumps(report,indent=2,ensure_ascii=False)+'\n'),
                        (Path(brief),markdown)):
        target.parent.mkdir(parents=True,exist_ok=True)
        temp=target.with_suffix(target.suffix+'.tmp')
        temp.write_text(data,encoding='utf-8')
        temp.replace(target)
    print('WP21_2025_REVIEW_OK: 10 DIP parents, 12 issued originals, '
          '11 separate rejected objections, 21 positions, '
          '0 confirmed new effective sanctions')
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path)
    ap.add_argument('--vorgang-state',type=Path)
    ap.add_argument('--position-state',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--brief',type=Path,required=True)
    a=ap.parse_args()
    if bool(a.source)==bool(a.vorgang_state or a.position_state):
        raise SystemExit('Entweder --source oder beide --vorgang-state und --position-state')
    if a.source:
        run(a.source,a.output,a.brief)
    elif a.vorgang_state and a.position_state:
        run_from_cache(a.vorgang_state,a.position_state,a.output,a.brief)
    else:
        raise SystemExit('Beide DIP-Cachepfade erforderlich')
