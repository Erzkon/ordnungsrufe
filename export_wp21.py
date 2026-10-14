#!/usr/bin/env python3
"""Publish only individually source-reviewed 21st-term sanctions (incomplete ledger).

NOT a parser of automatic candidates. New rows require independent manual review.
"""
import argparse
import csv
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

COLUMNS = ('ereignis_id', 'datum', 'wahlperiode', 'sitzung', 'person',
           'fraktion_zur_sitzung', 'beleg', 'pruefvermerk')


def valid_21_pdf(value, session):
    url = urlsplit(value)
    return (url.scheme == 'https' and url.netloc == 'dserver.bundestag.de'
            and url.path == f'/btp/21/21{session:03d}.pdf'
            and not url.query and re.fullmatch(r'page=[1-9][0-9]*', url.fragment) is not None)


def build(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(COLUMNS):
            raise ValueError('Quellenliste 21: unerwartete Spalten')
        rows = list(reader)
    if not rows:
        raise ValueError('Quellenliste 21 darf nicht leer sein; kein Null-Gesamtstand vortaeuschen')
    records = []
    ids = set()
    for i, row in enumerate(rows, start=2):
        if None in row or not all(v and v.strip() for v in row.values()):
            raise ValueError(f'Zeile {i}: Angaben oder Pruefvermerk fehlen')
        if row['wahlperiode'] != '21' or not re.fullmatch(r'21-\d{3}-[a-z0-9-]+', row['ereignis_id']):
            raise ValueError(f'Zeile {i}: Wahlperiode oder Ereignis-ID ungueltig')
        session = int(row['sitzung'])
        if not 1 <= session <= 450 or row['ereignis_id'][3:6] != f'{session:03d}':
            raise ValueError(f'Zeile {i}: Sitzungsnummer passt nicht zur Ereignis-ID')
        if not valid_21_pdf(row['beleg'], session):
            raise ValueError(f'Zeile {i}: PDF-Fundstelle muss zur Sitzung passen')
        if row['ereignis_id'] in ids:
            raise ValueError(f'Zeile {i}: doppelte Ereignis-ID')
        ids.add(row['ereignis_id'])
        dt = datetime.strptime(row['datum'], '%d.%m.%Y').date()
        if not date(2025,3,25) <= dt <= date.today():
            raise ValueError(f'Zeile {i}: Datum ungueltig')
        if any(x in row['person'] for x in ('<', '>', '\n')):
            raise ValueError(f'Zeile {i}: unerlaubte Personenschreibweise')
        records.append({
            'event_id': row['ereignis_id'], 'date': dt.isoformat(),
            'session': session, 'person_id': '', 'person': row['person'].strip(),
            'group': row['fraktion_zur_sitzung'].strip(), 'source': row['beleg']
        })
    records.sort(key=lambda x:(x['date'], x['session'], x['event_id']))
    return {
        'meta': {
            'legislature': 21, 'period': 'seit 2025',
            'snapshot_date': '2026-10-14', 'count': len(records),
            'events': len({r['event_id'] for r in records}),
            'people': len({r['person'] for r in records}),
            'rescinded_excluded': 0,
            'provisional': True, 'incomplete': True,
            'note': 'Dies ist eine kleine, einzeln überprüfte Anfangsauswahl, ausdrücklich KEINE vollständige Statistik der 21. Wahlperiode. Weitere Protokolle werden nach und nach geprüft. Automatische Hinweise zählen nicht mit.',
            'sources': {'bundestag': 'https://www.bundestag.de/services/opendata',
                        'methodology': 'https://github.com/Erzkon/ordnungsrufe/blob/main/WP21.md'}
        }, 'records': records,
    }


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', default='daten/wirksame_ordnungsrufe_21wp.csv')
    ap.add_argument('--output', default='docs/data/ordnungsrufe_21.json')
    ap.add_argument('--check', action='store_true')
    args=ap.parse_args()
    payload=json.dumps(build(args.input),ensure_ascii=False,indent=2)+'\n'
    target=Path(args.output)
    if args.check:
        if not target.is_file() or target.read_text(encoding='utf-8') != payload:
            raise SystemExit('21. Wahlperiode: CSV/JSON-Snapshot inkonsistent')
        print('OK: 21. Wahlperiode geprüfte Teilmenge konsistent')
    else:
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(payload,encoding='utf-8')
        print(f'{len(json.loads(payload)["records"])} einzeln gepruefte Eintraege (unvollstaendig)')

if __name__=='__main__': main()
