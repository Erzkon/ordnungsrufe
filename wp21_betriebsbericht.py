#!/usr/bin/env python3
"""Compact public-data-only operational status for the daily WP21 Actions run.

The report never changes reviewed sanctions. Missing/stale data remains visible
rather than turning into an invented 0 counter. Uses only local JSON snapshots.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

EXPECTED = {
    'scan_21.json': ('status', 'bereit', 'zuletzt_geprueft_utc'),
    'autopruefung_21.json': ('status', 'automatische_vorpruefung_ohne_freigabe',
                            'letzter_Quellenscan_utc'),
    'rechtsfolgen_21.json': ('status', 'ungepruefte_rechtsfolgen_hinweise',
                            'letzter_Quellenscan_utc'),
    'dip_live_21.json': ('status', 'dip_vorgangsmonitor_ohne_freigabe',
                         'last_success_utc'),
    'dip_positionen_21.json': ('status', 'dip_positionen_ohne_rechtswirkung',
                             'last_success_utc'),
}


def inspect(folder, now=None, max_age_hours=48):
    now = now or datetime.now(timezone.utc)
    results = {}
    for name, (status_field, status_expected, date_field) in EXPECTED.items():
        path = Path(folder)/name
        if not path.is_file():
            results[name]={'state':'missing','date':'','reason':'Kein Bericht vorhanden'}
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('status') != status_expected or data.get('wahlperiode', 21) != 21:
                raise ValueError('Unerwartete Berichtsart')
            timestamp = datetime.fromisoformat(data[date_field].replace('Z','+00:00'))
            if timestamp.tzinfo is None:
                raise ValueError('Zeitpunkt ohne UTC-Offset')
            age = (now - timestamp).total_seconds()/3600
            state = 'fresh' if 0 <= age <= max_age_hours else 'stale'
            if state == 'stale':
                reason='Quellenstand älter als 48 h oder aus der Zukunft'
            else:
                reason=''
            results[name]={'state':state,'date':timestamp.date().isoformat(),
                           'reason':reason}
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            results[name]={'state':'invalid','date':'','reason':type(exc).__name__}
    return results


def markdown(results, outcomes=None):
    outcomes = outcomes or {}
    labels = {
        'scan_21.json':'Offizielle Protokolle',
        'autopruefung_21.json':'Automatische Personen-Vorprüfung',
        'rechtsfolgen_21.json':'Einspruchs-/Rücknahme-Signale',
        'dip_live_21.json':'DIP: aktuelle Vorgangsmetadaten',
        'dip_positionen_21.json':'DIP: Vorgangspositionen und Folgeschritte',
    }
    status = {'fresh':'aktuell', 'stale':'veraltet',
              'missing':'fehlt', 'invalid':'ungültig'}
    lines=[
        '## Ordnungsruf-Counter · 21. Wahlperiode',
        '',
        '**Keine automatische Bestätigung neuer Ordnungsrufe**; '
        'die geprüften Zähler bleiben unabhängig von diesem Workflow.',
        '',
        '| Schritt | Quellenstand | Status |',
        '|---|---|---|',
    ]
    for name in EXPECTED:
        item = results[name]
        lines.append(f"| {labels[name]} | {item['date'] or '—'} | {status[item['state']]} |")
    if outcomes:
        lines += ['', '### Ablauf',
                  f"- XML-Scan: {outcomes.get('scan','unbekannt')}",
                  f"- Personen-Vorprüfung: {outcomes.get('autopruefung','unbekannt')}",
                  f"- Rechtsfolgen-Suche: {outcomes.get('rechtsfolgen','unbekannt')}",
                  f"- DIP-API-Abgleich: {outcomes.get('dip','unbekannt')}",
                  f"- DIP-Folgeschritte: {outcomes.get('dippositions','unbekannt')}"]
    warnings=[name for name in EXPECTED if results[name]['state']!='fresh']
    if warnings:
        lines += ['', '**Achtung:** Mindestens ein Bericht ist nicht aktuell '
                       'oder nicht verfügbar. Dies ist keine Aussage über '
                       'das Vorliegen oder Fehlen von Ordnungsrufen.']
    lines += ['', 'Prüfhinweise als CSV stehen in den Actions-Artefakten '
                  'dieses Laufs zur Verfügung, sofern die jeweiligen Schritte '
                  'erfolgreich waren.', '']
    return '\n'.join(lines)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', type=Path, default=Path('docs/data'))
    opts=ap.parse_args()
    results=inspect(opts.data)
    outcomes={key:os.environ.get(f'WP21_{key.upper()}_OUTCOME','unbekannt')
              for key in ('scan','autopruefung','rechtsfolgen','dip','dippositions')}
    report=markdown(results,outcomes)
    target=os.environ.get('GITHUB_STEP_SUMMARY')
    if target:
        with Path(target).open('a',encoding='utf-8') as stream:
            stream.write(report)
    print(report)
    for name,item in results.items():
        if item['state']!='fresh':
            print('::warning::WP21: ' + name + ' nicht aktuell (' + item['state'] + ').')


if __name__=='__main__':
    main()
