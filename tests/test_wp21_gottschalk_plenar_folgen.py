"""Conservative tests for later official XML and non-counting decisions."""
import tempfile
import unittest
from pathlib import Path
from lxml import etree
from wp21_gottschalk_plenar_folgen import inspect_rows,review,markdown,run


def xml(session,*text):
    root=etree.Element('dbtplenarprotokoll',attrib={
        'wahlperiode':'21','sitzung-nr':str(session),
        'sitzung-datum':'25.11.2025' if session==42 else '26.11.2025'})
    flow=etree.SubElement(root,'sitzungsverlauf')
    point=etree.SubElement(flow,'tagesordnungspunkt')
    for t in text:
        etree.SubElement(point,'p').text=t
    return root


FIRST='Einspruch des Abgeordneten Kay Gottschalk gegen den Ordnungsruf.'
SECOND='Kay Gottschalk erhebt Einspruch gegen den zweiten Ordnungsruf.'


class OfficialLaterPlenaryTests(unittest.TestCase):
    def test_first_known_objection_is_no_later_procedure(self):
        r=review({42:xml(42,FIRST),43:xml(43,'Haushaltsdebatte')})
        self.assertEqual(r['later_context_count'],0)
        self.assertEqual(len(r['known_first_appeal_in_42']),1)
        self.assertTrue(r['gottschalk_second_legal_effect_unresolved'])
        self.assertEqual(r['public_counter_delta'],0)
        self.assertIn('Keine Rechtsfolgenbestätigung',markdown(r))

    def test_later_explicit_second_is_manual_only(self):
        r=review({42:xml(42,FIRST),43:xml(43,SECOND)})
        self.assertEqual(r['later_context_count'],1)
        c=r['later_person_named_contexts'][0]
        self.assertTrue(c['second_measure_mentioned_in_context'])
        self.assertFalse(c['decision_confirmed_by_lexical_match'])
        self.assertEqual(c['counter_delta'],0)
        self.assertEqual(c['source_xml'],
                         'https://dserver.bundestag.de/btp/21/21043.xml')

    def test_person_name_not_borrowed_from_unrelated_appeal(self):
        rows=[(1,'Kay Gottschalk spricht zum Haushalt.'),
              (2,'Martin Sichert legt Einspruch gegen einen Ordnungsruf ein.')]
        self.assertEqual(inspect_rows(rows,43,'26.11.2025'),[])

    def test_cross_paragraph_context_is_not_decision(self):
        rows=[(1,'Kay Gottschalk erhebt Einspruch.'),
              (2,'Es geht um den zweiten Ordnungsruf.'),
              (3,'Der Einspruch von Martin Sichert wird zurückgewiesen.')]
        hints=inspect_rows(rows,43,'26.11.2025')
        self.assertEqual(len(hints),1)
        self.assertFalse(hints[0]['decision_confirmed_by_lexical_match'])
        self.assertTrue(hints[0]['second_measure_mentioned_in_context'])

    def test_source_line_hash_and_identity(self):
        hits=inspect_rows([(120,SECOND)],43,'26.11.2025')
        self.assertEqual(hits[0]['xml_line'],120)
        self.assertRegex(hits[0]['paragraph_sha256'],r'^[a-f0-9]{64}$')
        self.assertTrue(hits[0]['source_pdf'].endswith('21043.pdf'))

    def test_missing_baseline_and_gap_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'21/042'):
            review({42:xml(42,'Keine Entscheidungen')})
        with self.assertRaisesRegex(ValueError,'Unvollständige'):
            review({42:xml(42,FIRST),44:xml(44,SECOND)})

    def test_foreign_session_fails(self):
        other=xml(43,SECOND)
        other.set('wahlperiode','20')
        with self.assertRaises(ValueError):
            review({42:xml(42,FIRST),43:other})

    def test_report_cannot_confirm_law_or_absence(self):
        r=review({42:xml(42,FIRST)})
        for mutation in (
            {'public_counter_delta':1},
            {'automatically_confirmed_effective_sanctions':2},
            {'gottschalk_second_legal_effect_unresolved':False},
            {'other_nonplenary_or_future_official_documents_not_excluded':False}):
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                markdown({**r,**mutation})

    def test_missing_cached_session_leaves_no_audit_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'out.json'
            with self.assertRaisesRegex(ValueError,'Lücke'):
                run(Path(d),target,Path(d)/'out.md',
                    cache_only=True,last_session=43)
            self.assertFalse(target.exists())

    def test_three_terminal_missing_sessions_define_bounded_scope(self):
        with tempfile.TemporaryDirectory() as d:
            def load(session,cache):
                if session in (42,43):
                    t=FIRST if session==42 else SECOND
                    return etree.tostring(xml(session,t))+b' '*300
                return None
            r=run(Path(d),Path(d)/'out.json',Path(d)/'out.md',
                  max_session=48,load=load)
            self.assertEqual(r['sessions_checked'],2)
            self.assertEqual(r['later_context_count'],1)

    def test_unresolved_gap_before_next_xml_fails_without_output(self):
        with tempfile.TemporaryDirectory() as d:
            def load(session,cache):
                if session in (42,44):
                    t=FIRST if session==42 else SECOND
                    return etree.tostring(xml(session,t))+b' '*300
                return None
            target=Path(d)/'out.json'
            with self.assertRaisesRegex(ValueError,'Lücke'):
                run(Path(d),target,Path(d)/'out.md',
                    max_session=48,load=load)
            self.assertFalse(target.exists())


if __name__=='__main__':
    unittest.main()
