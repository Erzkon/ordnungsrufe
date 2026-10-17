#!/usr/bin/env python3
"""Read-only title-independent DIP /vorgangsposition audit within a dated window.

No parent title/abstract prefilter; every position in the query window is
paged and examined. No legal outcome or universal absence is inferred.
"""
import argparse
import json
import os
import re
from datetime import date
from pathlib import Path

from wp21_18_dip_verfahrenspositionen import named
from wp21_dip_monitor import PUBLIC_KEY
from wp21_dip_positionen import normalize_position, position_page

PARENT = '328225'
KNOWN_VOTE = '681803'
KNOWN_ORIGIN = '681046'
KNOWN_DATE = date(2025, 11, 25)
ORIGIN_DATE = date(2025, 11, 13)
EARLIEST = date(2025, 11, 13)
MAX_DAYS = 45
MAX_PAGES = 160
# Generic legislative "Aufhebung" or "Ablehnung" is NOT a disciplinary
# proceeding. With Gottschalk named as a motion sponsor it created false
# positives in unrelated tax and climate-policy laws. Require an explicit
# order/appeal signal in the position text instead.
KEYWORDS = re.compile(
    r'\b(?:ordnungsruf\w*|ordnungsma[ßs]nahm\w*|einspruch\w*|'
    r'widerspruch\w*|anfecht\w*|beschwerde\w*)\b', re.I)
SECOND = re.compile(r'\b(?:zweite\w*|2\.)\s+ordnungs(?:maßnahme|massnahme|ruf)\w*\b',
                    re.I)


def interval(start, end):
    begin, finish = date.fromisoformat(start), date.fromisoformat(end)
    if (begin < EARLIEST or finish < begin
            or (finish - begin).days >= MAX_DAYS
            or finish > date.today()):
        raise ValueError('Ungültiges oder zu großes DIP-Positionszeitfenster')
    return begin, finish


def pages(start, end, key, load=position_page, max_pages=MAX_PAGES):
    """Fail closed if pagination, dates or response identity are inconsistent."""
    interval(start, end)
    if not 1 <= max_pages <= MAX_PAGES:
        raise ValueError('Unzulässiges Seitenlimit')
    rows, visited = {}, set()
    cursor, total = None, None
    for number in range(1, max_pages + 1):
        params = {'f.wahlperiode': '21', 'f.datum.start': start, 'f.datum.end': end}
        if cursor is not None:
            params['cursor'] = cursor
        response = load(params, key)
        if not isinstance(response, dict):
            raise ValueError('DIP-Positionen: kein Antwortobjekt')
        docs, size, next_cursor = (response.get('documents'),
                                   response.get('numFound'), response.get('cursor'))
        if (not isinstance(docs, list) or len(docs) > 100
                or type(size) is not int or not 0 <= size <= MAX_PAGES * 100
                or not isinstance(next_cursor, (str, type(None)))):
            raise ValueError('DIP-Positionen: fehlerhafte/zu große API-Seite')
        if total is None:
            total = size
        elif total != size:
            raise ValueError('DIP-Positionen: Ergebniszahl veränderte sich')
        for raw in docs:
            if not isinstance(raw, dict):
                raise ValueError('DIP-Positionen: Fremddatensatz')
            ident, parent = str(raw.get('id', '')), str(raw.get('vorgang_id', ''))
            day = raw.get('datum')
            if (not re.fullmatch(r'[1-9]\d{0,11}', ident)
                    or not re.fullmatch(r'[1-9]\d{0,11}', parent)
                    or ident in rows or raw.get('wahlperiode') not in (None, 21)
                    or not isinstance(day, str)
                    or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day)
                    or not start <= day <= end):
                raise ValueError('DIP-Positionen: ID/Datum/Dublette ungültig')
            rows[ident] = raw
        if len(rows) == size:
            return list(rows.values()), number
        if (not docs or not next_cursor
                or next_cursor == cursor or next_cursor in visited):
            raise ValueError('DIP-Positionen: unvollständiger oder zyklischer Cursor')
        visited.add(next_cursor)
        cursor = next_cursor
    raise ValueError('DIP-Positionen: Limit vor Abschluss erreicht')


def fragments(raw):
    """Read names/appeal context from position fields, even with unrelated titles."""
    parts = []
    for field in ('titel', 'abstract', 'vorgangsposition'):
        val = raw.get(field) or ''
        if not isinstance(val, str) or len(val) > 5000:
            raise ValueError('DIP-Position: ungültiges Textfeld')
        parts.append((field, val))
    activities = raw.get('aktivitaet_anzeige') or []
    if not isinstance(activities, list) or len(activities) > 50:
        raise ValueError('DIP-Position: ungültige Aktivitätsliste')
    for activity in activities:
        if not isinstance(activity, dict):
            raise ValueError('DIP-Position: Aktivität kein Objekt')
        for field in ('titel', 'aktivitaetsart'):
            val = activity.get(field) or ''
            if not isinstance(val, str) or len(val) > 5000:
                raise ValueError('DIP-Position: ungültiger Aktivitätstext')
            parts.append(('aktivitaet_anzeige.' + field, val))
    return parts


def inspect(rows, start, end, page_count):
    begin, finish = interval(start, end)
    if (not isinstance(rows, list) or len(rows) > MAX_PAGES * 100
            or type(page_count) is not int or not 1 <= page_count <= MAX_PAGES):
        raise ValueError('DIP-Suchfenster unvollständig')
    candidates, ids, known = [], set(), False
    for raw in rows:
        if not isinstance(raw, dict):
            raise ValueError('DIP-Position kein Objekt')
        ident, parent = str(raw.get('id', '')), str(raw.get('vorgang_id', ''))
        if (not re.fullmatch(r'[1-9]\d{0,11}', ident)
                or not re.fullmatch(r'[1-9]\d{0,11}', parent)
                or ident in ids or not isinstance(raw.get('datum'), str)
                or not start <= raw['datum'] <= end
                or raw.get('wahlperiode') not in (None, 21)):
            raise ValueError('DIP-Positionsidentität oder Datum nicht belegbar')
        ids.add(ident)
        items = fragments(raw)
        names = [field for field, value in items if named(value, 'Kay Gottschalk')]
        contexts = [field for field, value in items if KEYWORDS.search(value)]
        if parent != PARENT and not (names and contexts):
            continue
        normalized = normalize_position(raw)
        if ident == KNOWN_ORIGIN:
            if (parent != PARENT or raw['datum'] != ORIGIN_DATE.isoformat()
                    or normalized['step'] != 'Ordnungsruf'):
                raise ValueError('Bekannte ursprüngliche Gottschalk-Position verändert')
        if ident == KNOWN_VOTE:
            if (parent != PARENT or raw['datum'] != KNOWN_DATE.isoformat()
                    or normalized['step'] != 'Abstimmung'
                    or 'Zurückweisung des Einspruchs'
                    not in normalized['official_decision_tenors']):
                raise ValueError('Bekannte erste Gottschalk-Abstimmung verändert')
            known = True
        candidates.append({
            'position_id': ident, 'parent_id': parent, 'date': raw['datum'],
            'source': normalized['source'], 'title': normalized['title'],
            'step': normalized['step'],
            'abstract_excerpt': normalized['official_position_abstract_excerpt'],
            'name_fields': sorted(set(names)),
            'procedural_fields': sorted(set(contexts)),
            'known_parent': parent == PARENT,
            'known_first_rejected_appeal': ident == KNOWN_VOTE,
            'known_original_position': ident == KNOWN_ORIGIN,
            'potential_second_measure': bool(
                SECOND.search(' '.join(val for _, val in items))),
            'decision_tenors': normalized['official_decision_tenors'],
            'manual_source_review_only': True,
        })
    if begin <= KNOWN_DATE <= finish and not known:
        raise ValueError('Bekannte Gottschalk-Positivkontrolle 681803 fehlt')
    candidates.sort(key=lambda r: (r['date'], int(r['position_id'])))
    other = [row for row in candidates
             if row['position_id'] not in (KNOWN_ORIGIN, KNOWN_VOTE)]
    return {
        'schema': 'wp21-gottschalk-title-independent-positions-v1',
        'source_endpoint': 'https://search.dip.bundestag.de/api/v1/vorgangsposition',
        'scope': 'wahlperiode_21_and_position_dates_only',
        'search_start': start, 'search_end': end,
        'complete_positions_examined': len(rows), 'api_pages': page_count,
        'known_first_appeal_verified':
            known if begin <= KNOWN_DATE <= finish else None,
        'candidates': candidates,
        'other_candidate_positions': len(other),
        'known_baseline_position_ids': [KNOWN_ORIGIN, KNOWN_VOTE],
        'manual_review_required': bool(other),
        'unsearched_dates_and_source_types_remain_open': True,
        'absence_of_second_appeal_not_established': True,
        'second_measure_legal_effectiveness_unresolved': True,
        'automatically_confirmed_effective_sanctions': 0,
        'automatically_rescinded_sanctions': 0,
        'public_counter_delta': 0,
    }


def markdown(report):
    if (report.get('schema') != 'wp21-gottschalk-title-independent-positions-v1'
            or report.get('unsearched_dates_and_source_types_remain_open') is not True
            or report.get('absence_of_second_appeal_not_established') is not True
            or report.get('second_measure_legal_effectiveness_unresolved') is not True
            or report.get('automatically_confirmed_effective_sanctions') != 0
            or report.get('automatically_rescinded_sanctions') != 0
            or report.get('public_counter_delta') != 0):
        raise ValueError('Unzulässige Schlussfolgerung aus DIP-Metadaten')
    lines = [
        '# Kay Gottschalk: DIP-Positionen ohne Titelvorfilter', '',
        f"Datum: {report['search_start']} bis {report['search_end']}",
        f"Abgeschlossene Seiten: {report['api_pages']}, "
        f"Positionen: {report['complete_positions_examined']}",
        f"Prüfkandidaten: {len(report['candidates'])}", '',
    ]
    for row in report['candidates']:
        lines.append(
            f"- [{row['position_id']}]({row['source']}) – "
            f"{row['date']} – {row['title']} – {row['step']} "
            f"(mögliche zweite Maßnahme: {row['potential_second_measure']})")
    lines.extend(['', '**Nur amtliche Metadaten, keine rechtliche Freigabe.**',
                  'Ein leeres Suchfenster beweist weder das Fehlen anderer '
                  'Einsprüche oder späterer Entscheidungen noch die '
                  'Wirksamkeit der zweiten Maßnahme.', ''])
    return '\n'.join(lines)


def run(start, end, output, brief, *, key=None, load=position_page,
        max_pages=MAX_PAGES):
    key = key or os.getenv('DIP_API_KEY') or PUBLIC_KEY
    if not key or '\n' in key or '\r' in key:
        raise ValueError('DIP-API-Key ungültig')
    raw, page_count = pages(start, end, key, load, max_pages)
    report = inspect(raw, start, end, page_count)
    body = markdown(report)
    for target, content in (
            (Path(output), json.dumps(report, ensure_ascii=False, indent=2) + '\n'),
            (Path(brief), body)):
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + '.tmp')
        tmp.write_text(content, encoding='utf-8')
        tmp.replace(target)
    if report['manual_review_required']:
        print('::warning::Titelfreie amtliche Gottschalk-Kandidaten gefunden; '
              'Einzelprüfung nötig, keine Zähleränderung')
    print('WP21_GOTTSCHALK_TITLE_INDEPENDENT_OK',
          report['complete_positions_examined'], 'positions,',
          report['api_pages'], 'pages,',
          len(report['candidates']), 'candidates, zero legal counts')
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--start', default='2025-11-13')
    cli.add_argument('--end', default='2025-12-12')
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--brief', type=Path, required=True)
    cli.add_argument('--max-pages', type=int, default=MAX_PAGES)
    args = cli.parse_args()
    run(args.start, args.end, args.output, args.brief, max_pages=args.max_pages)
