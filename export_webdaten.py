#!/usr/bin/env python3
"""Erzeugt deterministische JSON-Daten fuer die statische GitHub-Pages-Seite.

Quelle ist ausschliesslich die quellengepruefte, separat versionierte CSV.
Ausgenommene Ordnungsrufe werden NICHT in der Website exportiert.
"""
import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

REQUIRED = ('ereignis_id', 'datum', 'wahlperiode', 'sitzung', 'person_id',
            'person', 'fraktion_zur_sitzung', 'quell_url', 'beleg')
SOURCE_REPORT_KEYS = ('wirksame_massnahmen_in_arbeitsliste',
                      'bestaetigte_ereignis_ids', 'stephan_brandner',
                      'beatrix_von_storch', 'amtliche_personenzahl_beatrix_von_storch')
OFFICIAL_SOURCE = 'https://www.bundestag.de/dokumente/textarchiv/1949-09-20-ordnungsruf-1086652'
METHODOLOGY_SOURCE = 'https://www.bundestag.de/resource/blob/196296/08d0a21670ca40e45ecfdb242d119d58/Kapitel_07_16_Ordnungsma__nahmen-data.pdf'


def valid_proof(value):
    """Only release immutable official PDF source URLs, never unchecked strings."""
    u = urlsplit(value)
    return (u.scheme == 'https' and u.netloc == 'dserver.bundestag.de'
            and re.fullmatch(r'/btp/20/20\d{3}\.pdf', u.path) is not None
            and re.fullmatch(r'page=\d+', u.fragment) is not None
            and not u.query)


def build(csv_path, report_path):
    with Path(csv_path).open(newline='', encoding='utf-8-sig') as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or not set(REQUIRED).issubset(reader.fieldnames):
            raise ValueError('CSV: erforderliche Spalten fehlen')
        raw = list(reader)
    report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    if not set(SOURCE_REPORT_KEYS).issubset(report):
        raise ValueError('Kontrollbericht: wesentliche Kennzahlen fehlen')
    if not raw:
        raise ValueError('Leere Ausgangsdatei')
    records = []
    unique_pairs = set()
    for index, row in enumerate(raw, 2):
        if any(v is None for v in row.values()):
            raise ValueError(f'CSV-Zeile {index}: unvollstaendig')
        if row['wahlperiode'] != '20' or not re.fullmatch(r'\d{8}', row['person_id']):
            raise ValueError(f'CSV-Zeile {index}: falsche Wahlperiode oder Personen-ID')
        if not row['person'].strip() or not row['fraktion_zur_sitzung'].strip():
            raise ValueError(f'CSV-Zeile {index}: Person oder historische Zuordnung fehlt')
        if not valid_proof(row['beleg'].split(' | ')[0]):
            raise ValueError(f'CSV-Zeile {index}: ungueltiger Originalprotokoll-Beleg')
        sitzung = int(row['sitzung'])
        if not 1 <= sitzung <= 214:
            raise ValueError(f'CSV-Zeile {index}: ungueltige Sitzungsnummer')
        expected_pdf = f'/btp/20/20{sitzung:03d}.pdf'
        if expected_pdf not in row['beleg']:
            raise ValueError(f'CSV-Zeile {index}: Quellbeleg einer anderen Sitzung')
        date = datetime.strptime(row['datum'], '%d.%m.%Y').date()
        if not (datetime(2021, 10, 26).date() <= date <= datetime(2025, 3, 25).date()):
            raise ValueError(f'CSV-Zeile {index}: Datum ausserhalb der Wahlperiode')
        identity = row['ereignis_id'], row['person_id']
        if identity in unique_pairs:
            raise ValueError(f'CSV-Zeile {index}: doppelte Person/Ereignis-Kombination')
        unique_pairs.add(identity)
        records.append({
            'event_id': row['ereignis_id'],
            'date': date.isoformat(),
            'session': sitzung,
            'person_id': row['person_id'],
            'person': row['person'],
            'group': row['fraktion_zur_sitzung'],
            'source': row['beleg'].split(' | ')[0],
        })
    records.sort(key=lambda r: (r['date'], r['session'], r['event_id'], r['person_id']))
    count_by_name = Counter(r['person'] for r in records)
    event_count = len(set(r['event_id'] for r in records))
    expected = report['wirksame_massnahmen_in_arbeitsliste']
    if (len(records) != expected or event_count != report['bestaetigte_ereignis_ids']
        or count_by_name['Stephan Brandner'] != report['stephan_brandner']
        or count_by_name['Beatrix von Storch'] != report['beatrix_von_storch']):
        raise ValueError('CSV und unabhaengiger Korrekturbericht widersprechen sich')
    if expected != 135 or report['amtliche_personenzahl_beatrix_von_storch'] != 19:
        raise ValueError('20.-WP-Snapshot wurde ohne neue Quellenfreigabe veraendert')
    return {
        'meta': {
            'legislature': 20,
            'period': '2021–2025',
            'snapshot_date': '2026-10-14',
            'count': len(records),
            'events': event_count,
            'people': len({r['person_id'] for r in records}),
            'rescinded_excluded': report['zurueckgenommen'],
            'official_total': report['amtliche_statistik_wirksame_massnahmen'],
            'official_beatrix_von_storch': report['amtliche_personenzahl_beatrix_von_storch'],
            'verified_beatrix_von_storch': report['beatrix_von_storch'],
            'provisional': True,
            'note': ('Die Gesamtzahl stimmt mit der amtlichen Angabe ueberein. '
                     'Die Einzelzahl fuer Beatrix von Storch (18 quellengeprueft / 19 amtlich) '
                     'und eine moegliche DIP-Doppelregistrierung sind noch nicht abschliessend geklaert.'),
            'sources': {'bundestag': OFFICIAL_SOURCE, 'handbook': METHODOLOGY_SOURCE,
                        'methodology': 'https://github.com/Erzkon/ordnungsrufe/blob/main/QUELLENABGLEICH.md'},
        },
        'records': records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', default='daten/wirksame_ordnungsrufe_20wp.csv')
    parser.add_argument('--report', default='daten/korrekturbericht_20wp.json')
    parser.add_argument('--output', default='docs/data/ordnungsrufe.json')
    parser.add_argument('--check', action='store_true', help='Vergleich statt Dateiaenderung')
    options = parser.parse_args()
    payload = json.dumps(build(options.input, options.report), ensure_ascii=False, indent=2) + '\n'
    target = Path(options.output)
    if options.check:
        if not target.is_file() or target.read_text(encoding='utf-8') != payload:
            raise SystemExit('Webdaten nicht synchron: python export_webdaten.py erneut ausfuehren')
        print('OK: Quellen-Snapshot und Webdaten sind identisch.')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding='utf-8')
        print(f'Export: {len(json.loads(payload)["records"])} Eintraege -> {target}')


if __name__ == '__main__':
    main()
