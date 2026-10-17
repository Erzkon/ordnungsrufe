"""Fail-closed, fully paginated official Bundestag resolution-minute catalogue."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from wp21_gottschalk_amtliche_beschluesse import (
    SOURCES, PROVISIONAL_103,
)
from wp21_amtliche_protokolle_katalog import (
    INDEX_URL, FIRST, MAX_PAGE_BYTES, KNOWN_URLS, PAGE_SIZE,
    advertised_endpoint, catalogue, parse_page, audit, render, run,
    fetch_bytes,
)

ENDPOINT=(
    'https://www.bundestag.de/ajax/filterlist/de/dokumente/protokolle/'
    'amtlicheprotokolle/442098-442098'
)


def index():
    return (
        '<!doctype html><html><head></head><body>'
        '<section data-dataloader-url="'
        '/ajax/filterlist/de/dokumente/protokolle/'
        'amtlicheprotokolle/442098-442098" data-limit="10"></section>'
        '</body></html>'
    ).encode()


def official(s):
    return KNOWN_URLS.get(
        s, f'https://www.bundestag.de/resource/blob/999999/amtpr21{s:03d}.pdf')


def page(offset, *, max_session=100, total=796, skip=(), replace_id=None,
         bad_label=False):
    sessions=list(range(max_session-offset, max_session-offset-10, -1))
    links=[]
    for s in sessions:
        if s in skip:
            continue
        url=official(s)
        label=s+1 if bad_label and s==sessions[0] else s
        if replace_id and s==sessions[0]:
            url=url.replace('https://www.bundestag.de',
                            'https://other.example')
        links.append(
            f'<li><a target="_blank" href="{url}">'
            f'<span class="a-link__label">{label}. Sitzung am Freitag</span>'
            '</a></li>')
    return (
        '<section class="official">'
        + ''.join(links)
        + f'<nav data-hits="{total}" data-limit="10">'
        + '<button data-offset="10"></button></nav></section>'
    ).encode()


def provisional():
    return (
        b'<!doctype html><html><body>Tagesaktuelles Plenarprotokoll 21/103 '
        b'AUTORISIERTE FASSUNG Deutscher Bundestag 103. Sitzung '
        b'vom 16. Oktober 2026</body></html>'
    )


def textpages(s):
    first=f'21. Wahlperiode\nAmtliches Protokoll\n{s}. Sitzung des Bundestages\n'
    if s==FIRST:
        return [
            first+'Einleitung und Sitzungsgegenstände in der ersten Sitzung',
            'Zusatzpunkt 4 Einspruch des Kay Gottschalk gegen den '
            'erteilten Ordnungsruf wird zurückgewiesen, Abstimmung ist erfolgt.',
            'Die Sitzung wird geschlossen und ein neuer Termin bestimmt.']
    if s==76:
        return [first+'Umfassende Beschlüsse in dieser Plenarsitzung.',
                'Kay Gottschalk Einspruch gegen zweiten Ordnungsruf, '
                'weiterer parlamentarischer Vorgang zur Prüfung.']
    return [first+'Beschlussprotokoll mit mehreren Tagesordnungspunkten.',
            'Keine personenscharfe Einspruchsentscheidung auf dieser Seite.']


class SourceLoader:
    def __init__(self, latest=100, skip=(), bad_page=None, bad_total=None,
                 missing_source=None):
        self.latest=latest
        self.calls=[]
        self.skip=skip
        self.bad_page=bad_page
        self.bad_total=bad_total
        self.missing_source=missing_source

    def __call__(self, url, *, limit):
        self.calls.append(url)
        if url==INDEX_URL:
            return index()
        if url==PROVISIONAL_103:
            return provisional()
        if url.startswith(ENDPOINT+'?'):
            query=url.split('?',1)[1]
            items=dict(chunk.split('=',1) for chunk in query.split('&'))
            off=int(items['offset'])
            return page(off,max_session=self.latest,
                        skip=self.skip,
                        total=(797 if off==10 and self.bad_total else 796),
                        bad_label=(off==self.bad_page))
        if self.missing_source and url==self.missing_source:
            raise ValueError('Quelle fehlt')
        if re.fullmatch(
                r'https://www\.bundestag\.de/resource/blob/\d+/amtpr21\d{3}\.pdf',
                url):
            return url.encode('utf-8')*2
        raise ValueError(f'Unknown URL {url}')


def extractor(raw):
    m=re.search(rb'amtpr21(\d{3})\.pdf',raw)
    if not m:
        raise ValueError('synthetic source mismatch')
    return textpages(int(m.group(1)))


class CatalogueTests(unittest.TestCase):
    def test_official_page_advertises_exact_allowlisted_dataloader(self):
        self.assertEqual(advertised_endpoint(index()),ENDPOINT)
        forged=index().replace(b'/442098-442098',b'/external-other')
        with self.assertRaisesRegex(ValueError,'Dataloader'):
            advertised_endpoint(forged)
        two=index().replace(b'</body>',b'<div data-dataloader-url="/ajax/filterlist/de/dokumente/protokolle/amtlicheprotokolle/442099-442099"></div></body>')
        with self.assertRaisesRegex(ValueError,'Dataloader'):
            advertised_endpoint(two)

    def test_ten_official_links_from_page_and_true_session_labels(self):
        total,items=parse_page(page(0),0)
        self.assertEqual(total,796)
        self.assertEqual([s for s,_ in items],list(range(100,90,-1)))
        self.assertEqual(items[0][1],official(100))
        self.assertEqual(items[-1][1],official(91))
        with self.assertRaisesRegex(ValueError,'Sitzungstitel'):
            parse_page(page(0,bad_label=True),0)

    def test_full_59_sittings_across_six_paginated_live_queries(self):
        loader=SourceLoader()
        data=catalogue(loader)
        ids=[r['session'] for r in data['catalogue_entries']]
        self.assertEqual(ids,list(range(100,41,-1)))
        self.assertEqual(data['latest_published_official_minute'],100)
        self.assertEqual(len([u for u in loader.calls if '?' in u]),6)
        self.assertTrue(data['not_yet_published_minutes_outside_scope'])
        self.assertEqual(data['catalogue_entries'][-1]['source'],KNOWN_URLS[42])

    def test_link_gap_duplicate_page_or_drifting_hits_fail_closed(self):
        for config in ({'skip':(88,)},{'bad_total':True},
                       {'bad_page':20}):
            with self.subTest(config=config),self.assertRaises(ValueError):
                catalogue(SourceLoader(**config))

    def test_if_42_is_not_reached_it_cannot_claim_full_coverage(self):
        with self.assertRaises(ValueError):
            catalogue(SourceLoader(latest=175))
        with self.assertRaises(ValueError):
            parse_page(page(0),0,expected_total=795)
        with self.assertRaises(ValueError):
            fetch_bytes('https://example.com/resource/blob/999999/amtpr21042.pdf')

    def test_real_source_report_only_recommends_review(self):
        loader=SourceLoader()
        with tempfile.TemporaryDirectory() as d:
            report=run(Path(d)/'review.json',Path(d)/'review.md',
                       load=loader,extract=extractor,max_workers=2)
            self.assertEqual(report['minutes_checked'],59)
            self.assertEqual(report['pages_checked'],118+1)
            self.assertEqual(report['later_review_context_count'],1)
            self.assertEqual(report['later_review_contexts'][0]['session'],76)
            self.assertEqual(report['public_counter_delta'],0)
            self.assertTrue(report['second_gottschalk_measure_legality_unresolved'])
            self.assertTrue((Path(d)/'review.json').exists())
            self.assertEqual(json.loads((Path(d)/'review.json').read_text())
                             ['schema'],report['schema'])
            self.assertIn('Kein Zählerupdate',render(report))

    def test_late_pdf_failure_never_creates_partial_audit(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out.json'
            with self.assertRaisesRegex(ValueError,'Quelle fehlt'):
                run(out,Path(d)/'out.md',
                    load=SourceLoader(missing_source=official(76)),
                    extract=extractor,max_workers=1)
            self.assertFalse(out.exists())

    def test_legal_assertions_cannot_be_overridden(self):
        m=catalogue(SourceLoader())
        rows={}
        for entry in m['catalogue_entries']:
            sid=entry['session']
            rows[sid]={
                'session':sid,'official_url':entry['source'],
                'pdf_sha256':'0'*64,'pages_checked':1,
                'name_appeal_contexts':[],
                'possible_later_context_count':0,
                'baseline_known_first_appeal_only':sid==42}
        from wp21_gottschalk_amtliche_beschluesse import provisional_103
        report=audit(m,rows,provisional_103(provisional()))
        for x in ({'public_counter_delta':1},
                  {'not_all_future_or_other_documents_excluded':False},
                  {'second_gottschalk_measure_legality_unresolved':False},
                  {'automatically_confirmed_effective_sanctions':1}):
            with self.subTest(x=x),self.assertRaises(ValueError):
                render({**report,**x})

    def test_catalogue_does_not_implicitly_approve_missing_pdf(self):
        m=catalogue(SourceLoader())
        with self.assertRaisesRegex(ValueError,'Alle amtlich'):
            audit(m,{},{})


if __name__=='__main__':
    unittest.main()
