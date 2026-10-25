#!/usr/bin/env python3
"""Case-specific WP21 legal-followup evidence, NOT a sanctions approval engine.

Five previously sourced original grants are checked against exact published
objection identities and against fresh official DIP parent+position results.
"Not in a bounded collection" NEVER means no objection or no later remedy.
"""
import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from wp21_autopruefung import norm, read_reviewed
from wp21_dip_kontrolle import reference
from wp21_dip_monitor import PUBLIC_KEY, NoRedirect, relevant_item
from wp21_dip_positionen import fetch_positions, normalize_position
from wp21_einspruchsbelege import validated_index
from wp21_weitere_einspruchsberichte import validate as verified_reports
from wp21_18_dip_original_beschluesse import PINS
from wp21_five_origins import build as five_originals
from wp21_three_decisions import ROOT, SNAPSHOT, LEDGER

API='https://search.dip.bundestag.de/api/v1/vorgang/'
EXPECTED={
    (53,norm('Heidi Reichinnek')):'330237',
    (57,norm('Bernd Baumann')):'330700',
    (61,norm('Ulrich von Zons')):'332078',
    (65,norm('Luigi Pantisano')):'332778',
    (67,norm('Kathrin Gebel')):'333090',
}
INCOMPLETE_NOTICE=(
    'Für diesen Originalfall ist in den 17 bisher quellengeprüften '
    'zurückgewiesenen Einsprüchen kein EXAKTES Datum-/Personenpaar '
    'vorhanden. Das ist ausdrücklich KEIN Nachweis, dass kein Einspruch '
    'oder keine spätere Aufhebung existiert. Auch der DIP-Snapshot je '
    'Vorgang deckt keine fremden Vorgänge oder nicht veröffentlichte '
    'parlamentarische Entscheidungen ab.'
)


def historical_crosscheck(originals=None, reports=None, curated=None, snapshot=None, known=None):
    if snapshot is None:
        snapshot=reference(SNAPSHOT)
    if known is None:
        known,count=read_reviewed(LEDGER)
        if count!=8: raise ValueError('Bestätigte WP21-Teilauswahl verändert')
    if originals is None:
        originals=five_originals(snapshot=snapshot,known=known)['cases']
    if reports is None: reports=verified_reports()
    if curated is None: curated=validated_index()
    if (len(originals)!=5 or set(EXPECTED)!=set(PINS)&set(EXPECTED)
            or len(reports)!=13 or len(curated)!=4
            or sum(known.values())!=8
            or len(snapshot['entries'])!=24):
        raise ValueError('Kuratierte Original-/Einspruchsquellen unvollständig')
    out=[]
    for c in originals:
        session=c['session']; person=c['person']; key=(session,norm(person))
        if (key not in EXPECTED or EXPECTED[key]!=PINS[key]
                or key in known or c.get('original_source_individually_located') is not True):
            raise ValueError('Falsche oder bereits bestätigte Fallidentität')
        matches=[
            {**entry,'matching_method':'person_and_exact_original_grant_date'}
            for entry in reports.values()
            if norm(entry['person'])==key[1]
            and entry['original_date']==c['original_date']
            and (entry['original_session'] is None or entry['original_session']==session)
        ]
        match2=curated.get(key)
        if match2:
            matches.append({**match2,'matching_method':'official_curated_session_and_person'})
        # The frozen 13+4 published rejections have no matching original-date
        # claim for these five; explicitly separate unrelated same-name cases.
        same_name_other_grants=[
            {'original_date':entry['original_date'],
             'source':entry['source'],
             'sanction_type':entry['sanction_type'],
             'NOT_this_grant':True}
            for entry in reports.values()
            if norm(entry['person'])==key[1]
            and entry['original_date']!=c['original_date']
        ]
        if matches:
            # A new exact pair can be added only with independently checked
            # source text; don't silently accept a changed frozen corpus.
            raise ValueError('Neuer Einspruchsbeleg: individuelle Neubewertung nötig')
        out.append({
            'session':session, 'person':person,'original_date':c['original_date'],
            'official_dip_parent_id':EXPECTED[key],
            'official_dip_parent_url':'https://dip.bundestag.de/vorgang/'+EXPECTED[key],
            'original_pdf_url':c['original_pdf_url'],
            'original_xml_line':c['original_xml_line'],
            'bounded_curated_rejected_objection_matches':[],
            'same_name_other_date_reports_excluded':same_name_other_grants,
            'other_person_mentioned_in_report_not_recipient':True,
            'historical_corpus_fully_covers_all_legal_effects':False,
            'no_appeal_has_been_proven':False,
            'appeal_or_rescission_status':'not_conclusively_checked',
            'requires_case_specific_followup':True,
            'newly_approved_effective_sanctions':0,
        })
    if len({(e['session'],norm(e['person'])) for e in out})!=5:
        raise ValueError('Doppelte Prüffälle')
    out.sort(key=lambda c:c['session'])
    return {
        'schema':'wp21-five-legal-followup-matrix-v1',
        'source_snapshot':snapshot['last_manual_snapshot'],
        'source_collection':'bounded_13_additional_plus_4_priority_rejections_not_complete',
        'cases':out,
        'original_cases':5,'curated_rejected_objections_scanned':17,
        'definitively_closed_legal_effects':0,
        'automatically_approved_new_sanctions':0,
        'protected_ledger_changed':False,
        'warning':INCOMPLETE_NOTICE,
    }


def official_parent(ident,key,opener=None,sleep=time.sleep):
    if not re.fullmatch(r'[1-9]\d{0,11}',str(ident)):
        raise ValueError('DIP-Vorgangs-ID ungültig')
    opener=opener or build_opener(NoRedirect())
    req=Request(API+str(ident),headers={
        'Authorization':'ApiKey '+key,'Accept':'application/json',
        'User-Agent':'OrdnungsrufCounter/0.6 (github.com/Erzkon/ordnungsrufe)'})
    for attempt in range(3):
        try:
            with opener.open(req,timeout=25) as response:
                if response.status!=200: raise ValueError('DIP-Vorgang HTTP nicht 200')
                blob=response.read(250001)
            if len(blob)>250000: raise ValueError('DIP-Vorgang JSON zu groß')
            raw=json.loads(blob.decode('utf-8'))
            if (not isinstance(raw,dict) or str(raw.get('id'))!=str(ident)
                    or raw.get('wahlperiode')!=21):
                raise ValueError('DIP-Datensatz von anderem Vorgang')
            return raw
        except (HTTPError,URLError,TimeoutError,OSError) as exc:
            if isinstance(exc,HTTPError) and exc.code in (400,401,403,404):
                raise ValueError('DIP-API verweigert den Vorgang') from exc
            if attempt==2: raise
            sleep(2**attempt)
    raise RuntimeError('DIP-Abruf abgebrochen')


def assess_dip(case,parent,positions):
    """Accept only a fully fetched, pinned parent and its own positions."""
    ident=case['official_dip_parent_id']; date=case['original_date']
    if not isinstance(parent,dict) or not isinstance(positions,list):
        raise ValueError('Unvollständige DIP-Quellen')
    if str(parent.get('id'))!=ident or parent.get('wahlperiode')!=21:
        raise ValueError('Fremder DIP-Ursprungsvorgang')
    meta=relevant_item(parent)
    if meta is None or 'ordnungsruf' not in meta['title'].casefold():
        raise ValueError('DIP-Vorgang ohne ausdrücklichen Ordnungsruf')
    if not re.search(r'(?<!\w)'+re.escape(norm(case['person']))+r'(?!\w)',
                     norm(meta['title'])):
        raise ValueError('DIP-Vorgang anderer Empfänger')
    if len(positions)>20 or not positions:
        raise ValueError('Nicht plausibler Umfang von DIP-Verfahrenspositionen')
    result=[]; seen=set(); grants=0
    for raw in positions:
        if not isinstance(raw,dict):
            raise ValueError('Position ohne vollständige DIP-Rohdaten')
        p=normalize_position(raw)
        if p['parent_id']!=ident or p['id'] in seen:
            raise ValueError('DIP-Position fremden Vorgangs oder doppelt')
        seen.add(p['id'])
        if p['step'].casefold().strip()=='ordnungsruf' and p['date']==date:
            if p['official_plenary_session']!=case['session']:
                raise ValueError('Originalprotokoll nicht person-/sitzungsgebunden')
            grants+=1
            role='original_grant_step'
        elif p['step'].casefold().strip()=='abstimmung':
            role='unadjudicated_appeal_vote_metadata_candidate'
        else:
            role='other_procedure_step_needs_review'
        result.append({
            'official_position_id':p['id'],
            'official_position_api':'https://search.dip.bundestag.de/api/v1/vorgangsposition/'+p['id'],
            'date':p['date'],'role_for_review':role,
            'step':p['step'],'title':p['title'],
            'official_plenary_session':p['official_plenary_session'],
            'official_plenary_pdf':p['official_plenary_pdf_url'],
            'decision_tenor_metadata_only':p['official_decision_tenors'],
            'legal_effect_conclusively_verified':False,
            'additional_approved_sanctions':0,
        })
    if grants!=1:
        raise ValueError('Nicht exakt eine DIP-Originalerteilungsposition nachgewiesen')
    return {
        'official_dip_parent_id':ident,
        'original_grant_metadata_position_verified':True,
        'positions_completely_fetched_for_this_parent':True,
        'position_count':len(result),
        'other_step_review_hints':sum(x['role_for_review']!='original_grant_step'
                                      for x in result),
        'positions':result,
        'all_other_possible_later_cases_covered':False,
        'legal_effect_conclusively_verified':False,
        'automatic_count_change':0,
    }


def combine(historical,assessments=None,checked_at=None):
    """Read-only report, do not convert a missing record to negative proof."""
    if (historical['schema']!='wp21-five-legal-followup-matrix-v1'
            or len(historical['cases'])!=5
            or historical['automatically_approved_new_sanctions']!=0):
        raise ValueError('Ungültige Basis der Rechtsfolgenüberwachung')
    if assessments is None:
        result={**historical,
                'live_dip_parent_status':'not_checked',
                'live_dip_complete_for_exact_five_parents':False}
    else:
        if set(assessments)!={c['official_dip_parent_id']
                             for c in historical['cases']}:
            raise ValueError('Nicht alle fünf amtlichen DIP-Vorgänge geprüft')
        if not all(v['positions_completely_fetched_for_this_parent']
                   and v['automatic_count_change']==0 for v in assessments.values()):
            raise ValueError('Keine lückenhaften DIP-Quellenreports')
        result={**historical,'live_dip_parent_status':'all_five_refreshed',
                'live_dip_complete_for_exact_five_parents':True,
                'last_five_parent_probe_utc':checked_at,
                'cases':[{**c,'dip_parent_metadata_review':assessments[
                    c['official_dip_parent_id']]} for c in historical['cases']]}
    if result['automatically_approved_new_sanctions']!=0:
        raise ValueError('Unzulässige automatische Freigabe')
    return result


def render(report):
    if (report['automatically_approved_new_sanctions']
            or report['protected_ledger_changed'] or len(report['cases'])!=5):
        raise ValueError('Zähleränderung in Prüfbericht verboten')
    lines=['# WP21: Fünf einzelne spätere Rechtsfolgen-Prüfaufträge','',
           '**Kein individuell abschließend geprüfter Rechtsfolgenstatus.**',
           'Ein nicht gefundener Einspruch in einer Teilstichprobe ist '
           'kein Beweis für Einspruchsfreiheit.','',
           'DIP-Status: '+report['live_dip_parent_status'],'',
           '| Original | Quelle / Vorgang | Kuratierter Einspruch | DIP-Hinweise |',
           '|---|---|---|---|']
    for c in report['cases']:
        meta=c.get('dip_parent_metadata_review')
        state=(str(meta['other_step_review_hints'])+' zusätzliche Metadatenschritte'
               if meta else 'noch nicht frisch abgefragt')
        lines.append(
            f"| {c['person']} · 21/{c['session']:03d} "
            f"| [Original-PDF]({c['original_pdf_url']}) · "
            f"[DIP {c['official_dip_parent_id']}]({c['official_dip_parent_url']}) "
            f"| **Kein exakter Treffer in der begrenzten 17er-Auswahl; "
            f"spätere Rechtsfolgen offen** | {state} |")
    lines.extend(['',report['warning'],'',
                  '**Keine Zähleränderung, kein Schluss aus Abwesenheit eines Eintrags.**',''])
    return '\n'.join(lines)


def save(report,folder):
    folder=Path(folder).resolve(); allowed=(ROOT/'.audit').resolve()
    if folder!=allowed and allowed not in folder.parents:
        raise ValueError('Nur private .audit/-Prüfberichte zulässig')
    folder.mkdir(parents=True,exist_ok=True)
    for name,payload in [
        ('later_effects.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
        ('later_effects.md',render(report)),
    ]:
        dest=folder/name
        temp=dest.with_suffix(dest.suffix+'.tmp')
        temp.write_text(payload,encoding='utf-8')
        temp.replace(dest)
    return folder


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--offline',action='store_true',help='No live DIP access; default uses live API')
    cli.add_argument('--output-dir',type=Path,default=ROOT/'.audit/wp21_five_followups')
    args=cli.parse_args()
    historical=historical_crosscheck()
    if args.offline:
        result=combine(historical)
    else:
        key=os.getenv('DIP_API_KEY') or PUBLIC_KEY
        if not key or '\n' in key or '\r' in key:
            raise ValueError('Ungültiger DIP-API-Schlüssel')
        assessments={}
        for case in historical['cases']:
            ident=case['official_dip_parent_id']
            parent=official_parent(ident,key)
            positions=fetch_positions(ident,key)
            assessments[ident]=assess_dip(case,parent,positions)
            print('WP21_FIVE_DIP_PARENT_PROBE:',ident,case['person'],
                  len(positions),'positions, no legal counting',flush=True)
        result=combine(historical,assessments,
                       checked_at=datetime.now(timezone.utc).isoformat())
    save(result,args.output_dir)
    print('WP21_FIVE_LEGAL_FOLLOWUP_PASS: 5 cases, 17 bounded appeal '
          'identities reviewed, '+result['live_dip_parent_status']+
          ', 0 newly approved effective sanctions')


if __name__=='__main__':
    main()
