"""Public feed remains a separate unverified text-location index."""
import unittest
from wp21_scan import public_feed

class TestFeed(unittest.TestCase):
    def setUp(self):
        self.summary = {'letzte_sitzung':99,'untersuchte_sitzungen':99,
                        'textstellen_zur_pruefung':2,
                        'zuletzt_geprueft_utc':'2026-10-14T08:00:00+00:00'}
        self.hint = {'hinweis_id':'21-099-L42-012345abcdef','sitzung':'99',
                     'datum':'08.10.2026','klasse':'possible_grant',
                     'textstelle':'Ich erteile einen Ordnungsruf.',
                     'xml_quelle':'https://evil.example/',
                     'pdf_quelle':'javascript:alert(1)'}

    def test_feed_is_unverified_and_uses_safe_links(self):
        feed=public_feed([self.hint],self.summary)
        self.assertEqual(feed['meta']['status'],'unverified_text_locations')
        self.assertNotIn('person',feed['items'][0])
        self.assertNotIn('group',feed['items'][0])
        self.assertEqual(feed['items'][0]['source'],
                         'https://dserver.bundestag.de/btp/21/21099.pdf')
        self.assertEqual(len(feed['items']),1)

    def test_excludes_non_actionable_mentions_and_truncates_text(self):
        h2=dict(self.hint,hinweis_id='21-099-L43-012345abcdee',
                klasse='mention_or_unclear')
        h1=dict(self.hint,textstelle='x'*1000)
        feed=public_feed([h1,h2],self.summary)
        self.assertEqual(feed['meta']['all_text_locations'],2)
        self.assertEqual(len(feed['items']),1)
        self.assertEqual(len(feed['items'][0]['excerpt']),220)

    def test_rejects_duplicates_and_invalid_sessions(self):
        with self.assertRaises(ValueError):
            public_feed([self.hint,self.hint],self.summary)
        with self.assertRaises(ValueError):
            public_feed([dict(self.hint,sitzung='100')],self.summary)

    def test_output_is_limited(self):
        hints=[dict(self.hint,hinweis_id=f'21-099-L{i}-{i:012x}')
               for i in range(1,51)]
        feed=public_feed(hints,self.summary)
        self.assertEqual(feed['meta']['selected_text_locations'],50)
        self.assertEqual(feed['meta']['shown'],40)
        self.assertEqual(len(feed['items']),40)

if __name__ == '__main__': unittest.main()
