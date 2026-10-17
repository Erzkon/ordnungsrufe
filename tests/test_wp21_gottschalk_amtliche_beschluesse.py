"""Non-counting official minutes and provisional HTML evidence regressions."""
import tempfile
import unittest
from pathlib import Path

from wp21_gottschalk_amtliche_beschluesse import (
    SOURCES, PROVISIONAL_103, MAX_PDF_BYTES, MAX_HTML_BYTES,
    audit, hints_for_pages, markdown, norm, provisional_103, run, download,
)


def pages(session):
    first = f'21. Wahlperiode\nAmtliches Protokoll\n{session}. Sitzung des Deutschen Bundestages\n'
    if session == 42:
        return [first+'Einzelplan 01 und weitere amtliche Sitzungsgegenstände',
                'Zusatzpunkt 3\nDer Einspruch des Abgeordneten Steffen Janich ' +
                'gegen den zweiten Ordnungsruf wird zurückgewiesen.\n' +
                'Zusatzpunkt 4\nDer Einspruch gemäß § 39 der Geschäftsordnung '
                'des Abgeordneten Kay Gottschalk gegen den am 13. November 2025 '
                'erteilten Ord-\nnungsruf wird zurückgewiesen.\n', 'Die nächste Sitzung wird vom Bundestag turnusmäßig einberufen.']
    return [first+'Tagesordnungspunkt 5\nKeine besondere Entscheidung im parlamentarischen Beschlussverfahren',
            'Kay Gottschalk beantragt die Annahme eines Gesetzentwurfs im Bundestag.']


def html():
    return (b'<!doctype html><html><head><title>Test</title></head><body>'
            b'Tagesaktuelles Plenarprotokoll 21/103 '
            b'NACH &#167; 117 GOBT AUTORISIERTE FASSUNG '
            b'Deutscher Bundestag 103. Sitzung Berlin, Freitag, '
            b'den 16. Oktober 2026</body></html>')


def fake():
    return {
        s: (b'%PDF-1.7 test', pages(s)) for s, url in SOURCES
    }


class OfficialResolutions(unittest.TestCase):
    def test_first_official_vote_42_is_anchored_only_as_baseline(self):
        hits=hints_for_pages(pages(42),42,SOURCES[0][1])
        self.assertEqual(len(hits),1)
        self.assertEqual(hits[0]['pdf_page'],2)
        self.assertTrue(hits[0]['known_first_objection_only'])
        self.assertFalse(hits[0]['second_measure_explicitly_named'])
        self.assertNotIn('Steffen Janich',hits[0]['context_excerpt'])
        self.assertFalse(hits[0]['automatic_legal_conclusion'])
        self.assertEqual(hits[0]['public_count_delta'],0)

    def test_hyphenated_pdf_linebreaks_do_not_hide_first_vote(self):
        self.assertEqual(norm('Ord-\nnungsruf und zurück-\ngewiesen'),
                         'Ordnungsruf und zurückgewiesen')

    def test_unrelated_mention_is_not_a_new_appeal(self):
        for session,url in SOURCES[1:]:
            self.assertEqual(hints_for_pages(pages(session),session,url),[])

    def test_source_identity_must_match_official_session(self):
        with self.assertRaisesRegex(ValueError,'Sitzungsidentität'):
            hints_for_pages(pages(97),96,SOURCES[1][1])
        with self.assertRaisesRegex(ValueError,'Erste'):
            hints_for_pages([pages(42)[0],'Gottschalk hält eine allgemeine Rede zu einem Gesetzentwurf.',pages(42)[2]],
                            42,SOURCES[0][1])

    def test_provisional_103_is_never_called_final_or_complete(self):
        p=provisional_103(html())
        self.assertTrue(p['scope_is_partial_authorised_transcript'])
        self.assertTrue(p['not_equivalent_to_final_plenary_xml_or_official_minutes'])
        self.assertEqual(p['named_appeal_contexts'],[])
        self.assertTrue(p['has_no_keyword_hit_is_not_negative_legal_proof'])

    def test_provisional_name_and_appeal_is_only_review(self):
        raw=html().replace(b'</body>',b' Kay Gottschalk Einspruch '
                           b'gegen zweiten Ordnungsruf.</body>')
        a=provisional_103(raw)
        self.assertEqual(len(a['named_appeal_contexts']),1)
        self.assertEqual(a['named_appeal_contexts'][0]['public_count_delta'],0)
        self.assertTrue(a['named_appeal_contexts'][0]['manual_review_only'])

    def test_wrong_session_or_unrecognized_pdf_urls_rejected(self):
        with self.assertRaisesRegex(ValueError,'Identität'):
            provisional_103(html().replace(b'21/103',b'21/104'))
        with self.assertRaises(ValueError):
            download('https://other.example/amtpr21042.pdf',MAX_PDF_BYTES,
                     opener=lambda *args,**kwargs:None)

    def test_deny_unread_proceedings_but_keep_known_first(self):
        r=audit(fake(),provisional_103(html()))
        self.assertEqual(r['official_minutes_sessions_checked'],12)
        self.assertEqual(r['checked_resolution_minutes'][0]
                         ['non_first_appeal_candidate_count'],0)
        self.assertEqual(len(r['checked_resolution_minutes'][0]
                             ['person_named_appeal_contexts']),1)
        self.assertTrue(r['missing_official_minutes_not_checked'])
        self.assertTrue(r['not_full_sequence_of_official_resolution_minutes'])
        self.assertIn('NICHT alle',markdown(r))

    def test_invalid_report_cannot_assert_legal_outcomes(self):
        r=audit(fake(),provisional_103(html()))
        for change in (
                {'public_counter_delta':1},
                {'missing_official_minutes_not_checked':False},
                {'not_full_sequence_of_official_resolution_minutes':False},
                {'second_measure_effectiveness_unresolved':False},
                {'automatically_confirmed_effective_sanctions':1}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                markdown({**r,**change})

    def test_live_source_failure_does_not_write_partial_report(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'audit.json'
            def loader(url,maxsize):
                if url==PROVISIONAL_103:
                    raise ValueError('Unavailable preliminary source')
                return b'%PDF-1.7 test'
            with self.assertRaisesRegex(ValueError,'Unavailable'):
                run(target,Path(d)/'audit.md',
                    download_source=loader,
                    extract=lambda data:pages(SOURCES[0][0]))
            self.assertFalse(target.exists())

    def test_fake_all_sources_report_is_only_audit(self):
        urls={u:s for s,u in SOURCES}
        def load(url,n):
            return html() if url==PROVISIONAL_103 else bytes(f'%PDF-{urls[url]}','ascii')
        def extract(raw):
            return pages(int(raw.decode('ascii').removeprefix('%PDF-')))
        with tempfile.TemporaryDirectory() as d:
            r=run(Path(d)/'audit.json',Path(d)/'audit.md',
                  download_source=load,extract=extract)
            self.assertEqual(r['public_counter_delta'],0)
            self.assertTrue((Path(d)/'audit.json').exists())
            self.assertEqual(len(r['checked_resolution_minutes']),12)


if __name__=='__main__':
    unittest.main()
