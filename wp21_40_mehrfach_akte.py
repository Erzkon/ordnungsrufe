#!/usr/bin/env python3
"""Isolated source-line dossier for the Nov 2025 two-grant cases.

Plenary 21/040 contains original words of chair Andrea Lindholz, while
21/042 expressly votes on Janich's FIRST and SECOND Ordnungsrufe.
We match paragraphs, not count every mention of "Ordnungsruf".
Official PDF cross-check is independent of XML parser event identities.
No published or individually reviewed effective measure is changed.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from parser import iter_session_text
from wp21_scan import fetch,safe_parse

PHRASES_40={
    'Sichert_original_issuance':
        r'ich\s+erteile\s+Ihnen\s+jetzt\s+einen\s+Ordnungsruf\b.*?'
        r'\bmit\s+dem\s+Finger\s+auf\s+Kollegen\s+gezeigt\b',
    'Janich_second_original_issuance_words':
        r'ich\s+erteile\s+Ihnen\s+auch\s+für\s+den\s+Widerspruch'
        r'\s+gerade\s+einen\s+zweiten\s+Ordnungsruf\b',
    'Gottschalk_first_original_issuance':
        r'Herr\s+Kollege\s+Gottschalk,?\s+ich\s+erteile\s+Ihnen'
        r'\s+jetzt\s+einen\s+Ordnungsruf\b',
    'Gottschalk_second_original_issuance':
        r'ich\s+erteile\s+Ihnen\s+einen\s+zweiten\s+Ordnungsruf\b',
}
# A conditional future warning is context, never a literal first issuance.
JANICH_CONDITIONAL_40=(
    r'Und\s+wenn\s+Sie\s+lachen\b.{0,120}'
    r'\berteile\s+ich\s+Ihnen\s+gleich\s+fürs\s+Lachen\s+den\s+nächsten\s+Ordnungsruf\b'
)
PHRASES_42={
    'Sichert_objection_vote':
        r'Wer\s+stimmt\s+für\s+den\s+Einspruch\s+des\s+Abgeordneten'
        r'\s+Martin\s+Sichert\b',
    'Janich_first_objection_vote':
        r'Einspruch\s+gegen\s+den\s+ersten\s+Ordnungsruf'
        r'\s+gegen\s+den\s+Abgeordneten\s+Steffen\s+Janich\b',
    'Janich_second_objection_vote':
        r'Einspruch\s+gegen\s+den\s+zweiten\s+Ordnungsruf'
        r'\s+gegen\s+den\s+Abgeordneten\s+Steffen\s+Janich\b',
    'Gottschalk_objection_vote':
        r'Einspruch\s+des\s+Abgeordneten\s+Kay\s+Gottschalk\b',
}
DATES={40:'13.11.2025',42:'25.11.2025'}


def matching_paragraph(rows,pattern,label):
    compiled=re.compile(pattern,re.I|re.S)
    found=[(line,text) for line,text in rows if compiled.search(text)]
    if len(found)!=1:
        raise ValueError(
            f'Amtliche Original-XML-Fundstelle {label!r} unklar: {len(found)}')
    line,phrase=found[0]
    if not isinstance(line,int) or line<1 or len(phrase)>5000:
        raise ValueError('Unplausible Länge oder Zeile amtlicher Wortlaut')
    return {'original_xml_line':line,
            'original_text_excerpt':' '.join(phrase.split())[:1000],
            'paragraph_sha256':hashlib.sha256(phrase.encode()).hexdigest(),
            'legal_measure_count_confirmed_by_this_paragraph':False}


def inspect(roots):
    if set(roots)!={40,42}:
        raise ValueError('Amtliche Quellprotokolle 21/040 und 21/042 benötigt')
    rows={}
    for session,root in roots.items():
        if (root.get('wahlperiode')!='21'
                or root.get('sitzung-nr')!=str(session)
                or root.get('sitzung-datum')!=DATES[session]):
            raise ValueError('Falsche amtliche Sitzung oder Datum')
        rows[session]=[(int(p.sourceline),text)
                      for p,text in iter_session_text(root)]
        if not rows[session]:
            raise ValueError('Kein echter stenografischer Sitzungswortlaut')
    grants={key:matching_paragraph(rows[40],pattern,key)
            for key,pattern in PHRASES_40.items()}
    conditional=matching_paragraph(
        rows[40],JANICH_CONDITIONAL_40,'Janich_first_conditional_warning')
    if (conditional['original_xml_line'] >=
            grants['Janich_second_original_issuance_words']['original_xml_line']):
        raise ValueError('Bedingte Janich-Androhung nicht vor zweiter Erteilung')
    votes={key:matching_paragraph(rows[42],pattern,key)
           for key,pattern in PHRASES_42.items()}
    # Vote outcomes are reported as "Der Einspruch ist damit zurückgewiesen."
    # Separate official report further confirms four independent rejections.
    spoken=' '.join(t for _,t in rows[42])
    rejections=len(re.findall(
        r'\bDer\s+Einspruch\s+ist\s+damit\s+zurückgewiesen\b',
        spoken,re.I))
    if rejections!=4:
        raise ValueError('Vier getrennte protokollierte Zurückweisungen fehlen')
    return {
        'schema':'wp21-40-42-source-episode-audit-v1',
        'status':'original_issuance_and_decision_wording_review_only',
        'original_protocol':'https://dserver.bundestag.de/btp/21/21040.xml',
        'original_pdf':'https://dserver.bundestag.de/btp/21/21040.pdf',
        'appeal_protocol':'https://dserver.bundestag.de/btp/21/21042.xml',
        'appeal_pdf':'https://dserver.bundestag.de/btp/21/21042.pdf',
        'distinct_original_issued_measures_from_independent_sources':5,
        'distinct_rejected_appeals_in_42':4,
        'gottschalk_original_issued_measures':2,
        'gottschalk_appeals_decided_in_42':1,
        'janich_appeals_distinguish_first_and_second':True,
        'original_phrase_locations_not_sanction_count':len(grants),
        'original_issuance_phrases_explicitly_located':len(grants),
        'janich_first_original_unconditional_issuance_xml_line':None,
        'janich_first_measure_basis':'separate_official_objection_decision_21_042',
        'janich_first_warning_is_issuance':False,
        'source_non_issuance_context_paragraphs':{
            'Janich_first_conditional_warning':conditional},
        'source_issuance_paragraphs':grants,
        'source_appeal_paragraphs':votes,
        'four_separate_vote_rejection_wordings_checked':rejections,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'protected_public_counters_changed':False,
        'warning':('Fünf ursprüngliche Maßnahmen sind quellübergreifend '
                   'dokumentiert, aber nur vier ausdrücklich ausgesprochene '
                   'Original-Erteilungsabsätze hier lokalisiert. Janichs '
                   'erste Erteilung wird NICHT aus der bedingten Androhung '
                   'rekonstruiert, sondern nur aus der späteren eigenständigen '
                   'Einspruchsentscheidung erschlossen. Gottschalks zweite '
                   'Maßnahme ist nicht durch den einen entschiedenen Einspruch '
                   'abgegolten; weitere Rechtsfolgen bleiben offen.'),
    }


def render_markdown(report):
    if (report.get('schema')!='wp21-40-42-source-episode-audit-v1'
            or report.get('distinct_original_issued_measures_from_independent_sources')!=5
            or report.get('distinct_rejected_appeals_in_42')!=4
            or report.get('gottschalk_original_issued_measures')!=2
            or report.get('gottschalk_appeals_decided_in_42')!=1
            or report.get('original_issuance_phrases_explicitly_located')!=4
            or report.get('janich_first_original_unconditional_issuance_xml_line') is not None
            or report.get('janich_first_measure_basis')!='separate_official_objection_decision_21_042'
            or report.get('janich_first_warning_is_issuance') is not False
            or len(report.get('source_non_issuance_context_paragraphs',{}))!=1
            or len(report.get('source_issuance_paragraphs',{}))!=4
            or len(report.get('source_appeal_paragraphs',{}))!=4
            or report.get('automatically_confirmed_effective_sanctions')!=0
            or report.get('protected_public_counters_changed')):
        raise ValueError('Unvollständige XML-Mehrfachakten-Quelle')
    lines=[
        '# Sitzungen 21/040 und 21/042: vier Einzel-Einsprüche versus fünf Rufe',
        '',
        '**Amtlich dokumentierte ursprüngliche Maßnahmen:** Sichert 1, Janich 2, Gottschalk 2.',
        '**Im Original 21/040 eindeutig formulierte Erteilungen:** vier.',
        'Janichs erste Erteilung hat keine zugeordnete unbedingte Original-XML-Zeile;', 
        'sie ist durch die spätere eigenständige Einspruchsentscheidung belegt.',
        '**In der späteren Sitzung 21/042 zurückgewiesene Einsprüche:**',
        'Sichert 1, Janich 2, Gottschalk 1.',
        '',
        '**Die Zahl gefundener XML-Absätze entspricht NICHT der Zahl',
        'eigenständiger rechtlich wirksamer Maßnahmen.**',
        '',
        '## Originaläußerungen 21/040',
        '',
    ]
    for name,record in report['source_issuance_paragraphs'].items():
        lines.append(
            f"- {name}: [XML 21/040 L{record['original_xml_line']}]"
            f"({report['original_protocol']}), "
            f"SHA256 {record['paragraph_sha256'][:16]}…")
    context=report['source_non_issuance_context_paragraphs']['Janich_first_conditional_warning']
    lines += [
        '', '## Bedingte Warnung (ausdrücklich KEINE Erteilung)',
        '',
        f"- Janich: [XML 21/040 L{context['original_xml_line']}]"
        f"({report['original_protocol']}), "
        f"SHA256 {context['paragraph_sha256'][:16]}…",
        'Bedingter Zukunftssatz, keine erfundene erste Erteilungsstelle.',
    ]
    lines+=['','## Einspruchsformulierungen 21/042','']
    for name,record in report['source_appeal_paragraphs'].items():
        lines.append(
            f"- {name}: [XML 21/042 L{record['original_xml_line']}]"
            f"({report['appeal_protocol']}), "
            f"SHA256 {record['paragraph_sha256'][:16]}…")
    lines += [
        '',f"Explizite, einzeln nachgewiesene Zurückweisungsformulierungen: "
        f"{report['four_separate_vote_rejection_wordings_checked']}.",
        'Das Fehlen einer zweiten Gottschalk-Einspruchsentscheidung in',
        'dieser Abstimmungsserie belegt keine endgültige Wirksamkeit.',
        '**Alle bestätigten Zähler bleiben unverändert.**','',
    ]
    return '\n'.join(lines)


def run(cache,output,brief):
    roots={}
    for session in sorted(DATES):
        data=fetch(session,Path(cache))
        if data is None:
            raise ValueError(f'Amtliches Originalprotokoll 21/{session:03d} fehlt')
        roots[session]=safe_parse(data,session)
    report=inspect(roots)
    markdown=render_markdown(report)
    for path,contents in ((Path(output),json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
                          (Path(brief),markdown)):
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(path.suffix+'.tmp')
        tmp.write_text(contents,encoding='utf-8')
        tmp.replace(path)
    print('WP21_40_42_SOURCE_EPISODES_OK: 5 original grants, 4 votes, '
          '4+4 original XML phrases, 0 approved effective measures.')
    return report


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--cache',type=Path,default=Path('.audit/wp21_original_xml'))
    a.add_argument('--output',type=Path,default=Path('.audit/wp21_40_42_source_episodes.json'))
    a.add_argument('--brief',type=Path,default=Path('.audit/wp21_40_42_source_episodes.md'))
    v=a.parse_args()
    run(v.cache,v.output,v.brief)
