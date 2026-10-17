#!/usr/bin/env python3
"""Individually original-sourced DIP plenary grant and rejection dossier.

A DIP position is a legal SOURCE, not a unit of verified effective measures.
"""
import argparse
import json
from pathlib import Path

from wp21_autopruefung import norm
from wp21_hochprioritaet_18 import EXPECTED_KEYS
from wp21_18_dip_verfahrenspositionen import control_dates,named
from wp21_dip_kontrolle import reference
from wp21_dip_positionen import normalize_position
from wp21_einspruchsbelege import validated_index

# All IDs verified directly against the official DIP API on 2026-10-16.
PINNED={
 (51,'Markus Frohnmaier'):329623,(52,'Martin Hess'):330133,
 (53,'Heidi Reichinnek'):330237,(57,'Bernd Baumann'):330700,
 (61,'Ulrich von Zons'):332078,(65,'Luigi Pantisano'):332778,
 (65,'Martin Reichardt'):332748,(67,'Kathrin Gebel'):333090,
 (67,'Kerstin Przygodda'):333088,(68,'Paula Piechotta'):333149,
 (69,'Fabian Fahl'):333185,(69,'Timon Dzienus'):333192,
 (71,'Mirze Edis'):333814,(71,'Robin Jünger'):333809,
 (86,'Cansin Köktürk'):336641,(89,'Kai Whittaker'):337087,
 (93,'Birgit Bessin'):339006,(94,'Cansin Köktürk'):339024,
}
PINS={(session,norm(name)):str(ident)
      for (session,name),ident in PINNED.items()}


def assemble(snapshot):
    if (not isinstance(snapshot,dict)
            or snapshot.get('status')!='official_position_source_reference_inventory'
            or snapshot.get('original_cases')!=18
            or snapshot.get('positions')!=22
            or snapshot.get('no_automated_sanction_decisions') is not True):
        raise ValueError('Kein vollständiger 18/22-DIP-Originalquellensnapshot')
    if set(PINS)!=EXPECTED_KEYS or len(set(PINS.values()))!=18:
        raise ValueError('Amtliche DIP-Vorgangsnachweise unvollständig')
    dates=control_dates(reference())
    decisions=validated_index()
    if len(decisions)!=4 or not set(decisions).issubset(EXPECTED_KEYS):
        raise ValueError('Vier unabhängige Bundestags-Entscheidungsquellen fehlen')
    rows=[]
    seen=set()
    position_ids=set()
    for case in snapshot.get('cases',[]):
        if not isinstance(case,dict):
            raise ValueError('DIP-Einzelfall ungültig')
        session=case.get('session')
        person=case.get('person')
        if type(session)!=int or not isinstance(person,str):
            raise ValueError('DIP-Person/Sitzung unbestimmt')
        key=(session,norm(person))
        if key not in PINS or key in seen:
            raise ValueError('DIP-Fall unbekannt oder doppelt')
        seen.add(key)
        parent=case.get('vorgang_id')
        if (parent!=PINS[key] or
                case.get('vorgang_source')!=
                'https://dip.bundestag.de/vorgang/'+parent):
            raise ValueError('Falscher amtlicher Vorgang im DIP-Fall')
        positions=case.get('positions')
        if not isinstance(positions,list) or not 1<=len(positions)<=2:
            raise ValueError('DIP-Quellpositionen fehlen oder sind mehrdeutig')
        grant=None
        appeal=None
        for item in positions:
            if not isinstance(item,dict) or not isinstance(
                    item.get('official_raw_metadata'),dict):
                raise ValueError('Rohdatennachweis der amtlichen Position fehlt')
            p=normalize_position(item['official_raw_metadata'])
            pid=p['id']
            if (pid!=item.get('id') or pid in position_ids
                    or p['parent_id']!=parent
                    or item.get('source_api')!=
                    'https://search.dip.bundestag.de/api/v1/vorgangsposition/'+pid
                    or not p['official_plenary_pdf_url']
                    or not p['official_plenary_xml_url']):
                raise ValueError('Position ohne amtlichen Parent-/Fundstellen-Nachweis')
            position_ids.add(pid)
            link={
                'dip_position_id':pid,
                'plenary_session':p['official_plenary_session'],
                'document_date':p['official_plenary_date'],
                'plenary_pdf_page':p['official_plenary_pdf_url'],
                'plenary_xml':p['official_plenary_xml_url'],
                'position_type':p['step'],
                'cannot_infer_number_of_effective_measures':True,
            }
            if p['step']=='Ordnungsruf':
                if (grant is not None or p['date']!=dates[key]
                        or p['official_plenary_session']!=session
                        or p['official_decision_tenors']):
                    raise ValueError('Originalerteilung gehört nicht zu dieser Sitzung')
                grant=link
            elif p['step']=='Abstimmung':
                decision=decisions.get(key)
                if (appeal is not None or decision is None
                        or p['date']!=decision['decision_date']
                        or p['official_plenary_date']!=decision['decision_date']
                        or p['official_plenary_session']<=session
                        or p['official_decision_tenors']!=
                        ['Zurückweisung des Einspruchs']
                        or not named(p['official_position_abstract_excerpt'],person)):
                    raise ValueError('Einspruchsbeschluss nicht quellen- und personenscharf')
                appeal={**link,
                    'explicit_dip_beschlusstenor':'Zurückweisung des Einspruchs',
                    'independent_bundestag_decision_report':decision['source'],
                    'no_automatic_measure_count':True}
            else:
                raise ValueError('Unbekannte DIP-Rechtsfolgenposition')
        if grant is None or bool(appeal)!=bool(decisions.get(key)):
            raise ValueError('Erteilung/Einspruch in Originalakte unvollständig')
        rows.append({
            'session':session,'person':person,'official_parent_id':parent,
            'official_vorgang_url':case['vorgang_source'],
            'original_date':dates[key],
            'original_grant_source':grant,
            'separate_appeal_decision_source':appeal,
            'legal_effect_and_distinct_issuance_count_not_inferred':True,
        })
    if len(seen)!=18 or len(position_ids)!=22:
        raise ValueError('Nicht alle 22 Originalpositionen zugeordnet')
    rows.sort(key=lambda r:(r['session'],norm(r['person'])))
    if sum(bool(r['separate_appeal_decision_source']) for r in rows)!=4:
        raise ValueError('Vier unabhängig geprüfte Einspruchsbeschlüsse fehlen')
    return {
        'status':'18_original_plenary_grant_sources_4_dip_rejected_objections_review_only',
        'case_count':18,'grant_source_position_count':18,
        'appeal_decision_tenor_count':4,'position_count':22,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'protected_public_counters_changed':False,
        'warn':('Eine DIP-Verfahrensposition und auch eine zurückgewiesene '
                'Beschwerde dürfen nicht als Zählbeweis für selbständige '
                'rechtswirksame Einzel-Ordnungsrufe gelten.'),
        'cases':rows,
    }


def render_markdown(result):
    if (result.get('case_count')!=18 or result.get('position_count')!=22
            or result.get('appeal_decision_tenor_count')!=4
            or result.get('automatically_confirmed_effective_sanctions')!=0
            or result.get('protected_public_counters_changed')):
        raise ValueError('Amtliche Quellenprüfmatrix nicht gesichert')
    lines=['# WP21: 18 offizielle DIP-Originalpositionen und 4 gesonderte Beschlüsse',
           '',
           '**18 individuelle DIP-Person/Sitzung-Quellen mit amtlichen',
           'Plenarprotokoll-PDF- und XML-Fundstellen. Vier zusätzlich',
           'personengebundene Entscheidungen: Zurückweisung des Einspruchs.**',
           '',
           '| Original | Person | DIP-Vorgang | Erteilungsseite | Einspruchsentscheidung |',
           '| --- | --- | --- | --- | --- |']
    for r in result['cases']:
        grant=r['original_grant_source']
        vote=r['separate_appeal_decision_source']
        decision=(f"[DIP-PDF 21/{vote['plenary_session']:03d}]"
                  f"({vote['plenary_pdf_page']}) · "
                  f"[Bundestagsbericht]({vote['independent_bundestag_decision_report']})"
                  if vote else 'Kein individueller Einspruchsbeschluss in dieser Stichprobe')
        lines.append(
            f"| 21/{r['session']:03d} | {r['person']} | "
            f"[{r['official_parent_id']}]({r['official_vorgang_url']}) | "
            f"[amtliches Plenar-PDF]({grant['plenary_pdf_page']}) | {decision} |")
    lines.extend(['',
        '**Beweisgrenze:** Weder 18 DIP-Verfahrenspositionen noch vier',
        'Einspruchszurückweisungen bestätigen die Anzahl unabhängiger',
        'rechtswirksamer Maßnahmen. Die Verfahrensvolltexte anderer Dokumente',
        'und die Möglichkeit späterer Aufhebungen bleiben separat zu prüfen.',
        '**Keine veröffentlichte oder bestätigte Zahl geändert.**',''])
    return '\n'.join(lines)


def run(source,output,brief):
    snapshot=json.loads(Path(source).read_text(encoding='utf-8'))
    result=assemble(snapshot)
    rendered=render_markdown(result)
    for target,payload in ((Path(output),json.dumps(result,ensure_ascii=False,indent=2)+'\n'),
                           (Path(brief),rendered)):
        target.parent.mkdir(parents=True,exist_ok=True)
        temp=target.with_suffix(target.suffix+'.tmp')
        temp.write_text(payload,encoding='utf-8')
        temp.replace(target)
    print('WP21_DIP_18_BESCHLUSS_OK: 18 grant sources, 4 rejected objections, 0 automatic sanctions')
    return result


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--brief',type=Path,required=True)
    args=cli.parse_args()
    run(args.source,args.output,args.brief)
