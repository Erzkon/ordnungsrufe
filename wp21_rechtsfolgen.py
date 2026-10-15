#!/usr/bin/env python3
"""Source-only signals about appeals, reversals and disputes in WP21 protocols.

Never rescind or approve a sanction automatically. A paragraph may reference
an earlier event or another law; output is an audit candidate, not legal status.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from parser import iter_session_text
from wp21_scan import safe_parse

FIELDS = ('signal_id','sitzung','datum','xml_zeile','kategorie','ausloeser',
          'protokoll_url','xml_url','textauszug')

# Never infer approval or final outcome from mere mention of "Einspruch".
ORDNUNG = re.compile(r'\bOrdnungsruf(?:e|es|en)?\b', re.I)
APPEAL = re.compile(r'\bEinspr(?:u|ü)ch(?:e|en|s)?\b', re.I)
RETRACT = re.compile(r'\b(?:zurückgenommen|zurückgezogen|aufgehoben|'
                     r'aufheben|widerrufen|widerrufen[enr]?|zurücknehme(?:n)?)\b', re.I)
REJECT = re.compile(r'\b(?:zurückgewiesen|abgewiesen|abgelehnt|'
                    r'keine\s+Mehrheit|nicht\s+stattgegeben|zurückzuweisen)\b', re.I)
CHALLENGE = re.compile(r'\b(?:überprüf(?:en|t|ung)|Geschäftsordnung|'
                       r'Präsidium\s+entscheid|beantrag(?:e|t|en))\b', re.I)


def classify_signal(text):
    """Only identify possible follow-up decisions explicitly mentioning an Ordnungsruf.

    Multiple opposing signals in one paragraph MUST remain ambiguous.
    """
    if not ORDNUNG.search(text):
        return None
    tags = []
    if APPEAL.search(text):
        tags.append('einspruch')
    if RETRACT.search(text):
        tags.append('moegliche_ruecknahme')
    if REJECT.search(text):
        tags.append('moegliche_zurueckweisung')
    if CHALLENGE.search(text):
        tags.append('pruefung')
    if not tags:
        return None
    return ('mehrdeutig' if len(tags) > 1 else tags[0], '+'.join(tags))


def extract_signals(files):
    rows = []
    seen = set()
    for session, path in enumerate(files, start=1):
        root = safe_parse(Path(path).read_bytes(), session)
        for node, text in iter_session_text(root):
            info = classify_signal(text)
            if not info:
                continue
            line = node.sourceline
            if not isinstance(line, int) or line < 1:
                raise ValueError('Signal ohne XML-Quellenzeile')
            digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
            ident = f'21-{session:03d}-L{line}-{digest}'
            if ident in seen:
                raise ValueError('Doppeltes Quellensignal')
            seen.add(ident)
            rows.append({
                'signal_id': ident,
                'sitzung': str(session),
                'datum': root.get('sitzung-datum'),
                'xml_zeile': str(line),
                'kategorie': info[0],
                'ausloeser': info[1],
                'protokoll_url': f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf',
                'xml_url': f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml',
                'textauszug': text[:800],
            })
    rows.sort(key=lambda r: (int(r['sitzung']), int(r['xml_zeile'])))
    return rows


def build_report(rows, scanned, timestamp):
    parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Zeitstempel ohne Zeitzone')
    totals = Counter(row['kategorie'] for row in rows)
    return {
        'wahlperiode': 21, 'status': 'ungepruefte_rechtsfolgen_hinweise',
        'letzter_Quellenscan_utc': timestamp, 'gescannte_sitzungen': scanned,
        'textstellen_gesamt': len(rows),
        'nach_kategorie': dict(sorted(totals.items())),
        'automatisch_zurueckgenommene_massnahmen': 0,
        'automatisch_zurueckgewiesene_einsprueche': 0,
        'hinweis': ('Schluesselwortfunde sind KEIN Beleg einer wirksamen Ruecknahme '
                    'oder eines beschiedenen Einspruchs. Historische Verweise, '
                    'Verfahrensdetails und spaetere Beschluesse sind separat zu pruefen.'),
    }


def run(cache_dir, summary_file, out_csv, out_json):
    from wp21_autopruefung import roots_from_cache
    summary = json.loads(Path(summary_file).read_text(encoding='utf-8'))
    last = summary.get('letzte_sitzung')
    if (summary.get('status') != 'bereit' or type(last) is not int
            or summary.get('untersuchte_sitzungen') != last):
        raise ValueError('Unvollstaendiger oder ungueltiger Quellenscan')
    files = roots_from_cache(cache_dir, last)
    rows = extract_signals(files)
    report = build_report(rows, last, summary['zuletzt_geprueft_utc'])
    csv_path = Path(out_csv)
    json_path = Path(out_json)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                         encoding='utf-8')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache-dir', type=Path, default=Path('.cache/wp21'))
    ap.add_argument('--source-summary', type=Path, default=Path('docs/data/scan_21.json'))
    ap.add_argument('--candidates', type=Path, default=Path('wp21_rechtsfolgen_hinweise.csv'))
    ap.add_argument('--report', type=Path, default=Path('docs/data/rechtsfolgen_21.json'))
    options = ap.parse_args()
    status = run(options.cache_dir, options.source_summary,
                 options.candidates, options.report)
    print(f"{status['textstellen_gesamt']} Rechtsfolgen-Fundstellen; "
          "0 automatische Ruecknahmen oder Einspruchsentscheidungen.")


if __name__ == '__main__':
    main()
