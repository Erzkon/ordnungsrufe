#!/usr/bin/env python3
"""Read-only exhaustive catalogue of *published* official 21st-term resolution PDFs.

The Bundestag's own page advertises its AJAX dataloader. Discover that
endpoint from the source HTML and paginate it at the site's advertised
10-document page size. Never invent a resource/blob identifier. A missing
page, duplicate, changed catalogue, or sitting-number gap invalidates the
whole audit; do not create a partial report or silently infer legal outcomes.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
import json
import re
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from wp21_gottschalk_amtliche_beschluesse import (
    SOURCES, PROVISIONAL_103, MAX_PDF_BYTES, MAX_HTML_BYTES,
    pdf_pages, hints_for_pages, provisional_103, download as known_download,
)

INDEX_URL = 'https://www.bundestag.de/dokumente/protokolle/amtlicheprotokolle'
OFFICIAL_HOST = 'https://www.bundestag.de'
CATALOGUE_RE = re.compile(
    r'/ajax/filterlist/de/dokumente/protokolle/amtlicheprotokolle/'
    r'\d{5,8}-\d{5,8}\Z'
)
PDF_URL = re.compile(
    r'https://www\.bundestag\.de/resource/blob/[1-9]\d{4,10}/'
    r'amtpr21(\d{3})\.pdf\Z'
)
LABEL = re.compile(r'\b(\d{1,3})\.\s*Sitzung\b')
FIRST = 42
PAGES_LIMIT = 13
PAGE_SIZE = 10
MAX_PAGE_BYTES = 2_000_000
MAX_FILE_BYTES = 3_000_000
KNOWN_URLS = dict(SOURCES)


class Markup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.dataloaders = []
        self.anchors = []
        self.open_anchor = None
        self.hits = []

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        url = props.get('data-dataloader-url')
        if url is not None:
            self.dataloaders.append(url)
        if props.get('data-hits'):
            self.hits.append(props['data-hits'])
        if tag == 'a':
            self.open_anchor = {'url': props.get('href', ''), 'pieces': []}

    def handle_data(self, data):
        if self.open_anchor is not None:
            self.open_anchor['pieces'].append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.open_anchor is not None:
            item = self.open_anchor
            self.anchors.append((item['url'], ' '.join(item['pieces'])))
            self.open_anchor = None


def parse_html(data):
    if not isinstance(data, bytes) or not 100 <= len(data) <= MAX_FILE_BYTES:
        raise ValueError('Amtlicher HTML-Katalog fehlt oder ist zu groß')
    text = data.decode('utf-8')
    if '<html' not in text[:1000].lower() and '<a ' not in text[:1000].lower():
        raise ValueError('Bundestag-Antwort ist keine erwartete HTML-Seite')
    parser = Markup()
    parser.feed(text)
    return parser


def advertised_endpoint(index_bytes):
    page = parse_html(index_bytes)
    paths = [x for x in page.dataloaders if CATALOGUE_RE.fullmatch(x)]
    if len(paths) != 1 or len(page.dataloaders) != 1:
        raise ValueError('Amtlicher Dataloader nicht eindeutig belegt')
    return OFFICIAL_HOST + paths[0]


def parse_page(body, offset, expected_total=None):
    html = parse_html(body)
    if len(html.hits) < 1 or len(set(html.hits)) != 1:
        raise ValueError('Amtlicher Katalog ohne stabile Gesamtzahl')
    count_str = html.hits[0]
    if not re.fullmatch(r'[1-9]\d{0,5}', count_str):
        raise ValueError('Ungültige amtliche Gesamttrefferzahl')
    total = int(count_str)
    if expected_total is not None and total != expected_total:
        raise ValueError('Amtliche Katalog-Gesamtzahl veränderte sich')
    items = []
    for url, label in html.anchors:
        match = PDF_URL.fullmatch(url)
        if not match:
            continue
        sitting = int(match.group(1))
        labels = LABEL.findall(label)
        if len(labels) != 1 or int(labels[0]) != sitting:
            raise ValueError('Amtlicher PDF-Link passt nicht zum Sitzungstitel')
        if not 1 <= sitting <= 150:
            raise ValueError('Fremde Wahlperiode/Sitzung im Katalog')
        items.append((sitting, url))
    if (not 1 <= len(items) <= PAGE_SIZE
            or offset % PAGE_SIZE != 0
            or offset >= total
            or len(items) != min(PAGE_SIZE, total-offset)):
        raise ValueError('Amtliche Katalogseite fehlt oder ist unvollständig')
    if len(set(items)) != len(items) or any(
            left[0] <= right[0] for left, right in zip(items, items[1:])):
        raise ValueError('Katalogeinträge sind doppelt oder nicht absteigend')
    return total, items


def fetch_bytes(url, *, limit=MAX_FILE_BYTES):
    if not (url == INDEX_URL or url == PROVISIONAL_103
            or CATALOGUE_RE.fullmatch(url.removeprefix(OFFICIAL_HOST))
            and url.startswith(OFFICIAL_HOST + '/')
            or url.startswith(OFFICIAL_HOST + '/ajax/filterlist/de/dokumente/protokolle/amtlicheprotokolle/')
            and urlsplit(url).path.startswith('/ajax/filterlist/de/dokumente/protokolle/amtlicheprotokolle/')
            and urlsplit(url).query in {
                urlencode({'offset': i, 'limit': PAGE_SIZE})
                for i in range(0, PAGES_LIMIT*PAGE_SIZE, PAGE_SIZE)}
            or PDF_URL.fullmatch(url)):
        raise ValueError('Quellen-URL nicht ausdrücklich Bundestag/Katalog')
    request = Request(url, headers={
        'User-Agent': 'OrdnungsrufCounter/0.7 (github.com/Erzkon/ordnungsrufe)',
        'Accept': 'application/pdf,text/html,*/*',
    })
    with urlopen(request, timeout=32) as response:
        if response.status != 200:
            raise ValueError('Amtlicher Katalog/Originaldatei HTTP != 200')
        final = response.geturl()
        # HTML service stays on the Bundestag domain; PDF links are same-host.
        if not final.startswith('https://www.bundestag.de/'):
            raise ValueError('Amtliche Quellenweiterleitung nicht belegt')
        data = response.read(limit+1)
    if not 100 <= len(data) <= limit:
        raise ValueError('Amtliche Datei leer oder zu groß')
    return data


def catalogue(load=fetch_bytes):
    endpoint = advertised_endpoint(load(INDEX_URL, limit=MAX_FILE_BYTES))
    found, expected = [], None
    seen = set()
    for offset in range(0, PAGES_LIMIT * PAGE_SIZE, PAGE_SIZE):
        url = endpoint + '?' + urlencode({'offset': offset, 'limit': PAGE_SIZE})
        total, records = parse_page(load(url, limit=MAX_PAGE_BYTES), offset,
                                    expected_total=expected)
        expected = total
        for sitting, original in records:
            if sitting in seen:
                raise ValueError('Amtlicher Katalog enthält Sitzungsdubletten')
            if found and sitting != found[-1][0] - 1:
                raise ValueError('Amtlicher Beschlussprotokoll-Katalog hat eine Sitzungsnummernlücke')
            seen.add(sitting)
            if sitting >= FIRST:
                found.append((sitting, original))
            elif sitting == FIRST-1:
                # The remainder belongs to earlier sittings; do not assert
                # the whole site's historical archive is exhaustively scanned.
                break
        if FIRST in seen:
            break
    if (not found or found[-1][0] != FIRST
            or found[0][0] < 90
            or len(found) != found[0][0] - FIRST + 1):
        raise ValueError('Amtlicher Katalog von neuester Sitzung bis 21/042 nicht lückenlos')
    for sitting, original in found:
        if sitting in KNOWN_URLS and original != KNOWN_URLS[sitting]:
            raise ValueError('Vorherige amtliche PDF-Quellenidentität hat sich verändert')
    return {
        'catalogue_url': INDEX_URL,
        'observed_dataloader': endpoint,
        'total_site_document_count': expected,
        'latest_published_official_minute': found[0][0],
        'first_checked_official_minute': FIRST,
        'catalogue_entries': [
            {'session': s, 'source': url} for s, url in found],
        'all_published_official_minutes_from_first_are_listed': True,
        'not_yet_published_minutes_outside_scope': True,
    }


def verify_pdf(entry, load=fetch_bytes, extract=pdf_pages):
    url, s = entry['source'], entry['session']
    if not PDF_URL.fullmatch(url) or int(PDF_URL.fullmatch(url).group(1)) != s:
        raise ValueError('Amtliche Original-PDF-ID stimmt nicht')
    raw = load(url, limit=MAX_PDF_BYTES)
    pages = extract(raw)
    candidates = hints_for_pages(pages, s, url)
    return {
        'session': s, 'official_url': url,
        'pdf_sha256': hashlib.sha256(raw).hexdigest(),
        'pages_checked': len(pages),
        'name_appeal_contexts': candidates,
        'possible_later_context_count': 0 if s == FIRST else len(candidates),
        'baseline_known_first_appeal_only': s == FIRST,
    }


def audit(manifest, records, provisional):
    expected_ids = [x['session'] for x in manifest['catalogue_entries']]
    if (len(expected_ids) < 30 or len(set(expected_ids)) != len(expected_ids)
            or set(records) != set(expected_ids)
            or expected_ids != list(range(expected_ids[0], FIRST-1, -1))):
        raise ValueError('Alle amtlich veröffentlichten Sitzungen müssen geprüft sein')
    ordered = [records[session] for session in expected_ids]
    return {
        'schema': 'wp21-all-published-official-resolution-minutes-v1',
        'official_catalogue': manifest,
        'pages_checked': sum(row['pages_checked'] for row in ordered),
        'minutes_checked': len(ordered),
        'source_reports': ordered,
        'known_first_vote_reference': FIRST,
        'later_review_contexts': [
            item for record in ordered if record['session'] != FIRST
            for item in record['name_appeal_contexts']],
        'later_review_context_count': sum(
            row['possible_later_context_count'] for row in ordered),
        'provisional_sitting_103': provisional,
        'no_publication_after_latest_does_not_prove_legal_absence': True,
        'not_all_future_or_other_documents_excluded': True,
        'second_gottschalk_measure_legality_unresolved': True,
        'public_counter_delta': 0,
        'automatically_confirmed_effective_sanctions': 0,
        'automatically_rescinded_sanctions': 0,
    }


def render(report):
    if (report.get('schema') !=
            'wp21-all-published-official-resolution-minutes-v1'
            or report.get('no_publication_after_latest_does_not_prove_legal_absence') is not True
            or report.get('not_all_future_or_other_documents_excluded') is not True
            or report.get('second_gottschalk_measure_legality_unresolved') is not True
            or report.get('public_counter_delta') != 0
            or report.get('automatically_confirmed_effective_sanctions') != 0
            or report.get('automatically_rescinded_sanctions') != 0):
        raise ValueError('Amtliche PDF-Metadaten erlauben keine Rechtsfolgenzählung')
    latest = report['official_catalogue']['latest_published_official_minute']
    lines = [
        '# Vollständiger Katalog der veröffentlichten Amtlichen Beschlussprotokolle',
        '', f"Bundestag-Originalkatalog: {INDEX_URL}",
        f"Veröffentlichte Sitzungen **21/042 bis 21/{latest:03d}**:",
        f"{report['minutes_checked']} vollständige PDF-Dokumente, "
        f"{report['pages_checked']} PDF-Seiten.",
        f"Spätere personenscharfe Kontexttreffer: "
        f"{report['later_review_context_count']}.",
        'Die bekannte erste Zurückweisung aus 21/042 ist eine Referenz.',
        'Nicht veröffentlichte neuere Amtliche Protokolle sind nicht geprüft.', '',
    ]
    for report_row in report['source_reports']:
        lines.append(
            f"- [21/{report_row['session']:03d}]({report_row['official_url']}): "
            f"{report_row['pages_checked']} Seiten, "
            f"{report_row['possible_later_context_count']} neue Prüfhinweise")
    lines.extend([
        '', '**Kein Zählerupdate und keine rechtliche Negativaussage.**',
        'Auch ein vollständiger amtlicher PDF-Katalog schließt andere '
        'Verfahrensdokumente oder künftige Entscheidungen nicht aus.', '',
    ])
    return '\n'.join(lines)


def run(output, brief, *, load=fetch_bytes, extract=pdf_pages,
        max_workers=4):
    if type(max_workers) is not int or not 1 <= max_workers <= 4:
        raise ValueError('Zu viele parallele amtliche Quellendownloads')
    manifest = catalogue(load)
    records = {}
    with ThreadPoolExecutor(max_workers=max_workers) as workers:
        reports = list(workers.map(
            lambda row: verify_pdf(row, load=load, extract=extract),
            manifest['catalogue_entries']))
    for row in reports:
        records[row['session']] = row
    # Session 103 is a *provisional* source, not an official minute.
    provisional = provisional_103(load(PROVISIONAL_103, limit=MAX_HTML_BYTES))
    report = audit(manifest, records, provisional)
    markdown = render(report)
    for target, text in (
            (Path(output), json.dumps(report, ensure_ascii=False, indent=2)+'\n'),
            (Path(brief), markdown)):
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix+'.tmp')
        tmp.write_text(text, encoding='utf-8')
        tmp.replace(target)
    if report['later_review_context_count']:
        print('::warning::Amtliche spätere Gottschalk-Kontexte '
              'zur manuellen Prüfung, keine Zählerfreigabe')
    print('WP21_ALL_PUBLISHED_MINUTES_OK',
          report['minutes_checked'], 'original PDFs,',
          report['pages_checked'], 'PDF pages,',
          report['later_review_context_count'], 'manual later hits,',
          'zero public count changes')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--brief', type=Path, required=True)
    p.add_argument('--max-workers', type=int, default=4)
    args = p.parse_args()
    run(args.output, args.brief, max_workers=args.max_workers)
