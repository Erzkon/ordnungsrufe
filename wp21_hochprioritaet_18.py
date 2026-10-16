#!/usr/bin/env python3
"""Read-only individual original-source dossiers for 18 priority WP21 cases.

A person/sitting parser mention is not a count of independently effective
sanctions. DIP reports ORIGINAL grants, not conclusive appeal decisions.
No public or confirmed count may be written by this module.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from parser import events, iter_session_text, speaker_index
from wp21_autopruefung import norm, read_reviewed
from wp21_dip_kontrolle import reference
from wp21_einspruchsbelege import validated_index
from wp21_episoden import PAIRS
from wp21_rechtsfolgen import classify_signal
from wp21_scan import HOST, fetch, safe_parse

# Snapshot of the 18 remaining HIGH-priority person/sitting keys after
# the audited 101-protocol original scan (#38932763448, 2026-10-16).
# This is a REVIEW scope, not a list of 18 proven effective sanctions.
TARGETS = {
    51: ('Markus Frohnmaier',),
    52: ('Martin Hess',),
    53: ('Heidi Reichinnek',),
    57: ('Bernd Baumann',),
    61: ('Ulrich von Zons',),
    65: ('Luigi Pantisano','Martin Reichardt'),
    67: ('Kathrin Gebel','Kerstin Przygodda'),
    68: ('Paula Piechotta',),
    69: ('Fabian Fahl','Timon Dzienus'),
    71: ('Mirze Edis','Robin Jünger'),
    86: ('Cansin Köktürk',),
    89: ('Kai Whittaker',),
    93: ('Birgit Bessin',),
    94: ('Cansin Köktürk',),
}
EXPECTED_KEYS = {(session,norm(name))
                 for session,names in TARGETS.items() for name in names}
# Reviewed exact original XML issuance locations from successful official
# 14-protocol dossier #38935257560, not counts of effective legal measures.
# A changed/extra/missing XML source line fails closed until source review.
ORIGINAL_LINES = {
    (51,norm('Markus Frohnmaier')):(3979,3981),
    (52,norm('Martin Hess')):(3749,),
    (53,norm('Heidi Reichinnek')):(6149,),
    (57,norm('Bernd Baumann')):(1487,),
    (61,norm('Ulrich von Zons')):(4557,),
    (65,norm('Luigi Pantisano')):(5104,),
    (65,norm('Martin Reichardt')):(2044,2046),
    (67,norm('Kathrin Gebel')):(3164,),
    (67,norm('Kerstin Przygodda')):(3079,),
    (68,norm('Paula Piechotta')):(5010,),
    (69,norm('Fabian Fahl')):(2204,),
    (69,norm('Timon Dzienus')):(2712,),
    (71,norm('Mirze Edis')):(4772,),
    (71,norm('Robin Jünger')):(2392,),
    (86,norm('Cansin Köktürk')):(1895,),
    (89,norm('Kai Whittaker')):(5865,),
    (93,norm('Birgit Bessin')):(3285,),
    (94,norm('Cansin Köktürk')):(1130,1140),
}

MAX_SOURCE_PARAGRAPHS = 5
# A source paragraph is a spoken phrase, NOT necessarily one legal measure.
# This gives the reviewer an explicit relationship hypothesis, not a count.
MULTI_PHRASE_EPISODES={
    (51,norm('Markus Frohnmaier')):'additional_issuance_requires_individual_legal_review',
    (65,norm('Martin Reichardt')):'same_issuance_repetition_possible',
    (94,norm('Cansin Köktürk')):'two_original_grants_already_separately_ledger_reviewed',
}
MAX_LEGAL_HINTS_PER_CASE = 12


def validate_scope():
    if (len(TARGETS)!=14 or len(EXPECTED_KEYS)!=18
            or sum(map(len,TARGETS.values()))!=18):
        raise ValueError('Hochprioritäts-Stichprobe verändert, Neuprüfung nötig')
    if set(ORIGINAL_LINES)!=EXPECTED_KEYS:
        raise ValueError('21 verifizierte Originalfundstellen nicht vollständig referenziert')
    if sum(map(len,ORIGINAL_LINES.values()))!=21:
        raise ValueError('Erteilungsformulierungs-Anker erfordern Neuprüfung')
    if {key for key,lines in ORIGINAL_LINES.items() if len(lines)>1}!=set(MULTI_PHRASE_EPISODES):
        raise ValueError('Mehrfachformulierungen nicht gesondert eingeordnet')
    for session,(first,comment,last,person,relation) in PAIRS.items():
        if session not in (51,65):
            continue
        key=(session,norm(person))
        if ORIGINAL_LINES[key]!=(first,last) or MULTI_PHRASE_EPISODES[key]!=relation:
            raise ValueError('Episoden-Regressionsquelle und 18er-Fallakte widersprechen sich')
    if len({(s,norm(name)) for s,group in TARGETS.items()
            for name in group})!=18:
        raise ValueError('Doppelte Personen/Sitzungen')


def original_entry(row,paragraphs):
    line=int(row['line'])
    text=paragraphs.get(line)
    if (text is None or row['evidence_type']!='possible_grant'
            or row['status']!='review_required'
            or text!=row['text'] and not text.startswith(row['text'])):
        raise ValueError(f'Parser-Prüfhinweis ohne eindeutigen Erteilungsabsatz: {line}')
    return {
        'xml_line':line,
        'text_excerpt':text[:1000],
        'text_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'recipient_attribution_method':row['zuordnungsmethode'],
        'xml_identity_status':row['identity_status'],
        'xml_person_id_if_available':row['person_id'],
        'presiding_issuer':row['issuer'],
        'issuer_evidence':row['issuer_evidence'],
        'is_separately_confirmed_effective_sanction':False,
    }


def legal_hints(root, session, subject=None):
    """Source mentions only. Same-session hits need not refer to subject."""
    found=[]
    for node,text in iter_session_text(root):
        hit=classify_signal(text)
        if hit is None:
            continue
        if subject is not None and norm(subject) not in norm(text):
            # Later protocols: accept only the explicit FULL name.
            # Same surnames (e.g. Reichardt) are not unique enough.
            continue
        found.append({
            'source_session':session,
            'xml_line':int(node.sourceline),
            'signal_type':hit[0],
            'signal_terms':hit[1],
            'original_text_excerpt':text[:800],
            'text_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'original_xml':f'{HOST}/21{session:03d}.xml',
            'person_and_legal_outcome_not_verified':True,
        })
    return found


def assemble(roots, dip, reviewed, later_roots=None, last_scanned=None):
    """Require all 14 official protocols and the 18 fixed DIP controls."""
    validate_scope()
    if set(roots)!=set(TARGETS):
        raise ValueError('Nicht alle 14 amtlichen Originalprotokolle vorhanden')
    if later_roots is not None and (type(last_scanned)!=int or
                                   last_scanned<max(TARGETS) or
                                   set(later_roots)!=set(range(1,last_scanned+1))):
        raise ValueError('Unvollständiger Zeitraum für spätere Rechtsfolgensuche')
    dip_index={(x['session'],norm(x['person'])):x for x in dip['entries']}
    if not EXPECTED_KEYS.issubset(dip_index):
        raise ValueError('Amtliche DIP-Positivreferenzen fehlen oder wurden verändert')
    # Four independently curated Bundestag decisions. This index cannot
    # provide measures, change confirmed CSV rows or establish final validity.
    decision_index=validated_index()
    if not set(decision_index).issubset(EXPECTED_KEYS):
        raise ValueError('Rechtsfolgen-Beleg nicht den 18 Originalfällen zuordenbar')
    index=speaker_index(roots.values())
    entries=[]
    for session,names in sorted(TARGETS.items()):
        root=roots[session]
        if (root.get('wahlperiode')!='21'
                or int(root.get('sitzung-nr') or 0)!=session):
            raise ValueError(f'Fremdes Originalprotokoll: {session}')
        paragraphs={int(node.sourceline):text
                    for node,text in iter_session_text(root)}
        occurrences={}
        for event in events(Path(f'21{session:03d}.xml'),root=root,index=index):
            key=norm(event['person'])
            occurrences.setdefault(key,[]).append(event)
        session_signals=legal_hints(root,session)
        for person in names:
            key=(session,norm(person))
            control=dip_index[key]
            hits=occurrences.get(key[1],[])
            if not 1<=len(hits)<=MAX_SOURCE_PARAGRAPHS:
                raise ValueError(
                    f'Personelle Original-XML-Erteilungsstellen fehlen/mehrdeutig: {session} {person} ({len(hits)})')
            sources=[original_entry(x,paragraphs) for x in hits]
            lines=[x['xml_line'] for x in sources]
            if len(set(lines))!=len(lines):
                raise ValueError('Doppelte Erteilungszeile im Parser')
            if tuple(sorted(lines))!=ORIGINAL_LINES[key]:
                raise ValueError(
                    f'Amtliche Originalfundstellen verändert: 21/{session:03d} '
                    f'{person}, gesehen {sorted(lines)}, erwartet {ORIGINAL_LINES[key]}')
            if (control['reported_grants'] not in (1,2,3)
                    or control['official_transcript']!=f'{HOST}/21{session:03d}.pdf'):
                raise ValueError('DIP-Prüfgrundlage unplausibel')
            # Even the limited 14-original case corpus can reveal explicit
            # future-person legal keyword evidence (e.g. Hess 52 -> 53,
            # Przygodda 67 -> 68). It is NOT a complete follow-up search.
            available_later=later_roots if later_roots is not None else roots
            later=[]
            for later_session in sorted(s for s in available_later if s>session):
                later.extend(legal_hints(
                    available_later[later_session],later_session,subject=person))
                if len(later)>MAX_LEGAL_HINTS_PER_CASE:
                    raise ValueError('Zu viele spätere Rechtsfolgen-Signale für sichere Kurzakte')
            if len(session_signals)>MAX_LEGAL_HINTS_PER_CASE:
                # No silent truncation of potentially relevant material.
                raise ValueError('Zu viele Sitzungs-Rechtsfolgensignale für sichere Kurzakte')
            verified=reviewed.get(key,0)
            multiple_context=MULTI_PHRASE_EPISODES.get(key)
            if bool(multiple_context)!=(len(sources)>1):
                raise ValueError('Unerwartete Mehrfacherteilungsformulierung')
            if key==(94,norm('Cansin Köktürk')) and not (
                    verified==2 and control['reported_grants']==2):
                raise ValueError('21/094: zwei getrennt belegte Originalmaßnahmen fehlen')
            if key in MULTI_PHRASE_EPISODES and session in (51,65) and (
                    control['reported_grants']!=1):
                raise ValueError('Episodenprüfakte und DIP-Stichprobe nicht synchron')
            appeal=decision_index.get(key)
            # This links only a documented procedural REJECTION, not an
            # independent decision that any number of legal grants is valid.
            appeal_evidence=({**appeal,
                              'matched_original_person_session':True,
                              'confirms_number_of_effective_sanctions':False,
                              'changes_protected_ledger':False}
                             if appeal is not None else None)
            entries.append({
                'case_id':f'wp21-{session:03d}-{len(entries)+1:02d}',
                'person_for_review':person,
                'session':session,
                'original_pdf':f'{HOST}/21{session:03d}.pdf',
                'original_xml':f'{HOST}/21{session:03d}.xml',
                'dip_original_grants_reference':control['reported_grants'],
                'verified_effective_measures_in_preexisting_partial_ledger':verified,
                'distinct_parser_issuance_wordings':len(sources),
                'original_parser_sources':sources,
                'multiple_wordings_may_be_one_legal_episode':len(sources)>1,
                'original_wording_episode_relation_for_review':(
                    multiple_context if multiple_context else 'single_parser_wording_only'),
                'official_bundestag_appeal_decision':appeal_evidence,
                'official_appeal_status':(
                    'officially_documented_rejected_objection'
                    if appeal_evidence else 'no_individually_curated_appeal_decision'),

                'requires_independent_individual_issuance_review':True,
                'requires_separate_appeal_and_effectiveness_review':True,
                'same_sitting_legal_keyword_signals_not_person_attributed':session_signals,
                'later_sitting_explicit_full_name_legal_keyword_signals_unverified':later,
                'later_sittings_search_scope':(
                    f'official_xml_1_through_{last_scanned}' if later_roots is not None
                    else 'only_14_selected_original_sessions_not_exhaustive'),
                'no_keyword_match_does_not_prove_no_appeal':True,
                'automatic_confirmations_or_rescissions':0,
            })
    if len(entries)!=18 or len({(e['session'],norm(e['person_for_review']))
                              for e in entries})!=18:
        raise ValueError('Nicht genau 18 individuelle quellenbezogene Prüffälle')
    return {
        'status':'18_person_session_original_evidence_dossiers_review_only',
        'wahlperiode':21,
        'official_protocols_reviewed':len(roots),
        'person_session_cases':len(entries),
        'individual_original_grant_phrase_locations':sum(
            e['distinct_parser_issuance_wordings'] for e in entries),
        'multiple_wording_person_session_cases':sum(
            e['multiple_wordings_may_be_one_legal_episode'] for e in entries),
        'separately_officially_documented_rejected_appeals':sum(
            bool(e['official_bundestag_appeal_decision']) for e in entries),
        'appeal_decisions_are_not_automatic_sanction_confirmations':True,
        'later_protocols_searched':last_scanned if later_roots is not None else 0,
        'selected_original_protocols_checked_for_explicit_later_mentions':len(roots),
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'protected_public_counters_changed':False,
        'warning':('Vier individuell dokumentierte Einspruchszurückweisungen ' 
                   'werden als offizielle Verfahrensentscheidungen zugeordnet, '
                   'ohne Anzahl, Rechtswirksamkeit oder bestandskräftige '
                   'Einzelmaßnahmen automatisch zu bestätigen. '
                   'Amtliche Erteilungsformulierungen und DIP-Originalverweise sind keine '
                   'eigenständig geprüften rechtswirksamen Einzelereignisse. '
                   'Rechtsfolgen-Suchbegriffe können Personen und Zeitpunkte nur '
                   'als manuell zu prüfende Hinweise verbinden; fehlende Treffer '
                   'sind kein Beleg für fehlende Einsprüche oder Aufhebungen.'),
        'cases':entries,
    }


def collect(cache, ledger, dip_file, scan_summary=None):
    folder=Path(cache)
    roots={}
    for session in sorted(TARGETS):
        data=fetch(session,folder)
        if data is None:
            raise ValueError(f'Amtliches XML {session:03d} fehlt')
        roots[session]=safe_parse(data,session)
    later_roots=None
    last=None
    if scan_summary is not None:
        summary=json.loads(Path(scan_summary).read_text(encoding='utf-8'))
        last=summary.get('letzte_sitzung')
        if (summary.get('status')!='bereit' or type(last)!=int
                or last<max(TARGETS) or last>450
                or summary.get('untersuchte_sitzungen')!=last):
            raise ValueError('Kein vollständiger aktueller XML-Scan')
        later_roots={}
        for session in range(1,last+1):
            data=fetch(session,folder)
            if data is None:
                raise ValueError(f'XML {session:03d} aus vollständigem Scan fehlt')
            later_roots[session]=safe_parse(data,session)
    known,_=read_reviewed(ledger)
    return assemble(roots,reference(dip_file),known,later_roots,last)


def render_manual_review_brief(report):
    """Deterministic compact reviewer matrix, NEVER a public counter feed."""
    if (report.get('status')!='18_person_session_original_evidence_dossiers_review_only'
            or report.get('person_session_cases')!=18
            or len(report.get('cases',[]))!=18
            or report.get('separately_officially_documented_rejected_appeals')!=4
            or report.get('automatically_confirmed_effective_sanctions')!=0
            or report.get('automatically_rescinded_sanctions')!=0
            or report.get('protected_public_counters_changed')):
        raise ValueError('18er-Einzelprüfbericht ist nicht vollständig oder sicher')
    lines=[
        '# Hochprioritäre WP21-Einzelereignisprüfung (nicht bestätigte Statistik)',
        '',
        '**18 Person/Sitzung-Fälle; 21 belegte präsidiale Erteilungsformulierungen.',
        'Vier amtlich belegte Einspruchszurückweisungen, jedoch 0',
        'automatisch bestätigte oder aufgehobene Maßnahmen.**',
        '',
        'DIP-Einträge belegen nur ursprüngliche Erteilungen; ein einzelner XML-',
        'Absatz ist keine unabhängig bestätigte rechtswirksame Maßnahme.',
        'Auch das Fehlen eines hier kuratierten Einspruchsbelegs bedeutet',
        '**nicht**, dass nie ein Einspruch oder eine Aufhebung stattfand.',
        '',
        '| Sitzung | Person | XML-Zeilen | DIP: ursprüngliche Rufe | Geprüfter Teilbestand | Episode | Einspruchsbeleg |',
        '| --- | --- | --- | ---: | ---: | --- | --- |',
    ]
    decisions=0
    seen=set()
    for row in report['cases']:
        key=(row['session'],norm(row['person_for_review']))
        if key not in EXPECTED_KEYS or key in seen:
            raise ValueError('Unbekannter oder doppelter Fall in Prüfmatrix')
        seen.add(key)
        source_lines=tuple(sorted(x['xml_line'] for x in row['original_parser_sources']))
        if source_lines!=ORIGINAL_LINES[key]:
            raise ValueError('XML-Fundstellen in Prüfmatrix verändert')
        episode=row['original_wording_episode_relation_for_review']
        appeal=row['official_bundestag_appeal_decision']
        if appeal:
            decisions+=1
            if (appeal['outcome']!='einspruch_zurueckgewiesen'
                    or appeal['confirms_number_of_effective_sanctions']
                    or appeal['changes_protected_ledger']):
                raise ValueError('Unzulässige automatische Einspruchsfreigabe')
            appeal_text=f"[zurückgewiesen {appeal['decision_date']}]({appeal['source']})"
        else:
            appeal_text='Keine Einzelentscheidung in kuratierter Vierer-Auswahl'
        linked=' / '.join(str(i) for i in source_lines)
        if episode=='single_parser_wording_only':
            episode_text='Einzelne Parser-Textstelle; Wirksamkeit offen'
        elif key==(94,norm('Cansin Köktürk')):
            episode_text='Zwei bereits im Teilbestand getrennt belegte Rufe'
        else:
            episode_text='Mehrfachformulierungen: individuelle Zahl offen'
        lines.append(
            f"| 21/{row['session']:03d} | {row['person_for_review']} | {linked} | "
            f"{row['dip_original_grants_reference']} | "
            f"{row['verified_effective_measures_in_preexisting_partial_ledger']} | "
            f"{episode_text} | {appeal_text} |")
    if seen!=EXPECTED_KEYS or decisions!=4:
        raise ValueError('Prüfmatrix enthält nicht genau alle Hochprioritätsfälle')
    lines.extend([
        '',
        '## Nächste fachliche Prüfhandlungen',
        '',
        '- 21/051 Frohnmaier (L3979/L3981): klären, ob zwei präsidiale',
        '  Formulierungen eine oder mehrere rechtlich eigenständige Erteilungen ergeben.',
        '- 21/065 Reichardt (L2044/L2046): Wiederholung derselben Erteilung',
        '  versus getrennte Maßnahme prüfen; Einspruchszurückweisung ist kein Zählbeweis.',
        '- 21/094 Köktürk (L1130/L1140): die bereits getrennt geprüften zwei',
        '  Ordnungsrufe mit Quellen verknüpft lassen; Ordnungsgeld nicht hinzuzählen.',
        '- Für weitere 14 Fälle fehlen in diesem eng kuratierten Index',
        '  individuelle Einspruchsentscheidungen: breitere DIP-/Originalquellensuche',
        '  fortsetzen, ohne aus fehlenden Treffern auf Rechtswirksamkeit zu schließen.',
        '',
        '**Keine automatische Veröffentlichung, keine Zähleränderung, keine Rechtsfreigabe.**',
        '',
    ])
    return '\n'.join(lines)


def run(cache,output,ledger,dip_file,scan_summary=None,brief=None):
    report=collect(cache,ledger,dip_file,scan_summary)
    target=Path(output)
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(target.suffix+'.tmp')
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',
                   encoding='utf-8')
    tmp.replace(target)
    if brief is not None:
        rendered=render_manual_review_brief(report)
        dest=Path(brief)
        dest.parent.mkdir(parents=True,exist_ok=True)
        safe=dest.with_suffix(dest.suffix+'.tmp')
        safe.write_text(rendered,encoding='utf-8')
        safe.replace(dest)
    print(f"HOCHPRIORITAET_18_OK: {report['person_session_cases']} "
          f"Personen/Sitzungen, {report['individual_original_grant_phrase_locations']} "
          "Original-XML-Erteilungsformulierungen; keine neuen bestätigten Maßnahmen.",
          flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,default=Path('.audit/wp21'))
    p.add_argument('--output',type=Path,default=Path('.audit/wp21_hochprioritaet_18.json'))
    p.add_argument('--ledger',type=Path,default=Path('daten/wirksame_ordnungsrufe_21wp.csv'))
    p.add_argument('--dip',type=Path,
                   default=Path('tests/fixtures/official_dip_wp21_positive_snapshot.json'))
    p.add_argument('--scan-summary',type=Path,
                   help='Only a validated, contiguous source scan permits later-session hints')
    p.add_argument('--brief',type=Path,
                   help='Human-readable separate review matrix; never confirmed counters')
    a=p.parse_args()
    run(a.cache,a.output,a.ledger,a.dip,a.scan_summary,a.brief)


if __name__=='__main__':
    main()
