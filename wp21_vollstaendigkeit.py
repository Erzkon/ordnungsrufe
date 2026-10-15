#!/usr/bin/env python3
"""Independent, strictly read-only coverage inventory for the 21st Bundestag term.

Distinguish (1) verified effective *measures*, (2) curated DIP claims about
original grants, (3) parser person/session *mentions* and (4) XML text locations.
None is automatically interchangeable with any other, nor is the curated DIP
sample a census. Never write to reviewed CSVs or the published counters.
"""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from wp21_autopruefung import norm, read_reviewed
from wp21_dip_kontrolle import REFERENCE, reference
from wp21_scan import HOST

FIELDS = ('fall_id', 'prioritaet', 'typ', 'sitzung', 'person', 'xml_zeile',
          'bestaetigte_massnahmen_teilbestand', 'dip_urspruengliche_erteilungen_stichprobe',
          'parser_person_sitzung_vorhanden', 'parser_fundstellen',
          'xml_textstellen_in_sitzung', 'grund', 'protokoll', 'dip_index')
VALID_CLASSES = {'possible_grant','named_group_confirmation','appeal_or_retrospective',
                 'warning_or_conditional','retrospective_reference','mention_or_unclear'}
MAX_ROWS = 20000
PUBLIC_LIMIT = 30


def csv_rows(path, required):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if (not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames))
                or not set(required).issubset(reader.fieldnames)):
            raise ValueError('Audit: CSV-Spalten fehlen oder sind doppelt')
        rows = list(reader)
    if len(rows) > MAX_ROWS or any(None in row for row in rows):
        raise ValueError('Audit: CSV beschädigt oder Sicherheitsgrenze erreicht')
    return rows


def scan_lines(path, last):
    rows = csv_rows(path, {'hinweis_id','sitzung','xml_zeile','klasse',
                           'xml_quelle','pdf_quelle','status'})
    keyed = {}
    ids = set()
    for row in rows:
        try:
            session = int(row['sitzung'])
            line = int(row['xml_zeile'])
        except (TypeError, ValueError) as exc:
            raise ValueError('Audit: XML-Zeile/Sitzung ungültig') from exc
        ident = row['hinweis_id']
        if (not 1 <= session <= last or line < 1
                or not re.fullmatch(r'21-\d{3}-L\d+-[a-f0-9]{12}',ident)
                or not ident.startswith(f'21-{session:03d}-L{line}-')
                or row['klasse'] not in VALID_CLASSES
                or row['status'] != 'manuelle_pruefung_erforderlich'
                or row['xml_quelle'] != f'{HOST}/21{session:03d}.xml'
                or row['pdf_quelle'] != f'{HOST}/21{session:03d}.pdf'
                or ident in ids):
            raise ValueError('Audit: Ungültiger, fremder oder doppelter XML-Hinweis')
        ids.add(ident)
        keyed[(session,line)] = keyed.get((session,line),[]) + [row]
    return keyed, len(rows)


def person_hints(path, last):
    rows = csv_rows(path, {'hinweis_id','sitzung','xml_zeile','person_vorschlag',
                           'klassifikation','pruefstatus','protokoll_21'})
    by_person=defaultdict(list)
    lines=defaultdict(list)
    ids=set()
    for row in rows:
        try:
            session=int(row['sitzung'])
            line=int(row['xml_zeile'])
        except (TypeError, ValueError) as exc:
            raise ValueError('Audit: Parser-Sitzung/Zeile ungültig') from exc
        person=norm(row['person_vorschlag'])
        ident=row['hinweis_id']
        if (not 1 <= session <= last or line < 1 or not person
                or not re.fullmatch(r'21-\d{3}-L\d+-[a-f0-9]{10}',ident)
                or not ident.startswith(f'21-{session:03d}-L{line}-')
                or row['klassifikation'] not in VALID_CLASSES
                or row['pruefstatus'] not in {'offen','referenz_abgeglichen'}
                or row['protokoll_21'] != f'{HOST}/21{session:03d}.pdf'
                or ident in ids):
            raise ValueError('Audit: Ungültiger oder doppelter Parser-Hinweis')
        ids.add(ident)
        key=(session,person)
        by_person[key].append(row)
        lines[(session,line)].append(row)
    return by_person,lines,len(rows)


def audited_summary(scan_report, parser_report, hints_count, parser_count):
    if (scan_report.get('status')!='bereit'
            or type(scan_report.get('letzte_sitzung')) is not int
            or not 1 <= scan_report['letzte_sitzung'] <= 450
            or scan_report.get('untersuchte_sitzungen') != scan_report['letzte_sitzung']
            or type(scan_report.get('textstellen_zur_pruefung')) is not int
            or scan_report['textstellen_zur_pruefung'] != hints_count
            or parser_report.get('status') != 'automatische_vorpruefung_ohne_freigabe'
            or parser_report.get('gescannte_sitzungen') != scan_report['letzte_sitzung']
            or parser_report.get('parser_personenhinweise') != parser_count
            or parser_report.get('letzter_Quellenscan_utc') !=
               scan_report.get('zuletzt_geprueft_utc')):
        raise ValueError('Audit: XML-/Parser-Snapshot nicht synchron oder unvollständig')
    stamp=datetime.fromisoformat(scan_report['zuletzt_geprueft_utc'].replace('Z','+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Audit: fehlende Zeitzone')
    return scan_report['letzte_sitzung'],stamp.isoformat(timespec='seconds')


def build_cases(verified, dip, parser, xml_lines, last):
    """Reference cases are per-person/session; XML rows are per-text-location."""
    dip_by_key={(x['session'],norm(x['person'])):x for x in dip['entries']}
    persons=set(verified)|set(dip_by_key)|set(parser)
    xml_by_session=Counter(session for session,_ in xml_lines)
    cases=[]
    missing_verified=missing_dip=multiple=0
    for session,person_key in sorted(persons):
        # Never declare a source false-negative if that session was not scanned.
        if session > last:
            continue
        key=(session,person_key)
        verified_count=verified.get(key,0)
        dip_row=dip_by_key.get(key)
        dip_count=dip_row['reported_grants'] if dip_row else 0
        proposed=parser.get(key,[])
        if verified_count > 1 or dip_count > 1:
            multiple+=1
        if verified_count and not proposed:
            missing_verified+=1
        if dip_row and not proposed:
            missing_dip+=1
        if dip_row and verified_count < dip_count:
            priority='hoch'
            reason='DIP-Auswahl nennt ursprüngliche Erteilungen, die im bestätigten Teilbestand nicht vollständig einzeln belegt sind'
        elif verified_count and not proposed:
            priority='hoch'
            reason='Einzeln bestätigte Referenz ohne Parser-Person/Sitzung-Hinweis: mögliche Erkennungslücke'
        elif dip_row and not proposed:
            priority='hoch'
            reason='DIP-Positivkontrolle ohne Parser-Person/Sitzung-Hinweis: mögliche Erkennungslücke'
        elif verified_count > 1 or dip_count > 1:
            priority='hoch'
            reason='Mehrfachvergabe in Person/Sitzung: Parser-Erwähnung belegt keine einzelnen Ereignisse'
        elif not dip_row and not verified_count:
            priority='mittel'
            reason='Parser-Person/Sitzung nicht unabhängig in dieser Referenzauswahl belegt'
        else:
            priority='niedrig'
            reason='Referenz-Person/Sitzung erscheint im Parser; getrennte Maßnahmen/Rechtsfolgen bleiben unabhängig zu prüfen'
        display=(dip_row['person'] if dip_row else proposed[0]['person_vorschlag']
                 if proposed else person_key)
        cases.append({
            'fall_id':f'person-{session:03d}-{len(cases)+1:05d}',
            'prioritaet':priority,'typ':'person_sitzung_ohne_einzelereignisabgleich',
            'sitzung':str(session),'person':display,'xml_zeile':'',
            'bestaetigte_massnahmen_teilbestand':str(verified_count),
            'dip_urspruengliche_erteilungen_stichprobe':str(dip_count) if dip_row else '',
            'parser_person_sitzung_vorhanden':'ja' if proposed else 'nein',
            'parser_fundstellen':str(len(proposed)),
            # Session-level count MUST NOT imply attribution to this person.
            'xml_textstellen_in_sitzung':str(xml_by_session[session]),
            'grund':reason,
            'protokoll':f'{HOST}/21{session:03d}.pdf',
            'dip_index':dip['official_index'] if dip_row else '',
        })
    # Every XML text location without any person-linked parser event remains
    # visible. Warnings/appeals are not missed grants by default.
    parser_lines={line for line in xml_lines if line in {loc
                   for rows in parser.values() for loc in
                   [(int(p['sitzung']),int(p['xml_zeile'])) for p in rows]}}
    unlinked=0
    for (session,line),rows in sorted(xml_lines.items()):
        if (session,line) in parser_lines:
            continue
        unlinked+=len(rows)
        high=any(x['klasse'] in {'possible_grant','named_group_confirmation'}
                 for x in rows)
        categories=','.join(sorted({row['klasse'] for row in rows}))
        cases.append({
            'fall_id':f'xml-{session:03d}-L{line}',
            'prioritaet':'hoch' if high else 'mittel',
            'typ':'xml_textstelle_ohne_person_parser',
            'sitzung':str(session),'person':'','xml_zeile':str(line),
            'bestaetigte_massnahmen_teilbestand':'',
            'dip_urspruengliche_erteilungen_stichprobe':'',
            'parser_person_sitzung_vorhanden':'nein',
            'parser_fundstellen':'0','xml_textstellen_in_sitzung':'1',
            'grund':'XML-Klasse: '+categories+'; ohne sichere Person/Einzelmaßnahme',
            'protokoll':f'{HOST}/21{session:03d}.pdf','dip_index':'',
        })
    priority={'hoch':0,'mittel':1,'niedrig':2}
    cases.sort(key=lambda row:(priority[row['prioritaet']],
                               -int(row['sitzung']),row['fall_id']))
    if len(cases)>MAX_ROWS:
        raise ValueError('Audit: Anzahl Prüffälle überschreitet Sicherheitslimit')
    return cases,{'confirmed_keys_without_parser':missing_verified,
                  'dip_sample_keys_without_parser':missing_dip,
                  'multiple_measure_person_session_keys':multiple,
                  'xml_text_locations_without_person_parser':unlinked}


def inventory(scan_report, parser_report, xml_csv, parser_csv, reviewed_csv, dip_path):
    known,verified_total=read_reviewed(reviewed_csv)
    dip=reference(dip_path)
    scanned=scan_report.get('letzte_sitzung')
    if type(scanned) is not int or not 1 <= scanned <= 450:
        raise ValueError('Audit: Zahl gescannter Sitzungen ungültig')
    xml_lines,hints_count=scan_lines(xml_csv,scanned)
    proposals,parser_lines,parser_count=person_hints(parser_csv,scanned)
    last,stamp=audited_summary(scan_report,parser_report,hints_count,parser_count)
    orphan=set(parser_lines)-set(xml_lines)
    if orphan:
        # The parser and XML text extractor must agree on origin location.
        # Otherwise no coverage claim can be made.
        raise ValueError('Audit: Parser-Textstelle ohne XML-Quelle: '+str(sorted(orphan)[:5]))
    rows,metrics=build_cases(known,dip,proposals,xml_lines,last)
    indexed=[x for x in dip['entries'] if x['session']<=last]
    missing_grants=sum(max(0,x['reported_grants']-known.get(
        (x['session'],norm(x['person'])),0)) for x in indexed)
    result={
        'wahlperiode':21,'status':'quellenvollstaendigkeit_ohne_automatische_freigabe',
        'last_success_utc':stamp, 'sessions_scanned':last,
        'verified_effective_measures_in_partial_ledger':verified_total,
        'verified_person_session_keys_within_scanned_sessions':
            sum(s<=last for s,_ in known),
        'verified_person_session_keys_outside_scan':
            sum(s>last for s,_ in known),
        'dip_sample_person_session_keys_within_scan':len(indexed),
        'dip_sample_person_session_keys_outside_scan':len(dip['entries'])-len(indexed),
        'dip_sample_reported_original_grants_within_scan':
            sum(x['reported_grants'] for x in indexed),
        'dip_sample_grants_not_in_verified_partial_ledger':missing_grants,
        'xml_text_locations':hints_count,
        'parser_person_hints':parser_count,
        'parser_distinct_person_session_keys':len(proposals),
        'parser_locations_without_xml_candidate':len(orphan),
        **metrics,
        'review_cases_total':len(rows),
        'high_priority_cases':sum(row['prioritaet']=='hoch' for row in rows),
        'medium_priority_cases':sum(row['prioritaet']=='mittel' for row in rows),
        'shown':min(len(rows),PUBLIC_LIMIT),
        'items':rows[:PUBLIC_LIMIT],
        'automatically_confirmed_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'warning':('Nur geprüfter Teilbestand + kuratierte DIP-Positivstichprobe + '
                   'XML-/Parser-Textstellen. Kein negativer Goldstandard, keine '
                   'Gesamtvollständigkeitsquote. Pro Person/Sitzung können mehrere '
                   'Ordnungsrufe existieren; Textstellen belegen keine einzelnen '
                   'rechtswirksamen Maßnahmen. Ungeprüfte Daten ändern keine Zähler.'),
    }
    return rows,result


def run(scan_summary,parser_report,xml_csv,parser_csv,verified,dip_path,full_out,public_out):
    scan=json.loads(Path(scan_summary).read_text(encoding='utf-8'))
    parsed=json.loads(Path(parser_report).read_text(encoding='utf-8'))
    rows,result=inventory(scan,parsed,xml_csv,parser_csv,verified,dip_path)
    # All source parsing/validation must finish BEFORE any output is replaced.
    target=Path(full_out)
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(target.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(target)
    report=Path(public_out)
    report.parent.mkdir(parents=True,exist_ok=True)
    temp=report.with_suffix(report.suffix+'.tmp')
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(report)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--scan-summary',type=Path,default=Path('docs/data/scan_21.json'))
    ap.add_argument('--parser-report',type=Path,default=Path('docs/data/autopruefung_21.json'))
    ap.add_argument('--xml-candidates',type=Path,default=Path('wp21_hinweise.csv'))
    ap.add_argument('--parser-candidates',type=Path,default=Path('wp21_autopruefung.csv'))
    ap.add_argument('--verified',type=Path,default=Path('daten/wirksame_ordnungsrufe_21wp.csv'))
    ap.add_argument('--dip-reference',type=Path,default=REFERENCE)
    ap.add_argument('--full',type=Path,default=Path('wp21_vollstaendigkeit_faelle.csv'))
    ap.add_argument('--report',type=Path,default=Path('docs/data/vollstaendigkeit_21.json'))
    args=ap.parse_args()
    result=run(args.scan_summary,args.parser_report,args.xml_candidates,
               args.parser_candidates,args.verified,args.dip_reference,
               args.full,args.report)
    print('XML/DIP-Vollständigkeits-Audit:',result['review_cases_total'],
          'Quellen-Prüffälle,',result['high_priority_cases'],'hohe Priorität;',
          '0 automatische Zähleränderungen.')


if __name__=='__main__':
    main()
