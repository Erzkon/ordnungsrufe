"""High-priority review report remains unverified and source-bound."""
import tempfile
import unittest
from pathlib import Path

from wp21_pruefbericht import category, create_brief, run
from wp21_vollstaendigkeit import FIELDS


def row(**kw):
    base={key:'' for key in FIELDS}
    base.update(fall_id='xml-015-L1414',prioritaet='hoch',
                typ='xml_textstelle_ohne_person_parser',sitzung='15',
                xml_zeile='1414',person='',parser_fundstellen='0',
                grund='Keine Person sicher verknüpft',
                textauszug='Ich erteile einen Ordnungsruf.',
                protokoll='https://dserver.bundestag.de/btp/21/21015.pdf')
    base.update(kw)
    return base


def summary(total=1,high=1):
    return {'wahlperiode':21,
            'status':'quellenvollstaendigkeit_ohne_automatische_freigabe',
            'automatically_confirmed_sanctions':0,
            'automatically_rescinded_sanctions':0,
            'last_success_utc':'2026-10-15T09:00:00+00:00',
            'sessions_scanned':100,
            'review_cases_total':total,'high_priority_cases':high}


class PrioritizedBriefTests(unittest.TestCase):
    def test_true_unattributed_xml_grant_does_not_add_recipient(self):
        output=create_brief([row()],summary())
        self.assertIn('XML-Zeile 1414',output)
        self.assertIn('Noch keine sichere Person',output)
        self.assertIn('keine änderung',output.lower())
        self.assertIn('keine bestätigten ordnungsrufe',output.lower())

    def test_known_missing_parser_kept_separate(self):
        case=row(fall_id='person-090-a',sitzung='90',person='Martin Sichert',
                 xml_zeile='',typ='person_sitzung_ohne_einzelereignisabgleich',
                 protokoll='https://dserver.bundestag.de/btp/21/21090.pdf',
                 bestaetigte_massnahmen_teilbestand='1',
                 dip_urspruengliche_erteilungen_stichprobe='1',
                 parser_person_sitzung_vorhanden='nein')
        self.assertEqual(category(case),'Bekannte Referenz vom Parser nicht erkannt')
        self.assertIn('Martin Sichert',create_brief([case],summary()))

    def test_dip_unverified_not_automatically_confirmed(self):
        case=row(fall_id='person-053-a',sitzung='53',person='Heidi Reichinnek',
                 xml_zeile='',typ='person_sitzung_ohne_einzelereignisabgleich',
                 protokoll='https://dserver.bundestag.de/btp/21/21053.pdf',
                 dip_urspruengliche_erteilungen_stichprobe='1',
                 parser_person_sitzung_vorhanden='ja',
                 bestaetigte_massnahmen_teilbestand='0')
        self.assertIn('ohne einzeln bestätigten',category(case))
        self.assertIn('kuratierte',create_brief([case],summary()).lower())

    def test_mismatched_high_tally_rejected(self):
        with self.assertRaisesRegex(ValueError,'Hochprioritäts'):
            create_brief([row()],summary(high=0))

    def test_untrusted_link_rejected_without_writing_output(self):
        with self.assertRaisesRegex(ValueError,'Quelle'):
            create_brief([row(protokoll='https://evil.example/payload')],summary())

    def test_escaping_and_only_high_priority_included(self):
        malicious=row(person='<script>alert(1)</script>',
                      textauszug='<img src=x onerror=alert(1)>')
        medium=row(fall_id='xml-016-L1414',sitzung='16',prioritaet='mittel',
                   person='Not high',protokoll='https://dserver.bundestag.de/btp/21/21016.pdf')
        output=create_brief([malicious,medium],summary(total=2,high=1))
        self.assertNotIn('<script>',output)
        self.assertNotIn('<img',output)
        self.assertNotIn('Not high',output)
        self.assertIn('&lt;script&gt;',output)

    def test_real_audit_fixture_is_read_only(self):
        # This is a synthetic XML-source report on a temp output, never
        # an actual confirmation of a measured sanction.
        with tempfile.TemporaryDirectory() as td:
            import csv,json
            p=Path(td)
            c=p/'cases.csv';j=p/'report.json';out=p/'brief.md'
            with c.open('w',encoding='utf-8',newline='') as stream:
                w=csv.DictWriter(stream,fieldnames=FIELDS)
                w.writeheader()
                w.writerow(row())
            j.write_text(json.dumps(summary()),encoding='utf-8')
            self.assertEqual(run(c,j,out),1)
            self.assertEqual(run(c,j,out),1)
            self.assertIn('Quellenstand',out.read_text())


if __name__=='__main__':
    unittest.main()
