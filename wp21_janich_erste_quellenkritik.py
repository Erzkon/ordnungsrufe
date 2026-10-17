#!/usr/bin/env python3
"""Forensic negative check for the first Steffen Janich call in 21/040.

No explicit independent first issuance is invented from the conditional
"wenn Sie lachen ... erteile ich Ihnen gleich ..." statement.
Official 21/042 still proves two separate rejected §39 objections.
The Bundestag article paraphrases Janich's appeal rationale; this is NOT
necessarily a literal statement of why the chair issued the second call.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from parser import iter_session_text
from wp21_scan import fetch, safe_parse

ORIGINAL='https://dserver.bundestag.de/btp/21/21040.xml'
DECISION='https://dserver.bundestag.de/btp/21/21042.xml'
ARTICLE='https://www.bundestag.de/dokumente/textarchiv/2025/kw48-de-einspruch-ordnungsruf-1127758'
# These source lines were independently checked on the genuine official PDFs
# page 4626 and page 4865 and on the source XML wordings.
LINES={
    'sichert_first_grant':(40,8715,r'\bIch\s+erteile\s+Ihnen\s+jetzt\s+einen\s+Ordnungsruf\b.{0,180}\bmit\s+dem\s+Finger\s+auf\s+Kollegen\s+gezeigt\b'),
    'janich_conditional_laughter_warning':(
        40,8717,
        r'\bUnd\s+wenn\s+Sie\s+lachen\b.{0,110}'
        r'\berteile\s+ich\s+Ihnen\s+gleich\s+fürs\s+Lachen\s+den\s+nächsten\s+Ordnungsruf\b'),
    'janich_explicit_second_issuance':(
        40,8719,
        r'\bIch\s+erteile\s+Ihnen\s+auch\s+für\s+den\s+Widerspruch\s+gerade\s+'
        r'einen\s+zweiten\s+Ordnungsruf\b'),
    'janich_first_objection_rejected':(
        42,1513,r'\bEinspruch\s+gegen\s+den\s+ersten\s+Ordnungsruf\b'
        r'.{0,95}\bSteffen\s+Janich\b.{0,280}'
        r'\bDer\s+Einspruch\s+ist\s+damit\s+zurückgewiesen\b'),
    'janich_second_objection_rejected':(
        42,1517,r'\bEinspruch\s+gegen\s+den\s+zweiten\s+Ordnungsruf\b'
        r'.{0,95}\bSteffen\s+Janich\b.{0,280}'
        r'\bDer\s+Einspruch\s+ist\s+damit\s+zurückgewiesen\b'),
}


def inspect_rows(paragraphs):
    """Exact line and wording crosscheck, fail closed on duplicates/shift."""
    if not isinstance(paragraphs,dict) or set(paragraphs)!={40,42}:
        raise ValueError('Zwei amtliche Original-/Einspruchssitzungen fehlen')
    found={}
    for label,(session,line,expression) in LINES.items():
        entries=paragraphs[session]
        if not isinstance(entries,list):
            raise ValueError('Amtlicher Sitzungswortlaut fehlt')
        hits=[(lineno,text) for lineno,text in entries
              if isinstance(text,str)
              and re.search(expression,' '.join(text.split()),re.I|re.S)]
        if len(hits)!=1 or hits[0][0]!=line:
            raise ValueError(f'Janich/Sichert original source mismatch: {label}')
        text=hits[0][1]
        if not 0<len(text)<=5000:
            raise ValueError('Ungültige Protokollabsatzlänge')
        found[label]={
            'xml_line':line,
            'source_url':ORIGINAL if session==40 else DECISION,
            'paragraph_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'original_excerpt':' '.join(text.split())[:1200],
        }
    warning=found['janich_conditional_laughter_warning']['original_excerpt']
    if (not re.search(r'\bwenn\b',warning,re.I)
            or not re.search(r'\bgleich\b',warning,re.I)
            or re.search(r'\bich\s+erteile\s+Ihnen\s+jetzt\b',warning,re.I)):
        raise ValueError('Bedingte Androhung fälschlich als aktuelle Erteilung behandelt')
    first,threat,second=[found[x]['xml_line'] for x in (
        'sichert_first_grant','janich_conditional_laughter_warning',
        'janich_explicit_second_issuance')]
    if not first<threat<second:
        raise ValueError('Originale sprachliche Abfolge nicht belegt')
    if (found['janich_first_objection_rejected']['xml_line']==
            found['janich_second_objection_rejected']['xml_line']):
        raise ValueError('Erster/zweiter Einspruch nicht unabhängig unterscheidbar')
    return {
        'schema':'wp21-janich-first-conditional-versus-second-grant-v1',
        'source_status':'genuine_spoken_xml_and_separate_individual_objection_decisions',
        'original_sitting':40,'original_date':'2025-11-13',
        'decision_sitting':42,'decision_date':'2025-11-25',
        'original_pdf':'https://dserver.bundestag.de/btp/21/21040.pdf#P.4626',
        'decision_pdf':'https://dserver.bundestag.de/btp/21/21042.pdf#P.4865',
        'independent_bundestag_decision_article':ARTICLE,
        'documented_distinct_original_measures':2,
        'documented_separately_rejected_objections':2,
        'first_independent_unconditional_issuance_xml_line':None,
        'first_original_measure_is_a_source_documented_case':True,
        'conditional_notice_is_not_unconditional_issuance_proof':True,
        'do_not_map_conditional_warning_to_first_issuance':True,
        'explicit_second_xml_line':second,
        'official_article_accounts_for_claim_about_continued_laughter':True,
        'original_chair_second_wording_mentions_objection':True,
        'possible_source_description_difference_requires_review':True,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'public_counter_delta':0,
        'source_passages':found,
        'warning':(
            'Der später amtlich bestätigte erste Ordnungsruf hat im '
            'stenografischen Original keinen individuell zugeordneten '
            'unbedingten Erteilungssatz. Die bedingte Formulierung '
            'auf XML-Zeile 8717 wird als Androhung und Kontext, '
            'NICHT als Erteilung, verknüpft. Der zweite erteilte '
            'Ruf ist auf Zeile 8719 ausdrücklich verzeichnet; '
            'zwei Einsprüche wurden gesondert abgewiesen. '
            'Die Wiedergabe von Janichs eigener Begründung im '
            'Bundestagsartikel kann eine andere Formulierung verwenden '
            'als der originale Sitzungsleitungssatz. '
            'Keine Aussage über ansonsten unbekannte Rechtsfolgen.'),
    }


def inspect(roots):
    if not isinstance(roots,dict) or set(roots)!={40,42}:
        raise ValueError('Beide Protokolle 21/040 und 21/042 erforderlich')
    expected={40:'13.11.2025',42:'25.11.2025'}
    paragraphs={}
    for session,root in roots.items():
        if (root.get('wahlperiode')!='21'
                or root.get('sitzung-nr')!=str(session)
                or root.get('sitzung-datum')!=expected[session]):
            raise ValueError('Falsches originales amtliches Protokolldatum')
        paragraphs[session]=[(int(node.sourceline),text)
                             for node,text in iter_session_text(root)]
        if len(paragraphs[session])<100:
            raise ValueError('Original-Plenarprotokoll-Wortlaut unvollständig')
    return inspect_rows(paragraphs)


def markdown(report):
    if (report.get('schema')!='wp21-janich-first-conditional-versus-second-grant-v1'
            or report.get('documented_distinct_original_measures')!=2
            or report.get('documented_separately_rejected_objections')!=2
            or report.get('first_independent_unconditional_issuance_xml_line') is not None
            or report.get('conditional_notice_is_not_unconditional_issuance_proof') is not True
            or report.get('automatically_confirmed_effective_sanctions')!=0
            or report.get('public_counter_delta')!=0):
        raise ValueError('Quellenkritische erste-Janich-Akte unvollständig')
    src=report['source_passages']
    lines=[
        '# Steffen Janich 21/040: keine unbelegte erste Erteilungszeile erfinden',
        '',
        '- **21/040, XML 8715**: eindeutige Erteilung an Sichert.',
        '- **21/040, XML 8717**: **bedingte Formulierung** '
        'für das Lachen, *keine eindeutig selbstständige unbedingte '
        'Erteilungsformulierung*.',
        '- **21/040, XML 8719**: ausdrücklich **zweiter** Ordnungsruf '
        'an Janich (Originaltext spricht vom Widerspruch).',
        '- **21/042, XML 1513 und 1517**: zwei getrennte '
        'zurückgewiesene Einsprüche, erster und zweiter Ruf.',
        '',
        f"[Originalprotokoll S. 4626]({report['original_pdf']}) · "
        f"[Beschlussprotokoll S. 4865]({report['decision_pdf']}) · "
        f"[Bundestagsartikel]({report['independent_bundestag_decision_article']})",
        '',
        'Die amtliche Meldung referiert Janichs eigene Begründung '
        'zum weiteren Lachen. Die ursprüngliche Präsidentinnen-'
        'Formulierung zum zweiten Ordnungsruf nennt dagegen Widerspruch. '
        'Beide Quellenaussagen werden getrennt bewahrt, nicht als '
        'identischer wörtlicher Verhängungsgrund gleichgesetzt.',
        '',
    ]
    for label,row in src.items():
        lines.append(f"- {label}: {row['source_url']} · "
                     f"L{row['xml_line']} · SHA256 {row['paragraph_sha256'][:16]}…")
    lines += ['','**Keine Zählerfreigabe oder automatische '
              'Rechtsfolgenbestätigung.**','']
    return '\n'.join(lines)


def run(cache,output,brief):
    roots={}
    for session in (40,42):
        data=fetch(session,Path(cache))
        if data is None:
            raise ValueError(f'Original-XML 21/{session:03d} nicht auffindbar')
        roots[session]=safe_parse(data,session)
    report=inspect(roots)
    prose=markdown(report)
    for target,contents in (
            (Path(output),json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
            (Path(brief),prose)):
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_suffix(target.suffix+'.tmp')
        temporary.write_text(contents,encoding='utf-8')
        temporary.replace(target)
    print('WP21_JANICH_FIRST_FORENSICS_OK: warning 8717 conditional, '
          'explicit second 8719, two separate objections 1513/1517, '
          'first unconditional grant XML line unlocated; zero count changes.')
    return report


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--cache',type=Path,default=Path('.audit/2025_original_xml'))
    cli.add_argument('--output',type=Path,default=Path('.audit/wp21_janich_first_evidence.json'))
    cli.add_argument('--brief',type=Path,default=Path('.audit/wp21_janich_first_evidence.md'))
    args=cli.parse_args()
    run(args.cache,args.output,args.brief)
