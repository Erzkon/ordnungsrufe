#!/usr/bin/env python3
"""Fail-closed, read-only WP21 person/event triage against confirmed reference.

This is NOT an automated approval mechanism. No result is written to the
verified CSV/JSON that powers the public counters. A parser is not evidence of
a final, legally effective sanction (appeals/retractions can come later).
"""
import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

from parser import (APPEAL, FUTURE_ONLY, GENERIC_FUTURE, PAST, THREAT,
                    events, speaker_index)
from wp21_scan import safe_parse

FIELDS = (
    'hinweis_id', 'sitzung', 'datum', 'person_vorschlag', 'xml_person_id',
    'fraktion_vorschlag', 'xml_zeile', 'klassifikation',
    'zuordnungsmethode', 'identitaet', 'prioritaet', 'grund',
    'pruefstatus', 'protokoll_21', 'textauszug',
)


def norm(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                           if not unicodedata.combining(c)).split())


def read_reviewed(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        required = {'sitzung', 'person', 'ereignis_id', 'wahlperiode', 'beleg'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError('Quellengepruefte CSV hat nicht das erwartete Schema')
        rows = list(reader)
    if not rows or any(None in row.values() for row in rows):
        raise ValueError('Leere oder ungueltige Referenzdaten')
    known = {}
    event_ids = set()
    for row in rows:
        session = int(row['sitzung'])
        if row['wahlperiode'] != '21' or not 1 <= session <= 450:
            raise ValueError('Referenzdaten falscher Wahlperiode')
        if row['ereignis_id'] in event_ids:
            raise ValueError('Doppelte Referenz-Ereignis-ID')
        event_ids.add(row['ereignis_id'])
        key = (session, norm(row['person']))
        if not key[1]:
            raise ValueError('Leere Person in Referenzdaten')
        known[key] = known.get(key, 0) + 1
    return known, len(rows)


def roots_from_cache(folder, end):
    """Use only contiguous, validated official transcripts; never a partial scan."""
    if not 1 <= end <= 450:
        raise ValueError('Ungueltige letzte Sitzung')
    files = []
    for n in range(1, end + 1):
        path = Path(folder) / f'21{n:03d}.xml'
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'Quellenluecke: Protokoll 21/{n:03d} fehlt')
        files.append(path)
    return files


def extract_proposals(files, reviewed):
    # Index speakers across all available sittings, as the existing
    # conservative extractor does. The index is only an identity *hint*.
    index = speaker_index(safe_parse(path.read_bytes(), n)
                          for n, path in enumerate(files, start=1))
    proposals = []
    seen_ids = set()
    for session, path in enumerate(files, start=1):
        root = safe_parse(path.read_bytes(), session)
        for item in events(path, index=index, root=root):
            person = ' '.join(item['person'].split())
            person_id = item['person_id']
            identity = item['identity_status']
            method = item['zuordnungsmethode']
            source_line = int(item['line'])
            text = item['text']
            if not person or not 1 <= source_line or len(text) > 1200:
                raise ValueError('Beschaedigte Parser-Ausgabe')
            digest = hashlib.sha256((person_id or norm(person)).encode('utf-8')).hexdigest()[:10]
            hint_id = f'21-{session:03d}-L{source_line}-{digest}'
            if hint_id in seen_ids:
                raise ValueError('Parser-Hinweis nicht eindeutig')
            seen_ids.add(hint_id)
            known = (session, norm(person)) in reviewed
            # Explicit named recipients are better review candidates, but
            # not reliable enough to count as confirmed sanctions.
            direct = (identity == 'matched_xml_person'
                      and bool(re.fullmatch(r'\d{8}', person_id))
                      and method in ('explizit_gegen', 'expliziter_dativ',
                                     'benannter_empfaenger')
                      and item['evidence_type'] == 'possible_grant'
                      and not any(pattern.search(text) for pattern in
                                  (THREAT, APPEAL, FUTURE_ONLY, GENERIC_FUTURE, PAST)))
            if known:
                priority, reason, status = (
                    'niedrig', 'Person/Sitzung bereits einzeln belegt; keine automatische Zweitzaehlung',
                    'referenz_abgeglichen')
            elif direct:
                priority, reason, status = (
                    'mittel', 'Explizite Empfaengerform mit XML-Identitaet; dennoch Quelle und Ruecknahmen pruefen',
                    'offen')
            else:
                priority, reason, status = (
                    'hoch', 'Identitaet, Erteilung oder Mehrfachvorgang ist nicht belastbar automatisch belegbar',
                    'offen')
            proposals.append({
                'hinweis_id': hint_id, 'sitzung': str(session),
                'datum': item['datum'], 'person_vorschlag': person,
                'xml_person_id': person_id, 'fraktion_vorschlag': item['fraktion'],
                'xml_zeile': str(source_line),
                'klassifikation': item['evidence_type'], 'zuordnungsmethode': method,
                'identitaet': identity, 'prioritaet': priority, 'grund': reason,
                'pruefstatus': status,
                'protokoll_21': f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf',
                'textauszug': text[:600],
            })
    # One person can legitimately receive multiple separate Ordnungsrufe per
    # sitting. Multiple parser locations are *not* proof of multiple grants.
    tally = Counter((r['sitzung'], norm(r['person_vorschlag']))
                    for r in proposals)
    for row in proposals:
        key = (row['sitzung'], norm(row['person_vorschlag']))
        if row['pruefstatus'] == 'offen' and tally[key] > 1:
            row['prioritaet'] = 'hoch'
            row['grund'] = 'Mehrere Textstellen zu Person/Sitzung: keine automatische Mehrfachzaehlung'
    rank = {'hoch': 0, 'mittel': 1, 'niedrig': 2}
    proposals.sort(key=lambda r: (rank[r['prioritaet']], -int(r['sitzung']),
                                  int(r['xml_zeile']), r['person_vorschlag']))
    return proposals


def make_report(rows, reviewed, reviewed_rows, scanned, last_scan):
    identified = {(int(r['sitzung']), norm(r['person_vorschlag']))
                  for r in rows}
    covered = sum(number for key, number in reviewed.items() if key in identified)
    missing = sum(number for key, number in reviewed.items() if key not in identified)
    return {
        'wahlperiode': 21,
        'status': 'automatische_vorpruefung_ohne_freigabe',
        'letzter_Quellenscan_utc': last_scan,
        'gescannte_sitzungen': scanned,
        'parser_personenhinweise': len(rows),
        'bereits_einzeln_belegte_massnahmen': reviewed_rows,
        'davon_referenz_person_sitzung_erkannt': covered,
        'davon_referenz_person_sitzung_nicht_erkannt': missing,
        'offene_personenhinweise': sum(r['pruefstatus'] == 'offen' for r in rows),
        'offene_prioritaet_hoch': sum(r['pruefstatus'] == 'offen' and r['prioritaet'] == 'hoch' for r in rows),
        'offene_prioritaet_mittel': sum(r['pruefstatus'] == 'offen' and r['prioritaet'] == 'mittel' for r in rows),
        'automatisch_freigegebene_ordnungsrufe': 0,
        'hinweis': ('Parser-Fundstellen sind keine geprueften Ordnungsrufe. '
                    'Referenzabgleich auf Person/Sitzung ist keine Eins-zu-eins-Ereignispruefung. '
                    'Keine automatische Veroeffentlichung von Personenstatistiken.'),
    }


def run(cache_dir, source_summary, verified, candidate_csv, report_json):
    scan = json.loads(Path(source_summary).read_text(encoding='utf-8'))
    end = scan.get('letzte_sitzung')
    if (scan.get('status') != 'bereit'
            or not isinstance(end, int)
            or scan.get('untersuchte_sitzungen') != end
            or not isinstance(scan.get('zuletzt_geprueft_utc'), str)):
        raise ValueError('Keine gueltige, vollstaendige Scan-Uebersicht vorhanden')
    datetime.fromisoformat(scan['zuletzt_geprueft_utc'].replace('Z', '+00:00'))
    files = roots_from_cache(cache_dir, end)
    reviewed, reviewed_rows = read_reviewed(verified)
    rows = extract_proposals(files, reviewed)
    report = make_report(rows, reviewed, reviewed_rows, end, scan['zuletzt_geprueft_utc'])
    candidate_csv = Path(candidate_csv)
    report_json = Path(report_json)
    candidate_csv.parent.mkdir(parents=True, exist_ok=True)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    # Do not output anything to daten/ or the confirmed website JSON.
    with candidate_csv.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                           encoding='utf-8')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache-dir', type=Path, default=Path('.cache/wp21'))
    ap.add_argument('--source-summary', type=Path, default=Path('docs/data/scan_21.json'))
    ap.add_argument('--verified', type=Path, default=Path('daten/wirksame_ordnungsrufe_21wp.csv'))
    ap.add_argument('--candidates', type=Path, default=Path('wp21_autopruefung.csv'))
    ap.add_argument('--report', type=Path, default=Path('docs/data/autopruefung_21.json'))
    opts = ap.parse_args()
    report = run(opts.cache_dir, opts.source_summary, opts.verified,
                 opts.candidates, opts.report)
    print(f"Vorpruefung: {report['parser_personenhinweise']} Parser-Hinweise, "
          f"{report['offene_personenhinweise']} offen, "
          "0 automatisch bestaetigte Massnahmen.")


if __name__ == '__main__':
    main()
