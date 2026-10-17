#!/usr/bin/env python3
"""Seven exact independently sourced 2025 original XML issuance loci.

Source lines were located from the complete eight-protocol official
research artifact in GitHub Actions 39024535122. Do not infer legal
effectiveness from an original utterance or from its paragraph count.

All known person/day grants except the three-person 21/040 group
are matched to ONE exact, unambiguous spoken-paragraph text and line.
21/040 is verified separately in wp21_40_mehrfach_akte.py; Janich's
first original issuance still needs an independent original XML line.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from parser import iter_session_text, action_match
from wp21_autopruefung import norm
from wp21_2025_dip_einzelakten import CASES
from wp21_scan import fetch,safe_parse

# Strict original speaker utterance patterns, NOT search-term occurrences.
LOCATIONS={
    (10,norm('Stephan Brandner')):(
        5850,r'\bHerr\s+Brandner,\s+ich\s+erteile\s+Ihnen\b'
             r'.{0,230}\beinen\s+Ordnungsruf\b'),
    (11,norm('Stephan Brandner')):(
        1035,r'\bAbgeordneten\s+Brandner\b.{0,180}\bOrdnungsruf\s+erteilen\b'
             r'.{0,260}\berteile\s+ich\s+ihm\s+einen\s+Ordnungsruf\b'),
    (15,norm('Luigi Pantisano')):(
        853,r'\bIch\s+erteile\s+einen\s+Ordnungsruf\s+an\s+den\s+'
            r'Abgeordneten\b.{0,70}\bHerrn\s+Pantisano\b'),
    (25,norm('Mirze Edis')):(
        1386,r'\bAbgeordnete\s+Mirze\s+Edis\b.{0,160}\b'
             r'Ich\s+erteile\s+einen\s+Ordnungsruf\b'),
    (43,norm('Martin Reichardt')):(
        2396,r'\bIch\s+erteile\s+Ihnen\s+hiermit\s+einen\s+Ordnungsruf,'
             r'\s+Herr\s+Reichardt\b'),
    (49,norm('Stephan Brandner')):(
        3278,r'\bAbgeordneten\s+Stephan\s+Brandner\b.{0,110}'
             r'\beinen\s+Ordnungsruf\s+erteilen\b'),
    (50,norm('Martin Reichardt')):(
        5629,r'\bBundestagsabgeordneten\s+Martin\s+Reichardt\b'
             r'.{0,35}\beinen\s+Ordnungsruf\b'),
}
DAYS={
    session:datetime.strptime(original_date,'%Y-%m-%d').strftime('%d.%m.%Y')
    for original_date,person,ident,session,decision_sitting,grants,votes in CASES
    if session!=40
}
if len(DAYS)!=7 or set(DAYS)!={key[0] for key in LOCATIONS}:
    raise ValueError('Seven original session sources expected')


def exact_match(paragraphs,session,person):
    """One exact original spoken paragraph; never a same-name vote/recap."""
    key=(session,norm(person))
    if key not in LOCATIONS:
        raise ValueError('Unreviewed 2025 source identity')
    required,expression=LOCATIONS[key]
    pattern=re.compile(expression,re.I|re.S)
    found=[(line,text) for line,text in paragraphs if pattern.search(text)]
    if len(found)!=1 or found[0][0]!=required:
        raise ValueError(f'XML 21/{session:03d}: original issuance line '
                         f'{required} for {person} missing/duplicated/shifted')
    line,text=found[0]
    if (type(line)!=int or not 0<len(text)<=5000
            or not action_match(text)
            or not re.search(r'\bOrdnungsruf\b',text,re.I)):
        raise ValueError('Expected actual issuing speech not present')
    return {
        'session':session,'person':person,'original_date':DAYS[session],
        'original_xml_line':line,
        'original_xml_source':f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml',
        'original_pdf_source':f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf',
        'paragraph_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'issuer_utterance_excerpt':' '.join(text.split())[:1000],
        'source_attribution':'exact original plenary speech verified against separately sourced DIP person/day',
        'legally_effective_individual_sanction_confirmed':False,
        'automatic_public_counter_delta':0,
    }


def inspect(roots):
    if not isinstance(roots,dict) or set(roots)!=set(DAYS):
        raise ValueError('All seven separately documented 2025 originals required')
    records=[]
    for session,root in sorted(roots.items()):
        if (root.get('wahlperiode')!='21'
                or root.get('sitzung-nr')!=str(session)
                or root.get('sitzung-datum')!=DAYS[session]):
            raise ValueError(f'Unexpected original XML session/date for 21/{session:03d}')
        paragraphs=[(int(p.sourceline),text) for p,text in iter_session_text(root)]
        if len(paragraphs)<30:
            raise ValueError('Missing official spoken-paragraph source')
        for original_date,person,ident,sit,decision,number,votes in CASES:
            if sit==session:
                records.append(exact_match(paragraphs,session,person))
    if len(records)!=7 or len({(x['session'],norm(x['person'])) for x in records})!=7:
        raise ValueError('Seven original person/session lines not uniquely attributable')
    return {
        'schema':'wp21-2025-seven-verified-original-xml-loci-v1',
        'source_run':'https://github.com/Erzkon/ordnungsrufe/actions/runs/39024535122',
        'individually_sourced_original_xml_lines':7,
        'known_other_21_040_lines_validated_separately':4,
        'first_janich_original_xml_line_is_still_unlocated':True,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'public_counter_delta':0,
        'cases':sorted(records,key=lambda x:(x['session'],norm(x['person']))),
    }


def markdown(report):
    if (report.get('schema')!='wp21-2025-seven-verified-original-xml-loci-v1'
            or report.get('individually_sourced_original_xml_lines')!=7
            or report.get('automatically_confirmed_effective_sanctions')!=0
            or report.get('public_counter_delta')!=0
            or len(report.get('cases',[]))!=7):
        raise ValueError('Untrusted 2025 original XML source report')
    lines=['# Sieben weitere Original-XML-Erteilungsstellen der 21. Wahlperiode',
           '',
           '**Sieben originale Erteilungsabsätze sind individuell anhand '
           'Person, Ursprungssitzung, amtlichem Originaltag und Wortlaut '
           'quellengeprüft.** Keine automatische Freigabe rechtswirksamer Maßnahmen.',
           '',
           '| Sitzung | Person | Original-XML-Zeile | Amtliche PDF-Quelle |',
           '| --- | --- | --- | --- |']
    for row in report['cases']:
        lines.append(
            f"| 21/{row['session']:03d} | {row['person']} | "
            f"{row['original_xml_line']} | "
            f"[Original-PDF]({row['original_pdf_source']}) |")
    lines += [
        '',
        '**Offen:** Der erste von zwei Janich-Ordnungsrufen in Sitzung',
        '21/040 ist zwar offiziell als individuelle Maßnahme samt',
        'späterem Einspruch belegt, besitzt hier aber weiterhin keinen',
        'einzeln bestätigten ursprünglichen Erteilungswortlaut.',
        'Sieben neue Originalfundstellen + vier bekannte 21/040-Fundstellen',
        'sind elf unterschiedliche Erteilungszeilen, nicht elf rechtlich',
        'wirksame oder veröffentlichbare Einzelmaßnahmen.','']
    return '\n'.join(lines)


def run(cache,output,brief):
    roots={}
    for session in DAYS:
        raw=fetch(session,Path(cache))
        if raw is None:
            raise ValueError(f'Missing original XML 21/{session:03d}')
        roots[session]=safe_parse(raw,session)
    report=inspect(roots)
    prose=markdown(report)
    for path,contents in ((Path(output),json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
                          (Path(brief),prose)):
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(path.suffix+'.tmp')
        tmp.write_text(contents,encoding='utf-8')
        tmp.replace(path)
    print('WP21_SEVEN_ORIGINAL_XML_OK: 7 exact official issuance lines, '
          '7+4=11 located original-issuance source paragraphs, '
          '1 first-Janich line unlocated, zero legal confirmations')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,default=Path('.audit/2025_original_xml'))
    parser.add_argument('--output',type=Path,default=Path('.audit/2025_7_original_lines.json'))
    parser.add_argument('--brief',type=Path,default=Path('.audit/2025_7_original_lines.md'))
    args=parser.parse_args()
    run(args.cache,args.output,args.brief)
