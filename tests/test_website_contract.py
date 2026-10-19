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

    def test_dynamic_accessible_names_include_visible_label(self):
        self.assertNotIn('aria-label="Ordnungsruf-Counter',self.html)
        self.assertNotIn("button.setAttribute('aria-label'",self.js)
        self.assertIn("el('span', 'sr-only', ' Einträge anzeigen')",self.js)

    def test_axe_contrast_patches_are_kept(self):
        stylesheet=(ROOT/'styles.css').read_text(encoding='utf-8')
        self.assertIn('--muted:#53616b',stylesheet)
        self.assertIn('--gold-dark:#84531d',stylesheet)
        self.assertIn('color:#58646e',stylesheet)

    def test_provenance_links_have_label_in_name_without_unsafely_changing_urls(self):
        self.assertNotIn("link.setAttribute('aria-label'",self.js)
        self.assertIn("link.append(el('span','sr-only'",self.js)
        self.assertIn("link.rel = 'noopener noreferrer'",self.js)

    def test_native_form_labels_and_mobile_legibility(self):
        self.assertNotIn('aria-label="Nach Person oder Sitzungsnummer suchen"',self.html)
        self.assertNotIn('aria-label="Historische Zugehörigkeit filtern"',self.html)
        self.assertNotIn('aria-label="Reihenfolge"',self.html)
        for text in ('PERSON ODER SITZUNG','ZUGEHÖRIGKEIT','SORTIERUNG'):
            self.assertIn(f'<span>{text}</span>',self.html)
        stylesheet=(ROOT/'styles.css').read_text(encoding='utf-8')
        self.assertIn('.metric-label{font-size:11px',stylesheet)
        self.assertIn('.metric-foot{font-size:12px',stylesheet)
        self.assertIn('@media(forced-colors:active)',stylesheet)
        smoke=Path('tests/browser_smoke.cjs').read_text(encoding='utf-8')
        self.assertIn("name:'forced-colors',value:'active'",smoke)

    def test_empty_search_notice_keeps_readable_contrast(self):
        style=(ROOT/'styles.css').read_text(encoding='utf-8')
        self.assertIn('.empty-state{text-align:center;color:#53616b',style)
        self.assertNotIn('.empty-state{text-align:center;color:#70818d',style)

    def test_last_page_focus_after_load_button_disappears(self):
        self.assertIn("const previouslyShown = $('records-body').rows.length;",self.js)
        self.assertIn("const newRow = $('records-body').rows[previouslyShown];",self.js)
        self.assertIn('newRow.tabIndex = -1;',self.js)
        self.assertIn('newRow.focus({preventScroll:false});',self.js)
        smoke=Path('tests/browser_smoke.cjs').read_text(encoding='utf-8')
        self.assertIn('Final keyboard pagination retains focus',smoke)
        self.assertIn('count<=135',smoke)

    def test_invalid_published_dataset_shows_accessible_error_without_numbers(self):
        self.assertIn('id="data-error"',self.html)
        self.assertIn('role="alert" hidden',self.html)
        self.assertIn("const alert=$('data-error');",self.js)
        self.assertIn("alert.hidden=false;",self.js)
        smoke=Path('tests/browser_smoke.cjs').read_text(encoding='utf-8')
        self.assertIn("getAttribute('role')),'alert'",smoke)
        self.assertIn("tamperedViolations",smoke)

    def test_progressive_table_append_without_replacing_existing_nodes(self):
        self.assertIn('function renderRecords({appendOnly = false} = {})',self.js)
        self.assertIn('const start = appendOnly ? body.rows.length : 0;',self.js)
        self.assertIn('if (!appendOnly) body.replaceChildren();',self.js)
        self.assertIn('for (const item of shown.slice(start))',self.js)
        self.assertIn('renderRecords({appendOnly:true});',self.js)
        smoke=Path('tests/browser_smoke.cjs').read_text(encoding='utf-8')
        self.assertIn('firstRowHandle',smoke)

    def test_controls_stay_disabled_when_verified_ledgers_fail(self):
        for tag in ('id="search" type="search" autocomplete="off" disabled',
                    '<select id="group-filter" disabled>',
                    '<select id="sort" disabled>',
                    'id="period-20" class="period-button is-active" type="button" disabled'):
            self.assertIn(tag,self.html)
        self.assertIn('state.datasets={};',self.js)
        self.assertIn('state.records=[];',self.js)
        self.assertIn("$(id).disabled=true;",self.js)
        self.assertIn("$(id).disabled=false;",self.js)
        self.assertIn("$(id).textContent='—';",self.js)
        self.assertIn("$('wp20-note').hidden=true;",self.js)

    def test_slow_and_unavailable_http_ledgers_never_display_false_zero(self):
        smoke=Path('tests/browser_smoke.cjs').read_text(encoding='utf-8')
        self.assertIn('Delayed verified dataset keeps controls locked',smoke)
        self.assertIn('HTTP source outage fails closed',smoke)
        self.assertIn("status:503,contentType:'text/plain'",smoke)
        self.assertIn('new Promise(resolve=>{unblock=resolve;})',smoke)
        self.assertIn("assert.equal(blocked.total,'—')",smoke)

    def test_failed_verification_offers_safe_explicit_retry(self):
        self.assertIn('id="retry-data" class="button button-more"',self.html)
        self.assertIn("$('retry-data').addEventListener('click',()=>window.location.reload());",self.js)
        self.assertIn("$('retry-data').hidden=false;",self.js)
        smoke=Path('tests/browser_smoke.cjs').read_text(encoding='utf-8')
        self.assertIn("failFirst&&req.url().endsWith('/data/ordnungsrufe_21.json')",smoke)
        self.assertIn('Accessible data reload recovers only after both ledgers validate',smoke)

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
