#!/usr/bin/env python3
"""Read-only bounded HISTORICAL DIP position backfill, never a legal counter.

Traverse successive nonoverlapping dated position windows without any parent
title prefilter. Commit an audit report only if *every* cursor page of *every*
window was successfully validated. It cannot exclude other source types or
positions with no identifying searchable name.
"""
import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path

from wp21_gottschalk_unkategorisierte_positionen import (
    KNOWN_ORIGIN, KNOWN_VOTE, MAX_DAYS, PUBLIC_KEY, inspect, pages,
    position_page,
)

MAX_HISTORY_DAYS = 370
MAX_WINDOWS = 10


def windows(start, end):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first < date(2025, 11, 13) or last < first:
        raise ValueError('Historische Positionsspanne ungültig')
    if (last - first).days > MAX_HISTORY_DAYS or last > date.today():
        raise ValueError('Historischer DIP-Positionshorizont zu groß')
    result = []
    current = first
    while current <= last:
        finish = min(last, current + timedelta(days=MAX_DAYS - 1))
        result.append((current.isoformat(), finish.isoformat()))
        current = finish + timedelta(days=1)
    if not 1 <= len(result) <= MAX_WINDOWS:
        raise ValueError('Zu viele historische Einzelzeitfenster')
    return result


def review(start, end, *, key=PUBLIC_KEY, load=position_page):
    snapshots = []
    global_positions = set()
    full_pages = 0
    full_positions = 0
    candidates = []
    known_vote = False
    for a, b in windows(start, end):
        raw, n = pages(a, b, key, load=load)
        result = inspect(raw, a, b, n)
        for position in raw:
            ident = str(position['id'])
            if ident in global_positions:
                raise ValueError('DIP-Position zwischen Zeitfenstern doppelt')
            global_positions.add(ident)
        full_pages += n
        full_positions += len(raw)
        known_vote = known_vote or result['known_first_appeal_verified'] is True
        candidates.extend(result['candidates'])
        snapshots.append({
            'start': a, 'end': b,
            'completed_pages': n, 'complete_position_count': len(raw),
            'candidate_count': len(result['candidates']),
            'nonbaseline_candidate_count': result['other_candidate_positions'],
        })
    if date.fromisoformat(start) <= date(2025, 11, 25) <= date.fromisoformat(end):
        if not known_vote:
            raise ValueError('Historische erste Einspruchsreferenz fehlt')
    candidates.sort(key=lambda x: (x['date'], int(x['position_id'])))
    outside = [row for row in candidates
               if row['position_id'] not in (KNOWN_ORIGIN, KNOWN_VOTE)]
    return {
        'schema': 'wp21-gottschalk-unfiltered-historical-positions-v1',
        'search_start': start, 'search_end': end,
        'source': 'https://search.dip.bundestag.de/api/v1/vorgangsposition',
        'title_filter_used': False,
        'full_windows': snapshots, 'completed_windows': len(snapshots),
        'completed_api_pages': full_pages,
        'complete_position_count': full_positions,
        'known_first_vote_reference_checked': known_vote,
        'all_person_named_or_known_parent_candidates': candidates,
        'new_nonbaseline_candidates': outside,
        'manual_review_required': bool(outside),
        'missing_second_vote_is_not_proven': True,
        'other_dates_source_types_or_non_named_positions_unchecked': True,
        'second_measure_legal_effectiveness_unresolved': True,
        'automatically_confirmed_effective_sanctions': 0,
        'automatically_rescinded_sanctions': 0,
        'public_counter_delta': 0,
    }


def markdown(r):
    if (r.get('schema') != 'wp21-gottschalk-unfiltered-historical-positions-v1'
            or r.get('title_filter_used') is not False
            or r.get('missing_second_vote_is_not_proven') is not True
            or r.get('other_dates_source_types_or_non_named_positions_unchecked') is not True
            or r.get('second_measure_legal_effectiveness_unresolved') is not True
            or r.get('automatically_confirmed_effective_sanctions') != 0
            or r.get('automatically_rescinded_sanctions') != 0
            or r.get('public_counter_delta') != 0):
        raise ValueError('Historischer Befund darf nicht als Sanktion gelten')
    lines = ['# Historischer Gottschalk-DIP-Positionsabgleich', '',
             f"Zeitraum: {r['search_start']} bis {r['search_end']}",
             f"Vollständig gelesene Zeitfenster: {r['completed_windows']}",
             f"Vollständige Seiten: {r['completed_api_pages']}",
             f"Positionsdatensätze: {r['complete_position_count']}",
             f"Zusätzliche Quellenkandidaten: {len(r['new_nonbaseline_candidates'])}",
             '',
             '## Begrenzt geprüfte Zeitfenster', '']
    for w in r['full_windows']:
        lines.append(
            f"- {w['start']} bis {w['end']}: "
            f"{w['complete_position_count']} Positionen auf "
            f"{w['completed_pages']} Seiten; "
            f"{w['nonbaseline_candidate_count']} Kandidaten")
    lines.extend(['', '## Zusätzliche manuelle Prüfhinweise', ''])
    for row in r['new_nonbaseline_candidates']:
        lines.append(
            f"- [{row['position_id']}]({row['source']}) vom {row['date']}: "
            f"{row['step']} – {row['title']}")
    lines.extend(['', '**Keine automatische Zählerfreigabe.** ',
                  'Das Fehlen weiterer name- oder parentbezogener Positionen '
                  'innerhalb dieses Zeitraums schließt andere amtliche '
                  'Dokumenttypen, fehlende Namensangaben und spätere '
                  'Entscheidungen nicht aus.', ''])
    return '\n'.join(lines)


def run(start, end, output, brief, *, key=None, load=position_page):
    key = key or os.getenv('DIP_API_KEY') or PUBLIC_KEY
    if '\n' in key or '\r' in key:
        raise ValueError('DIP-API-Key ungültig')
    data = review(start, end, key=key, load=load)
    explanation = markdown(data)
    # No file is written until every source page has passed validation.
    for target, body in (
            (Path(output), json.dumps(data, ensure_ascii=False, indent=2) + '\n'),
            (Path(brief), explanation)):
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + '.tmp')
        temp.write_text(body, encoding='utf-8')
        temp.replace(target)
    if data['manual_review_required']:
        print('::warning::Titelfreier historischer DIP-Suchlauf hat '
              'zusätzliche manuelle Gottschalk-Kandidaten ermittelt; '
              'kein Zählerupdate.')
    print('WP21_GOTTSCHALK_HISTORY_OK:',
          data['completed_windows'], 'windows,',
          data['completed_api_pages'], 'pages,',
          data['complete_position_count'], 'positions,',
          len(data['new_nonbaseline_candidates']), 'additional candidates')
    return data


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--start', default='2025-11-13')
    cli.add_argument('--end', default='2026-10-17')
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--brief', type=Path, required=True)
    arg = cli.parse_args()
    run(arg.start, arg.end, arg.output, arg.brief)
