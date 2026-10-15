#!/usr/bin/env python3
"""Small real-network DIP endpoint smoke test, no user data or ledger writes.

Use in CI only as an observable warning, since remote availability and the
public API key are beyond this repository's control.
"""
import sys
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from wp21_dip_monitor import PUBLIC_KEY, request_page
from wp21_dip_positionen import API_POSITIONS


def recent_pagination_probe(load, key, now):
    """Exercise real pagination through injectable transport, never publish data."""
    from wp21_dip_monitor import paginate, relevant_item
    recent, page_count = paginate(now-timedelta(days=1), key, load=load, max_pages=60)
    return {
        'documents':len(recent),
        'pages':page_count,
        'title_or_abstract_matches':sum(relevant_item(row) is not None for row in recent),
    }


def probe(load=request_page, key=PUBLIC_KEY):
    cases = [
        ('Vorgänge', {'f.wahlperiode':'21','f.id':'330701'}, None),
        ('Vorgangspositionen', {'f.wahlperiode':'21','f.vorgang':'330701'}, API_POSITIONS),
    ]
    result = {}
    for label,params,endpoint in cases:
        if endpoint:
            payload = load(params,key,endpoint=endpoint)
        else:
            payload = load(params,key)
        if (not isinstance(payload,dict)
                or type(payload.get('numFound')) is not int
                or not isinstance(payload.get('documents'),list)
                or len(payload['documents']) > 100):
            raise ValueError('DIP-Liveantwort hat unerwartetes Format: '+label)
        result[label] = {'numFound':payload['numFound'],
                         'first_page_rows':len(payload['documents'])}
    # Verify one actual linkage and procedural-step object, not merely
    # that an HTTP endpoint returns JSON.
    from wp21_dip_positionen import fetch_positions, normalize_position
    linked = fetch_positions('330701',key)
    for raw in linked:
        item = normalize_position(raw)
        if item['parent_id'] != '330701':
            raise ValueError('Amtliche Verfahrensposition verweist auf falschen Vorgang')
    result['Vorgangspositions-Verknuepfung'] = {'linked_positions':len(linked)}
    if linked:
        sample = linked[0]
        result['Positionsschema'] = {
            'field_names':sorted(sample),
            'step_example':str(sample.get('vorgangsposition',''))[:120],
            'title_example':str(sample.get('titel',''))[:120],
            'activity_types':str(sample.get('aktivitaet_anzeige',''))[:100],
            'has_decision_field':'beschlussfassung' in sample,
        }
    # Validate the incremental filter actually used by the scheduled workflow.
    from wp21_dip_monitor import iso
    params = {
        'f.wahlperiode':'21',
        'f.aktualisiert.start':iso(datetime.now(timezone.utc)-timedelta(days=2))
    }
    latest = load(params,key)
    if not isinstance(latest,dict) or type(latest.get('numFound')) is not int or not isinstance(latest.get('documents'),list):
        raise ValueError('DIP-Aktualisierungsfilter nicht verwendbar')
    result['Aktualisierungsfilter'] = {'matches':latest['numFound'],
                                       'first_page':len(latest['documents'])}
    # A genuine multi-page trial catches schema and cursor differences hidden
    # by single-item probes. It is read-only and limited to the last 24 hours.
    result['DIP_Mehrseitenprobe_24h'] = recent_pagination_probe(
        load, key, datetime.now(timezone.utc))
    from wp21_dip_monitor import START
    history = load({'f.wahlperiode':'21','f.aktualisiert.start':iso(START)},key)
    if not isinstance(history,dict) or type(history.get('numFound')) is not int:
        raise ValueError('Initialer DIP-Backfill-Filter nicht verwendbar')
    estimated_pages=(history['numFound']+99)//100
    result['Erstlauf-Kapazitaet']={'historical_records':history['numFound'],
                                 'estimated_pages':estimated_pages}
    if estimated_pages > 1200:
        raise ValueError('Historische DIP-Erstladung würde das Seitenlimit überschreiten')
    # Exercise the same strict XML validator and review parser as production,
    # but for ONE archived protocol only; never touch reviewed datasets.
    from wp21_scan import safe_parse, review_rows, HOST, MAX_SIZE
    request = Request(HOST+'/21094.xml',
                      headers={'User-Agent':'OrdnungsrufCounter/0.7 (GitHub CI)'})
    with urlopen(request,timeout=35) as response:
        source = response.read(MAX_SIZE+1)
    root = safe_parse(source,94)
    candidates = review_rows(root,94)
    # An independent live XML-to-person-parser consistency check on the
    # original transcript: parser lines must come from an XML review location,
    # not from an accidental fabricated/misaligned reference. This is
    # detection coverage, never an effectiveness or sanction-count claim.
    from pathlib import Path
    from parser import events, speaker_index
    people = list(events(Path('21094.xml'), index=speaker_index([root]), root=root))
    xml_lines = {int(row['xml_zeile']) for row in candidates}
    unmatched = [str(row['line']) for row in people if int(row['line']) not in xml_lines]
    if unmatched:
        raise ValueError('Parser-Personenhinweise ohne zugehörige XML-Textstellen: ' +
                         ', '.join(unmatched[:5]))
    result['Originalprotokoll_21_094']={
        'bytes':len(source),
        'text_locations':len(candidates),
        'parser_person_hints':len(people),
        'parser_locations_without_xml_candidate':len(unmatched),
        'date':root.get('sitzung-datum')
    }
    return result


def main():
    try:
        details=probe()
        print('DIP-REST-Endpunkte erreichbar und Listenformat lesbar:',details)
    except Exception as error:
        print('::warning::DIP-Liveverbindung nicht bestätigt: '+
              type(error).__name__+': '+str(error))
        raise SystemExit(1)


if __name__=='__main__':
    main()
