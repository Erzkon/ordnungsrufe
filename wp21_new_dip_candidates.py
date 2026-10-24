#!/usr/bin/env python3
"""Read-only discovery of DIP source candidates beyond 18 pinned WP21 parents.

This inventory never adjudicates sanctions, creates counters or modifies source
data. A parent absent from PINS is NOT necessarily a new/valid Ordnungsruf.
The scan only covers documents returned by the chosen DIP update window.
"""
import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wp21_18_dip_original_beschluesse import PINS
from wp21_autopruefung import norm
from wp21_dip_kontrolle import reference
from wp21_dip_monitor import (
    PUBLIC_KEY, START, iso, paginate, relevant_item, request_page,
)

ROOT = Path(__file__).resolve().parent
AUDIT_ROOT = ROOT / '.audit'
DEFAULT_DAYS = 45
ORIGINAL = re.compile(
    r'\b(?:erteilung (?:eines|von|zweier|mehrerer) ordnungsruf\w*|'
    r'ordnungsruf\w* (?:an|gegen|für|fuer)\b)', re.I)
FOLLOWUP = re.compile(
    r'\b(?:einspruch\w*|beschwerde\w*|zurückgenomm\w*|aufheb\w*|'
    r'zurückgewiesen\w*|ordnungsgeld\w*)', re.I)
WARNING = (
    'DIP-Vorgangstitel/Abstract und ein vollständiger Abruf innerhalb des '
    'angegebenen Aktualisierungsfensters beweisen weder ursprüngliche '
    'selbständige Erteilung noch aktuelle Rechtswirksamkeit oder '
    'Vollständigkeit der Wahlperiode. Unbekannt bedeutet nur: keine der '
    '18 fest verankerten DIP-Eltern-IDs. Ein Treffer kann bereits in der '
    'acht Maßnahmen umfassenden geprüften Teilmenge liegen. '
    'Kein automatischer Zählerwechsel.'
)


def possible_reference_overlap(doc, sample):
    """Conservative name/date hint, not a verified identity or deduplication."""
    title = norm(doc.get('titel') or '')
    date = doc.get('datum')
    matches = []
    for entry in sample['entries']:
        expected = datetime.strptime(entry['date'], '%d.%m.%Y').date().isoformat()
        person = norm(entry['person'])
        if date == expected and re.search(
                r'(?<!\w)' + re.escape(person) + r'(?!\w)', title):
            matches.append({'session':entry['session'], 'person':entry['person']})
    return matches


def classify(doc):
    title = doc['titel']
    # Do not treat an appeal/retraction/penalty as an original grant even if
    # the phrase "Ordnungsruf" occurs elsewhere in the title.
    if FOLLOWUP.search(title):
        return 'procedure_or_other_sanction_not_original_proof'
    if ORIGINAL.search(title):
        return 'possible_original_grant_metadata'
    return 'other_ordnungsruf_metadata_review'


def build(documents, *, since, now, pages, snapshot=None):
    snapshot = reference() if snapshot is None else snapshot
    if (snapshot.get('$schema') != 'ordnungsruf-dip-positive-control-v1'
            or len(snapshot.get('entries', [])) != 24
            or len(PINS) != 18 or len(set(PINS.values())) != 18):
        raise ValueError('Kuratierte DIP-Ausgangsreferenz wurde verändert')
    if (since.tzinfo is None or now.tzinfo is None or
            not START <= since <= now or now > datetime.now(timezone.utc) +
            timedelta(days=2) or type(pages) is not int or pages < 1):
        raise ValueError('DIP-Entdeckungszeitfenster ungültig')
    if not isinstance(documents, list) or len(documents) > 120000:
        raise ValueError('Kein vollständiger überschaubarer DIP-Dokumentensatz')
    pinned_ids = set(PINS.values())
    seen = set()
    pinned_seen = []
    possible = []
    related = []
    for doc in documents:
        if not isinstance(doc, dict):
            raise ValueError('DIP-Vorgang ohne Rohdaten')
        ident = str(doc.get('id', ''))
        if (not re.fullmatch(r'[1-9]\d{0,11}', ident) or
                doc.get('wahlperiode') != 21 or ident in seen):
            raise ValueError('DIP-Quelle fremder Wahlperiode oder doppelt')
        seen.add(ident)
        item = relevant_item(doc)
        if item is None:
            continue
        if ident in pinned_ids:
            pinned_seen.append(ident)
            continue
        kind = classify(doc)
        entry = {
            'official_dip_parent_id': ident,
            'official_dip_parent_url': item['source'],
            'title': item['title'],
            'source_date': item['date'],
            'updated_utc': item['updated'],
            'classification_for_manual_review': kind,
            'possible_overlap_with_dated_positive_sample':
                possible_reference_overlap(doc, snapshot),
            'original_issue_individually_verified': False,
            'subsequent_legal_effect_verified': False,
            'confirmed_additional_sanctions': 0,
        }
        if kind == 'possible_original_grant_metadata':
            possible.append(entry)
        else:
            related.append(entry)
    for group in (possible, related):
        group.sort(key=lambda row:(row['updated_utc'], int(row['official_dip_parent_id'])),
                   reverse=True)
    return {
        'schema':'wp21-dip-outside-pins-discovery-v1',
        'status':'source_discovery_only_no_effectiveness_decision',
        'since_utc':iso(since), 'observed_until_utc':iso(now),
        'full_legislative_period_update_window':since == START,
        'api_pages_completely_fetched':pages,
        'total_dip_documents_in_update_window':len(documents),
        'pinned_18_parents_seen_in_window':len(pinned_seen),
        'possible_original_parent_ids_outside_18_pins':len(possible),
        'other_relevant_parent_ids_outside_18_pins':len(related),
        'possible_originals_for_individual_review':possible,
        'other_metadata_for_individual_review':related,
        'automatically_confirmed_new_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'protected_counters_changed':False,
        'warning':WARNING,
    }


def markdown(report):
    if (report['automatically_confirmed_new_sanctions'] != 0 or
            report['automatically_rescinded_sanctions'] != 0 or
            report['protected_counters_changed']):
        raise ValueError('Statistische Freigabe im Quellenscan verboten')
    lines = [
        '# WP21: weitere DIP-Quellen außerhalb von 18 bekannten Eltern-IDs',
        '',
        '**Keine bestätigten neuen Maßnahmen. Keine Wahlperiodengesamtzahl.**',
        '',
        'Aktualisierungsfilter: ' + report['since_utc'] +
        ' bis ' + report['observed_until_utc'],
        '',
        'Vollständige Wahlperioden-Zeitspanne als Filter: ' +
        ('ja' if report['full_legislative_period_update_window'] else 'nein'),
        '',
        '| DIP-Eltern-ID | Amtlicher Vorgangstitel | Vorläufige Einordnung |',
        '|---|---|---|',
    ]
    for c in (report['possible_originals_for_individual_review'] +
              report['other_metadata_for_individual_review']):
        title = c['title'].replace('|','\\|').replace('\n',' ')[:180]
        lines.append(
            '| [' + c['official_dip_parent_id'] + '](' +
            c['official_dip_parent_url'] + ') | ' + title + ' | ' +
            c['classification_for_manual_review'] + ' |')
    lines.extend(['', report['warning'], '',
                  '**Keine Änderungen bestätigter CSV-/JSON-Daten.**', ''])
    return '\n'.join(lines)


def save(report, folder):
    path = Path(folder).resolve()
    root = AUDIT_ROOT.resolve()
    if root not in path.parents or path.is_symlink():
        raise ValueError('DIP-Discovery-Ausgaben nur im privaten .audit-Unterordner')
    path.mkdir(parents=True, exist_ok=True)
    for name, contents in (
        ('outside_pins.json', json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
        ('outside_pins.md', markdown(report))):
        temporary = path / (name + '.tmp')
        temporary.write_text(contents, encoding='utf-8')
        temporary.replace(path / name)


def run(*, since=None, now=None, key=None, load=request_page,
        output_dir=AUDIT_ROOT/'wp21_dip_discovery', max_pages=1200):
    now = now or datetime.now(timezone.utc)
    since = since or max(START, now - timedelta(days=DEFAULT_DAYS))
    if since.tzinfo is None or now.tzinfo is None or not START <= since <= now:
        raise ValueError('DIP-Abfragezeitfenster ungültig')
    docs, pages = paginate(since, key or os.getenv('DIP_API_KEY') or PUBLIC_KEY,
                           load=load, max_pages=max_pages)
    report = build(docs,since=since,now=now,pages=pages)
    save(report, output_dir)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days',type=int,default=DEFAULT_DAYS)
    parser.add_argument('--full-term',action='store_true')
    parser.add_argument('--output-dir',type=Path,default=AUDIT_ROOT/'wp21_dip_discovery')
    options = parser.parse_args()
    if not 1 <= options.days <= 365:
        raise ValueError('DIP-Entdeckungsfenster muss 1 bis 365 Tage betragen')
    now = datetime.now(timezone.utc)
    since = START if options.full_term else max(START, now-timedelta(days=options.days))
    report = run(since=since, now=now, output_dir=options.output_dir)
    print(f"WP21 DIP: {report['total_dip_documents_in_update_window']} Dokumente "
          f"vollständig auf {report['api_pages_completely_fetched']} Seiten, "
          f"{report['possible_original_parent_ids_outside_18_pins']} "
          'mögliche neue Quellen außerhalb der 18 verankerten DIP-IDs; '
          'null automatische Zähleränderungen.')


if __name__=='__main__':
    main()
