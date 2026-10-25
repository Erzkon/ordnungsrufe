#!/usr/bin/env python3
"""Pinned official XML wording audit for three problematic 2025 DIP parents.

These are exact parliamentary *utterance* and attribution findings, not an
approval of any effective sanction. Parent 322921's displayed "Reichardt"
metadata conflicts with the explicitly documented Keuter recipient at
21/014, pp. 1221-1222. Neither metadata nor a repeated name may create an
extra confirmed measure.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from wp21_new_dip_candidates import AUDIT_ROOT
from wp21_priority_xml_scout import EXPECTED as SOURCE_EXPECTED

# Only official XML wordings already cross-checked against the PDF pages.
# XML row numbers are authoritative within the pinned full session XML.
WORDINGS={
  14:{
    2311:(r'\bHerr Kollege\b.*\beinen Ordnungsruf erteilen\b.*\bSchwätzer\b',
          'explicit_grant_reichardt_original_context'),
    5693:(r'\bIch verhänge hiermit einen Ordnungsruf\b.*\bich kündige das hiermit nur schon mal an\b',
          'unattributed_announcement_not_independently_issued_to_reichardt'),
    5705:(r'\bMein Ordnungsruf gilt Herrn Keuter\b',
          'explicit_keuter_recipient_not_reichardt'),
    5779:(r'\bdann gibt es gleich noch einen Ordnungsruf hinterher\b',
          'conditional_future_not_issued'),
  },
  43:{
    2393:(r'\bIch müsste Ihnen theoretisch einen Ordnungsruf erteilen\b',
          'theoretical_not_issued'),
    2396:(r'\bIch erteile Ihnen hiermit einen Ordnungsruf, Herr Reichardt\b',
          'different_reichardt_21_043_original'),
    2405:(r'\bAuch Sie kriegen einen Ordnungsruf\b',
          'keuter_first_21_043_with_later_explicit_recipient_clarification'),
    2418:(r'\bDer zweite Ordnungsruf, den ich erteilt habe, ging an den Abgeordneten Keuter\b',
          'retrospective_person_identity_for_first_keuter'),
    3493:(r'\bHerrn Frohnmaier erteile ich einen Ordnungsruf\b',
          'different_person_frohnmaier'),
    3495:(r'\bIhnen erteile ich jetzt den zweiten Ordnungsruf, Herr Keuter\b',
          'explicit_second_keuter_21_043'),
    3497:(r'\bAuch Ihnen erteile ich einen Ordnungsruf; Namen rufe ich gleich aus\b',
          'unidentified_other_person_not_keuter'),
  }
}
GRANT_ROLES={
    'explicit_grant_reichardt_original_context',
    'keuter_first_21_043_with_later_explicit_recipient_clarification',
    'explicit_second_keuter_21_043',
}
OUTPUT_WARNING=(
    'Drei separate gesprochene Originalformulierungen wurden quellengenau '
    'lokalisiert: Reichardt 21/014 und Keuter zweimal in 21/043. Die Zuordnung '
    'des ersten Reichardt-Falls erfordert die amtliche PDF-Seite 1133, weil '
    'die Rede von "Herr Kollege" statt des vollständigen Namens spricht. '
    'DIP-Vorgang 322921 führt Reichardt im Titel, während das verlinkte '
    'Plenarprotokoll auf den Seiten 1221-1222 ausdrücklich Keuter als '
    'Empfänger benennt: manueller Quellenkonflikt, nicht zählen. '
    'Weitere Einsprüche, Rücknahmen oder sonstige Rechtsfolgen wurden '
    'hier nicht abschließend geprüft; keine automatische Statistikfreigabe.'
)


def verify(scout):
    if (not isinstance(scout,dict)
            or scout.get('schema')!='wp21-reichardt-keuter-official-xml-scout-v1'
            or scout.get('confirmed_independent_new_grants')!=0
            or scout.get('automatically_confirmed_effective_sanctions')!=0
            or scout.get('protected_statistics_changed') is not False
            or scout.get('official_positions_expected')!=4):
        raise ValueError('Original-XML-Ausgangsbasis unvollständig oder zählerverändernd')
    sessions=scout.get('sessions')
    if (not isinstance(sessions,list) or len(sessions)!=2
            or [r.get('session') for r in sessions]!=[14,43]):
        raise ValueError('Originale 21/014 und 21/043 fehlen')
    results=[]
    for original in sessions:
        session=original['session']
        expected=SOURCE_EXPECTED[session]
        if (original['original_day']!=expected['date']
                or original['name']!=expected['person']
                or original['source_is_full_original_spoken_xml'] is not True
                or original['position_to_specific_spoken_paragraph_conclusively_verified'] is not False
                or original['automatically_confirmed_new_sanctions']!=0
                or original['spoken_paragraphs_checked']<30):
            raise ValueError('Nicht derselbe amtliche Original-XML-Quellenlauf')
        expected_refs={tuple(x) for x in expected['positions']}
        actual_refs={
            (p['official_parent_id'],p['official_position_id'],p['official_pdf_page'])
            for p in original['all_dip_parent_position_refs']
        }
        if actual_refs!=expected_refs:
            raise ValueError('DIP-Eltern- oder Verfahrenspositions-ID geändert')
        paragraphs=original['candidate_paragraphs']
        if (not isinstance(paragraphs,list) or
                len(paragraphs)!=original['raw_ordnungsruf_mention_paragraphs']):
            raise ValueError('Originalabsätze fehlen')
        by_line={}
        for p in paragraphs:
            line=p.get('xml_line')
            text=p.get('text')
            if (type(line)!=int or line in by_line or
                    not isinstance(text,str) or len(text)>1800 or
                    not re.fullmatch(r'[0-9a-f]{64}',str(p.get('paragraph_sha256','')))
                    or p.get('individual_original_grant_verified') is not False
                    or p.get('legally_effective_sanction_verified') is not False):
                raise ValueError('Manipulierte Original-XML-Zeilen')
            # Original text has at most 1800 characters in the source scout.
            # The pinned target lines are shorter and must hash byte-identically.
            if len(text)<1800 and hashlib.sha256(text.encode()).hexdigest()!=p['paragraph_sha256']:
                raise ValueError('Original-XML-Wortlaut/Hash unterschiedlich')
            by_line[line]=p
        selected=[]
        for line,(pattern,role) in WORDINGS[session].items():
            hit=by_line.get(line)
            if hit is None or not re.search(pattern,hit['text'],re.I|re.S):
                raise ValueError(f'21/{session:03d} XML-Zeile {line}: Wortlaut oder Empfänger verändert')
            selected.append({
                'session':session,'xml_line':line,
                'role':role,'spoken_text':hit['text'],
                'paragraph_sha256':hit['paragraph_sha256'],
                'official_xml':hit['source_xml'],
                'current_issuance_phrase_requires_separate_legal_effect_review':
                    role in GRANT_ROLES,
                'legally_effective_sanction_decided':False,
                'automatic_counter_delta':0,
            })
        results.append({
            'session':session,'original_day':expected['date'],
            'identities_and_warning_negative_controls_validated':len(selected),
            'source_loci':selected,
        })
    # Explicit temporal/person distinctions that must never be collapsed:
    first,second=results
    ids_first={c['xml_line']:c['role'] for c in first['source_loci']}
    ids_second={c['xml_line']:c['role'] for c in second['source_loci']}
    if (not 2311<5693<5705<5779 or
            not 2393<2396<2405<2418<3493<3495<3497 or
            ids_first[5705]!='explicit_keuter_recipient_not_reichardt' or
            ids_second[2418]!='retrospective_person_identity_for_first_keuter'):
        raise ValueError('Originaler chronologischer Quellenbezug ungültig')
    return {
        'schema':'wp21-014-043-individual-spoken-source-audit-v1',
        'official_sessions':[14,43],
        'source_utterances_located_for_individual_review':3,
        'source_utterance_loci':[
            {'session':row['session'],'xml_line':p['xml_line'],'role':p['role'],
             'paragraph_sha256':p['paragraph_sha256'],
             'official_xml':p['official_xml']}
            for row in results for p in row['source_loci'] if p['role'] in GRANT_ROLES
        ],
        'sources_with_explicit_identified_recipient_not_reichardt':[
            {'parent_id':'322921','position_id':'672193',
             'pdf_source':'https://dserver.bundestag.de/btp/21/21014.pdf#P.1221',
             'recipient_clarified_on_next_pdf_page':'Stefan Keuter',
             'xml_original_clarification_line':5705,
             'person_attribution_in_dip_title_requires_manual_review':True,
             'automatic_source_match_or_statistical_count':False},
        ],
        'keuter_first_original_pdf_page':'https://dserver.bundestag.de/btp/21/21043.pdf#P.4997',
        'keuter_second_original_pdf_page':'https://dserver.bundestag.de/btp/21/21043.pdf#P.5015',
        'individual_sources_still_require_legal_effect_review':True,
        'original_texts_with_negative_controls':results,
        'automatic_verified_sanction_count_delta':0,
        'protected_statistical_ledgers_changed':False,
        'warning':OUTPUT_WARNING,
    }


def render(report):
    if (report.get('schema')!='wp21-014-043-individual-spoken-source-audit-v1'
            or report.get('automatic_verified_sanction_count_delta')!=0
            or report.get('protected_statistical_ledgers_changed') is not False
            or report.get('source_utterances_located_for_individual_review')!=3
            or len(report.get('sources_with_explicit_identified_recipient_not_reichardt',[]))!=1):
        raise ValueError('Quellenbelege dürfen keine Statistik automatisch verändern')
    lines=[
        '# WP21: genaue Original-XML-Bindung Reichardt 21/014 / Keuter 21/043','',
        '**Drei gesprochene Originalstellen individuell lokalisiert; '
        'null neue automatisch rechtswirksam bestätigte Maßnahmen.**','',
        '| Original | XML-Zeile | Einordnung |',
        '|---|---:|---|']
    for item in report['source_utterance_loci']:
        lines.append(
            f"| [21/{item['session']:03d}]({item['official_xml']}) "
            f"| {item['xml_line']} | {item['role']} |")
    lines.extend(['','## Personen- und Quellenkonflikt',
                  '[DIP 322921](https://dip.bundestag.de/vorgang/322921) '
                  'ist im Titel Reichardt-gebunden, aber die '
                  '[amtliche PDF-Seite 1222]'
                  '(https://dserver.bundestag.de/btp/21/21014.pdf#P.1222) '
                  'nennt ausdrücklich Herrn Keuter als Empfänger. '
                  'Diese Stelle ist **kein zweiter automatisch sicherer '
                  'Reichardt-Ruf**.','',
                  '## Negative Originaltextkontrollen',''])
    for sec in report['original_texts_with_negative_controls']:
        for x in sec['source_loci']:
            lines.append('- 21/'+f"{sec['session']:03d}"+
                         ' XML-Zeile '+str(x['xml_line'])+' – '+x['role'])
    lines.extend(['',report['warning'],'','**Kein Merge, keine Zähleränderung.**',''])
    return '\n'.join(lines)


def save(report,output_dir):
    dest=Path(output_dir).resolve()
    root=AUDIT_ROOT.resolve()
    if dest==root or root not in dest.parents or dest.is_symlink():
        raise ValueError('Quellenbelege ausschließlich im .audit-Unterordner')
    dest.mkdir(parents=True,exist_ok=True)
    for name,data in (
        ('verified_wordings.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
        ('verified_wordings.md',render(report))):
        tmp=dest/(name+'.tmp')
        tmp.write_text(data,encoding='utf-8')
        tmp.replace(dest/name)


def run(*, input_path=AUDIT_ROOT/'wp21_priority_originals/original_contexts.json',
        output_dir=AUDIT_ROOT/'wp21_priority_originals'):
    source=json.loads(Path(input_path).read_text(encoding='utf-8'))
    report=verify(source)
    save(report,output_dir)
    return report


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--input',type=Path,
                     default=AUDIT_ROOT/'wp21_priority_originals/original_contexts.json')
    cli.add_argument('--output-dir',type=Path,
                     default=AUDIT_ROOT/'wp21_priority_originals')
    args=cli.parse_args()
    result=run(input_path=args.input,output_dir=args.output_dir)
    print(result['source_utterances_located_for_individual_review'],
          'individuelle wörtliche Originalstellen,'
          '1 DIP-Titel-/Empfängerkonflikt,',
          '0 neue wirksame Zählerfreigaben.')


if __name__=='__main__':
    main()
