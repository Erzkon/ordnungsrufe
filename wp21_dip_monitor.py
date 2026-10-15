#!/usr/bin/env python3
"""Incremental, read-only DIP Bundestag update monitor for the 21st term.

Fetches complete /vorgang pages by f.aktualisiert.start, preserving the
last successful state. Title/abstract keyword screening is a review heuristic,
NOT a count, exhaustive DIP search, or a final legal decision.

DIP public API key published at https://dip.bundestag.de/über-dip/hilfe/api
(valid initially through May 2027). DIP_API_KEY env var overrides it.
"""
import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

API = 'https://search.dip.bundestag.de/api/v1/vorgang'
PUBLIC_KEY = 'R2BZaee.DjdCyihKZMf8AOjtScubP2EVydegzjmBIQ'
START = datetime(2025, 3, 25, tzinfo=timezone.utc)
LOOKBACK_DAYS = 30
MAX_RESPONSE = 3 * 1024 * 1024
MAX_MATCHES = 15000
RELEVANT = re.compile(r'\b(?:ordnungsruf\w*|ordnungsgeld\w*|ordnungsma[ßs]nahm\w*)', re.I)
LEGAL = re.compile(r'\b(?:einspruch\w*|zurückgenomm\w*|zurückgezogen\w*|'
                   r'aufgehoben\w*|aufhebung\w*|zurückgewiesen\w*|'
                   r'abgewiesen\w*|widerruf\w*|abgelehnt\w*)', re.I)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError('DIP-API-Weiterleitung verweigert')


def utc(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('DIP-Zeitpunkt ohne Zeitzone')
    return dt.astimezone(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec='seconds')


def request_page(params, key, opener=None, sleep=time.sleep, endpoint=API):
    opener = opener or build_opener(NoRedirect())
    args = urlencode(params)
    if endpoint not in (API, 'https://search.dip.bundestag.de/api/v1/vorgangsposition'):
        raise ValueError('DIP-Endpunkt nicht zugelassen')
    url = endpoint + '?' + args
    req = Request(url, headers={
        'Authorization': 'ApiKey ' + key,
        'Accept': 'application/json',
        'User-Agent': 'OrdnungsrufCounter/0.6 (github.com/Erzkon/ordnungsrufe)',
    })
    for attempt in range(3):
        try:
            with opener.open(req, timeout=30) as response:
                if response.status != 200:
                    raise ValueError('DIP-HTTP-Antwort ist nicht 200')
                blob = response.read(MAX_RESPONSE + 1)
            if len(blob) > MAX_RESPONSE:
                raise ValueError('DIP-Antwort überschreitet Größengrenze')
            return json.loads(blob.decode('utf-8'))
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            if isinstance(exc, HTTPError) and exc.code in (400, 401, 403, 404):
                raise ValueError('DIP-Anfrage abgelehnt (Status ' + str(exc.code) + ')') from exc
            if attempt == 2:
                raise
            sleep(2 ** attempt)
    raise RuntimeError('DIP-Abruf unerwartet beendet')


def paginate(since, key, load=request_page, max_pages=1200):
    """Every page must be visited before a snapshot can be committed."""
    if not 1 <= max_pages <= 2000:
        raise ValueError('Ungültiges Seitenlimit')
    cursor = None
    seen_cursors = set()
    found = {}
    total = None
    for page_idx in range(max_pages):
        params = {'f.wahlperiode': '21', 'f.aktualisiert.start': iso(since)}
        if cursor is not None:
            params['cursor'] = cursor
        result = load(params, key)
        if not isinstance(result, dict):
            raise ValueError('DIP: ungültiges JSON')
        docs = result.get('documents')
        number = result.get('numFound')
        next_cursor = result.get('cursor')
        if (not isinstance(docs, list) or len(docs) > 100
                or type(number) is not int or not 0 <= number <= 300000
                or not isinstance(next_cursor, (str, type(None)))):
            raise ValueError('DIP: unerwartetes Listenschema')
        if total is None:
            total = number
        elif number != total:
            # Changing result sets can lead to silent gaps in cursor searches.
            raise ValueError('DIP: numFound änderte sich während der Abfrage')
        for item in docs:
            if not isinstance(item, dict) or not re.fullmatch(r'[1-9]\d{0,11}',str(item.get('id',''))):
                raise ValueError('DIP: Vorgang ohne gültige ID')
            if item.get('wahlperiode') != 21:
                raise ValueError('DIP: falsche Wahlperiode')
            ident = str(item['id'])
            if ident in found:
                raise ValueError('DIP: Vorgang mehrfach über Cursor geliefert')
            found[ident] = item
        if len(found) >= number:
            if len(found) != number:
                raise ValueError('DIP: numFound widerspricht den Dokumenten')
            return list(found.values()), page_idx + 1
        if not next_cursor or next_cursor == cursor or next_cursor in seen_cursors:
            raise ValueError('DIP: Cursor vor vollständigem Ergebnis beendet/zyklisch')
        if not docs:
            raise ValueError('DIP: leere Seite vor vollständigem Ergebnis')
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    raise ValueError('DIP: Seitenlimit erreicht, Abfrage unvollständig')


def relevant_item(doc):
    """Keep only stable public metadata and explicit lexical evidence."""
    title = doc.get('titel', '')
    abstract = doc.get('abstract') or ''
    if not isinstance(title, str) or not isinstance(abstract, str):
        raise ValueError('DIP: kein Textfeld')
    combined = (title + ' ' + abstract).strip()
    if not RELEVANT.search(combined):
        return None
    ident = str(doc['id'])
    changed = utc(doc['aktualisiert'])
    eventdate = doc.get('datum', '')
    if eventdate:
        datetime.strptime(eventdate, '%Y-%m-%d')
    if changed < START:
        raise ValueError('DIP: Veränderungsdatum vor Beginn 21. WP')
    return {
        'id': ident, 'updated': iso(changed), 'date': eventdate,
        'title': ' '.join(title.split())[:320],
        'abstract_excerpt': ' '.join(abstract.split())[:550],
        'kind': 'rechtsfolgen_hinweis' if LEGAL.search(combined) else 'ordnungsruf_bezug',
        'source': 'https://dip.bundestag.de/vorgang/' + ident,
    }


def digest(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False)
                          .encode('utf-8')).hexdigest()


def load_state(path):
    path = Path(path)
    if not path.is_file():
        return {'last_success_utc': None, 'items': {}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 'dip21-incremental-v1':
        raise ValueError('DIP-Zustand: unbekanntes Schema')
    timestamp = utc(data['last_success_utc'])
    if timestamp < START or timestamp > datetime.now(timezone.utc) + timedelta(minutes=10):
        raise ValueError('DIP-Zustand: ungültiger Zeitstempel')
    items = data['items']
    if not isinstance(items, dict) or len(items) > MAX_MATCHES:
        raise ValueError('DIP-Zustand: ungültige Einträge')
    for ident, item in items.items():
        if (not re.fullmatch(r'[1-9]\d{0,11}', ident)
                or item.get('id') != ident
                or item.get('source') != 'https://dip.bundestag.de/vorgang/' + ident):
            raise ValueError('DIP-Zustand: ungültiger Link')
    return {'last_success_utc': iso(timestamp), 'items': items}


def evolve(previous, documents, now, *, complete_term=False):
    if now.tzinfo is None:
        raise ValueError('Zeitpunkt ohne Zeitzone')
    old = previous['items']
    merged = dict(old)
    changes = []
    seen = set()
    for doc in documents:
        ident = str(doc['id'])
        if ident in seen:
            raise ValueError('DIP: Dublette')
        seen.add(ident)
        new = relevant_item(doc)
        before = old.get(ident)
        if new is None:
            # Entries that became irrelevant remain in state with explicit
            # status rather than disappearing from history silently.
            if before is not None and before.get('active', True):
                merged[ident] = {**before, 'active': False}
                changes.append({'id': ident, 'change':'nicht_mehr_treffend',
                                'title':before['title'], 'source':before['source']})
            continue
        updated = {**new, 'active': True}
        if before is None:
            change = 'neu'
        elif digest({k:v for k,v in before.items() if k != 'active'}) != digest(new) or not before.get('active', True):
            change = 'aktualisiert'
        else:
            change = None
        merged[ident] = updated
        if change:
            changes.append({'id':ident,'change':change,
                            'title':new['title'],'kind':new['kind'],'source':new['source']})
    if complete_term:
        # Only a COMPLETE legislative-period refresh proves that an older
        # record is no longer present in the official DIP result set.
        # Rolling 30-day windows must NEVER deactivate absent older records.
        for ident, before in old.items():
            if ident not in seen and before.get('active', True):
                merged[ident] = {**before, 'active': False}
                changes.append({'id': ident,
                                'change':'nicht_mehr_im_gesamtbestand',
                                'title':before['title'], 'source':before['source']})
    if len(merged) > MAX_MATCHES:
        raise ValueError('DIP-Snapshot überschreitet Obergrenze')
    changes.sort(key=lambda row:(row['change'], int(row['id'])),reverse=True)
    state={'schema':'dip21-incremental-v1','last_success_utc':iso(now),'items':merged}
    active=sum(row.get('active',True) for row in merged.values())
    report={
        'wahlperiode':21,
        'status':'dip_vorgangsmonitor_ohne_freigabe',
        'last_success_utc':iso(now),
        'initial_backfill':previous['last_success_utc'] is None,
        'tracked_relevant_vorgaenge':active,
        'new_vorgaenge':sum(x['change']=='neu' for x in changes),
        'changed_vorgaenge':sum(x['change']=='aktualisiert' for x in changes),
        'no_longer_matching':sum(x['change']=='nicht_mehr_treffend' for x in changes),
        'missing_from_complete_term':sum(x['change']=='nicht_mehr_im_gesamtbestand'
                                         for x in changes),
        'legal_signals_total':sum(row.get('active',True) and row['kind']=='rechtsfolgen_hinweis'
                                  for row in merged.values()),
        'recent_changes':changes[:25],
        'automatically_confirmed_sanctions':0,
        'warning':('DIP-Suchfilter durchforstet Vorgangstitel und Abstract, nicht alle '
                   'Vorgangspositionen, Protokolltexte oder spätere Rechtsfolgen. '
                   'Neu/aktualisiert ist ein DIP-Metadatenereignis, keine '
                   'bestätigte Ordnungsrufmaßnahme; keine vollständige Statistik.'),
    }
    return state,report,changes


def run(state_file, report_file, changes_file, *, now=None, key=None, load=request_page,
        max_pages=1200):
    now = now or datetime.now(timezone.utc)
    key = key or os.getenv('DIP_API_KEY') or PUBLIC_KEY
    if not key or '\n' in key or '\r' in key:
        raise ValueError('DIP-API-Key ungültig')
    previous = load_state(state_file)
    last = utc(previous['last_success_utc']) if previous['last_success_utc'] else START
    # Monthly full re-check: DIP can backdate a correction or a cache can
    # retain a previously stale result. The first Sunday of each month
    # refreshes the entire term, while ordinary days use a 30-day overlap.
    # The caller can also force a full rescan for recovery/debugging.
    full_refresh = (previous['last_success_utc'] is None or
                    (now.day <= 7 and now.weekday() == 6))
    since = START if full_refresh else max(START, last - timedelta(days=LOOKBACK_DAYS))
    documents, pages = paginate(since, key, load=load, max_pages=max_pages)
    state,report,changes=evolve(previous,documents,now,complete_term=full_refresh)
    report.update({'request_since_utc':iso(since), 'api_pages':pages,
                   'full_term_refresh':full_refresh,
                   'changed_documents_scanned':len(documents)})
    # All network pages and validation have succeeded. Only now replace files.
    artifacts = [(Path(state_file),state),(Path(report_file),report)]
    for file,payload in artifacts:
        file.parent.mkdir(parents=True,exist_ok=True)
        temp=file.with_suffix(file.suffix+'.tmp')
        temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temp.replace(file)
    target=Path(changes_file)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--state',type=Path,default=Path('.cache/dip21/state.json'))
    ap.add_argument('--report',type=Path,default=Path('docs/data/dip_live_21.json'))
    ap.add_argument('--changes',type=Path,default=Path('wp21_dip_aenderungen.json'))
    ap.add_argument('--max-pages',type=int,default=1200)
    args=ap.parse_args()
    report=run(args.state,args.report,args.changes,max_pages=args.max_pages)
    print(f"DIP-Vorgänge: {report['changed_documents_scanned']} aktualisierte Metadaten "
          f"auf {report['api_pages']} Seiten, {report['tracked_relevant_vorgaenge']} "
          f"relevante Vorgänge im Monitoring. "
          f"Neue: {report['new_vorgaenge']}; geändert: {report['changed_vorgaenge']}; "
          "keine automatischen Ordnungsruf-Freigaben.")


if __name__=='__main__':
    main()
