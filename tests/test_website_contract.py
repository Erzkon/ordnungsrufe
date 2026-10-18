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

    def test_accessible_navigation_and_horizontal_table(self):
        self.assertIn('<main id="inhalt" tabindex="-1">',self.html)
        self.assertIn('class="skip-link" href="#inhalt"',self.html)
        self.assertIn('class="table-scroller" role="region"',self.html)
        self.assertIn('aria-label="Horizontale Maßnahmen-Tabelle" tabindex="0"',self.html)
        self.assertIn('id="records-caption" class="sr-only"',self.html)
        self.assertIn('id="period-announcement" class="sr-only" role="status"',self.html)
        self.assertIn('aria-live="polite" aria-atomic="true"',self.html)

    def test_keyboard_ranking_controls_focus_and_period_announces_scope(self):
        self.assertIn('$(filterName).focus({preventScroll:true});',self.js)
        self.assertIn("$('period-announcement').textContent",self.js)
        self.assertIn('Unvollständige Auswahl, keine Gesamtzahl.',self.js)
        self.assertIn("$('records-caption').textContent",self.js)

    def test_manual_case_review_link_keeps_no_automatic_counting(self):
        self.assertIn('/blob/main/OFFENE_EINZELFAELLE.md',self.html)
        self.assertIn('nicht repräsentativ',self.html)

    def test_independent_dip_sections_exist(self):
        for id_ in ('wp21-activity','wp21-dip-live','wp21-dip-detail',
                    'wp21-dip-cases','wp21-dip-cases-meta',
                    'wp21-legal-detail','wp21-triage-detail',
                    'wp21-coverage-detail'):
            self.assertIn(id_,self.identifiers)

    def test_main_confirmation_labels_not_reused_for_unverified_cases(self):
        self.assertIn('bisher einzeln',self.js.lower())
        self.assertIn('keine bestätigten ordnungsrufe',self.html.lower())
        self.assertIn('keine automatisch',self.js.lower())

if __name__=='__main__':
    unittest.main()
