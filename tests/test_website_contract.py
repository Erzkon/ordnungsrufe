"""Static website integration guard: JS references must exist in the rendered HTML.

This catches accidentally renamed/missing IDs which node --check cannot catch.
"""
import re
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'docs'


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k=='id' and v:
                self.ids.append(v)


class TestWebsiteContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(ROOT/'index.html').read_text(encoding='utf-8')
        cls.js=(ROOT/'app.js').read_text(encoding='utf-8')
        parser=Elements()
        parser.feed(cls.html)
        cls.identifiers=parser.ids

    def test_no_duplicate_html_ids(self):
        duplicates={k:v for k,v in Counter(self.identifiers).items() if v>1}
        self.assertEqual(duplicates,{})

    def test_all_literal_js_dom_ids_exist_in_markup(self):
        refs=set(re.findall(r"\$\(['\"]([A-Za-z0-9_-]+)['\"]\)",self.js))
        missing=refs-set(self.identifiers)
        self.assertEqual(missing,set(),f'JavaScript points to missing HTML elements: {missing}')

    def test_independent_dip_sections_exist(self):
        for id_ in ('wp21-activity','wp21-dip-live','wp21-dip-detail',
                    'wp21-dip-cases','wp21-dip-cases-meta',
                    'wp21-legal-detail','wp21-triage-detail'):
            self.assertIn(id_,self.identifiers)

    def test_main_confirmation_labels_not_reused_for_unverified_cases(self):
        self.assertIn('bisher einzeln',self.js.lower())
        self.assertIn('keine bestätigten ordnungsrufe',self.html.lower())
        self.assertIn('keine automatisch',self.js.lower())

if __name__=='__main__':
    unittest.main()
