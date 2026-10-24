#!/usr/bin/env python3
"""Read-only exhaustive DIP parent/position refresh for 12 other pinned WP21 review cases.

Together with the pre-existing five-case audit, this covers all 17 pending
person/session combinations in the dated positive sample. It is NOT a
complete review of all potentially separate DIP proceedings, and it grants
zero legal effectiveness decisions and changes zero approved counters.
"""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wp21_autopruefung import norm, read_reviewed
from wp21_dip_kontrolle import reference
from wp21_18_dip_original_beschluesse import PINS
from wp21_hochprioritaet_18 import EXPECTED_KEYS, ORIGINAL_LINES, validate_scope
from wp21_batch_review import POSITIVE, LEDGER, build as review_queue
from wp21_five_origins import build as five_originals
from wp21_five_rechtsfolgen import (
    EXPECTED as FIVE_PINS, assess_dip, official_parent, PUBLIC_KEY,
)
from wp21_dip_positionen import fetch_positions
from wp21_three_decisions import ROOT

OUT=ROOT/'.audit/wp21_all17_followups'
WARNING=(
    'Das vollständige Abrufen der Verfahrenspositionen von 17 exakt bekannten '
    'amtlichen DIP-Originalvorgängen bedeutet nicht, dass weitere getrennte '
    'Vorgänge, spätere Rücknahmen, gerichtliche Entscheidungen oder sonstige '
    'Rechtsfolgen vollständig bekannt sind. Einzelne Abstimmungspositionen '
    'sind zunächst Metadaten-Hinweise, keine rechtliche Wirksamkeitsfeststellung.'
)


def sources(snapshot=None, known=None):
    validate_scope()
    snapshot=reference(POSITIVE) if snapshot is None else snapshot
    if known is None:
        known,n=read_reviewed(LEDGER)
        if n!=8:
            raise ValueError('Öffentlicher WP21-Teilbestand verändert')
    q=review_queue(snapshot,known,8)
    five=five_originals(snapshot=snapshot,known=known)
    five_keys={(c['session'],norm(c['person'])) for c in five['cases']}
    expected_five={(session,person) for session,person in FIVE_PINS}
    if five_keys!=expected_five or len(five_keys)!=5:
        raise ValueError('Fünf bereits live geprüfte Originalfälle geändert')
    if (len(q['cases'])!=17 or len(PINS)!=18 or
            not set(FIVE_PINS).issubset(set(PINS)) or
            set(FIVE_PINS)!=five_keys or
            q['automatic_approved_sanctions']!=0):
        raise ValueError('Datierter DIP-Audit oder 18 Originalquellen geändert')
    indexed={(row['session'],norm(row['person'])):row
             for row in snapshot['entries']}
    remaining=[]
    for c in q['cases']:
        key=(c['session'],norm(c['person']))
        if key in five_keys:
            continue
        control=indexed.get(key)
        if not control or key not in EXPECTED_KEYS or key not in PINS:
            raise ValueError('DIP-Ursprungsfall ohne zuordenbare Quelle')
        if (tuple(c['original_xml_lines'])!=ORIGINAL_LINES[key] or
                c['reported_but_not_individually_verified']!=1 or
                c['already_verified_measures']!=0 or
                control['reported_grants']!=1 or
                c['source_pdf']!=control['official_transcript']):
            raise ValueError('Original-Erteilungsstichprobe nicht konsistent')
        day=datetime.strptime(control['date'],'%d.%m.%Y').date().isoformat()
        remaining.append({
            'session':c['session'],
            'person':c['person'],
            'original_date':day,
            'original_xml_lines':c['original_xml_lines'],
            'original_pdf_url':c['source_pdf'],
            'official_dip_parent_id':PINS[key],
            'official_dip_parent_url':'https://dip.bundestag.de/vorgang/'+PINS[key],
            'individually_curated_appeal_decision':c['official_appeal_decision'],
            'multiple_wording_relation':c['multiple_wording_relation'],
            'additional_approved_sanctions':0,
            'case_has_conclusive_individual_legal_effect_review':False,
        })
    if len(remaining)!=12 or len({c['official_dip_parent_id'] for c in remaining})!=12:
        raise ValueError('Nicht genau zwölf ergänzende originalverankerte DIP-IDs')
    if sum(bool(c['individually_curated_appeal_decision']) for c in remaining)!=4:
        raise ValueError('Vier separat belegte Einsprüche unter den zwölf fehlen')
    if len({(c['session'],norm(c['person'])) for c in remaining}|five_keys)!=17:
        raise ValueError('Nicht alle 17 Person-/Sitzungsfälle separat zugeordnet')
    return {
        'schema':'wp21-pinned-other-12-dip-sources-v1',
        'snapshot_date':snapshot['last_manual_snapshot'],
        'already_refreshed_five':sorted(FIVE_PINS.values(),key=int),
        'twelve_cases':remaining,
        'scope':'dated_original_sample_17_cases_not_the_entire_term',
        'fully_reviewed_legal_effects':0,
        'automatically_approved_new_sanctions':0,
        'protected_public_counter_changes':0,
        'warning':WARNING,
    }


def combine(base,results=None,five_live=None,refreshed_at=None):
    if (base.get('schema')!='wp21-pinned-other-12-dip-sources-v1'
            or len(base['twelve_cases'])!=12
            or base['automatically_approved_new_sanctions']!=0):
        raise ValueError('Zwölfer-Ausgangsbasis unsicher')
    if results is None:
        if five_live is not None:
            raise ValueError('Keine Fünfer-Livequelle ohne Zwölfer-Liveprüfung')
        return {**base,'live_status':'not_checked','all_17_pinned_parents_refreshed':False,
                'total_additional_position_review_hints':None}
    expected={x['official_dip_parent_id'] for x in base['twelve_cases']}
    if set(results)!=expected or len(results)!=12:
        raise ValueError('Nicht alle zwölf amtlichen Positionen vollständig abgefragt')
    if (not isinstance(five_live,dict)
            or five_live.get('schema')!='wp21-five-legal-followup-matrix-v1'
            or five_live.get('live_dip_parent_status')!='all_five_refreshed'
            or not five_live.get('live_dip_complete_for_exact_five_parents')
            or five_live.get('automatically_approved_new_sanctions')!=0
            or five_live.get('protected_ledger_changed') is not False
            or len(five_live.get('cases',[]))!=5):
        raise ValueError('Geprüfte Fünfer-Liveausgabe fehlt oder unsicher')
    five_ids={x['official_dip_parent_id'] for x in five_live['cases']}
    if five_ids!=set(base['already_refreshed_five']) or expected&five_ids:
        raise ValueError('Doppelte oder fehlende DIP-Eltern unter 17 Originalfällen')
    for c in five_live['cases']:
        assessment=c.get('dip_parent_metadata_review')
        if (not isinstance(assessment,dict)
                or assessment.get('official_dip_parent_id')!=c['official_dip_parent_id']
                or assessment.get('positions_completely_fetched_for_this_parent') is not True
                or assessment.get('automatic_count_change')!=0):
            raise ValueError('Fünfer-DIP-Positionen unvollständig')
    for case in base['twelve_cases']:
        assessment=results[case['official_dip_parent_id']]
        if (assessment.get('official_dip_parent_id')!=case['official_dip_parent_id']
                or assessment.get('positions_completely_fetched_for_this_parent') is not True
                or assessment.get('automatic_count_change')!=0):
            raise ValueError('Zwölfer-DIP-Position unvollständig oder fremd')
    if refreshed_at is None:
        raise ValueError('Zeitpunkt des amtlichen Live-Abrufs fehlt')
    fresh=datetime.fromisoformat(refreshed_at)
    five_time=datetime.fromisoformat(five_live['last_five_parent_probe_utc'])
    if (fresh.tzinfo is None or five_time.tzinfo is None
            or abs(fresh-five_time)>timedelta(hours=1)):
        raise ValueError('Beide getrennten Live-Abrufe müssen zeitnah sein')
    augmented=[
        {**c,'dip_parent_metadata_review':results[c['official_dip_parent_id']]}
        for c in base['twelve_cases']
    ]
    all_assessments=[c['dip_parent_metadata_review'] for c in augmented]+[
        c['dip_parent_metadata_review'] for c in five_live['cases']]
    if len(all_assessments)!=17:
        raise ValueError('Siebzehn Live-Prüffälle nicht vollständig')
    # Distinguish four already individually curated appeal-vote positions
    # from newly surfaced, as-yet-unattributed procedure metadata. Merely
    # seeing a vote position never adjudicates the legal effect.
    categorized=[]
    for c in augmented:
        curated=c['individually_curated_appeal_decision']
        for p in c['dip_parent_metadata_review']['positions']:
            if p['role_for_review']=='original_grant_step':
                continue
            preexisting=bool(
                curated and p['role_for_review']=='unadjudicated_appeal_vote_metadata_candidate'
                and p['date']==curated['date']
                and p['official_plenary_session'] is not None
                and p['official_plenary_session']>c['session']
                and 'Zurückweisung des Einspruchs' in p['decision_tenor_metadata_only']
            )
            categorized.append({
                'person':c['person'],'session':c['session'],
                'official_dip_parent_id':c['official_dip_parent_id'],
                'official_position_id':p['official_position_id'],
                'official_position_api':p['official_position_api'],
                'date':p['date'],'role_for_review':p['role_for_review'],
                'already_independently_curated_vote_metadata':preexisting,
                'needs_new_manual_source_review':not preexisting,
                'legal_effect_decided_by_this_classifier':False,
            })
    for c in five_live['cases']:
        for p in c['dip_parent_metadata_review']['positions']:
            if p['role_for_review']=='original_grant_step':
                continue
            categorized.append({
                'person':c['person'],'session':c['session'],
                'official_dip_parent_id':c['official_dip_parent_id'],
                'official_position_id':p['official_position_id'],
                'official_position_api':p['official_position_api'],
                'date':p['date'],'role_for_review':p['role_for_review'],
                'already_independently_curated_vote_metadata':False,
                'needs_new_manual_source_review':True,
                'legal_effect_decided_by_this_classifier':False,
            })
    if len(categorized)!=sum(
            a['other_step_review_hints'] for a in all_assessments):
        raise ValueError('Zusatzpositionen ohne vollständig kategorisierte Quelle')
    return {
        **base,'twelve_cases':augmented,
        'live_status':'all_17_pinned_parents_refreshed',
        'all_17_pinned_parents_refreshed':True,
        'live_refreshed_at_utc':refreshed_at,
        'five_additional_case_summaries':[{
            'person':c['person'],'session':c['session'],
            'official_dip_parent_id':c['official_dip_parent_id'],
            'position_count':c['dip_parent_metadata_review']['position_count'],
            'other_step_review_hints':
                c['dip_parent_metadata_review']['other_step_review_hints'],
        } for c in five_live['cases']],
        'total_dip_parent_originals_covered':17,
        'total_dip_positions_in_17_parents':sum(
            a['position_count'] for a in all_assessments),
        'total_additional_position_review_hints':sum(
            a['other_step_review_hints'] for a in all_assessments),
        'all_additional_procedure_positions':categorized,
        'already_curated_vote_metadata_positions':sum(
            x['already_independently_curated_vote_metadata'] for x in categorized),
        'new_uncurated_procedure_position_hints':sum(
            x['needs_new_manual_source_review'] for x in categorized),
        'fully_reviewed_legal_effects':0,
        'automatically_approved_new_sanctions':0,
        'protected_public_counter_changes':0,
    }


def markdown(data):
    if (data['automatically_approved_new_sanctions']!=0
            or data['protected_public_counter_changes']!=0):
        raise ValueError('Automatisches Zählen nicht zulässig')
    lines=[
        '# WP21: 17 exakt zugeordnete amtliche DIP-Ursprungsvorgänge',
        '',
        'DIP-Auswahl vom '+data['snapshot_date']+
          ': 17 offene, **nicht bestätigte** Person-/Sitzungskombinationen, '
          'keine Vollerhebung der 21. WP.',
        '',
        '**Live-Status:** '+data['live_status'], '',
        '| Person / Sitzung | Exakter Ursprung | DIP-Metadatenpositionen | Rechtsfolgenstatus |',
        '|---|---|---:|---|',
    ]
    for c in data['twelve_cases']:
        meta=c.get('dip_parent_metadata_review')
        size=meta['position_count'] if meta else 'noch nicht live geprüft'
        lines.append(
            f"| {c['person']} / 21/{c['session']:03d} "
            f"| [DIP {c['official_dip_parent_id']}]({c['official_dip_parent_url']}) "
            f"| {size} | weiterer individueller Rechtsfolgenreview offen |")
    if data.get('five_additional_case_summaries'):
        for c in data['five_additional_case_summaries']:
            lines.append(f"| {c['person']} / 21/{c['session']:03d} "
                         f"| DIP {c['official_dip_parent_id']} "
                         f"| {c['position_count']} | aus separatem Fünfer-Livebericht; offen |")
    if data.get('all_17_pinned_parents_refreshed'):
        lines.extend([
            '',
            '**Zusatzpositionen insgesamt:** '+str(
                data['total_additional_position_review_hints']),
            '**Bereits quellengebunden kuratierte Einspruchsabstimmungs-Metadaten:** '+
                str(data['already_curated_vote_metadata_positions']),
            '**Noch nicht zugeordnete neue Verfahrenspositions-Hinweise:** '+
                str(data['new_uncurated_procedure_position_hints']),
            '**Diese Trennung ist kein Abschluss der individuellen Rechtsfolgenprüfung.**',
        ])
    lines.extend(['',data['warning'],'',
                  '**Nur Verfahrenspositionsmetadaten, keine Wirksamkeitsentscheidung.**',
                  '**Geschützte CSV-/JSON-Zähler bleiben unverändert.**',''])
    return '\n'.join(lines)


def save(report,path):
    path=Path(path).resolve();root=(ROOT/'.audit').resolve()
    if path!=root and root not in path.parents:
        raise ValueError('Ausgaben nur unter privatem .audit-Verzeichnis')
    path.mkdir(parents=True,exist_ok=True)
    files={
        'all17.json':json.dumps(report,ensure_ascii=False,indent=2)+'\n',
        'all17.md':markdown(report),
    }
    for name,value in files.items():
        dest=path/name
        tmp=dest.with_suffix(dest.suffix+'.tmp')
        tmp.write_text(value,encoding='utf-8')
        tmp.replace(dest)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--offline',action='store_true')
    p.add_argument('--five-live-report',type=Path)
    p.add_argument('--output-dir',type=Path,default=OUT)
    args=p.parse_args()
    baseline=sources()
    if args.offline:
        report=combine(baseline)
    else:
        if args.five_live_report is None:
            raise ValueError('Live-Zwölfer-Abgleich benötigt den Fünfer-Livebericht')
        five=json.loads(args.five_live_report.read_text(encoding='utf-8'))
        key=os.getenv('DIP_API_KEY') or PUBLIC_KEY
        if not key or '\n' in key or '\r' in key:
            raise ValueError('Ungültiger DIP-API-Schlüssel')
        result={}
        for c in baseline['twelve_cases']:
            ident=c['official_dip_parent_id']
            parent=official_parent(ident,key)
            positions=fetch_positions(ident,key)
            result[ident]=assess_dip(c,parent,positions)
            print('WP21_REMAINING_PARENT_PROBE:',ident,c['person'],
                  len(positions),'position(s), all legal effects open',flush=True)
        report=combine(baseline,result,five,
                       refreshed_at=datetime.now(timezone.utc).isoformat())
    save(report,args.output_dir)
    print('WP21_ALL17_DIP_REVIEW_PASS:',len(report['twelve_cases']),
          'other originals + 5 independent originals,',
          report['live_status'],'no automated sanctions.')
if __name__=='__main__':
    main()
