#!/usr/bin/env python3
"""Bounded, read-only evidence context for gaps in curated WP21 DIP references.

A paragraph or neighbor can be an addressee, the chair, an injured person, or
another MP. Context is *never* an inferred recipient or confirmed sanction.
"""
import argparse
import json
import re
from pathlib import Path

from parser import (candidates, events, issuer_context, iter_session_text,
                    normal, speaker_index)
from wp21_dip_kontrolle import REFERENCE, reference
from wp21_scan import HOST, fetch, safe_parse

DEFAULT_SESSIONS = (52,53,57,61,65,67,68,71,77,90,93,94)
MAX_SNIPPET = 520
MAX_ENTRIES = 80


def snippet(text, limit=MAX_SNIPPET):
    return normal(text)[:limit]


def examine(root, session, person_names):
    """Inspect real session paragraphs without crossing speaker bounds as facts."""
    path=Path(f'21{session:03d}.xml')
    paras=list(iter_session_text(root))
    hints=list(candidates(path,root=root))
    idx=speaker_index([root])
    proposals=list(events(path,index=idx,root=root))
    annotations={}
    for p,text in paras:
        annotations[int(p.sourceline)]=(p,text)
    sources={int(x['line']):x for x in hints}
    grantlines={int(x['line']) for x in hints if
                x['classification'] in ('possible_grant','named_group_confirmation')}
    results=[]
    for person in person_names:
        family=person.split()[-1].casefold()
        # A surname is a *search hint*, including mentions by other speakers;
        # never treat its occurrence alone as evidence of a sanction.
        linked=[(line,text) for line,(element,text) in annotations.items()
                if family in text.casefold() and
                re.search(r'(?<!\w)'+re.escape(family)+r'(?!\w)',text,re.I)]
        selected=set(grantlines)
        selected.update(line for line,_ in linked)
        records=[]
        for line in sorted(selected):
            p,txt=annotations[line]
            j=next((i for i,(item,_) in enumerate(paras)
                    if int(item.sourceline)==line),None)
            previous=snippet(paras[j-1][1],180) if j is not None and j>0 else ''
            following=snippet(paras[j+1][1],180) if j is not None and j+1<len(paras) else ''
            marker,kind=issuer_context(p)
            known=[x for x in proposals if int(x['line'])==line]
            records.append({
                'line':line,
                'classification':sources[line]['classification'] if line in sources else 'name_only',
                'contains_target_surname':line in {n for n,_ in linked},
                'text':snippet(txt),
                'preceding_context_not_recipient_evidence':previous,
                'following_context_not_recipient_evidence':following,
                'speaker_marker_not_recipient':marker,
                'speaker_marker_type':kind,
                'parser_people_not_confirmed':[{'person':x['person'],
                    'method':x['zuordnungsmethode']} for x in known],
            })
        # Cap selected rows; keep ALL source grant paragraphs before surname-only
        # paragraphs. A cap is reported, never advertised as complete coverage.
        records.sort(key=lambda x:(0 if x['classification'] in
                     ('possible_grant','named_group_confirmation') else 1,
                     0 if x['contains_target_surname'] else 1,x['line']))
        total=len(records)
        results.append({'session':session,'person':person,
            'expected_recipient_is_only_dip_positive_control':True,
            'grant_locations_in_session':len(grantlines),
            'name_mention_paragraphs':len(linked),
            'candidate_contexts_total':total,
            'contexts_shown':min(total,MAX_ENTRIES),
            'truncated':total>MAX_ENTRIES,
            'source_pdf':f'{HOST}/21{session:03d}.pdf',
            'contexts':records[:MAX_ENTRIES],
        })
    return results


def collect(cache, sessions=DEFAULT_SESSIONS, source=REFERENCE):
    ref=reference(source)
    chosen=set(sessions)
    if not chosen or any(type(x)!=int or not 1<=x<=450 for x in chosen):
        raise ValueError('Unzulässige Sitzung für Quellendiagnose')
    grouped={}
    for item in ref['entries']:
        if item['session'] in chosen:
            grouped.setdefault(item['session'],[]).append(item['person'])
    if set(grouped)!=chosen:
        raise ValueError('Keine kuratierte DIP-Positivreferenz zu einer Zielsitzung')
    records=[]
    for session,names in sorted(grouped.items()):
        data=fetch(session,Path(cache))
        if data is None:
            raise ValueError(f'Amtliches XML 21/{session:03d} noch nicht verfügbar')
        root=safe_parse(data,session)
        records.extend(examine(root,session,names))
        print(f'Quellendiagnose 21/{session:03d}: {len(names)} Referenzpersonen',flush=True)
    return {'status':'gezielte_quellendiagnose_nicht_verifizierte_zuordnung',
            'wahlperiode':21,'source_index':ref['official_index'],
            'sessions_loaded':len(grouped),
            'person_session_targets':len(records),
            'no_auto_confirmation':True,
            'warning':('Angrenzende Absätze können andere Sprecher, Geschädigte '
                       'oder historische Erwähnungen enthalten. Keine Personen- '
                       'oder Einzelereigniszuordnung allein daraus ableiten.'),
            'cases':records}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache',type=Path,default=Path('.audit/targeted_xml'))
    ap.add_argument('--sessions',type=str,default=','.join(map(str,DEFAULT_SESSIONS)))
    ap.add_argument('--output',type=Path,default=Path('.audit/targeted_context.json'))
    args=ap.parse_args()
    sessions=tuple(int(s.strip()) for s in args.sessions.split(','))
    result=collect(args.cache,sessions=sessions)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Nur Quellenkontext:',result['person_session_targets'],
          'kuratierte Personen/Sitzung-Ziele. 0 automatisch bestätigte Maßnahmen.')


if __name__=='__main__':
    main()
