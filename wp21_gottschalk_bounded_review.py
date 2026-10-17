#!/usr/bin/env python3
"""Bounded official DIP source review for Kay Gottschalk's second 21/040 call.

The one-off government DIP title/date filtered inventory is FINITE. A
non-match within that inventory is NOT proof of absence of a different
§39 procedure, late published decision, other parent category, or the
legal effectiveness of the separate second original reprimand.
"""
import argparse
import json
import re
from pathlib import Path

from wp21_18_dip_verfahrenspositionen import named

PARENT='328225'
SOURCE='https://dip.bundestag.de/vorgang/'+PARENT
PDF40='https://dserver.bundestag.de/btp/21/21040.pdf#P.4635'
PDF42='https://dserver.bundestag.de/btp/21/21042.pdf#P.4865'
FIRST='Einspruch des Abg Kay Gottschalk (AfD) gegen die erste Ordnungsmaßnahme'


def inspect(doc):
    if (not isinstance(doc,dict)
            or doc.get('schema')!='wp21-gottschalk-later-procedure-bounded-review-v1'
            or doc.get('search_start')!='2025-11-13'
            or doc.get('search_end')!='2026-10-17'
            or doc.get('search_query')!='official_21wp_title_ordnungsruf_and_vorgang_datum'
            or doc.get('other_parliamentary_procedures_outside_this_title_date_filter_not_excluded') is not True
            or doc.get('missing_second_vote_is_not_proof_of_final_effectiveness') is not True
            or doc.get('automatically_confirmed_effective_sanctions')!=0
            or doc.get('automatically_rescinded_sanctions')!=0
            or doc.get('public_counters_changed') is not False):
        raise ValueError('Offiziell begrenzter DIP-Quellenfilter nicht eindeutig')
    total=doc.get('fully_traversed_filtered_dip_parent_count')
    pages=doc.get('official_dip_api_pages_checked')
    if (type(total)!=int or not 1<=total<=750
            or type(pages)!=int or not 1<=pages<=12
            or total>(pages*100)):
        raise ValueError('Amtliche DIP-Titelsuche nicht vollstaendig paginiert')
    items=doc.get('gottschalk_named_source_parents')
    if (not isinstance(items,list)
            or doc.get('named_gottschalk_parent_count')!=len(items)
            or not items or len(items)>total):
        raise ValueError('Personengebundene DIP-Quellenkandidaten fehlen')
    ids=set()
    inspected=[]
    for item in items:
        if not isinstance(item,dict):
            raise ValueError('DIP-Vorgang ohne Quellobjekt')
        ident=str(item.get('id',''))
        title=item.get('title')
        if (not re.fullmatch(r'[1-9]\d{0,11}',ident)
                or ident in ids
                or not isinstance(title,str)
                or not named(title,'Kay Gottschalk')
                or not re.search(r'\bordnungsruf\w*\b',title,re.I)
                or item.get('source')!='https://dip.bundestag.de/vorgang/'+ident):
            raise ValueError('Fremder/mehrdeutiger Gottschalk-Ordnungsruf-Vorgang')
        ids.add(ident)
        positions=item.get('complete_parent_positions')
        if (not isinstance(positions,list)
                or item.get('official_position_count')!=len(positions)
                or len(positions)>50):
            raise ValueError('Amtlicher Vorgang hat keine vollständige Positionsliste')
        posids=set()
        for row in positions:
            if not isinstance(row,dict):
                raise ValueError('Amtlicher DIP-Positionsinhalt ungültig')
            pid=str(row.get('id',''))
            if not re.fullmatch(r'[1-9]\d{0,11}',pid) or pid in posids:
                raise ValueError('DIP-Positionen-ID doppelt/fremd')
            posids.add(pid)
        inspected.append(item)
    origin=next((x for x in inspected if x['id']==PARENT),None)
    if origin is None or sum(x['id']==PARENT for x in inspected)!=1:
        raise ValueError('Original-Sammelvorgang 328225 fehlt im vollständigen Suchfenster')
    if (origin.get('date')!='2025-11-25'
            or origin.get('title')!='Erteilung von zwei Ordnungsrufen an den Abg Kay Gottschalk (AfD)'
            or origin.get('source')!=SOURCE):
        raise ValueError('Zwei ursprüngliche Gottschalk-Rufe nicht amtlich dokumentiert')
    positions=origin['complete_parent_positions']
    byid={str(row['id']):row for row in positions}
    if set(byid)!={'681046','681803'}:
        raise ValueError('Unerwartete zweite oder fehlende amtliche Verfahrensposition')
    original=byid['681046']
    decision=byid['681803']
    if (original.get('date')!='2025-11-13'
            or original.get('step')!='Ordnungsruf'
            or original.get('plenary_session')!=40
            or original.get('plenary_pdf')!=PDF40
            or original.get('decision_tenors')!=[]
            or decision.get('date')!='2025-11-25'
            or decision.get('step')!='Abstimmung'
            or decision.get('plenary_session')!=42
            or decision.get('plenary_pdf')!=PDF42
            or decision.get('abstract_excerpt')!=FIRST
            or decision.get('decision_tenors')!=['Zurückweisung des Einspruchs']):
        raise ValueError('Erste und zweite Gottschalk-Maßnahme oder Beschluss falsch zugeordnet')
    candidates=doc.get('second_appeal_explicitly_worded_candidates')
    if not isinstance(candidates,list):
        raise ValueError('Separater Einspruchskandidaten-Befund ungültig')
    if (candidates or len(inspected)!=1):
        # The frozen historical result is one original parent only; new
        # source candidates are an investigation trigger, never approval.
        raise ValueError('Neues mögliches Gottschalk-Verfahren: manuelle Quellenprüfung erforderlich')
    return {
        'schema':'wp21-gottschalk-second-bounded-official-review-v1',
        'source_survey_run':'https://github.com/Erzkon/ordnungsrufe/actions/runs/39031525919',
        'query_type':'official_dip_title_date_finite_not_a_complete_appeal_register',
        'query_start':'2025-11-13','query_end':'2026-10-17',
        'official_title_filtered_dip_parent_count':total,
        'official_title_filtered_dip_pages':pages,
        'named_gottschalk_parents_within_scope':len(inspected),
        'official_parent_id':PARENT,
        'original_two_separate_issuances_confirmed':2,
        'original_grant_position_id':original['id'],
        'original_pdf':PDF40,
        'first_appeal_rejection_position_id':decision['id'],
        'first_appeal_decision_pdf':PDF42,
        'first_appeal_original_abstract':FIRST,
        'second_individually_decided_appeal_in_this_scoped_source_count':0,
        'other_procedures_outside_title_date_filter_unchecked':True,
        'absence_of_appeal_anywhere_not_established':True,
        'effectiveness_of_second_call_not_established':True,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'public_counter_delta':0,
        'note':('36 Ordnungsruf-titulierte DIP-Elternvorgänge im begrenzten '
                'Wahlperioden-/Datumsfenster geprüft: ein Gottschalk-Vorgang '
                'mit zwei ursprünglichen Erteilungen, aber nur ausdrücklich '
                'erster Einspruchsentscheidung. Der Suchumfang reicht '
                'nicht aus, um alle anderen möglichen §39-Verfahren '
                'oder spätere Rechtsfolgen auszuschließen.'),
    }


def markdown(result):
    if (result.get('schema')!='wp21-gottschalk-second-bounded-official-review-v1'
            or result.get('official_parent_id')!=PARENT
            or result.get('original_two_separate_issuances_confirmed')!=2
            or result.get('second_individually_decided_appeal_in_this_scoped_source_count')!=0
            or result.get('other_procedures_outside_title_date_filter_unchecked') is not True
            or result.get('absence_of_appeal_anywhere_not_established') is not True
            or result.get('effectiveness_of_second_call_not_established') is not True
            or result.get('automatically_confirmed_effective_sanctions')!=0
            or result.get('public_counter_delta')!=0):
        raise ValueError('Gefährlich verkürzter Gottschalk-Quellenbericht')
    return '\n'.join([
        '# Kay Gottschalk: begrenzter amtlicher Folgeentscheidungsabgleich',
        '',
        f"**Offizielle Ordnungsruf-DIP-Vorgänge im Suchfenster:** "
        f"{result['official_title_filtered_dip_parent_count']}.",
        '**Davon mit Gottschalk-Personenbezug:** '
        f"{result['named_gottschalk_parents_within_scope']}.",
        '',
        '- Ursprung: [21/040, zwei Erteilungen]'
        f"({result['original_pdf']}) – "
        f"[amtlicher DIP-Vorgang {PARENT}]({SOURCE}).",
        '- Individuelle DIP-Position **681803**: Einspruch gegen die '
        '**erste** Ordnungsmaßnahme, in [21/042 zurückgewiesen]'
        f"({result['first_appeal_decision_pdf']}).",
        '- **Kein weiterer ausdrücklich auf den zweiten Ruf bezogener '
        'DIP-Vorgang innerhalb dieses eng gefilterten Quellenbestands**.',
        '',
        '**Kein Vollständigkeitsbeweis außerhalb des Datums-/Titelfilters.**',
        'Keine Feststellung, dass der zweite Ruf endgültig wirksam ist;',
        'andere Einspruchsverfahren oder spätere Entscheidungen können',
        'außerhalb dieses Suchbereichs dokumentiert sein.',
        '',
        '**Keine automatische Zähleränderung.**','',
    ])


def run(source,output,brief):
    snapshot=json.loads(Path(source).read_text(encoding='utf-8'))
    result=inspect(snapshot)
    prose=markdown(result)
    for target,data in ((Path(output),json.dumps(result,ensure_ascii=False,indent=2)+'\n'),
                        (Path(brief),prose)):
        target.parent.mkdir(parents=True,exist_ok=True)
        temp=target.with_suffix(target.suffix+'.tmp')
        temp.write_text(data,encoding='utf-8')
        temp.replace(target)
    print('WP21_GOTTSCHALK_SCOPED_DIP_OK: '
          f"{result['official_title_filtered_dip_parent_count']} "
          'filtered sources, one named parent, two original grants, '
          'one rejected first appeal, zero in-scope second-decision '
          'candidates, zero automatic legal conclusions.')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--brief',type=Path,required=True)
    opts=parser.parse_args()
    run(opts.source,opts.output,opts.brief)
