"""Safety and evidence contracts for Keuter/Reichardt official spoken XML audit."""
import copy
import tempfile
import unittest
from pathlib import Path
from lxml import etree

from wp21_priority_xml_scout import EXPECTED, inspect_session, audit, render, save
from wp21_new_dip_candidates import AUDIT_ROOT


def root(session, replacements=None):
    target=EXPECTED[session]
    base=etree.Element('dbtplenarprotokoll',wahlperiode='21',
                       attrib={'sitzung-nr':str(session),
                               'sitzung-datum':target['date']})
    course=etree.SubElement(base,'sitzungsverlauf')
    for i in range(45):
        speech=etree.SubElement(course,'rede')
        p=etree.SubElement(speech,'p')
        p.text=(replacements or {}).get(i,'Parlamentarischer Wortbeitrag ohne Maßnahmen.')
    # lxml sourceline is populated only after parsing serialized XML.
    return etree.fromstring(etree.tostring(base,encoding='utf-8',pretty_print=True))


class PriorityOfficialOriginalReviewTests(unittest.TestCase):
    def test_both_full_source_sessions_and_no_count_changes(self):
        a=root(14,{
            18:'Herr Reichardt, ich erteile Ihnen einen Ordnungsruf.',
            26:'Ordnungsruf für Herrn Reichardt wurde angekündigt.',
        })
        b=root(43,{
            15:'Herr Keuter, ich erteile Ihnen einen Ordnungsruf.',
            30:'Ich erteile Ihnen einen zweiten Ordnungsruf, Herr Keuter.',
        })
        report=audit({14:a,43:b})
        self.assertEqual(report['official_positions_expected'],4)
        self.assertEqual(report['confirmed_independent_new_grants'],0)
        self.assertEqual(report['automatically_confirmed_effective_sanctions'],0)
        self.assertFalse(report['protected_statistics_changed'])
        self.assertEqual(len(report['sessions']),2)
        self.assertEqual(report['sessions'][0]['raw_ordnungsruf_mention_paragraphs'],2)
        self.assertEqual(report['sessions'][1]['raw_ordnungsruf_mention_paragraphs'],2)
        self.assertEqual(report['sessions'][0]['person_context_candidates'],2)
        self.assertIn('Original-XML-Quellensichtung',render(report))
        self.assertTrue(all(x['individual_original_grant_verified'] is False
                            for s in report['sessions'] for x in s['candidate_paragraphs']))

    def test_threat_or_retrospective_text_not_promoted_to_issuance(self):
        roots={14:root(14,{
            11:'Wenn Sie so weitermachen, Herr Reichardt, erteile ich Ihnen gleich einen Ordnungsruf.',
            23:'Herr Reichardt hat in der letzten Sitzung einen Ordnungsruf erhalten.'}),
            43:root(43,{
            20:'Herr Keuter bekam früher einen Ordnungsruf.'})}
        report=audit(roots)
        self.assertEqual(report['automatically_confirmed_effective_sanctions'],0)
        hints=[p for s in report['sessions'] for p in s['candidate_paragraphs']]
        self.assertTrue(all(p['individual_original_grant_verified'] is False for p in hints))

    def test_unsupported_session_and_wrong_date_rejected(self):
        with self.assertRaises(ValueError):
            inspect_session(root(14),43)
        with self.assertRaises(KeyError):
            inspect_session(root(14),99)
        bad=root(14,{12:'Ordnungsruf für Reichardt'})
        bad.set('sitzung-datum','27.06.2025')
        with self.assertRaises(ValueError):
            inspect_session(bad,14)
        with self.assertRaises(ValueError):
            audit({14:root(14,{10:'Herr Reichardt, einen Ordnungsruf.'})})

    def test_no_mention_is_not_disguised_as_complete_source(self):
        with self.assertRaises(ValueError):
            inspect_session(root(14),14)

    def test_rejects_public_output_and_counter_mutation(self):
        report=audit({
            14:root(14,{18:'Ordnungsruf für Reichardt'}),
            43:root(43,{19:'Ordnungsruf für Keuter'})})
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                save(report,Path(temporary)/'public')
        tampered=copy.deepcopy(report)
        tampered['confirmed_independent_new_grants']=1
        with self.assertRaises(ValueError):
            render(tampered)
        AUDIT_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=AUDIT_ROOT) as temporary:
            dest=Path(temporary)/'sources'
            save(report,dest)
            self.assertTrue((dest/'original_contexts.json').is_file())
            self.assertTrue((dest/'original_contexts.md').is_file())


if __name__=='__main__':
    unittest.main()
