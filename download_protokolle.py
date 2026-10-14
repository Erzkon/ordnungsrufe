"""Download all XML transcripts of one Bundestag term with strict validation.

Uses only Python's standard library for downloads. XML is parsed with lxml
(already required by parser.py) without loading external DTD/entities.
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lxml import etree

BASE_URL = 'https://dserver.bundestag.de/btp/20'
MAX_XML_BYTES = 25 * 1024 * 1024


def check_xml(payload, session):
    """Reject empty, malformed, unexpected or mislabelled documents."""
    if len(payload) < 150:
        raise ValueError('Datei ist zu klein, um ein Plenarprotokoll zu sein')
    if len(payload) > MAX_XML_BYTES:
        raise ValueError('Datei ist unerwartet gross')
    root = etree.fromstring(payload, parser=etree.XMLParser(
        resolve_entities=False, load_dtd=False, no_network=True,
        recover=False, huge_tree=False))
    if root.tag != 'dbtplenarprotokoll':
        raise ValueError(f'Unerwartetes XML-Wurzelelement: {root.tag}')
    if root.get('wahlperiode') != '20' or root.get('sitzung-nr') != str(session):
        raise ValueError('Wahlperiode/Sitzungsnummer passen nicht zur URL')
    if not root.get('sitzung-datum'):
        raise ValueError('Sitzungsdatum fehlt')
    if root.find('sitzungsverlauf') is None:
        raise ValueError('Sitzungsverlauf fehlt')
    return root.get('sitzung-datum')


def download_one(session, folder, retries=4):
    filename = f'20{session:03d}.xml'
    url = f'{BASE_URL}/{filename}'
    final_path = folder / filename
    last_error = "unbekannter Fehler"
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers={
                'User-Agent': 'OrdnungsrufCounter/0.3 (github.com/Erzkon/ordnungsrufe)',
                'Accept': 'application/xml,text/xml,*/*',
            })
            with urlopen(req, timeout=35) as response:
                payload = response.read(MAX_XML_BYTES + 1)
            date = check_xml(payload, session)
            temp_path = final_path.with_suffix('.xml.tmp')
            temp_path.write_bytes(payload)
            temp_path.replace(final_path)
            return dict(session=session, file=filename, url=url, status='ok',
                        datum=date, bytes=len(payload))
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            # A genuine HTTP 404 is not fixed by repeating the same request.
            if isinstance(exc, HTTPError) and exc.code == 404:
                break
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 8))
    return dict(session=session, file=filename, url=url, status='error',
                error=last_error)


def download_all(folder, report_path, start=1, end=214, workers=5):
    if not 1 <= start <= end <= 214:
        raise ValueError('Erlaubter Sitzungsbereich: 1 bis 214')
    folder.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(download_one, n, folder): n for n in range(start, end + 1)}
        for future in as_completed(tasks):
            result = future.result()
            results.append(result)
            print(f"{result['session']:03d}: {result['status']}"
                  + (f" ({result['error']})" if result['status'] == 'error' else ''), flush=True)
    results.sort(key=lambda r: r['session'])
    succeeded = sum(r['status'] == 'ok' for r in results)
    report = {
        'quelle': BASE_URL,
        'wahlperiode': 20,
        'bereich': {'von': start, 'bis': end},
        'download_utc': datetime.now(timezone.utc).isoformat(),
        'erwartet': end - start + 1,
        'erfolgreich': succeeded,
        'fehlgeschlagen': len(results) - succeeded,
        'vollstaendig': succeeded == len(results),
        'dateien': results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Geprueft: {succeeded}/{len(results)}. Report: {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description='Bundestag XML Wahlperiode 20 herunterladen')
    parser.add_argument('--folder', type=Path, default=Path('protokolle'))
    parser.add_argument('--report', type=Path, default=Path('download-report.json'))
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=214)
    parser.add_argument('--workers', type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.workers <= 12:
        parser.error('Workers muessen zwischen 1 und 12 liegen')
    report = download_all(args.folder, args.report, args.start, args.end, args.workers)
    if not report['vollstaendig']:
        parser.exit(1, 'FEHLER: Mindestens ein Protokoll fehlt. Siehe download-report.json.\n')


if __name__ == '__main__':
    main()
