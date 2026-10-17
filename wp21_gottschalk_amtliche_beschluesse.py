#!/usr/bin/env python3
"""Read-only, NON-exhaustive official resolution-minute PDFs and provisional 21/103.

Sources are ONLY independently verified Bundestag URLs in an explicit
manifest. We deliberately do not guess resource/blob IDs or assert complete
coverage of missing sessions. Findings are review hints, not sanction counts.
"""
import argparse
import hashlib
import io
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

# Curated direct references found in the official Bundestag archive.
SOURCES = (
    (42, 'https://www.bundestag.de/resource/blob/1127824/amtpr21042.pdf'),
    (47, 'https://www.bundestag.de/resource/blob/1128778/amtpr21047.pdf'),
    (50, 'https://www.bundestag.de/resource/blob/1133828/amtpr21050.pdf'),
    (62, 'https://www.bundestag.de/resource/blob/1151672/amtpr21062.pdf'),
    (64, 'https://www.bundestag.de/resource/blob/1155776/amtpr21064.pdf'),
    (72, 'https://www.bundestag.de/resource/blob/1164732/amtpr21072.pdf'),
    (75, 'https://www.bundestag.de/resource/blob/1167292/amtpr21075.pdf'),
    (90, 'https://www.bundestag.de/resource/blob/1193900/amtpr21090.pdf'),
    (96, 'https://www.bundestag.de/resource/blob/1217460/amtpr21096.pdf'),
    (97, 'https://www.bundestag.de/resource/blob/1217462/amtpr21097.pdf'),
    (98, 'https://www.bundestag.de/resource/blob/1223440/amtpr21098.pdf'),
    (99, 'https://www.bundestag.de/resource/blob/1223442/amtpr21099.pdf'),
)
PROVISIONAL_103 = (
    'https://www.bundestag.de/dokumente/protokolle/vorlaeufig/'
    'vorlaeufig-196520'
)
PUBLIC_ARCHIVE = 'https://www.bundestag.de/dokumente/protokolle/amtlicheprotokolle'
KNOWN = 42
MAX_PDF_BYTES = 7 * 1024 * 1024
MAX_HTML_BYTES = 3 * 1024 * 1024
NAME = re.compile(r'\bKay\s+Gottschalk\b', re.I)
APPEAL = re.compile(r'\b(?:Einspruch\w*|Widerspruch\w*)\b', re.I)
ORDER = re.compile(r'\b(?:Ordnungsruf\w*|Ordnungsma[ßs]nahme\w*)\b', re.I)
SECOND = re.compile(r'\b(?:zweite[nmrs]?|2\.)\s+Ordnungs(?:ruf\w*|ma[ßs]nahme\w*)\b', re.I)


def norm(text):
    # Official PDF often line-breaks "Ord-\nnungsruf" and "zurück-\ngewiesen".
    text = re.sub(r'(?<=\w)-\s*\n\s*(?=\w)', '', text)
    text = text.replace('\u00ad', '').replace('\u0002', '')
    return ' '.join(text.split())


def download(url, max_bytes, *, opener=urlopen):
    allowed = {u for _, u in SOURCES} | {PROVISIONAL_103}
    if url not in allowed:
        raise ValueError('Nicht freigegebene Bundestag-Quelle')
    request = Request(url, headers={
        'User-Agent': 'OrdnungsrufCounter/0.7 (github.com/Erzkon/ordnungsrufe)',
        'Accept': 'application/pdf' if url.endswith('.pdf') else 'text/html',
    })
    with opener(request, timeout=32) as response:
        if response.status != 200:
            raise ValueError('Amtliche Quelle HTTP != 200')
        final = response.geturl()
        if not final.startswith('https://www.bundestag.de/'):
            raise ValueError('Unerlaubte Weiterleitung von Bundestag-Quelle')
        raw = response.read(max_bytes + 1)
    if not 100 <= len(raw) <= max_bytes:
        raise ValueError('Quelle leer oder zu groß')
    return raw


def pdf_pages(data):
    from pypdf import PdfReader
    if not data.startswith(b'%PDF-') or len(data) > MAX_PDF_BYTES:
        raise ValueError('Amtliche Protokolldatei ist kein begrenztes PDF')
    pdf = PdfReader(io.BytesIO(data), strict=True)
    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 55:
        raise ValueError('Protokoll-PDF nicht lesbar')
    pages = []
    for page in pdf.pages:
        text = page.extract_text(extraction_mode='plain')
        if not isinstance(text, str) or len(text) > 85000:
            raise ValueError('PDF-Seite ohne gültigen Text')
        pages.append(text)
    return pages


def hints_for_pages(pages, session, url):
    if not isinstance(pages, list) or not 1 <= len(pages) <= 55:
        raise ValueError('PDF-Seiten fehlen')
    first = norm(pages[0])
    if (f'{session}. Sitzung' not in first
            or 'Amtliches Protokoll' not in first
            or '21. Wahlperiode' not in first):
        raise ValueError('Amtliches Protokoll hat falsche Sitzungsidentität')
    hits = []
    for page_num, raw in enumerate(pages, 1):
        text = norm(raw)
        if len(text) < 40:
            raise ValueError('PDF-Seite ohne maschinell prüfbaren Text')
        for match in NAME.finditer(text):
            # The first official vote follows Janich's SECOND objection
            # on the same PDF page. Do not borrow its ordinal for Gottschalk.
            left = max(0, match.start()-280)
            heading = text.rfind('Zusatzpunkt', left, match.start())
            if heading >= 0:
                left = heading
            context = text[left:match.end()+280]
            own_following = text[match.end():match.end()+180]
            own_following = re.split(
                r'\b(?:Zusatzpunkt|Tagesordnungspunkt|Der Einspruch)\b',
                own_following, maxsplit=1)[0]
            if not (APPEAL.search(context) and ORDER.search(context)):
                continue
            hits.append({
                'session': session, 'pdf_page': page_num, 'source': url,
                'context_excerpt': context[:550],
                'source_page_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                'second_measure_explicitly_named': (
                    session != KNOWN and bool(SECOND.search(own_following))),
                'known_first_objection_only': session == KNOWN,
                'requires_person_and_outcome_source_review': True,
                'automatic_legal_conclusion': False,
                'public_count_delta': 0,
            })
    if session == KNOWN:
        # A proven positive source, not proof of the second objection.
        known = [x for x in hits if x['pdf_page'] == 2 and
                 'zurückgewiesen' in norm(x['context_excerpt']).lower()]
        if len(known) != 1:
            raise ValueError('Erste Gottschalk-Einspruchsentscheidung 21/042 fehlt')
    return hits


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.blocked = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.blocked += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript') and self.blocked:
            self.blocked -= 1
    def handle_data(self, data):
        if not self.blocked:
            self.text.append(data)


def provisional_103(data):
    if (not isinstance(data, bytes) or len(data) > MAX_HTML_BYTES
            or b'<html' not in data[:1000].lower()):
        raise ValueError('Unbekannte tagesaktuelle HTML-Quelle')
    parser = TextOnly()
    parser.feed(data.decode('utf-8'))
    text = norm(' '.join(parser.text))
    if (not re.search(r'Tagesaktuelles Plenarprotokoll\s+21/103', text)
            or not re.search(r'103\.\s*Sitzung', text)
            or not re.search(r'16\.\s*Oktober\s*2026', text)
            or 'AUTORISIERTE FASSUNG' not in text):
        raise ValueError('Vorläufige Protokoll-Identität 21/103 verändert')
    hits = []
    for match in NAME.finditer(text):
        nearby = text[max(0,match.start()-240):match.end()+240]
        if APPEAL.search(nearby) and ORDER.search(nearby):
            hits.append({
                'source': PROVISIONAL_103, 'session': 103,
                'context_excerpt': nearby,
                'possible_second_measure': bool(SECOND.search(nearby)),
                'manual_review_only': True, 'public_count_delta': 0,
            })
    return {
        'session': 103, 'url': PROVISIONAL_103, 'source_type': 'provisional_html',
        'sha256': hashlib.sha256(data).hexdigest(),
        'scope_is_partial_authorised_transcript': True,
        'not_equivalent_to_final_plenary_xml_or_official_minutes': True,
        'named_appeal_contexts': hits,
        'has_no_keyword_hit_is_not_negative_legal_proof': True,
    }


def audit(minutes, provisional):
    if set(minutes) != {s for s,_ in SOURCES}:
        raise ValueError('Nicht alle einzeln belegten PDF-Quellen untersucht')
    report = {
        'schema': 'wp21-gottschalk-official-minute-sample-v1',
        'official_archive': PUBLIC_ARCHIVE,
        'checked_resolution_minutes': [],
        'official_minutes_sessions_checked': len(SOURCES),
        'only_explicitly_sourced_pdf_urls_examined': True,
        'missing_official_minutes_not_checked': True,
        'not_full_sequence_of_official_resolution_minutes': True,
        'new_appeal_decision_not_automatically_established': True,
        'second_measure_effectiveness_unresolved': True,
        'provisional_session_103': provisional,
        'automatically_confirmed_effective_sanctions': 0,
        'automatically_rescinded_sanctions': 0,
        'public_counter_delta': 0,
    }
    for session, url in SOURCES:
        raw, pages = minutes[session]
        hits = hints_for_pages(pages, session, url)
        report['checked_resolution_minutes'].append({
            'session': session, 'url': url,
            'pdf_sha256': hashlib.sha256(raw).hexdigest(),
            'pages_checked': len(pages), 'person_named_appeal_contexts': hits,
            'candidate_count': len(hits),
            'non_first_appeal_candidate_count':
                len(hits) if session != KNOWN else 0,
        })
    return report


def markdown(r):
    if (r.get('schema') != 'wp21-gottschalk-official-minute-sample-v1'
            or r.get('missing_official_minutes_not_checked') is not True
            or r.get('not_full_sequence_of_official_resolution_minutes') is not True
            or r.get('new_appeal_decision_not_automatically_established') is not True
            or r.get('second_measure_effectiveness_unresolved') is not True
            or r.get('automatically_confirmed_effective_sanctions') != 0
            or r.get('automatically_rescinded_sanctions') != 0
            or r.get('public_counter_delta') != 0):
        raise ValueError('Unbelegte juristische Schlussfolgerung')
    lines = [
        '# Amtliche Beschlussprotokolle: begrenzte Quellenstichprobe', '',
        f"Nachgewiesene amtliche PDF-Quellen: "
        f"{r['official_minutes_sessions_checked']}.",
        'Diese Stichprobe deckt die übrigen Sitzungen nicht ab.', '',
    ]
    for row in r['checked_resolution_minutes']:
        lines.append(f"- [21/{row['session']:03d}]({row['url']}): "
                     f"{row['pages_checked']} Seiten, "
                     f"{row['candidate_count']} Gottschalk-/Einspruchs-Kontexte; "
                     f"{row['non_first_appeal_candidate_count']} nach "
                     'Abzug der bekannten ersten Entscheidung.')
    preview = r['provisional_session_103']
    lines += [
        '', f"[21/103 – tagesaktuelles, nicht endgültiges Protokoll]"
        f"({preview['url']}): "
        f"{len(preview['named_appeal_contexts'])} Kontexttreffer.",
        '', '**Keine automatische Rechtsfolgenannahme oder Zähleränderung.**',
        'Die Stichprobe umfasst NICHT alle Amtlichen Protokolle; '
        'das vorläufige Dokument ist nicht die endgültige Fassung. '
        'Ein fehlender Treffer beweist weder Abwesenheit von Einsprüchen '
        'noch die Wirksamkeit der zweiten Maßnahme.', '',
    ]
    return '\n'.join(lines)


def run(output, brief, *, download_source=download, extract=pdf_pages):
    sources = {}
    for session, url in SOURCES:
        data = download_source(url, MAX_PDF_BYTES)
        sources[session] = (data, extract(data))
    html = download_source(PROVISIONAL_103, MAX_HTML_BYTES)
    report = audit(sources, provisional_103(html))
    text = markdown(report)
    # Write only after all sources pass validation, never modify public counters.
    for path, value in (
            (Path(output), json.dumps(report, ensure_ascii=False, indent=2)+'\n'),
            (Path(brief), text)):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(value, encoding='utf-8')
        tmp.replace(path)
    print('WP21_GOTTSCHALK_MINUTES_OK',
          report['official_minutes_sessions_checked'], 'verified PDF sources,',
          len(report['provisional_session_103']['named_appeal_contexts']),
          'provisional 103 hints, no legal count changes')
    return report


if __name__ == '__main__':
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--output', type=Path, required=True)
    arg.add_argument('--brief', type=Path, required=True)
    args = arg.parse_args()
    run(args.output, args.brief)
