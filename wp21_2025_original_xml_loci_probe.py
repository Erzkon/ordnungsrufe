#!/usr/bin/env python3
"""Read-only one-off discovery of exact 2025 original grant XML paragraphs.

Only the eight official original sittings of the ten independently sourced
DIP person/date cases are fetched. Candidate wording is never counted as a
separately legally effective sanction. A near-person utterance is only
context; nothing is automatically approved.

Prefer inspecting stable source paragraph line + full normalized text, rather
than confusing one issuance with another mention of "Ordnungsruf".
"""
import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from parser import iter_session_text, action_match, classify
from wp21_2025_dip_einzelakten import CASES
from wp21_scan import fetch,safe_parse

TERM=re.compile(r'\bOrdnungsruf(?:e|es|en)?\b',re.I)
SITTINGS={s:datetime.strptime(day,'%Y-%m-%d').strftime('%d.%m.%Y')
          for day,person,parent,s,next_s,grants,votes in CASES}
if len(SITTINGS)!=8:
    raise ValueError('Expected exactly eight distinct 2025 original sittings')

PROVEN40=(8715,8719,8990,8992)


def inspect_one(root,session):
    """Return bounded source paragraphs and context for human line selection."""
    if (session not in SITTINGS
            or root.get('wahlperiode')!='21'
            or root.get('sitzung-nr')!=str(session)
            or root.get('sitzung-datum')!=SITTINGS[session]):
        raise ValueError('Wrong official plenary original source date/session')
    texts=[]
    for node,text in iter_session_text(root):
        if not text.strip():
            continue
        n=node.sourceline
        if type(n)!=int or n<1:
            raise ValueError('Original XML line missing')
        texts.append((n,text))
    if len(texts)<30:
        raise ValueError('Original stenographic session paragraphs incomplete')
    hits=[i for i,(_,text) in enumerate(texts) if TERM.search(text)]
    if not hits:
        raise ValueError('No source mentions of Ordnungsruf in expected sitting')
    if len(hits)>120:
        raise ValueError('Unexpectedly many issuance mentions; cannot review safely')
    candidates=[]
    for i in hits:
        line,text=texts[i]
        context=[{'line':texts[k][0],'text':texts[k][1][:430]}
                 for k in range(max(0,i-2),min(len(texts),i+3)) if k!=i]
        candidates.append({
            'xml_line':line,
            'source_text':' '.join(text.split())[:1250],
            'paragraph_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'issuance_verb_present':bool(action_match(text)),
            'parser_classification_review_only':classify(text),
            'contextual_neighbor_paragraphs':context,
            'candidate_not_legal_verification':True,
        })
    if session==40:
        present={row['xml_line'] for row in candidates}
        # Existing exact grant paragraphs must remain in the one-off
        # research extract even when the relevant original uses unusual words.
        if not set(PROVEN40).issubset(present):
            raise ValueError('Known official 21/040 grant lines unexpectedly missing')
    return {
        'session':session,
        'date':SITTINGS[session],
        'official_xml':f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml',
        'total_spoken_paragraphs':len(texts),
        'candidate_paragraphs':candidates,
        'known_grants_21_040':list(PROVEN40) if session==40 else [],
        'no_effective_sanction_count_inferred':True,
    }


def run(cache,output,brief):
    records=[]
    for session in sorted(SITTINGS):
        raw=fetch(session,Path(cache))
        if raw is None:
            raise ValueError(f'Missing official original protocol 21/{session:03d}')
        root=safe_parse(raw,session)
        row=inspect_one(root,session)
        records.append(row)
        print('SOURCE_2025_ORIGINAL',
              f'21/{session:03d}',row['date'],
              f"spoken={row['total_spoken_paragraphs']}",
              f"term_candidates={len(row['candidate_paragraphs'])}",flush=True)
    if len(records)!=8:
        raise ValueError('Incomplete 2025 original protocol survey')
    report={
        'schema':'wp21-2025-original-xml-candidate-lines-v1',
        'source_protocol_count':8,
        'candidate_source_lines':sum(len(r['candidate_paragraphs']) for r in records),
        'known_21_040_lines_verified':4,
        'all_remaining_unlocated_lines_must_be_reviewed_individually':True,
        'automatically_confirmed_effective_measures':0,
        'public_statistics_modified':False,
        'sessions':records,
    }
    lines=[
        '# 2025 Originalprotokolle: nur prüfpflichtige Wortlaut-Fundstellen',
        '',
        'Acht Originalprotokolle der zehn DIP-Fälle: **keine automatisch',
        'freigegebene rechtswirksame Maßnahme**.',
        '',
    ]
    for session in records:
        lines.extend([
            f"## Original 21/{session['session']:03d} vom {session['date']}",
            '',
            f"Quelle: {session['official_xml']}",
            '',
        ])
        for c in session['candidate_paragraphs']:
            lines.append(
                f"- **XML L{c['xml_line']}** (Parserhinweis: "
                f"{c['parser_classification_review_only']}): "
                f"{c['source_text'][:850]} "
                f"[SHA256 {c['paragraph_sha256'][:14]}…]")
        lines.append('')
    lines.append('**Fundstellen sind nur Recherchekandidaten, keine Sanktionen.**')
    for target,data in ((Path(output),json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
                        (Path(brief),'\n'.join(lines)+'\n')):
        target.parent.mkdir(parents=True,exist_ok=True)
        temp=target.with_suffix(target.suffix+'.tmp')
        temp.write_text(data,encoding='utf-8')
        temp.replace(target)
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache',type=Path,default=Path('.audit/original_2025_xml'))
    ap.add_argument('--output',type=Path,default=Path('.audit/original_2025_candidates.json'))
    ap.add_argument('--brief',type=Path,default=Path('.audit/original_2025_candidates.md'))
    a=ap.parse_args()
    run(a.cache,a.output,a.brief)
