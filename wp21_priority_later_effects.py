#!/usr/bin/env python3
"""Pinned, read-only legal-followup survey for Reichardt and Keuter sources.

Three official parent IDs have four original DIP positions but no individual
legal effectiveness is inferred. Check all positions within those parents,
then screen the *dated, bounded* candidate-parent inventory for other metadata.
An unmatched term, unrelated same-person proceeding, or missing appeal in
these bounded sources is NEVER evidence that no later remedy exists.
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from wp21_autopruefung import norm
from wp21_dip_monitor import PUBLIC_KEY
from wp21_dip_positionen import fetch_positions, normalize_position
from wp21_five_rechtsfolgen import official_parent
from wp21_new_dip_candidates import AUDIT_ROOT
from wp21_priority_xml_verify import verify as verify_original_xml
from wp21_weitere_einspruchsberichte import validate as validated_objections, OTHER_MEASURE
from wp21_einspruchsbelege import validated_index as validated_high_priority

ROOT=Path(__file__).resolve().parent
EXPECTED={
    '322921':{
        'original_date':'2025-06-26','original_session':14,
        'displayed_person':'Martin Reichardt',
        'original_recipient_from_plenary':'Stefan Keuter',
        'original_position_pages':{'672193':1221},
        'original_source_verification':'keuter_clarification_xml_5705',
        'metadata_recipient_conflict':True,
    },
    '322922':{
        'original_date':'2025-06-26','original_session':14,
        'displayed_person':'Martin Reichardt',
        'original_recipient_from_plenary':'Martin Reichardt',
        'original_position_pages':{'672194':1133},
        'original_source_verification':'reichardt_issuance_xml_2311',
        'metadata_recipient_conflict':False,
    },
    '328596':{
        'original_date':'2025-11-26','original_session':43,
        'displayed_person':'Stefan Keuter',
        'original_recipient_from_plenary':'Stefan Keuter',
        'original_position_pages':{'681904':4996,'682732':5015},
        'original_source_verification':'keuter_grants_xml_2405_and_3495',
        'metadata_recipient_conflict':False,
    },
}
WARNING=(
    'Die drei amtlichen DIP-Elternvorgänge und ihr vollständiger aktueller '
    'Verfahrenspositionsstand erfassen NICHT automatisch alle anderen '
    'Einspruchsvorgänge, späteren Plenarentscheidungen, Rücknahmen oder '
    'gerichtlichen Rechtsfolgen. Ein aktuell fehlender weiterer '
    'Verfahrensschritt ist kein Nachweis eines unangefochtenen oder '
    'fortbestehenden Ordnungsrufs. Reichardt- und Keuter-Namensgleichheit '
    'in fremden Elternvorgängen verknüpft diese Fälle nicht. '
    'Zwei Keuter-Originalpositionen werden nicht automatisch zwei '
    'abschließend wirksamen Sanktionen. Keine Zähleränderung.'
)
NAME_RE={
    name:re.compile(r'(?<!\w)'+re.escape(norm(name))+r'(?!\w)')
    for name in ('Martin Reichardt','Stefan Keuter')
}
LEGAL_SIGNAL=re.compile(r'\b(?:einspruch\w*|widerspruch\w*|zur[uü]ck\w*|'
                        r'aufheb\w*|widerruf\w*|stattgegeben\w*|anfecht\w*)',re.I)
DIFFERENT_SANCTION=re.compile(r'\b(?:ordnungsgeld\w*|sitzungsausschluss\w*)',re.I)


def original_role_consistent(originals):
    """Bind the actual spoken evidence, including the false Reichardt title."""
    report=verify_original_xml(originals)
    loci={(p['session'],p['xml_line']) for p in report['source_utterance_loci']}
    if (loci!={(14,2311),(43,2405),(43,3495)}
            or report['automatic_verified_sanction_count_delta']!=0
            or report['protected_statistical_ledgers_changed'] is not False
            or len(report['sources_with_explicit_identified_recipient_not_reichardt'])!=1
            or report['sources_with_explicit_identified_recipient_not_reichardt'][0]
               ['parent_id']!='322921'):
        raise ValueError('Unabhängige Original-XML-Identitätskontrolle fehlt')
    return report


def inspect_parent(ident,parent,positions):
    """Validate complete current steps for one exact official parent."""
    if ident not in EXPECTED or not isinstance(parent,dict) or not isinstance(positions,list):
        raise ValueError('Nicht verankerter oder unvollständiger DIP-Elternvorgang')
    expected=EXPECTED[ident]
    if (str(parent.get('id'))!=ident or parent.get('wahlperiode')!=21
            or len(positions)<len(expected['original_position_pages'])
            or len(positions)>50):
        raise ValueError('Amtliche DIP-Eltern-/Positionsabfrage unvollständig')
    title=parent.get('titel')
    if (not isinstance(title,str) or 'ordnungsruf' not in title.casefold()
            or not NAME_RE[expected['displayed_person']].search(norm(title))):
        raise ValueError('DIP-Titel oder Elternidentität unerwartet verändert')
    seen=set();originals=[];later=[]
    for raw in positions:
        if not isinstance(raw,dict):
            raise ValueError('Amtliche DIP-Position ohne Rohdaten')
        p=normalize_position(raw)
        if p['parent_id']!=ident or p['id'] in seen:
            raise ValueError('Position gehört zu fremdem Elternvorgang oder ist doppelt')
        seen.add(p['id'])
        position={
            'official_position_id':p['id'],
            'source_url':'https://search.dip.bundestag.de/api/v1/vorgangsposition/'+p['id'],
            'date':p['date'],
            'step':p['step'],
            'title':p['title'],
            'official_plenary_session':p['official_plenary_session'],
            'official_plenary_pdf':p['official_plenary_pdf_url'],
            'updated_utc':p['updated'],
            'legal_signal_fields':p['signal_fields'],
            'official_decision_tenors_metadata_only':p['official_decision_tenors'],
            'official_abstract_excerpt':p['official_position_abstract_excerpt'],
            'source_cannot_confirm_final_legal_effect':True,
            'newly_confirmed_effective_sanctions':0,
        }
        if p['id'] in expected['original_position_pages']:
            page=expected['original_position_pages'][p['id']]
            pdf=(f'https://dserver.bundestag.de/btp/21/'
                 f'21{expected["original_session"]:03d}.pdf#P.{page}')
            if (p['step'].strip().casefold()!='ordnungsruf'
                    or p['official_plenary_chamber']!='Bundestag'
                    or p['date']!=expected['original_date']
                    or p['official_plenary_session']!=expected['original_session']
                    or p['official_plenary_pdf_url']!=pdf
                    or p['official_plenary_xml_url']!=
                    f'https://dserver.bundestag.de/btp/21/21{expected["original_session"]:03d}.xml'):
                raise ValueError('Amtliche Originalposition wurde verschoben oder verwechselt')
            position['source_class']='pinned_original_metadata_not_individual_legal_effect'
            originals.append(position)
        else:
            position['source_class']=(
                'possible_appeal_or_later_legal_effect_metadata'
                if p['signal_fields'] or p['step'].strip().casefold()=='abstimmung'
                else 'other_parent_procedure_step_needs_manual_review'
            )
            later.append(position)
    if {r['official_position_id'] for r in originals}!=set(expected['original_position_pages']):
        raise ValueError('Nicht alle amtlichen Ursprungsschritte dieses DIP-Vorgangs')
    originals.sort(key=lambda c:int(c['official_position_id']))
    later.sort(key=lambda c:int(c['official_position_id']))
    return {
        'official_dip_parent_id':ident,
        'official_dip_parent_url':'https://dip.bundestag.de/vorgang/'+ident,
        'displayed_dip_title':title,
        'displayed_dip_person_metadata_only':expected['displayed_person'],
        'original_recipient_from_official_plenary':expected['original_recipient_from_plenary'],
        'parent_title_recipient_conflicts_with_spoken_original':
            expected['metadata_recipient_conflict'],
        'original_day':expected['original_date'],
        'original_sitting':expected['original_session'],
        'original_spoken_source_qualification':expected['original_source_verification'],
        'all_parent_positions_fetched':True,
        'original_dip_position_count':len(originals),
        'additional_parent_procedure_position_count':len(later),
        'original_positions':originals,
        'later_parent_positions_for_individual_review':later,
        'no_later_position_in_this_parent_proves_absence_of_appeal':False,
        'all_possible_other_legal_proceedings_checked':False,
        'legal_effect_of_each_grant_conclusively_verified':False,
        'automatic_approved_effective_sanctions':0,
    }


def bounded_other_parent_hints(discovery):
    """Screen already fully paged DIP review inventory; no claimed source linkage.

    The inventory itself contains only relevant metadata outside a fixed
    pre-existing set of 18 parent IDs, within its declared update window.
    """
    if (not isinstance(discovery,dict)
            or discovery.get('schema')!='wp21-dip-outside-pins-discovery-v1'
            or discovery.get('status')!='source_discovery_only_no_effectiveness_decision'
            or discovery.get('automatically_confirmed_new_sanctions')!=0
            or discovery.get('protected_counters_changed') is not False
            or discovery.get('api_pages_completely_fetched',0)<1):
        raise ValueError('Unvollständiges oder zählerveränderndes DIP-Quellenfenster')
    hits=[];seen=set()
    candidates=(discovery['possible_originals_for_individual_review']+
                discovery['other_metadata_for_individual_review'])
    if (len(candidates)!=(discovery['possible_original_parent_ids_outside_18_pins']+
                          discovery['other_relevant_parent_ids_outside_18_pins'])):
        raise ValueError('DIP-Metadatenübersicht widersprüchlich')
    for row in candidates:
        ident=row['official_dip_parent_id']
        if ident in seen or not re.fullmatch(r'[1-9]\d{0,11}',ident):
            raise ValueError('Doppelte oder ungültige Quellen-ID')
        seen.add(ident)
        if ident in EXPECTED:
            continue
        title=row['title']
        named=[name for name,rx in NAME_RE.items() if rx.search(norm(title))]
        if not named:
            continue
        kind=('distinct_sanction_type_not_an_ordnungsruf_appeal'
              if DIFFERENT_SANCTION.search(title) else
              'procedure_keyword_possible_related_metadata'
              if LEGAL_SIGNAL.search(title) else
              'same_name_different_or_unlinked_original_metadata')
        hits.append({
            'official_parent_id':ident,
            'source':row['official_dip_parent_url'],
            'source_date':row['source_date'],
            'title':title,
            'named_person_metadata_only':named,
            'source_class':kind,
            'exact_original_case_link_verified':False,
            'appeal_outcome_or_current_effectiveness_verified':False,
            'automatically_confirmed_sanctions':0,
        })
    # This second stream scans the complete already-fetched DIP result set,
    # including documents where neither title nor abstract says Ordnungsruf.
    # It is still only a full-name + procedural-keyword hint.
    shadow=discovery.get('unfiltered_priority_procedure_parents',[])
    if (not isinstance(shadow,list) or len(shadow)>500 or
            len(shadow)!=discovery.get('unfiltered_priority_procedure_parent_count',len(shadow))):
        raise ValueError('Ungefilterte DIP-Rechtsfolgenquelle unvollständig')
    shadow_hits=0
    for row in shadow:
        ident=row['official_dip_parent_id']
        title=row['title']
        names=row['matched_full_person_names_metadata_only']
        if (ident in seen or not re.fullmatch(r'[1-9]\d{0,11}',ident)
                or ident in EXPECTED or
                row['official_dip_parent_url']!='https://dip.bundestag.de/vorgang/'+ident
                or not isinstance(title,str) or not isinstance(names,list)
                or not names or not set(names)<=set(NAME_RE)
                or not all(NAME_RE[name].search(norm(title+' '+row['abstract_excerpt']))
                           for name in names)
                or row['matched_procedural_text_not_full_legal_decision'] is not True
                or row['ordnungsruf_keyword_present_in_title_or_abstract'] is not False
                or row['original_measure_identity_verified'] is not False
                or row['appeal_or_legal_outcome_decided'] is not False
                or row['automatically_approved_effective_sanctions']!=0):
            raise ValueError('Ungefilterte fremde DIP-Quelle ohne sichere Prüfgrenze')
        seen.add(ident)
        shadow_hits+=1
        hits.append({
            'official_parent_id':ident,
            'source':row['official_dip_parent_url'],
            'source_date':row['source_date'],
            'title':title,
            'named_person_metadata_only':names,
            'source_class':'other_dip_parent_possible_procedure_without_ordnungsruf_keyword',
            'exact_original_case_link_verified':False,
            'appeal_outcome_or_current_effectiveness_verified':False,
            'automatically_confirmed_sanctions':0,
        })
    hits.sort(key=lambda x:int(x['official_parent_id']))
    return {
        'unfiltered_legal_shadow_evaluated':(
            'unfiltered_priority_procedure_parents' in discovery),
        'unfiltered_procedure_keyword_parent_hints':shadow_hits,
        'update_window_since_utc':discovery['since_utc'],
        'update_window_until_utc':discovery['observed_until_utc'],
        'full_term_update_filter_used':discovery['full_legislative_period_update_window'],
        'source_scope':'bounded_keyword_filtered_DIP_parents_excluding_existing_18_pins',
        'named_other_parent_metadata_candidates':hits,
        'matched_to_any_of_four_individual_grants_automatically':0,
        'absence_of_other_relevant_sources_proven':False,
    }


def historical_appeal_exclusions():
    appeals=validated_objections()
    high=validated_high_priority()
    if (len(appeals)!=13 or len(high)!=4
            or OTHER_MEASURE.get('sanction_type')!='ordnungsgeld'
            or OTHER_MEASURE.get('person')!='Martin Reichardt'):
        raise ValueError('Kuratierte Einspruchs-/Ordnungsgeld-Quellen nicht ausreichend')
    historical=[]
    expected_originals={
        ('2025-06-26',norm('Martin Reichardt')),
        ('2025-06-26',norm('Stefan Keuter')),
        ('2025-11-26',norm('Stefan Keuter')),
    }
    for row in appeals.values():
        if norm(row['person']) not in {norm('Martin Reichardt'),norm('Stefan Keuter')}:
            continue
        if (row['original_date'],norm(row['person'])) in expected_originals:
            raise ValueError('Neuer exakter Einspruch: manuelle Neuprüfung erforderlich')
        historical.append({
            'person':row['person'],
            'different_original_day':row['original_date'],
            'independent_official_bundestag_article':row['source'],
            'original_cannot_be_one_of_three_checked_parents':True,
        })
    for (session,person),entry in high.items():
        if person not in {norm('Martin Reichardt'),norm('Stefan Keuter')}:
            continue
        historical.append({
            'person':entry['person'],
            'different_original_day':None,
            'different_original_session':session,
            'independent_official_bundestag_article':entry['source'],
            'original_cannot_be_one_of_three_checked_parents':True,
        })
    historical.sort(key=lambda x:(x['person'],x.get('different_original_day') or ''))
    return {
        'known_official_objections_to_other_originals_excluded':historical,
        'separately_curated_reichardt_ordnungsGELD_negative_control':{
            **OTHER_MEASURE,
            'not_an_ordnungsruf':True,
            'not_reassigned_to_any_priority_original':True,
        },
        'no_bounded_objection_match_proves_no_appeal':False,
    }


def consolidate(pinned,original_scout,discovery):
    if (not isinstance(pinned,dict) or set(pinned)!=set(EXPECTED)):
        raise ValueError('Eine der drei priorisierten DIP-Elternakten fehlt')
    verified=original_role_consistent(original_scout)
    summary=bounded_other_parent_hints(discovery)
    historical=historical_appeal_exclusions()
    for ident,doc in pinned.items():
        expected=EXPECTED[ident]
        if (doc['official_dip_parent_id']!=ident
                or doc['original_dip_position_count']!=len(expected['original_position_pages'])
                or not doc['all_parent_positions_fetched']
                or doc['automatic_approved_effective_sanctions']!=0
                or doc['legal_effect_of_each_grant_conclusively_verified'] is not False):
            raise ValueError('Amtliche Fallmatrix nicht vollständig oder statusverändert')
    rows=[pinned[ident] for ident in sorted(EXPECTED,key=int)]
    if sum(x['original_dip_position_count'] for x in rows)!=4:
        raise ValueError('Ursprungs-Positionen über drei Eltern verwechselt')
    return {
        'schema':'wp21-2025-three-priority-legal-followups-v1',
        'status':'three_pinned_parents_refreshed_other_source_window_review_only',
        'official_parents_refreshed':3,
        'official_original_position_refs':4,
        'individually_spoken_source_loci_previously_checked':
            verified['source_utterances_located_for_individual_review'],
        'person_conflict_reichardt_title_vs_keuter_original':
            rows[0]['parent_title_recipient_conflicts_with_spoken_original'],
        'all_three_parent_position_lists_complete':True,
        'pinned_parent_cases':rows,
        'possible_other_parent_sources':summary,
        'independent_existing_articles':historical,
        'no_additional_parent_position_is_not_proof_of_no_appeal':True,
        'no_complete_cross_document_legal_exhaustiveness_claim':True,
        'effectiveness_of_any_individual_grant_automatically_proven':False,
        'automatically_approved_new_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'protected_counter_files_modified':False,
        'warning':WARNING,
    }


def render(report):
    if (report.get('schema')!='wp21-2025-three-priority-legal-followups-v1'
            or report.get('automatically_approved_new_sanctions')!=0
            or report.get('automatically_rescinded_sanctions')!=0
            or report.get('protected_counter_files_modified') is not False):
        raise ValueError('Unerlaubter Rechtsfolgen-Zählschritt')
    lines=['# WP21: getrennte Rechtsfolgen-Prüfung Reichardt / Keuter','',
           '**Null automatisch bestätigte oder aberkannte Maßnahmen.**','',
           'Die drei Elternvorgänge haben in sich vollständig abgefragte '
           'DIP-Verfahrenspositionen. Andere Verfahrensvorgänge und '
           'gerichtliche Rechtsfolgen sind davon nicht vollständig erfasst.','',
           '| Elternvorgang | Amtlicher ursprünglicher Empfänger | Ursprungsschritte '
           '| Weitere Schritte im Elternvorgang |','|---|---|---:|---:|']
    for c in report['pinned_parent_cases']:
        lines.append(
            '| [DIP '+c['official_dip_parent_id']+']('+
            c['official_dip_parent_url']+') | '+
            c['original_recipient_from_official_plenary']+' | '+
            str(c['original_dip_position_count'])+' | '+
            str(c['additional_parent_procedure_position_count'])+' |')
        for extra in c['later_parent_positions_for_individual_review']:
            lines.append('- Zusätzliche [amtliche DIP-Position '+extra['official_position_id']+
                         ']('+extra['source_url']+'): '+extra['source_class']+
                         ' – **keine automatische Entscheidung**.')
    lines.extend(['','## Namensgleiche andere DIP-Eltern außerhalb der drei Fälle','',
                  'Aktualisierungsfilter: '+
                  report['possible_other_parent_sources']['update_window_since_utc']+
                  ' bis '+report['possible_other_parent_sources']['update_window_until_utc'],
                  'Vollzeitraum-Filter: '+
                  str(report['possible_other_parent_sources']['full_term_update_filter_used']),''])
    for hint in report['possible_other_parent_sources']['named_other_parent_metadata_candidates']:
        lines.append('- [DIP '+hint['official_parent_id']+']('+hint['source']+') – '+
                     hint['source_class']+' – '+hint['title'])
    lines.append('')
    lines.append('Zusätzliche **ohne Ordnungsruf-Wort** gefundene potentielle '
                 'Verfahrensquellen im gesamten DIP-Suchergebnis: '+
                 str(report['possible_other_parent_sources'][
                     'unfiltered_procedure_keyword_parent_hints'])+
                 ' – **ohne fallbezogene Rechtsfolgenzuordnung**.')
    lines.append('')
    lines.append('**Selbst der vollständige DIP-Zeitraum ersetzt keine '
                 'personen- und maßnahmenbezogene Prüfung anderer Verfahren.**')
    lines.extend(['','## Unabhängig belegte Einsprüche zu ANDEREN Originalen',''])
    for x in report['independent_existing_articles'][
            'known_official_objections_to_other_originals_excluded']:
        lines.append('- '+x['person']+' – '+
                     str(x.get('different_original_day') or
                         'anderer Ursprungssitzung '+str(x.get('different_original_session'))) +
                     ': '+x['independent_official_bundestag_article'])
    lines.extend(['','Das separate Ordnungsgeld Reichardt vom 15.10.2026 '
                  'ist **kein Ordnungsruf**.','',report['warning'],''])
    return '\n'.join(lines)



def review_alerts(report):
    """Only new official metadata for manual issue notices after approved merge.

    No occurrence/absence of an appeal is decided by this classifier.
    """
    if (not isinstance(report,dict)
            or report.get('schema')!='wp21-2025-three-priority-legal-followups-v1'
            or report.get('automatically_approved_new_sanctions')!=0
            or report.get('automatically_rescinded_sanctions')!=0
            or report.get('protected_counter_files_modified') is not False
            or report.get('official_parents_refreshed')!=3):
        raise ValueError('Quelle für GitHub-Reviewmeldung unzureichend')
    hints=[];seen=set()
    for case in report['pinned_parent_cases']:
        parent=case['official_dip_parent_id']
        if parent not in EXPECTED or not case['all_parent_positions_fetched']:
            raise ValueError('DIP-Elternaktensicherung vor Alerts fehlt')
        for step in case['later_parent_positions_for_individual_review']:
            ident=step['official_position_id']
            key=('position',ident)
            if (key in seen or
                    not re.fullmatch(r'[1-9]\d{0,11}',ident) or
                    step['source_url']!=
                    'https://search.dip.bundestag.de/api/v1/vorgangsposition/'+ident or
                    step['source_cannot_confirm_final_legal_effect'] is not True or
                    step['newly_confirmed_effective_sanctions']!=0):
                raise ValueError('Unzulässige DIP-Reviewposition in Quellenalarm')
            seen.add(key)
            hints.append({
                'kind':'new_parent_procedure_position',
                'official_parent_id':parent,
                'official_position_id':ident,
                'source_url':step['source_url'],
                'source_date':step['date'],
                'label':step['source_class'],
                'case_link_and_legal_outcome_still_require_manual_review':True,
                'automatic_count_delta':0,
            })
    for item in report['possible_other_parent_sources'][
            'named_other_parent_metadata_candidates']:
        # Do NOT turn an unrelated grant or separately regulated fine into
        # an appeal alert. Even a literal "Einspruch" with the same name is
        # only a source candidate, not necessarily the same original grant.
        if item['source_class'] not in (
                'procedure_keyword_possible_related_metadata',
                'other_dip_parent_possible_procedure_without_ordnungsruf_keyword'):
            continue
        ident=item['official_parent_id']
        key=('parent',ident)
        if (key in seen or ident in EXPECTED or
                not re.fullmatch(r'[1-9]\d{0,11}',ident) or
                item['source']!='https://dip.bundestag.de/vorgang/'+ident or
                item['exact_original_case_link_verified'] is not False or
                item['appeal_outcome_or_current_effectiveness_verified'] is not False):
            raise ValueError('Fremdvorgang ohne sichere negative Quellenabgrenzung')
        seen.add(key)
        hints.append({
            'kind':'other_parent_name_and_procedure_keyword_only',
            'official_parent_id':ident,
            'official_position_id':None,
            'source_url':item['source'],
            'source_date':item['source_date'],
            'label':item['title'],
            'case_link_and_legal_outcome_still_require_manual_review':True,
            'automatic_count_delta':0,
        })
    hints.sort(key=lambda x:(x['kind'],int(x['official_parent_id']),
                             int(x['official_position_id'] or 0)))
    return {
        'schema':'wp21-priority-legal-review-alerts-v1',
        'status':'review_hints_not_verified_appeals',
        'current_parent_sources_completely_refreshed':True,
        'other_source_window_is_bounded':True,
        'hint_count':len(hints),
        'hints':hints,
        'automatically_approved_sanctions':0,
        'protected_counters_modified':False,
        'absence_of_hints_means_no_appeal':False,
    }


def save(report,directory):
    base=AUDIT_ROOT.resolve()
    path=Path(directory).resolve()
    if path==base or base not in path.parents or path.is_symlink():
        raise ValueError('Rechtsfolgenprüfungen nur im nichtöffentlichen Audit-Unterordner')
    path.mkdir(parents=True,exist_ok=True)
    alert=review_alerts(report)
    for name,body in (
        ('priority_later_effects.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
        ('priority_later_effects.md',render(report)),
        ('priority_review_alerts.json',json.dumps(alert,ensure_ascii=False,indent=2)+'\n')):
        temporary=path/(name+'.tmp')
        temporary.write_text(body,encoding='utf-8')
        temporary.replace(path/name)


def run(*,source=AUDIT_ROOT/'wp21_priority_originals/original_contexts.json',
        discovery=AUDIT_ROOT/'wp21_dip_discovery/outside_pins.json',
        output=AUDIT_ROOT/'wp21_priority_later_effects',
        key=None,fetch_parent=official_parent,fetch_children=fetch_positions):
    api_key=key or os.getenv('DIP_API_KEY') or PUBLIC_KEY
    scout=json.loads(Path(source).read_text(encoding='utf-8'))
    window=json.loads(Path(discovery).read_text(encoding='utf-8'))
    original_role_consistent(scout)
    cases={}
    for ident in sorted(EXPECTED,key=int):
        parent=fetch_parent(ident,api_key)
        positions=fetch_children(ident,api_key)
        cases[ident]=inspect_parent(ident,parent,positions)
    report=consolidate(cases,scout,window)
    save(report,output)
    return report


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--original-scout',type=Path,
                     default=AUDIT_ROOT/'wp21_priority_originals/original_contexts.json')
    cli.add_argument('--discovery',type=Path,
                     default=AUDIT_ROOT/'wp21_dip_discovery/outside_pins.json')
    cli.add_argument('--output-dir',type=Path,default=AUDIT_ROOT/'wp21_priority_later_effects')
    options=cli.parse_args()
    report=run(source=options.original_scout,discovery=options.discovery,
               output=options.output_dir)
    print('WP21 priority DIP legal: 3 exact parents, 4 pinned original positions, '
          +str(sum(x['additional_parent_procedure_position_count']
                   for x in report['pinned_parent_cases']))+
          ' other positions in those parents; other sources remain open. '
          'No automatic counter updates.')


if __name__=='__main__':
    main()
