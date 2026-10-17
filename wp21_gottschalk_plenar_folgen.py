#!/usr/bin/env python3
"""Read-only official Bundestag XML survey for later Kay Gottschalk objections.

Word matches identify manual-review candidates; they do not establish a
separate decision, a legal effect, or the absence of other official records.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from parser import iter_session_text
from wp21_scan import fetch, safe_parse

PREFIX='https://dserver.bundestag.de/btp/21/'
ARTICLE=('https://www.bundestag.de/dokumente/textarchiv/2025/'
         'kw48-de-einspruch-ordnungsruf-1127758')
NAME=re.compile(r'\bKay\s+Gottschalk\b',re.I)
APPEAL=re.compile(r'\b(?:Einspruch\w*|Widerspruch\w*)\b',re.I)
ORDER=re.compile(r'\b(?:Ordnungsruf\w*|Ordnungsma[ßs]nahme\w*)\b',re.I)
SECOND=re.compile(r'\b(?:zweite[nmrs]?|2\.)\s+Ordnungs(?:ruf\w*|ma[ßs]nahme\w*)\b',re.I)


def inspect_rows(rows, session, date):
    if (not isinstance(rows,list) or not 42<=session<=150
            or not re.fullmatch(r'\d{2}\.\d{2}\.\d{4}',date)
            or len(rows)>60000):
        raise ValueError('Amtliche Plenarabsätze unzuverlässig')
    results=[]
    for i,row in enumerate(rows):
        if (not isinstance(row,tuple) or len(row)!=2
                or type(row[0]) is not int or row[0]<1
                or not isinstance(row[1],str) or len(row[1])>12000):
            raise ValueError('Beschädigter Original-XML-Absatz')
        line,text=row
        if not NAME.search(text):
            continue
        adjacent=rows[max(0,i-2):min(i+3,len(rows))]
        own_appeal=bool(APPEAL.search(text))
        own_order=bool(ORDER.search(text))
        if not ((own_appeal and any(ORDER.search(t) for _,t in adjacent))
                or (own_order and any(APPEAL.search(t) for _,t in adjacent))):
            continue
        context=' '.join(p for _,p in adjacent)
        results.append({
            'session':session, 'session_date':date,'xml_line':line,
            'source_xml':f'{PREFIX}21{session:03d}.xml',
            'source_pdf':f'{PREFIX}21{session:03d}.pdf',
            'paragraph_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'original_excerpt':' '.join(text.split())[:1000],
            'context_excerpt':' '.join(context.split())[:1200],
            'own_appeal_text':own_appeal,'own_order_text':own_order,
            'second_measure_mentioned_in_context':bool(SECOND.search(context)),
            'source_class':('known_first_decision_reference' if session==42
                            else 'manual_review_only'),
            'decision_confirmed_by_lexical_match':False,
            'counter_delta':0,
        })
    return results


def review(roots):
    if (not isinstance(roots,dict) or not roots
            or 42 not in roots or max(roots)>=150
            or set(roots)!=set(range(42,max(roots)+1))):
        raise ValueError('Unvollständige Folge von amtlichen Sitzungs-XMLs')
    first=[]
    later=[]
    sessions=[]
    count=0
    for session,root in sorted(roots.items()):
        if (root.get('wahlperiode')!='21'
                or root.get('sitzung-nr')!=str(session)):
            raise ValueError('Fremdes Plenarprotokoll')
        rows=[(int(p.sourceline),t) for p,t in iter_session_text(root)]
        if not rows:
            raise ValueError('Gesprochener XML-Sitzungstext fehlt')
        date=root.get('sitzung-datum','')
        hits=inspect_rows(rows,session,date)
        (first if session==42 else later).extend(hits)
        sessions.append({'session':session,'date':date,
                         'spoken_paragraphs':len(rows),'review_contexts':len(hits)})
        count+=len(rows)
    if not first:
        raise ValueError('Bekannte Gottschalk-Einspruchsreferenz 21/042 fehlt')
    return {
        'schema':'wp21-gottschalk-plenary-followups-v1',
        'first_session':42,'last_session':max(roots),
        'sessions_checked':len(roots),'spoken_paragraphs_checked':count,
        'known_first_appeal_in_42':first,
        'later_person_named_contexts':later,
        'later_context_count':len(later),'source_sessions':sessions,
        'official_first_appeal_article':ARTICLE,
        'other_nonplenary_or_future_official_documents_not_excluded':True,
        'later_appeal_decision_not_established_by_keywords':True,
        'janich_first_issuance_wording_not_invented':True,
        'gottschalk_second_legal_effect_unresolved':True,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,'public_counter_delta':0,
    }


def markdown(r):
    if (r.get('schema')!='wp21-gottschalk-plenary-followups-v1'
            or r.get('other_nonplenary_or_future_official_documents_not_excluded') is not True
            or r.get('later_appeal_decision_not_established_by_keywords') is not True
            or r.get('janich_first_issuance_wording_not_invented') is not True
            or r.get('gottschalk_second_legal_effect_unresolved') is not True
            or r.get('automatically_confirmed_effective_sanctions')!=0
            or r.get('automatically_rescinded_sanctions')!=0
            or r.get('public_counter_delta')!=0):
        raise ValueError('Textbelege sind keine Zählerfreigabe')
    lines=['# Gottschalk – spätere amtliche Plenarprotokolle','',
           f"Vollständig gelesene Sitzungen: 21/042 bis "
           f"21/{r['last_session']:03d} ({r['sessions_checked']}).",
           f"Gesprochene Absätze: {r['spoken_paragraphs_checked']}.",
           f"Spätere Kontexttreffer zur Prüfung: {r['later_context_count']}.",
           'Die erste Entscheidung 21/042 bleibt eine bekannte Referenz.',
           '']
    for row in r['later_person_named_contexts']:
        lines.append(f"- [21/{row['session']:03d} L{row['xml_line']}]"
                     f"({row['source_xml']}) – "
                     f"{row['original_excerpt'][:250]} "
                     '(nicht verifizierter Folgeverfahrenshinweis)')
    lines += ['',f"[Amtlicher Textarchiv-Beleg zur ersten Entscheidung]"
              f"({r['official_first_appeal_article']})",'',
              '**Keine Rechtsfolgenbestätigung und keine Zähleränderung.** '
              'Andere amtliche Dokumentarten, nicht eindeutig namentlich '
              'zuordenbare Erwähnungen und spätere Entscheidungen sind '
              'nicht ausgeschlossen.','']
    return '\n'.join(lines)


def run(cache,output,brief,*,max_session=125,cache_only=False,
        last_session=None,load=fetch):
    cache=Path(cache)
    if not 43<=max_session<=150:
        raise ValueError('Maximale Sitzungsnummer ungültig')
    if cache_only:
        if type(last_session) is not int or not 42<=last_session<max_session:
            raise ValueError('Validiertes XML-Scanende erforderlich')
        sequence=range(42,last_session+1)
    else:
        sequence=range(42,max_session+1)
    roots={}
    missing=[]
    for session in sequence:
        if cache_only:
            file=cache/f'21{session:03d}.xml'
            data=file.read_bytes() if file.is_file() else None
        else:
            data=load(session,cache)
        if data is None:
            missing.append(session)
            if cache_only:
                raise ValueError('Lücke im erfolgreichen XML-Scan-Cache')
            if len(missing)>=3: break
            continue
        if missing:
            raise ValueError('Ungeklärte Lücke in amtlicher Plenarsitzungsfolge')
        roots[session]=safe_parse(data,session)
    if not cache_only and len(missing)<3:
        raise ValueError('Ende der veröffentlichten XMLs nicht ermittelt')
    r=review(roots)
    content=markdown(r)
    for path,data in ((Path(output),json.dumps(r,ensure_ascii=False,indent=2)+'\n'),
                      (Path(brief),content)):
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(path.suffix+'.tmp')
        tmp.write_text(data,encoding='utf-8')
        tmp.replace(path)
    if r['later_context_count']:
        print('::warning::Gottschalk-Folgetexte nur manuell überprüfen; '
              'keine automatische Entscheidung')
    print('WP21_GOTTSCHALK_PLENARY_OK',r['sessions_checked'],'XMLs,',
          r['spoken_paragraphs_checked'],'spoken paragraphs,',
          r['later_context_count'],'later review hints, zero count changes')
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--brief',type=Path,required=True)
    p.add_argument('--max-session',type=int,default=125)
    p.add_argument('--cache-only',action='store_true')
    p.add_argument('--last-session',type=int)
    x=p.parse_args()
    run(x.cache,x.output,x.brief,max_session=x.max_session,
        cache_only=x.cache_only,last_session=x.last_session)
