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
MAX_SOURCE_PARAGRAPHS = 5
MAX_LEGAL_HINTS_PER_CASE = 12


def validate_scope():
    if (len(TARGETS)!=14 or len(EXPECTED_KEYS)!=18
            or sum(map(len,TARGETS.values()))!=18):
        raise ValueError('Hochprioritäts-Stichprobe verändert, Neuprüfung nötig')
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
            if (control['reported_grants'] not in (1,2,3)
                    or control['official_transcript']!=f'{HOST}/21{session:03d}.pdf'):
                raise ValueError('DIP-Prüfgrundlage unplausibel')
            later=[]
            if later_roots is not None:
                for later_session in range(session+1,last_scanned+1):
                    later.extend(legal_hints(
                        later_roots[later_session],later_session,subject=person))
                    if len(later)>MAX_LEGAL_HINTS_PER_CASE:
                        raise ValueError('Zu viele spätere Rechtsfolgen-Signale für sichere Kurzakte')
            if len(session_signals)>MAX_LEGAL_HINTS_PER_CASE:
                # No silent truncation of potentially relevant material.
                raise ValueError('Zu viele Sitzungs-Rechtsfolgensignale für sichere Kurzakte')
            verified=reviewed.get(key,0)
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
                'requires_independent_individual_issuance_review':True,
                'requires_separate_appeal_and_effectiveness_review':True,
                'same_sitting_legal_keyword_signals_not_person_attributed':session_signals,
                'later_sitting_explicit_full_name_legal_keyword_signals_unverified':later,
                'later_sittings_search_scope':(
                    f'official_xml_1_through_{last_scanned}' if later_roots is not None
                    else 'not_checked_outside_original_sitting'),
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
        'later_protocols_searched':last_scanned if later_roots is not None else 0,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'protected_public_counters_changed':False,
        'warning':('Amtliche Erteilungsformulierungen und DIP-Originalverweise sind keine '
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


def run(cache,output,ledger,dip_file,scan_summary=None):
    report=collect(cache,ledger,dip_file,scan_summary)
    target=Path(output)
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(target.suffix+'.tmp')
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',
                   encoding='utf-8')
    tmp.replace(target)
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
    a=p.parse_args()
    run(a.cache,a.output,a.ledger,a.dip,a.scan_summary)


if __name__=='__main__':
    main()
