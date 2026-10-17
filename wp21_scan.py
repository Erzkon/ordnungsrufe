#!/usr/bin/env python3
"""Daily 21st-term XML scan for *review candidates*, NEVER verified statistics.

GitHub Pages may show the scan's state and its candidate-text count, but does
not incorporate candidates into reviewed sanction counters automatically.
"""
import argparse
import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lxml import etree
from parser import candidates

HOST = 'https://dserver.bundestag.de/btp/21'
MAX_SIZE = 25 * 1024 * 1024
PUBLIC_CLASSES = ('possible_grant', 'named_group_confirmation',
                  'appeal_or_retrospective', 'warning_or_conditional')
PUBLIC_LIMIT = 40
FIELDS = ('hinweis_id', 'sitzung', 'datum', 'klasse', 'xml_zeile',
          'textstelle', 'xml_quelle', 'pdf_quelle', 'status')


def safe_parse(data, session):
    if not 150 <= len(data) <= MAX_SIZE:
        raise ValueError('XML-Datei zu gross oder zu klein')
    root = etree.fromstring(data, etree.XMLParser(
        resolve_entities=False, load_dtd=False, no_network=True,
        recover=False, huge_tree=False))
    if root.tag != 'dbtplenarprotokoll' or root.get('wahlperiode') != '21':
        raise ValueError('Unerwartete XML-Wahlperiode/DTD')
    if root.get('sitzung-nr') != str(session) or root.find('sitzungsverlauf') is None:
        raise ValueError('Unerwartete XML-Sitzung/fehlender Sitzungsverlauf')
    datum = root.get('sitzung-datum', '')
    try:
        datetime.strptime(datum, '%d.%m.%Y')
    except ValueError as exc:
        raise ValueError('XML-Sitzungsdatum ungueltig') from exc
    return root


def review_rows(root, session):
    date = root.get('sitzung-datum')
    path = Path(f'21{session:03d}.xml')
    result = []
    for item in candidates(path, root=root):
        code = hashlib.sha256(item['text'].encode('utf-8')).hexdigest()[:12]
        result.append({
            'hinweis_id': f'21-{session:03d}-L{item["line"]}-{code}',
            'sitzung': str(session), 'datum': date,
            'klasse': item['classification'], 'xml_zeile': str(item['line']),
            'textstelle': item['text'][:850],
            'xml_quelle': f'{HOST}/21{session:03d}.xml',
            'pdf_quelle': f'{HOST}/21{session:03d}.pdf',
            'status': 'manuelle_pruefung_erforderlich',
        })
    return result


def fetch(session, cache_dir, refresh=False):
    """Return bytes or None if the Bundestag responds 404 (not yet released)."""
    target=cache_dir / f'21{session:03d}.xml'
    if target.exists() and not refresh:
        data=target.read_bytes()
        safe_parse(data,session)
        return data
    request=Request(f'{HOST}/21{session:03d}.xml', headers={
        'User-Agent': 'OrdnungsrufCounter/0.4 (github.com/Erzkon/ordnungsrufe)',
        'Accept':'application/xml,text/xml,*/*',
    })
    for attempt in range(3):
        try:
            with urlopen(request,timeout=35) as response:
                data=response.read(MAX_SIZE+1)
            safe_parse(data,session)
            cache_dir.mkdir(parents=True,exist_ok=True)
            tmp=target.with_suffix('.tmp')
            tmp.write_bytes(data)
            tmp.replace(target)
            return data
        except HTTPError as exc:
            if exc.code==404:
                return None
            if attempt==2: raise
        except (TimeoutError, ConnectionError, OSError):
            if attempt==2: raise
        time.sleep(2**attempt)
    raise RuntimeError('XML Download gescheitert')


def scan(cache, max_session=250, refresh_last=6, refresh_older_bucket=None):
    """Recheck recently published XMLs and a rotating seventh of older sessions.

    In addition to the newest documents, each day re-downloads about 1/7 of
    archived files, so a silently revised official XML does not remain cached
    forever. A failed refresh fails closed, retaining the previous web snapshot.
    """
    if refresh_older_bucket is None:
        refresh_older_bucket = datetime.now(timezone.utc).weekday()
    if type(refresh_older_bucket) is not int or not 0 <= refresh_older_bucket <= 6:
        raise ValueError('Ungueltiger woechentlicher Refresh-Bucket')
    cache.mkdir(parents=True,exist_ok=True)
    cached=[int(m.group(1)) for p in cache.glob('21*.xml')
            if (m:=re.fullmatch(r'21(\d{3})\.xml',p.name))]
    max_cached=max(cached,default=0)
    last_ok=0
    missing=[]
    hints=[]
    consecutive_404=0
    for session in range(1,max_session+1):
        refresh = (session <= max_cached and (
            session >= max_cached - refresh_last or
            session % 7 == refresh_older_bucket))
        data=fetch(session,cache,refresh=refresh)
        if data is None:
            missing.append(session)
            consecutive_404+=1
            if consecutive_404>=3:
                break
            continue
        consecutive_404=0
        root=safe_parse(data,session)
        hints.extend(review_rows(root,session))
        last_ok=session
        if session % 10==0:
            print(f'XML 21: bis Sitzung {session} geprüft',flush=True)
    if last_ok==0:
        raise ValueError('Kein Protokoll der 21. Wahlperiode verfuegbar')
    gaps=[n for n in missing if n<last_ok]
    if gaps:
        raise ValueError(f'Quellenluecken vor Sitzung {last_ok}: {gaps}')
    if last_ok==max_session:
        raise ValueError('Maximale Sitzungsnummer erreicht: Vollstaendigkeit nach oben unklar')
    ids=[r['hinweis_id'] for r in hints]
    if len(ids)!=len(set(ids)):
        raise ValueError('Nicht eindeutige Hinweis-IDs')
    return hints,{
        'status':'bereit', 'wahlperiode':21, 'letzte_sitzung':last_ok,
        'untersuchte_sitzungen':last_ok, 'textstellen_zur_pruefung':len(hints),
        'automatisch_bestaetigte_ordnungsrufe':0,
        'woechentlicher_quellenrefresh_bucket':refresh_older_bucket,
        'zuletzt_geprueft_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'hinweis':'Automatisch erkannte Textstellen sind KEINE bestätigten Ordnungsrufe; Fälle können Erwähnungen, Drohungen, Einsprüche oder Dubletten sein.'
    }



def public_feed(hints, summary, limit=PUBLIC_LIMIT):
    """Publish a limited, *unverified* activity feed, never a sanction counter.

    No person or faction is attributed automatically. The source URL is
    constructed from the validated session, not copied from candidate input.
    """
    if not 1 <= limit <= 100:
        raise ValueError('Feed-Limit ausserhalb des Sicherheitsbereichs')
    allowed = set(PUBLIC_CLASSES)
    selected = []
    unique = set()
    for h in hints:
        session = int(h['sitzung'])
        if not 1 <= session <= summary['letzte_sitzung']:
            raise ValueError('Feed: Sitzung ausserhalb des gescannten Bereichs')
        if not re.fullmatch(r'21-\d{3}-L\d+-[0-9a-f]{12}', h['hinweis_id']):
            raise ValueError('Feed: ungueltige Hinweis-ID')
        if h['hinweis_id'] in unique:
            raise ValueError('Feed: doppelte Hinweis-ID')
        unique.add(h['hinweis_id'])
        if h['klasse'] not in allowed:
            continue
        date = datetime.strptime(h['datum'], '%d.%m.%Y').date().isoformat()
        # Only excerpts, never assume the extract represents the full debate.
        snippet = ' '.join(h['textstelle'].split())[:220]
        selected.append({
            'id': h['hinweis_id'], 'session': session, 'date': date,
            'kind': h['klasse'], 'excerpt': snippet,
            'source': f'{HOST}/21{session:03d}.pdf',
        })
    # Multiple paragraphs can reference the same event. The feed deliberately
    # calls these *text locations* and does not collapse/count sanctions.
    selected.sort(key=lambda x: (x['date'], x['session'], x['id']), reverse=True)
    return {
        'meta': {
            'legislature': 21, 'status': 'unverified_text_locations',
            'last_scan_utc': summary['zuletzt_geprueft_utc'],
            'sessions_scanned': summary['untersuchte_sitzungen'],
            'all_text_locations': summary['textstellen_zur_pruefung'],
            'selected_text_locations': len(selected),
            'shown': min(len(selected), limit),
            'warning': 'Textstellen sind keine bestaetigten Ordnungsrufe. Keine automatische Personen- oder Fraktionszuordnung.',
        },
        'items': selected[:limit],
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache-dir',type=Path,default=Path('.cache/wp21'))
    p.add_argument('--candidates',type=Path,default=Path('wp21_hinweise.csv'))
    p.add_argument('--summary',type=Path,default=Path('docs/data/scan_21.json'))
    p.add_argument('--max-session',type=int,default=250)
    p.add_argument('--public-feed',type=Path,default=Path('docs/data/hinweise_21.json'))
    a=p.parse_args()
    if not 10<=a.max_session<=450:
        p.error('--max-session muss zwischen 10 und 450 liegen')
    hints,summary=scan(a.cache_dir,max_session=a.max_session)
    a.candidates.parent.mkdir(parents=True,exist_ok=True)
    with a.candidates.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(hints)
    a.summary.parent.mkdir(parents=True,exist_ok=True)
    a.summary.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    a.public_feed.parent.mkdir(parents=True,exist_ok=True)
    a.public_feed.write_text(json.dumps(public_feed(hints,summary),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{summary["untersuchte_sitzungen"]} Protokolle, {len(hints)} Hinweise (kein gepruefter Counter).')

if __name__=='__main__':main()
