#!/usr/bin/env python3
"""Cross-reference uncounted DIP discovery with previously curated 2025 dossiers.

A shared official DIP parent ID, original sitting, date and full person name
provide a source-level match, not a newly approved effective Ordnungsruf.
DIP position counts cannot be equated with distinct grants (Janich/Gottschalk).
Outputs are strictly audit-only and never touch verified counter files.
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path

from wp21_18_dip_verfahrenspositionen import named
from wp21_2025_dip_einzelakten import CASES, verified_case_index
from wp21_2025_sieben_originalzeilen import LOCATIONS
from wp21_autopruefung import norm
from wp21_weitere_einspruchsberichte import validate as validated_appeals
from wp21_new_dip_candidates import AUDIT_ROOT

ROOT=Path(__file__).resolve().parent
BASE=ROOT/'.audit/wp21_dip_discovery'
SOURCE_NOTICE=(
    'Zehn bereits recherchierte 2025-DIP-Elternvorgänge sind keine zehn neuen '
    'Ordnungsrufe. Ihre zwölf ursprünglich berichteten Erteilungen und elf '
    'separat belegten Einspruchszurückweisungen sind keine zwölf abschließend '
    'rechtswirksamen Maßnahmen. Insbesondere Gottschalks zweiter Ruf, '
    'Janichs fehlende erste wörtliche Originalerteilung und getrennte '
    'Rechtsfolgen bleiben offen. Das Fehlen eines Vorgangs im Zehnerdossier '
    'beweist nicht, dass ihn keine andere Projektakte behandelt. '
    'Keine Änderung bestätigter Zähler.'
)


def crosswalk(discovery, queue, *, cases=CASES, appeals=None):
    if (not isinstance(discovery,dict)
            or discovery.get('schema')!='wp21-dip-outside-pins-discovery-v1'
            or discovery.get('original_position_enrichment_status')!=
               'all_possible_parents_positions_refreshed'
            or discovery.get('automatically_confirmed_new_sanctions')!=0
            or discovery.get('automatically_rescinded_sanctions')!=0
            or discovery.get('protected_counters_changed') is not False
            or not isinstance(queue,dict)
            or queue.get('schema')!='wp21-dip-unmatched-manual-review-queue-v1'
            or queue.get('automatic_counted_new_sanctions')!=0
            or queue.get('protected_ledgers_changed') is not False):
        raise ValueError('DIP-Discovery oder manuelle Queue nicht quellen-/zählersicher')
    # Curated source identity may not silently drift, even in mock tests.
    verified=verified_case_index()
    if tuple(cases)!=CASES or len(verified)!=10:
        raise ValueError('Unabhängiges Zehner-Originaldossier verändert')
    appeals=validated_appeals() if appeals is None else appeals
    if (len(appeals)!=13 or
            sum(e['original_date'].startswith('2025-') for e in appeals.values())!=11):
        raise ValueError('Individuelle amtliche Einspruchsquellen fehlen')
    originals=discovery.get('possible_originals_for_individual_review')
    if (not isinstance(originals,list)
            or len(originals)!=discovery.get('possible_original_parent_ids_outside_18_pins')):
        raise ValueError('Nicht alle neuen DIP-Ursprünge in der Discovery')
    pending=[c for batch in queue.get('batches',[]) for c in batch]
    if (len(pending)!=queue.get('pending_parent_review_tasks')
            or len(pending)!=discovery.get('candidates_without_positive_sample_original_match')
            or queue.get('source_since_utc')!=discovery.get('since_utc')
            or queue.get('source_full_term_update_window')!=
               discovery.get('full_legislative_period_update_window')
            or len({c['official_dip_parent_id'] for c in pending})!=len(pending)):
        raise ValueError('Fachliche Queue nicht identisch zur ursprünglichen Discovery')
    expected_pending={
        c['official_dip_parent_id'] for c in originals
        if not c['matched_dated_positive_sample_by_original_position']
    }
    if {c['official_dip_parent_id'] for c in pending}!=expected_pending:
        raise ValueError('DIP-Discovery-Queue enthält falsche oder fehlende Eltern-IDs')
    pinned={entry[2]:entry for entry in CASES}
    if len(pinned)!=10:
        raise ValueError('Doppelte kuratierte DIP-Eltern-ID')
    seen=set()
    prior=[]
    other=[]
    for case in originals:
        ident=case['official_dip_parent_id']
        if ident in seen or not re.fullmatch(r'[1-9]\d{0,11}', ident):
            raise ValueError('DIP-Elternakte ohne eindeutige ID')
        seen.add(ident)
        if ident not in expected_pending:
            continue
        origins=case['original_position_sources']
        followups=case['other_position_sources_needing_legal_review']
        if (not case['all_official_parent_positions_fetched']
                or len(origins)!=case['official_original_position_count']
                or len(origins)+len(followups)!=case['official_parent_position_count']
                or case['confirmed_additional_sanctions']!=0):
            raise ValueError('DIP-Original-/Verfahrenspositionen widersprüchlich')
        common={
            'official_dip_parent_id':ident,
            'official_parent_url':case['official_dip_parent_url'],
            'title':case['title'],
            'original_sources':origins,
            'other_procedure_position_sources':followups,
            'automatic_approved_measures':0,
            'all_later_legal_effects_individually_verified':False,
        }
        if ident in pinned:
            day,person,_,session,decision_session,grants,votes=pinned[ident]
            matched_origins=[
                p for p in origins if p['official_plenary_session']==session
                and p['date']==day and
                p['official_plenary_pdf_url'].startswith(
                    f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf#P.')
            ]
            if (not named(case['title'],person)
                    or len(origins)!=1 or len(matched_origins)!=1
                    or case.get('matched_dated_positive_sample_by_original_position')):
                raise ValueError('Zehner-Altakte: Person, Sitzungsdatum oder Originalfundstelle unpassend')
            matched_votes=[
                appeals.get((day,norm(person),ordinal))
                for ordinal in range(1,votes+1)
            ]
            if (any(e is None for e in matched_votes)
                    or len(matched_votes)!=votes
                    or any(e['original_session'] not in (None,session)
                           for e in matched_votes)
                    or any(e['decision_date'] not in {p['date'] for p in followups}
                           for e in matched_votes)):
                raise ValueError('Zehner-Altakte: unabhängige Einspruchsquelle fehlt')
            decision_dates={e['decision_date'] for e in matched_votes}
            official_votes=[
                p for p in followups
                if p['step']=='Abstimmung'
                and p['official_plenary_session']==decision_session
                and p['date'] in decision_dates
                and re.fullmatch(r'[1-9]\d{0,11}',p['official_position_id'])
            ]
            if (len(official_votes)<votes
                    or len({p['official_position_id'] for p in official_votes})
                        !=len(official_votes)):
                raise ValueError('Amtliche Einspruchspositionen nicht person-/sitzungsscharf')
            anchors=LOCATIONS.get((session,norm(person)))
            if bool(anchors)!=(session!=40):
                raise ValueError('Historische Original-XML-Anker nicht konsistent')
            source_detail=(
                'janich_first_original_spoken_line_still_unlocated'
                if person=='Steffen Janich' and session==40 else
                'gottschalk_second_appeal_outside_first_decision_unresolved'
                if person=='Kay Gottschalk' and session==40 else
                'individually_documented_2025_origin_and_objections'
            )
            prior.append({
                **common,
                'already_in_ten_case_2025_dossier':True,
                'original_sitting':session,
                'original_day':day,
                'full_name':person,
                'reported_initial_grants_from_independent_dossier':grants,
                'source_grant_dip_position_count':len(origins),
                'independently_documented_rejected_objections':votes,
                'decision_sitting':decision_session,
                'matched_appeal_vote_dip_position_ids':[
                    p['official_position_id'] for p in official_votes],
                'vote_positions_do_not_imply_ordinal_mapping_without_abstract':True,
                'official_objection_reports':[
                    {'individual_objection_ordinal':e['individual_objection_ordinal'],
                     'decision_date':e['decision_date'],'source':e['source'],
                     'not_an_original_grant':True} for e in matched_votes
                ],
                'original_xml_line_from_seven_case_dossier':
                    anchors[0] if anchors else None,
                'original_xml_status':source_detail,
                'possible_additional_still_effective_measures_inferred':0,
            })
        else:
            special=(
                'multiple_official_grant_steps_do_not_prove_distinct_effective_calls'
                if len(origins)>1 else
                'no_official_original_step_requires_manual_source_research'
                if not origins else
                'original_pdf_known_without_independent_final_effect_review'
            )
            other.append({
                **common,
                'already_in_ten_case_2025_dossier':False,
                'review_priority':(
                    'hoch' if len(origins)!=1 or followups else 'mittel'),
                'remaining_source_problem':special,
                'possibly_in_other_existing_project_dossiers':True,
                'newly_approved_sanctions':0,
            })
    # Identical recipient-title, original sitting and day can still be
    # TWO official DIP parents. Never silently deduplicate them or assume
    # either one is a separate effective sanction without the original words.
    by_context={}
    for c in other:
        if c['original_sources']:
            p=c['original_sources'][0]
            token=(p['official_plenary_session'],p['date'],norm(c['title']))
            by_context.setdefault(token,[]).append(c)
    collisions=[]
    for (session,day,title),group in by_context.items():
        if len(group)<2:
            continue
        ids=sorted((x['official_dip_parent_id'] for x in group),key=int)
        collisions.append({
            'official_original_session':session,
            'original_day':day,
            'same_normalized_parent_title':title,
            'distinct_official_parent_ids':ids,
            'independent_original_grants_verified_from_this_overlap':False,
        })
        for c in group:
            c['other_dip_parents_same_original_context']=[
                ident for ident in ids if ident!=c['official_dip_parent_id']]
            c['review_priority']='hoch'
            c['collision_requires_separate_original_xml_issuance_review']=True
    for c in other:
        c.setdefault('other_dip_parents_same_original_context',[])
        c.setdefault('collision_requires_separate_original_xml_issuance_review',False)
    collisions.sort(key=lambda row:(row['official_original_session'],row['original_day']))
    if len({p['official_position_id'] for c in prior+other
            for p in c['original_sources']})!=sum(len(c['original_sources'])
                                                     for c in prior+other):
        raise ValueError('Doppelte amtliche Original-DIP-Position zwischen Elternakten')
    prior.sort(key=lambda c:(c['original_day'], c['official_dip_parent_id']))
    other.sort(key=lambda c:(
        0 if c['review_priority']=='hoch' else 1,
        int(c['official_dip_parent_id'])))
    if (len(prior)+len(other)!=len(expected_pending)
            or sum(c['reported_initial_grants_from_independent_dossier'] for c in prior)
               !=sum(pinned[c['official_dip_parent_id']][5] for c in prior)
            or any(c['automatic_approved_measures']!=0 for c in prior+other)):
        raise ValueError('DIP-Altakte und offener Forschungsbestand unvollständig')
    return {
        'schema':'wp21-2025-dip-dossier-overlap-v1',
        'since_utc':discovery['since_utc'],
        'full_term_filter':discovery['full_legislative_period_update_window'],
        'all_unmatched_dip_parent_tasks':len(expected_pending),
        'previously_curated_ten_parent_dossier_matches':len(prior),
        'remaining_outside_ten_parent_dossier_tasks':len(other),
        'independently_reported_initial_grants_in_matched_dossiers':
            sum(x['reported_initial_grants_from_independent_dossier'] for x in prior),
        'independently_reported_rejected_appeals_in_matched_dossiers':
            sum(x['independently_documented_rejected_objections'] for x in prior),
        'possible_cross_parent_original_context_collisions':collisions,
        'parents_needing_collision_review':sum(
            bool(c['other_dip_parents_same_original_context']) for c in other),
        'special_prior_cases_still_open':[
            c['official_dip_parent_id'] for c in prior
            if c['original_xml_status']!=
               'individually_documented_2025_origin_and_objections'
        ],
        'previously_curated_parent_cases':prior,
        'remaining_parent_cases_for_individual_review':other,
        'automatically_confirmed_new_measures':0,
        'automatically_rescinded_measures':0,
        'protected_counter_changes':0,
        'warning':SOURCE_NOTICE,
    }


def markdown(report):
    if (report['automatically_confirmed_new_measures']!=0
            or report['automatically_rescinded_measures']!=0
            or report['protected_counter_changes']!=0):
        raise ValueError('Zähleränderung in Quellenabgleich verboten')
    lines=[
        '# WP21: Quellen-Deduplikation zu 2025er Einzelfallakten','',
        '**Keine automatische Bestätigung von Ordnungsrufen oder Einspruchsfreiheit.**','',
        'DIP-Aktualisierungsfenster seit '+report['since_utc'],
        'Vorher kuratiertes Zehnerdossier: '+
        str(report['previously_curated_ten_parent_dossier_matches']),
        'Andere Elternvorgänge mit Recherchebedarf: '+
        str(report['remaining_outside_ten_parent_dossier_tasks']),'',
        '## Im bereits dokumentierten Zehnerdossier','',
        '| Amtlicher DIP-Vorgang | Ursprung | Originalberichte | Einspruchsbelege | Restproblem |',
        '|---|---|---:|---:|---|',
    ]
    for c in report['previously_curated_parent_cases']:
        lines.append(
            '| ['+c['official_dip_parent_id']+']('+c['official_parent_url']+
            ') | '+c['full_name']+' 21/'+f"{c['original_sitting']:03d}"+
            ' | '+str(c['reported_initial_grants_from_independent_dossier'])+
            ' | '+str(c['independently_documented_rejected_objections'])+
            ' | '+c['original_xml_status']+' |')
    lines.extend(['','## Noch nicht diesem Zehnerdossier zugeordnet','',
                  '| Amtliche DIP-Akte | Originalfundstellen | Zusätzliche Verfahrensschritte | Prüfung |',
                  '|---|---:|---:|---|'])
    for c in report['remaining_parent_cases_for_individual_review']:
        lines.append(
            '| ['+c['official_dip_parent_id']+']('+c['official_parent_url']+
            ') | '+str(len(c['original_sources']))+
            ' | '+str(len(c['other_procedure_position_sources']))+
            ' | '+c['remaining_source_problem']+' |')
    if report['possible_cross_parent_original_context_collisions']:
        lines.extend(['','## Getrennte DIP-Eltern mit gleichem Originalkontext',
                      '**Nicht automatisch zusammenfassen oder doppelt zählen.**',''])
        for collision in report['possible_cross_parent_original_context_collisions']:
            ids=', '.join('[DIP '+ident+'](https://dip.bundestag.de/vorgang/'+ident+')'
                          for ident in collision['distinct_official_parent_ids'])
            lines.append('- Sitzung 21/'+str(collision['official_original_session'])+
                         ', '+collision['original_day']+': '+ids+
                         ' – unabhängige Originalerteilungen im XML manuell abgrenzen')
    lines.extend(['',report['warning'],'',
                  '**Ausschließlich Forschungsdossier, keine Änderung an bestätigten CSV/JSON.**',''])
    return '\n'.join(lines)



def next_review_queue(report, batch_size=5):
    """Batch only parents *outside* the ten already individually documented."""
    if (report.get('schema')!='wp21-2025-dip-dossier-overlap-v1'
            or report.get('automatically_confirmed_new_measures')!=0
            or report.get('protected_counter_changes')!=0
            or type(batch_size) is not int or not 1<=batch_size<=10):
        raise ValueError('DIP-Forschungsqueue kann keine Zähler freigeben')
    rows=report['remaining_parent_cases_for_individual_review']
    if len(rows)!=report['remaining_outside_ten_parent_dossier_tasks']:
        raise ValueError('Andere Eltern-DIP-Fälle fehlen')
    tasks=[]
    for c in rows:
        tasks.append({
            'official_dip_parent_id':c['official_dip_parent_id'],
            'official_parent_url':c['official_parent_url'],
            'original_sources':c['original_sources'],
            'later_position_sources':c['other_procedure_position_sources'],
            'priority':c['review_priority'],
            'cross_parent_context_ids':c['other_dip_parents_same_original_context'],
            'known_ten_parent_2025_dossier_already_reviewed':False,
            'next_individual_checklist':[
                'Amtlichen Originalwortlaut und Adressat im Original-XML/PDF individuell prüfen',
                'Bei mehrfachen DIP-Positionen oder gleicher Person/Sitzung andere Elternakten abgrenzen',
                'Frühere Einzelakten, Einsprüche, spätere Beschlüsse und Rücknahmen separat abgleichen',
                'Keine rechtswirksame Maßnahme ohne eigenständige Quellen- und Rechtsfolgenfreigabe zählen',
            ],
            'automatically_approved_measures':0,
        })
    tasks.sort(key=lambda c:(0 if c['priority']=='hoch' else 1,
                             int(c['official_dip_parent_id'])))
    return {
        'schema':'wp21-2025-after-dossier-noncounting-queue-v1',
        'source_since_utc':report['since_utc'],
        'total_parent_tasks':len(tasks),
        'high_priority_parent_tasks':sum(c['priority']=='hoch' for c in tasks),
        'batch_size':batch_size,
        'batches':[tasks[i:i+batch_size] for i in range(0,len(tasks),batch_size)],
        'previous_ten_parent_dossiers_are_not_repeated_as_new_tasks':True,
        'automatic_counter_change':0,
        'warning':SOURCE_NOTICE,
    }


def next_review_markdown(report):
    if (report['automatic_counter_change']!=0 or
            not report['previous_ten_parent_dossiers_are_not_repeated_as_new_tasks']):
        raise ValueError('Zähleränderung und doppelte Neuaufgabe verboten')
    lines=['# WP21: nur verbleibende Eltern-DIP-Rechercheaufgaben', '',
           '**Keine amtlich abschließend bestätigten neuen Maßnahmen.**', '',
           'Noch nicht im Zehnerdossier: '+str(report['total_parent_tasks'])+
           '; davon hohe Priorität: '+str(report['high_priority_parent_tasks']), '']
    for idx,batch in enumerate(report['batches'],start=1):
        lines.append('## Arbeitsbündel '+str(idx))
        for c in batch:
            lines.append('- **'+c['priority']+'** [DIP '+c['official_dip_parent_id']+
                         ']('+c['official_parent_url']+')')
            for p in c['original_sources']:
                lines.append('  - [Original-Protokollquelle '+p['official_position_id']+
                             ']('+p['official_plenary_pdf_url']+')')
            if c['cross_parent_context_ids']:
                lines.append('  - **Gleicher Originalkontext mit Eltern-ID(s):** '+
                             ', '.join(c['cross_parent_context_ids'])+
                             '; eigenständige Erteilungen nicht automatisch behaupten')
            for action in c['next_individual_checklist']:
                lines.append('  - [ ] '+action)
        lines.append('')
    lines.extend([report['warning'],'', '**Zählerdaten unverändert.**',''])
    return '\n'.join(lines)

def run(discovery_file,queue_file,output_dir):
    folder=Path(output_dir).resolve()
    root=AUDIT_ROOT.resolve()
    if folder==root or root not in folder.parents or folder.is_symlink():
        raise ValueError('Abgleich nur in eigenem .audit-Unterverzeichnis')
    discovery=json.loads(Path(discovery_file).read_text(encoding='utf-8'))
    queue=json.loads(Path(queue_file).read_text(encoding='utf-8'))
    report=crosswalk(discovery,queue)
    folder.mkdir(parents=True,exist_ok=True)
    queue=next_review_queue(report)
    targets={
        'dossier_overlap.json':json.dumps(report,ensure_ascii=False,indent=2)+'\n',
        'dossier_overlap.md':markdown(report),
        'next_review_queue.json':json.dumps(queue,ensure_ascii=False,indent=2)+'\n',
        'next_review_queue.md':next_review_markdown(queue),
    }
    for name,payload in targets.items():
        temporary=folder/(name+'.tmp')
        temporary.write_text(payload,encoding='utf-8')
        temporary.replace(folder/name)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discovery',type=Path,default=BASE/'outside_pins.json')
    parser.add_argument('--review-queue',type=Path,default=BASE/'review_queue.json')
    parser.add_argument('--output-dir',type=Path,default=BASE/'existing_2025_dossiers')
    args=parser.parse_args()
    report=run(args.discovery,args.review_queue,args.output_dir)
    print('WP21 Quelldossier-Overlap:',
          report['previously_curated_ten_parent_dossier_matches'],
          'vorherige Elternakten,',
          report['remaining_outside_ten_parent_dossier_tasks'],
          'weitere DIP-Elternaufgaben; keine Zähleränderung.')


if __name__=='__main__':
    main()
