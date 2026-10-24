"""Exact official spoken-source wording tests; no live API needed."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from wp21_new_dip_candidates import AUDIT_ROOT
from wp21_priority_xml_scout import EXPECTED
from wp21_priority_xml_verify import verify, render, save, run


TEXTS={
14:{
  2311:'– Herr Kollege, dann muss ich Ihnen leider einen Ordnungsruf erteilen dafür, dass Sie die Rednerin als „Schwätzer“ bezeichnet haben.',
  5693:'Ich verhänge hiermit einen Ordnungsruf für die Verwendung des Begriffs „Sie sind ein Vaterlandsverräter!“. Ich weiß nicht genau, wer von Ihnen es gerufen hat; ich kündige das hiermit nur schon mal an.',
  5705:'So, wir haben jetzt zwei Punkte: Mein Ordnungsruf gilt Herrn Keuter. Von ihm kam offensichtlich die von mir beanstandete Bemerkung.',
  5779:'– Ich lasse jetzt noch mal nachschauen, wer das jetzt war. Dann gibt es gleich noch einen Ordnungsruf hinterher – weil es so schön ist –, wenn Sie die Präsidentin noch mal kritisieren.',
},
43:{
  2393:'Ich müsste Ihnen theoretisch einen Ordnungsruf erteilen,',
  2396:'Ich erteile Ihnen hiermit einen Ordnungsruf, Herr Reichardt. Sie kennen anscheinend die Geschäftsordnung nicht.',
  2405:'– Auch Sie kriegen einen Ordnungsruf, weil Sie anscheinend nicht verstanden haben, dass diese Debatte in den Ältestenrat gehört.',
  2418:'Vielen Dank. – Für das Protokoll noch mal präzisiert: Der zweite Ordnungsruf, den ich erteilt habe, ging an den Abgeordneten Keuter, weil Kritik am Vorsitz durchaus erlaubt ist.',
  3493:'– Herrn Frohnmaier erteile ich einen Ordnungsruf.',
  3495:'– Ihnen erteile ich jetzt den zweiten Ordnungsruf, Herr Keuter.',
  3497:'– Auch Ihnen erteile ich einen Ordnungsruf; Namen rufe ich gleich aus.',
}}


def fixture():
    sessions=[]
    for session,lines in sorted(TEXTS.items()):
        target=EXPECTED[session]
        cases=[{
            'xml_line':line,
            'text':text,
            'paragraph_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'source_xml':f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml',
            'individual_original_grant_verified':False,
            'legally_effective_sanction_verified':False,
        } for line,text in lines.items()]
        sessions.append({
            'session':session,'original_day':target['date'],
            'name':target['person'],'source_is_full_original_spoken_xml':True,
            'position_to_specific_spoken_paragraph_conclusively_verified':False,
            'automatically_confirmed_new_sanctions':0,
            'spoken_paragraphs_checked':100,
            'raw_ordnungsruf_mention_paragraphs':len(cases),
            'all_dip_parent_position_refs':[
                {'official_parent_id':parent,'official_position_id':position,
                 'official_pdf_page':page}
                for parent,position,page in target['positions']],
            'candidate_paragraphs':cases,
        })
    return {
        'schema':'wp21-reichardt-keuter-official-xml-scout-v1',
        'confirmed_independent_new_grants':0,
        'automatically_confirmed_effective_sanctions':0,
        'protected_statistics_changed':False,
        'official_positions_expected':4,
        'sessions':sessions,
    }


class PinnedOfficialUtteranceTests(unittest.TestCase):
    def test_three_spoken_sources_with_dip_person_conflict_are_noncounting(self):
        report=verify(fixture())
        self.assertEqual(report['source_utterances_located_for_individual_review'],3)
        self.assertEqual(report['automatic_verified_sanction_count_delta'],0)
        self.assertFalse(report['protected_statistical_ledgers_changed'])
        self.assertEqual(len(report['source_utterance_loci']),3)
        self.assertEqual(
            {(x['session'],x['xml_line']) for x in report['source_utterance_loci']},
            {(14,2311),(43,2405),(43,3495)})
        conflicts=report['sources_with_explicit_identified_recipient_not_reichardt']
        self.assertEqual(conflicts[0]['parent_id'],'322921')
        self.assertEqual(conflicts[0]['recipient_clarified_on_next_pdf_page'],'Stefan Keuter')
        self.assertIn('Quelle',render(report))

    def test_changes_to_speaker_or_original_wording_are_rejected(self):
        for session,line,newtext in (
            (14,5705,'Mein Ordnungsruf gilt Herrn Reichardt.'),
            (14,2311,'Ich würde Ihnen einen Ordnungsruf erteilen.'),
            (43,2418,'Der zweite Ordnungsruf ging an den Abgeordneten Reichardt.'),
            (43,3495,'Ihnen erteile ich einen zweiten Ordnungsruf, Herr Frohnmaier.'),
        ):
            with self.subTest(session=session,line=line):
                data=fixture()
                p=next(p for s in data['sessions'] if s['session']==session
                       for p in s['candidate_paragraphs'] if p['xml_line']==line)
                p['text']=newtext
                p['paragraph_sha256']=hashlib.sha256(newtext.encode()).hexdigest()
                with self.assertRaises(ValueError):
                    verify(data)

    def test_duplicate_official_line_modified_hash_and_dip_anchor_fails_closed(self):
        d=fixture()
        d['sessions'][0]['candidate_paragraphs'].append(
            copy.deepcopy(d['sessions'][0]['candidate_paragraphs'][0]))
        d['sessions'][0]['raw_ordnungsruf_mention_paragraphs']+=1
        with self.assertRaises(ValueError):
            verify(d)
        d=fixture()
        d['sessions'][0]['candidate_paragraphs'][0]['paragraph_sha256']='0'*64
        with self.assertRaises(ValueError):
            verify(d)
        d=fixture()
        d['sessions'][1]['all_dip_parent_position_refs'][0]['official_position_id']='999999'
        with self.assertRaises(ValueError):
            verify(d)

    def test_counter_tampering_or_missing_full_source_must_fail(self):
        d=fixture()
        d['confirmed_independent_new_grants']=1
        with self.assertRaises(ValueError):
            verify(d)
        d=fixture()
        d['sessions'][1]['source_is_full_original_spoken_xml']=False
        with self.assertRaises(ValueError):
            verify(d)
        d=fixture()
        d['sessions'][1]['candidate_paragraphs'].pop()
        with self.assertRaises(ValueError):
            verify(d)

    def test_only_audit_output_and_preserved_ledgers(self):
        report=verify(fixture())
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                save(report,Path(temp)/'not_audit')
        AUDIT_ROOT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=AUDIT_ROOT) as temp:
            folder=Path(temp)
            source=folder/'scout.json'
            source.write_text(json.dumps(fixture()),encoding='utf-8')
            before=Path('daten/wirksame_ordnungsrufe_21wp.csv').read_bytes()
            result=run(input_path=source,output_dir=folder/'checked')
            self.assertEqual(result['automatic_verified_sanction_count_delta'],0)
            self.assertTrue((folder/'checked/verified_wordings.json').exists())
            self.assertTrue((folder/'checked/verified_wordings.md').exists())
            self.assertEqual(before,Path('daten/wirksame_ordnungsrufe_21wp.csv').read_bytes())


if __name__=='__main__':
    unittest.main()
