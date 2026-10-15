#!/usr/bin/env python3
"""Small real-network DIP endpoint smoke test, no user data or ledger writes.

Use in CI only as an observable warning, since remote availability and the
public API key are beyond this repository's control.
"""
import sys

from wp21_dip_monitor import PUBLIC_KEY, request_page
from wp21_dip_positionen import API_POSITIONS


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
