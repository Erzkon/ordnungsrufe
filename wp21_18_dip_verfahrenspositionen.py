#!/usr/bin/env python3
"""Read-only DIP Vorgang/Position -> original 18 WP21 cases review crosswalk.

DIP data is official metadata, NOT an independently effective sanction.
A full name without the original session or original grant date cannot
identify a case; position keywords cannot determine an appeal outcome.
Only successfully refreshed, complete upstream DIP snapshots may be read.
No public or verified counter is ever written by this module.
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from wp21_autopruefung import norm
from wp21_dip_kontrolle import reference
from wp21_einspruchsbelege import validated_index
from wp21_dip_monitor import load_state, utc
from wp21_dip_positionen import read_position_state
from wp21_hochprioritaet_18 import EXPECTED_KEYS, TARGETS, validate_scope

DIP_PREFIX='https://dip.bundestag.de/vorgang/'
MAX_PARENT_HINTS=300
MAX_POSITION_HINTS=900
WORDS=re.compile(r'\bordnungsruf(?:e|es|en)?\b',re.I)
DIFFERENT_MEASURE=re.compile(r'\b(?:ordnungsgeld(?:es)?|sitzungsausschluss(?:es)?)\b',re.I)
SITTING=re.compile(r'\b(?:in|aus)\s+der\s+(\d{1,3})\.\s*Sitzung\b',re.I)
PROTOCOL=re.compile(r'\b(?:BT[- ]Pl(?:enarprotokoll|Pr)|Plenarprotokoll)?\s*'
                    r'21\s*/\s*0*(\d{1,3})\b',re.I)
ALLOWED_KINDS={'rechtsfolgen_hinweis','ordnungsruf_bezug'}


def mentioned_sittings(text):
    """Detect unambiguous original plenary sitting identifiers, not page counts."""
    return {int(x) for rx in (SITTING,PROTOCOL)
            for x in rx.findall(text) if 1<=int(x)<=450}


def named(text, person):
    """Only complete first+last name matching token boundaries, never substrings."""
    return bool(re.search(r'(?<!\w)'+re.escape(norm(person))+r'(?!\w)',norm(text)))


def control_dates(dip_reference):
    """Map curated original sitting dates; these are not appeal decision dates."""
    result={}
    for control in dip_reference['entries']:
        key=(control['session'],norm(control['person']))
        if key not in EXPECTED_KEYS:
            continue
        value=datetime.strptime(control['date'],'%d.%m.%Y').date().isoformat()
        if key in result and result[key]!=value:
            raise ValueError('DIP-Positivstichprobe hat widersprüchliche Originaldaten')
        result[key]=value
    if set(result)!=EXPECTED_KEYS:
        raise ValueError('18 Originaltermine der kuratierten DIP-Stichprobe fehlen')
    return result


def crosswalk(vorgang, positionen, dip_reference=None):
    """Return bounded and explicitly NON-authoritative metadata review queue."""
    validate_scope()
    if not vorgang.get('last_success_utc') or not positionen.get('last_success_utc'):
        raise ValueError('Zwei erfolgreich abgeschlossene DIP-Snapshots erforderlich')
    if utc(positionen['last_success_utc'])<utc(vorgang['last_success_utc']):
        raise ValueError('Verfahrenspositionen älter als Vorgangsmetadaten')
    dates=control_dates(dip_reference or reference())
    decisions=validated_index()
    if not set(decisions).issubset(EXPECTED_KEYS):
        raise ValueError('Amtlicher Einspruchsbeleg gehört nicht zu den 18 Referenzfällen')
    parents=vorgang.get('items')
    positions=positionen.get('items')
    if not isinstance(parents,dict) or not isinstance(positions,dict):
        raise ValueError('DIP-Snapshotstruktur ungültig')
    if len(parents)>15000 or len(positions)>5000:
        raise ValueError('Zu viele DIP-Metadatensätze für begrenzten Audit')
    per_parent={}
    for ident,p in positions.items():
        if not p.get('active',True):
            continue
        parent=p.get('parent_id')
        if (not re.fullmatch(r'[1-9]\d{0,11}',str(ident))
                or p.get('id')!=ident
                or not re.fullmatch(r'[1-9]\d{0,11}',str(parent))):
            raise ValueError('Positions-ID oder übergeordneter DIP-Vorgang ungültig')
        per_parent.setdefault(parent,[]).append(p)
    cases={(session,norm(person)):{
        'session':session,'person':person,'original_grant_date':dates[(session,norm(person))],
        'candidate_vorgaenge':[], 'total_candidate_positions':0,
        'official_dip_metadata_confirms_effective_sanctions':False,
        'manual_appeal_and_legal_effect_review_required':True}
        for session,names in TARGETS.items() for person in names}
    ambiguous=[]
    disregarded_different_sanction=0
    found_bound=0
    total_bound_positions=0
    for ident,row in sorted(parents.items(),key=lambda x:int(x[0])):
        if not row.get('active',True):
            continue
        if (not re.fullmatch(r'[1-9]\d{0,11}',ident)
                or row.get('id')!=ident
                or row.get('source')!=DIP_PREFIX+ident
                or row.get('kind') not in ALLOWED_KINDS):
            raise ValueError('Nichtamtlicher oder beschädigter DIP-Vorgang')
        title=row.get('title','')
        excerpt=row.get('abstract_excerpt','')
        date=row.get('date','')
        if not all(isinstance(x,str) for x in (title,excerpt,date)):
            raise ValueError('DIP-Feld mit unerwartetem Datentyp')
        body=' '.join((title,excerpt))
        matching=[(s,norm(person)) for s,names in TARGETS.items()
                  for person in names if named(body,person)]
        if not matching:
            continue
        if not WORDS.search(body) or DIFFERENT_MEASURE.search(title):
            # In particular: Köktürk's Ordnungsgeld is NOT a third Ordnungsruf.
            disregarded_different_sanction+=1
            continue
        source_sittings=mentioned_sittings(body)
        explicit=[key for key in matching if source_sittings=={key[0]}]
        by_date=[key for key in matching if
                 not source_sittings and date and dates[key]==date]
        by_official_appeal_date=[
            key for key in matching if not source_sittings and date
            and key in decisions and decisions[key]['decision_date']==date]
        if len(explicit)==1:
            key=explicit[0]
            kind='explicit_original_sitting_candidate'
        elif len(by_date)==1:
            key=by_date[0]
            kind='exact_original_date_candidate'
        elif not by_date and len(by_official_appeal_date)==1:
            # Some official DIP Vorgang dates reflect the parliamentary
            # objection decision date rather than the original grant day.
            # Require a separately verified official Bundestag decision
            # for precisely this original person/session, not mere words.
            key=by_official_appeal_date[0]
            kind='independently_documented_appeal_date_candidate'
        else:
            # No same-name-only link. E.g. Reichardt 21/077 != 21/065.
            ambiguous.append({
                'parent_id':ident,'official_vorgang':row['source'],
                'title':title[:230],
                'metadata_date':date,
                'explicit_sittings_in_metadata':sorted(source_sittings),
                'candidate_original_keys':[f'21/{s:03d}:{p}' for s,p in matching],
                'status':'unbound_dip_person_mention_needs_manual_check',
            })
            if len(ambiguous)>MAX_PARENT_HINTS:
                raise ValueError('Zu viele ungebundene DIP-Kandidaten')
            continue
        pos=[]
        for p in sorted(per_parent.get(ident,[]),key=lambda x:int(x['id'])):
            pid=p['id']
            if (p.get('source')!=row['source']
                    or p.get('kind') not in ('moegliche_rechtsfolge','verfahrensschritt')
                    or not isinstance(p.get('step',''),str)
                    or not isinstance(p.get('title',''),str)
                    or not isinstance(p.get('signal_fields',[]),list)):
                raise ValueError('Beschädigte Position eines zugeordneten DIP-Vorgangs')
            # Real DIP metadata records: "Ordnungsruf" on the original
            # sitting day and later "Abstimmung" on each of the four
            # independently sourced appeal-decision dates. A generic
            # "Abstimmung" alone does NOT prove the outcome of the vote.
            procedural_word=' '.join(p['step'].casefold().split())
            position_date=p.get('date')
            if procedural_word=='ordnungsruf' and position_date==dates[key]:
                role='original_grant_step_metadata_only'
            elif (procedural_word=='abstimmung'
                  and key in decisions
                  and position_date==decisions[key]['decision_date']):
                role='appeal_date_vote_step_independently_corroborated'
            else:
                role='other_or_ambiguous_procedural_step'
            doc_session=p.get('official_plenary_session')
            doc_date=p.get('official_plenary_date')
            doc_pdf=p.get('official_plenary_pdf_url')
            doc_xml=p.get('official_plenary_xml_url')
            tenors=p.get('official_decision_tenors',[])
            abstract=p.get('official_position_abstract_excerpt','')
            if doc_session is not None and (
                    type(doc_session)!=int or not 1<=doc_session<=450
                    or not isinstance(doc_date,str) or not isinstance(doc_pdf,str)
                    or not isinstance(doc_xml,str) or not isinstance(tenors,list)):
                raise ValueError('Ungültiger DIP-Originalfundstellenbeleg')
            if not isinstance(tenors,list) or len(tenors)>10 or any(
                    not isinstance(x,str) or not x or len(x)>300 for x in tenors):
                raise ValueError('Unsicherer gespeicherter DIP-Beschlusstenor')
            if not isinstance(abstract,str):
                raise ValueError('Unsicheres gespeichertes DIP-Positionsabstract')
            if doc_session is not None:
                expected=f'https://dserver.bundestag.de/btp/21/21{doc_session:03d}'
                if (doc_date!=position_date or doc_xml!=expected+'.xml'
                        or not re.fullmatch(
                            re.escape(expected)+r'\\.pdf#P\\.[1-9]\\d{0,5}',doc_pdf)):
                    raise ValueError('Gespeicherter DIP-Originalquelllink manipuliert/inkonsistent')
            if (role=='original_grant_step_metadata_only' and doc_session is not None
                    and doc_session!=key[0]):
                raise ValueError('Fremde ursprüngliche Sitzungsquelle in DIP')
            if (role=='appeal_date_vote_step_independently_corroborated'
                    and doc_session is not None and doc_session<=key[0]):
                raise ValueError('Einspruchsabstimmung nicht in späterer Sitzung')
            source_verified_grant=(role=='original_grant_step_metadata_only'
                and doc_session==key[0] and doc_date==dates[key]
                and bool(doc_pdf and doc_xml))
            source_verified_rejection=(
                role=='appeal_date_vote_step_independently_corroborated'
                and doc_session is not None and doc_session>key[0]
                and doc_date==decisions[key]['decision_date']
                and tenors==['Zurückweisung des Einspruchs']
                and isinstance(abstract,str) and named(abstract,key[1])
                and bool(doc_pdf and doc_xml))
            pos.append({
                'id':pid,'parent_id':ident,'updated':p.get('updated'),
                'date':position_date,'step':p['step'][:350],
                'title':p['title'][:230],
                'kind':p['kind'],'signal_fields':p['signal_fields'],
                'source':row['source'],
                'procedural_step_role_for_review':role,
                'independent_bundestag_appeal_report':(
                    decisions[key]['source']
                    if role=='appeal_date_vote_step_independently_corroborated'
                    else None),
                'official_plenary_protocol_session':doc_session,
                'official_plenary_pdf_page':doc_pdf,
                'official_plenary_xml':doc_xml,
                'official_position_decision_tenors_review_only':tenors,
                'official_original_grant_position_source_verified':source_verified_grant,
                'independent_dip_appeal_rejection_tenor_source_verified':source_verified_rejection,
                'legal_measure_count_from_metadata':None,
                'is_individual_appeal_outcome_legally_confirmed':False,
            })
            total_bound_positions+=1
            if total_bound_positions>MAX_POSITION_HINTS:
                raise ValueError('Zu viele Verfahrenspositions-Hinweise')
        cases[key]['candidate_vorgaenge'].append({
            'parent_id':ident,'source':row['source'],
            'title':title[:300],'metadata_date':date,
            'original_source_link_type':kind,
            'explicit_sittings_in_metadata':sorted(source_sittings),
            'position_count':len(pos),'procedural_position_hints':pos,
            'metadata_kind':row['kind'],
            'individual_legal_effect_not_inferred':True,
        })
        cases[key]['total_candidate_positions']+=len(pos)
        found_bound+=1
        if found_bound>MAX_PARENT_HINTS:
            raise ValueError('Zu viele DIP-Vorgangskandidaten')
    records=[cases[(session,norm(person))] for session,names in sorted(TARGETS.items())
             for person in names]
    if len(records)!=18 or len({(x['session'],norm(x['person'])) for x in records})!=18:
        raise ValueError('18 Originalfälle für DIP-Abgleich nicht vollständig')
    if sum(len(x['candidate_vorgaenge']) for x in records)!=found_bound:
        raise ValueError('DIP-Vorgangszahl inkonsistent')
    return {
        'schema':'wp21-18-dip-procedure-crosswalk-v1',
        'status':'official_dip_metadata_review_only_not_legal_effect',
        'sources':{
            'vorgang_snapshot_utc':vorgang['last_success_utc'],
            'position_snapshot_utc':positionen['last_success_utc'],
            'original_reference':'curated_dip_positive_snapshot_not_complete_history',
            'position_sources_bound_by_official_parent_id':True,
        },
        'original_cases':18,
        'cases_with_bound_parent_candidates':sum(bool(x['candidate_vorgaenge'])
                                                for x in records),
        'bound_vorgang_candidates':found_bound,
        'bound_position_hints':total_bound_positions,
        'source_verified_original_grant_positions':sum(
            p['official_original_grant_position_source_verified']
            for case in records for parent in case['candidate_vorgaenge']
            for p in parent['procedural_position_hints']),
        'source_verified_independent_dip_rejected_appeals':sum(
            p['independent_dip_appeal_rejection_tenor_source_verified']
            for case in records for parent in case['candidate_vorgaenge']
            for p in parent['procedural_position_hints']),
        'original_grant_step_metadata_positions':sum(
            p['procedural_step_role_for_review']=='original_grant_step_metadata_only'
            for case in records for parent in case['candidate_vorgaenge']
            for p in parent['procedural_position_hints']),
        'independent_appeal_date_vote_metadata_positions':sum(
            p['procedural_step_role_for_review']=='appeal_date_vote_step_independently_corroborated'
            for case in records for parent in case['candidate_vorgaenge']
            for p in parent['procedural_position_hints']),
        'unbound_same_name_vorgaenge':len(ambiguous),
        'independently_documented_appeal_date_candidates':sum(
            p['original_source_link_type']=='independently_documented_appeal_date_candidate'
            for case in records for p in case['candidate_vorgaenge']),
        'different_measures_safely_excluded':disregarded_different_sanction,
        'automatically_confirmed_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'protected_statistics_changed':False,
        'warning':('DIP-Metadaten verbinden Vorgänge und Positionen, nicht '
                   'automatisch einzelne rechtswirksame Maßnahmen. '
                   'Sitzungs-/Datumsbezüge sind manuelle Quellenhinweise. '
                   'Fehlende DIP-Kandidaten beweisen keine ausbleibenden Einsprüche.'),
        'cases':records,'unbound_same_name_review_candidates':ambiguous,
    }


def render_markdown(report):
    if (report.get('schema')!='wp21-18-dip-procedure-crosswalk-v1'
            or report.get('original_cases')!=18
            or len(report.get('cases',[]))!=18
            or report.get('automatically_confirmed_sanctions')!=0
            or report.get('automatically_rescinded_sanctions')!=0
            or report.get('protected_statistics_changed')):
        raise ValueError('Unvollständiger/unsicherer DIP-Reviewbericht')
    lines=[
        '# DIP-Vorgänge und Verfahrenspositionen zu 18 Originalfällen – nur Prüfhinweise',
        '',
        f"**DIP-Vorgangssnapshot:** {report['sources']['vorgang_snapshot_utc']}  ",
        f"**DIP-Positionenstand:** {report['sources']['position_snapshot_utc']}  ",
        f"**Gebundene Vorgänge:** {report['bound_vorgang_candidates']}  ",
        f"**Positionen:** {report['bound_position_hints']}  ",
        f"**Quellengeprüfte Originalprotokoll-Positionen:** "
        f"{report['source_verified_original_grant_positions']}  ",
        f"**Quellengeprüfte DIP-Einspruchszurückweisungen:** "
        f"{report['source_verified_independent_dip_rejected_appeals']}  ",
        f"**Ursprüngliche Erteilungs-Positionshinweise:** "
        f"{report['original_grant_step_metadata_positions']}  ",
        f"**Abstimmungspositionen mit unabhängigen Beschlussberichten:** "
        f"{report['independent_appeal_date_vote_metadata_positions']}  ",
        f"**Nur über separat belegtes Einspruchsdatum verknüpfte Vorgänge:** "
        f"{report['independently_documented_appeal_date_candidates']}  ",
        f"**Nicht sicher gebundene Namensvorgänge:** {report['unbound_same_name_vorgaenge']}",
        '',
        '> Keine bestätigte Rechtswirksamkeit. Weder ein DIP-Vorgang noch '
        'die Anzahl von Verfahrenspositionen ist die Anzahl wirksamer Ordnungsrufe.',
        '',
        '| Ursprüngliche Sitzung | Person | Datum | DIP-Vorgänge / Positionen | Abgleichqualität |',
        '| --- | --- | --- | --- | --- |',
    ]
    for case in report['cases']:
        candidates=case['candidate_vorgaenge']
        links=', '.join(f"[{p['parent_id']}]({p['source']})"
                        for p in candidates) or 'Keine eindeutige Kandidatenbindung'
        modes=', '.join(p['original_source_link_type'] for p in candidates) or 'keine'
        lines.append(
            f"| 21/{case['session']:03d} | {case['person']} | "
            f"{case['original_grant_date']} | {links} / "
            f"{case['total_candidate_positions']} Positionen | {modes} |")
    lines.extend([
        '',
        '## Ungebundene, namentlich passende DIP-Vorgänge',
        '',
        'Diese Vorgänge werden wegen fremder/widersprüchlicher Sitzungsnummern',
        'oder fehlender exakter Datumsangabe **keiner** Erteilung zugerechnet.',
    ])
    for x in report['unbound_same_name_review_candidates']:
        lines.append(f"- [{x['parent_id']}]({x['official_vorgang']}) – "
                     f"{x['title'][:160]} "
                     f"(Sitzungen {x['explicit_sittings_in_metadata']}; Datum {x['metadata_date']}).")
    lines.extend([
        '',
        '## Fachliche Prüfschranken',
        '',
        '- Nur der vollständige amtliche Personenname plus ursprünglicher',
        '  Sitzungsbezug, das Erteilungsdatum oder ein **unabhängig amtlich',
        '  belegtes Einspruchsentscheidungsdatum** können einen **unbestätigten**',
        '  DIP-Vorgangskandidaten an genau eine Originalakte binden.',
        '- Originalpositionen „Ordnungsruf“ und spätere Positionen',
        '  „Abstimmung“ bleiben eigenständige Metadatenbelege; die',
        '  Abstimmungszuordnung setzt einen externen Beschlussbericht',
        '  mit genau diesem Namen, dieser Sitzung und diesem Datum voraus.',
        '- Die Verfahrenspositionen bleiben über originale DIP-Vorgang-IDs'
        '  verbunden. Schlagwörter wie Einspruch, Rücknahme und Ablehnung',
        '  sind **keine** unabhängig geprüften Beschlüsse.',
        '- Ältere, inaktive Metadaten bleiben im inkrementellen',
        '  Quellensnapshot historisiert, werden aber nicht als aktive',
        '  Vorgänge der Einzelakten gezählt.',
        '- Fehlende Treffer, API-Fehler oder nicht vorhandene',
        '  Dokumentvolltexte begründen keine abschließende Wirksamkeit.',
        '- Diese Ausgaben verändern weder bestätigte CSV/JSON-Dateien',
        '  noch öffentliche Zähler.',
        '',
    ])
    return '\n'.join(lines)


def run(vorgang_state, position_state, output, brief):
    parent=load_state(vorgang_state)
    child=read_position_state(position_state)
    report=crosswalk(parent,child)
    document=render_markdown(report)
    for path,payload in ((Path(output),json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
                         (Path(brief),document)):
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(path.suffix+'.tmp')
        tmp.write_text(payload,encoding='utf-8')
        tmp.replace(path)
    print(f"DIP-18-PRUEFUNG: {report['original_cases']} Einzelakten, "
          f"{report['bound_vorgang_candidates']} gebundene Vorgangs-Kandidaten, "
          f"{report['bound_position_hints']} positionsbezogene Metadaten, "
          "0 automatisch bestätigte Maßnahmen.")
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vorgang-state',type=Path,
                    default=Path('.cache/dip21/state.json'))
    ap.add_argument('--position-state',type=Path,
                    default=Path('.cache/dip21/positionen.json'))
    ap.add_argument('--output',type=Path,
                    default=Path('.audit/wp21_18_dip_verfahrenspositionen.json'))
    ap.add_argument('--brief',type=Path,
                    default=Path('.audit/wp21_18_dip_verfahrenspositionen.md'))
    a=ap.parse_args()
    run(a.vorgang_state,a.position_state,a.output,a.brief)


if __name__=='__main__':
    main()
