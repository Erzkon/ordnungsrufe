#!/usr/bin/env python3
"""Read-only 21/040 Gottschalk/Mixl source -> DIP -> 21/042 vote crosswalk.

The 21/042 minute documents ONE rejected Gottschalk objection, but does
not give its ordinal. Bundestag's contemporaneous report discusses his
"Pfui" objection, consistent with the first spoken issuance in 21/040.
Neither establishes any decision on his second original measure.

For Mixl, only the stenographic attribution + admission are known from
21/040. A bounded title-independent DIP-position search is a manual
discovery aid; missing metadata cannot establish nonexistence of a grant
or appeal. Never change the four public verified statistics.
"""
import argparse
import json
import os
from pathlib import Path
from datetime import date

from wp21_gottschalk_unkategorisierte_positionen import (
    PARENT, KNOWN_ORIGIN, KNOWN_VOTE, KEYWORDS, fragments,
    pages as dip_pages, inspect as dip_inspect, PUBLIC_KEY,
)
from wp21_dip_positionen import fetch_positions, normalize_position
from wp21_18_dip_verfahrenspositionen import named
from wp21_gottschalk_amtliche_beschluesse import (
    SOURCES, MAX_PDF_BYTES, hints_for_pages, pdf_pages,
    download as download_official_pdf,
)
from wp21_weitere_einspruchsberichte import (
    EVIDENCE, PROTOCOL40, SOURCES as ARTICLES,
)

SCHEMA = 'wp21-40-gottschalk-mixl-dip-appeal-crosswalk-v1'
START, END = '2025-11-13', '2025-12-12'
VOTE_SOURCE = next(url for s, url in SOURCES if s == 42)
ORIGINAL = 'https://dserver.bundestag.de/btp/21/21040.xml'


def validate_original(case):
    if (not isinstance(case, dict)
            or case.get('schema') !=
                'wp21-21_040-gottschalk-mixl-speaker-and-interjection-review-v1'
            or case.get('official_original') != ORIGINAL
            or case.get('session') != 40
            or case.get('no_attribution_of_9005_to_gottschalk_or_janich') is not True
            or case.get('all_attributions_require_manual_legal_review') is not True
            or case.get('public_counter_delta') != 0):
        raise ValueError('Ursprüngliche Gottschalk/Mixl-Fallakte nicht authentisch')
    got = case.get('gottschalk_immediate_second_issuance')
    mix = case.get('mixl_anonymous_interjection_and_admission')
    if (not isinstance(got,dict) or not isinstance(mix,dict)
            or got.get('context_supported_recipient') != 'Kay Gottschalk'
            or got.get('appeal_or_legal_effect_confirmed') is not False
            or got.get('second_sentence_names_recipient_explicitly') is not False
            or got.get('speech_continuity_and_reply_verified') is not True
            or mix.get('context_supported_speaker') != 'Reinhard Mixl'
            or mix.get('formal_recipient_named_at_issuance') is not False
            or mix.get('separate_appeal_or_legal_effect_confirmed') is not False):
        raise ValueError('Sprecher-/Zwischenruf-Beleg oder Beweisgrenze verändert')
    for key,line in (
            ('initial_explicit_recipient',8990),
            ('same_chair_second_issuance',8992),
            ('immediate_recipient_reply',8994)):
        row=got.get(key)
        if not isinstance(row,dict) or row.get('xml_line')!=line or row.get('original_source')!=ORIGINAL:
            raise ValueError('Gottschalk-Originalzeile verschoben')
    for key,line in (
            ('original_interjection_name_and_word',9002),
            ('chair_warning_did_not_identify_person',9005),
            ('immediate_self_admission',9006)):
        row=mix.get(key)
        if not isinstance(row,dict) or row.get('xml_line')!=line or row.get('original_source')!=ORIGINAL:
            raise ValueError('Mixl-Originalzeile verschoben')


def inspect_dip_parent(raw):
    if not isinstance(raw,list) or not 2<=len(raw)<=100:
        raise ValueError('Verknüpfte DIP-Gottschalk-Positionen unvollständig')
    normalized=[]
    ids=set()
    for doc in raw:
        if not isinstance(doc,dict) or str(doc.get('vorgang_id'))!=PARENT:
            raise ValueError('Fremder DIP-Vorgang')
        ident=str(doc.get('id'))
        if not ident.isdecimal() or ident in ids:
            raise ValueError('Doppelte/unlesbare DIP-Position')
        ids.add(ident)
        position=normalize_position(doc)
        normalized.append(position)
    if not {KNOWN_ORIGIN,KNOWN_VOTE}<=ids:
        raise ValueError('Bekannte Original- und Zurückweisungsposition fehlen')
    by_id={str(doc['id']):doc for doc in raw}
    orig=normalize_position(by_id[KNOWN_ORIGIN])
    vote=normalize_position(by_id[KNOWN_VOTE])
    if (by_id[KNOWN_ORIGIN].get('datum')!=START
            or orig.get('step')!='Ordnungsruf'
            or by_id[KNOWN_VOTE].get('datum')!='2025-11-25'
            or vote.get('step')!='Abstimmung'
            or 'Zurückweisung des Einspruchs'
                not in vote.get('official_decision_tenors', [])):
        raise ValueError('Amtliche Gottschalk-Positivkontrollen verändert')
    return {
        'known_vorgang_id':PARENT,
        'known_issuance_position_id':KNOWN_ORIGIN,
        'known_vote_position_id':KNOWN_VOTE,
        'known_vorgang_position_count':len(raw),
        'additional_same_vorgang_positions_for_manual_review':[
            x for x in normalized
            if str(x['id']) not in (KNOWN_ORIGIN,KNOWN_VOTE)],
        'dip_metadaten_do_not_split_two_original_calls':True,
        'dip_vote_cannot_be_applied_to_both_calls':True,
    }


def extract_mixl_position_hints(raw):
    if not isinstance(raw,list):
        raise ValueError('Amtliche Positionsübersicht unvollständig')
    ids=set()
    hits=[]
    for doc in raw:
        if not isinstance(doc,dict) or not isinstance(doc.get('datum'),str):
            raise ValueError('Nichtamtliche DIP-Position')
        ident=str(doc.get('id'))
        if not ident.isdecimal() or ident in ids or not START<=doc['datum']<=END:
            raise ValueError('Mixl-DIP-Positions-ID/-Datum ungültig')
        ids.add(ident)
        parts=fragments(doc)
        names=[field for field,text in parts if named(text,'Reinhard Mixl')]
        procedural=[field for field,text in parts if KEYWORDS.search(text)]
        if not names or not procedural:
            continue
        position=normalize_position(doc)
        hits.append({
            'position_id':ident,
            'parent_id':str(doc['vorgang_id']),
            'date':doc['datum'],
            'source':position['source'],
            'step':position['step'],
            'name_fields':names,
            'order_or_objection_fields':procedural,
            'requires_manual_source_review':True,
            'person_link_and_procedural_vocabulary_not_a_legal_decision':True,
        })
    return sorted(hits,key=lambda x:(x['date'],int(x['position_id'])))


def reconcile(case,parent,raw_positions,pages_checked,minute_pages):
    validate_original(case)
    par=inspect_dip_parent(parent)
    # The existing title-independent scanner is independently anchored
    # on known first rejection position 681803.
    dates=dip_inspect(raw_positions, START, END, pages_checked)
    if dates['known_first_appeal_verified'] is not True:
        raise ValueError('First Gottschalk appeal DIP position not recovered')
    minute=hints_for_pages(minute_pages,42,VOTE_SOURCE)
    if len(minute)!=1 or not minute[0]['known_first_objection_only']:
        raise ValueError('Amtliches Beschlussprotokoll 21/042 nicht einzeln verifiziert')
    matches=[
        x for x in EVIDENCE
        if x['original_date']==START and x['decision_date']=='2025-11-25'
        and x['person']=='Kay Gottschalk']
    if (len(matches)!=1
            or matches[0]['source']!=ARTICLES['2025nov13']
            or matches[0]['individual_objection_ordinal']!=1
            or PROTOCOL40['original_grants_by_person'].get('Kay Gottschalk')!=2
            or PROTOCOL40['rejected_objections_in_this_article_by_person'].get('Kay Gottschalk')!=1):
        raise ValueError('Unabhängige Bundestags-Artikel-/Einspruchsbasis geändert')
    mixl=extract_mixl_position_hints(raw_positions)
    return {
        'schema':SCHEMA,
        'source_type':'manual_review_crosswalk_not_effective_sanctions',
        'original_21_040_xml':ORIGINAL,
        'original_evidence':{
            'gottschalk_first_line':8990,'gottschalk_second_line':8992,
            'mixl_named_interjection_line':9002,
            'mixl_anonymous_chair_issuance_line':9005,
            'mixl_immediate_admission_line':9006,
            'recipient_context_was_independently_reviewed':True,
        },
        'gottschalk':{
            'two_original_calls_supported_by_21_040':True,
            'original_dip_parent':par,
            'one_formal_rejected_objection_in_21_042':{
                'official_minutes_source':VOTE_SOURCE,'pdf_page':minute[0]['pdf_page'],
                'article_source':ARTICLES['2025nov13'],
                'dip_vote_position_id':KNOWN_VOTE,
                'ordinal_named_in_resolution':False,
                'article_pfui_rationale_supports_link_to_first_issuance':True,
                'automatically_proves_second_objection_or_outcome':False,
            },
            'second_appeal_status':'unverified_not_absence_proved',
        },
        'mixl':{
            'interjection_speaker_from_official_commented_xml':'Reinhard Mixl',
            'original_chair_issuance_did_not_name_recipient':True,
            'position_window_start':START,
            'position_window_end':END,
            'candidate_dip_positions':mixl,
            'dated_metadata_cannot_prove_no_other_appeal':True,
            'appeal_decision_status':'unverified',
        },
        'title_independent_dip_positions_examined':len(raw_positions),
        'complete_dip_pages_examined':pages_checked,
        'official_minutes_21_042_checked':True,
        'other_periods_and_documents_unchecked':True,
        'no_automatic_recipient_or_legal_effect_decision':True,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'public_counter_delta':0,
    }


def markdown(r):
    if (r.get('schema')!=SCHEMA
            or r.get('other_periods_and_documents_unchecked') is not True
            or r.get('no_automatic_recipient_or_legal_effect_decision') is not True
            or r.get('gottschalk',{}).get('second_appeal_status')!='unverified_not_absence_proved'
            or r.get('mixl',{}).get('appeal_decision_status')!='unverified'
            or r.get('public_counter_delta')!=0
            or r.get('automatically_confirmed_effective_sanctions')!=0
            or r.get('automatically_rescinded_sanctions')!=0):
        raise ValueError('Keine automatische Rechtsfolgenfreigabe aus Quellentriage')
    g=r['gottschalk']
    m=r['mixl']
    lines=[
        '# 21/040: Original, DIP, Einwände und Beschluss zu Gottschalk/Mixl','',
        'Gottschalk: 2 ursprüngliche Erteilungen (XML 8990 und 8992).',
        f"DIP Vorgang [{PARENT}](https://dip.bundestag.de/vorgang/{PARENT}): "
        f"Origin-Position {KNOWN_ORIGIN}, Einspruchsvotum {KNOWN_VOTE}.",
        f"Das [amtliche Beschlussprotokoll 21/042]({VOTE_SOURCE}) belegt "
        'eine Zurückweisung, ohne einen ersten oder zweiten Ordinal zu nennen.',
        f"Der [Bundestagsartikel]({ARTICLES['2025nov13']}) nennt ausdrücklich "
        'Gottschalks Pfui-Begründung, aber keinen zweiten Einspruch.',
        'Eine spätere Entscheidung zur zweiten Maßnahme ist weder festgestellt '
        'noch für alle künftigen Zeiträume ausgeschlossen.','',
        'Mixl: originaler namentlicher Zwischenruf XML 9002, bei der '
        'Erteilung XML 9005 nennt die Sitzungsleitung noch keinen '
        'Empfänger, Eigenbestätigung XML 9006.',
        f"Von {START} bis {END} titelunabhängig geprüfte amtliche "
        f"DIP-Positionsdatensätze: {r['title_independent_dip_positions_examined']} "
        f"auf {r['complete_dip_pages_examined']} Seiten.",
        f"Mixl-Personen-/Ordnungsbezug als Prüfkandidat: "
        f"{len(m['candidate_dip_positions'])}.",
    ]
    for row in m['candidate_dip_positions']:
        lines.append(
            f"- [Position {row['position_id']}]({row['source']}) vom "
            f"{row['date']}: nur manueller Kontext")
    lines.extend([
        '', '**Keine bestätigte Rechtswirksamkeit; kein Zählerupdate.**',
        'DIP-Nichttreffer innerhalb des begrenzten Suchfensters beweisen '
        'keine Nichterteilung und keine fehlenden späteren Rechtsfolgen.','',
    ])
    return '\n'.join(lines)


def run(source_file, output, brief, *, key=None,
        get_parent=fetch_positions, get_pages=dip_pages,
        pdf_load=download_official_pdf, extract=pdf_pages):
    case=json.loads(Path(source_file).read_text(encoding='utf-8'))
    validate_original(case)
    key=key or os.getenv('DIP_API_KEY') or PUBLIC_KEY
    if not key or '\r' in key or '\n' in key:
        raise ValueError('DIP-Schlüssel fehlt')
    parent=get_parent(PARENT,key)
    positions,count=get_pages(START,END,key)
    pdf=pdf_load(VOTE_SOURCE,MAX_PDF_BYTES)
    minute=extract(pdf)
    report=reconcile(case,parent,positions,count,minute)
    md=markdown(report)
    for name,body in ((Path(output),json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
                      (Path(brief),md)):
        name.parent.mkdir(parents=True,exist_ok=True)
        temporary=name.with_suffix(name.suffix+'.tmp')
        temporary.write_text(body,encoding='utf-8')
        temporary.replace(name)
    if report['mixl']['candidate_dip_positions'] or report['gottschalk']['original_dip_parent']['additional_same_vorgang_positions_for_manual_review']:
        print('::warning::Quellengebundene weitere DIP-Kandidaten manuell prüfen')
    print('WP21_DIP_GOTTSCHALK_MIXL_CROSSWALK_OK',
          len(positions),'DIP positions,',count,'pages,',
          len(report['mixl']['candidate_dip_positions']),'Mixl source hints;',
          'single known Gottschalk objection and no legal count change')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-case',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--brief',type=Path,required=True)
    args=parser.parse_args()
    run(args.source_case,args.output,args.brief)
