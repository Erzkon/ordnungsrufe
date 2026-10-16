#!/usr/bin/env python3
"""Separate read-only source dossier for three ambiguous issuance episodes.

Each episode has TWO original chair utterances around ONE official reaction:
WP21/049 Brandner, WP21/051 Frohnmaier, WP21/065 Reichardt. The speaker
of that reaction and whether the second utterance is a new legal measure
must NEVER be inferred solely from the count of 'Ordnungsruf' phrases.

This report is independent of and must not change confirmed CSV/JSON ledgers.
"""
import argparse
import hashlib
import json
from pathlib import Path

from parser import events,iter_session_text,speaker_index
from wp21_episoden import PAIRS,episode_summary
from wp21_scan import HOST,fetch,safe_parse


def inspect(roots):
    if set(roots)!=set(PAIRS):
        raise ValueError('Es müssen drei amtliche Originalprotokolle vorliegen')
    index=speaker_index(roots.values())
    records=[]
    for session,root in sorted(roots.items()):
        if (root.get('wahlperiode')!='21'
                or int(root.get('sitzung-nr') or 0)!=session):
            raise ValueError('Fremdes oder beschädigtes Sitzungsprotokoll')
        first,mid,last,recipient,relation=PAIRS[session]
        paragraphs={int(p.sourceline):(p,t) for p,t in iter_session_text(root)}
        found={}
        for event in events(Path(f'21{session:03d}.xml'),root=root,index=index):
            found.setdefault(int(event['line']),[]).append(event)
        if first not in paragraphs or last not in paragraphs:
            raise ValueError('Originalzeile der Episode fehlt')
        if first not in found or last not in found:
            raise ValueError('Quellenerteilung nicht personell belegbar')
        first_hits=found[first]
        last_hits=found[last]
        if (len(first_hits)!=1 or len(last_hits)!=1
                or any(x['person']!=recipient or x['status']!='review_required'
                       for x in first_hits+last_hits)):
            raise ValueError('Mehrdeutiger Originalempfänger der Erteilungsstellen')
        expected={
            49:(first,'expliziter_vollname_49_3278_kein_namensprefix',
                last,'fortsetzung_benannter_erteilungsrede_xmlzeile_3278'),
            51:(first,'direkte_anrede',
                last,'neuer_benannter_zwischenruf_xmlzeile_3980'),
            65:(first,'gleiche_erteilungsepisode_spaetere_anrede_xmlzeile_2046',
                last,'anrede_vor_erteilung'),
        }[session]
        if (first_hits[0]['zuordnungsmethode']!=expected[1]
                or last_hits[0]['zuordnungsmethode']!=expected[3]):
            raise ValueError('Quellennachweis oder Empfängermethode verändert')
        if session==49 and any(x['person']=='Thomas Stephan'
                                for x in first_hits+last_hits):
            raise ValueError('False XML recipient Thomas Stephan')
        source_nodes=list(root.iter('kommentar'))
        comment=next((node for node in source_nodes
                      if int(node.sourceline)==mid),None)
        if comment is None:
            raise ValueError('Originaler Zwischenruf/Beifall fehlt')
        excerpt=' '.join(''.join(comment.itertext()).split())
        if len(excerpt)>500:
            raise ValueError('Zu langer nicht begrenzter Quellenkommentar')
        a,b=paragraphs[first][1],paragraphs[last][1]
        entries=[{
            'xml_line':line,
            'original_excerpt':text[:900],
            'sha256':hashlib.sha256(text.encode()).hexdigest(),
            'source_person_review_hint':item[0]['person'],
            'original_identity_evidence':item[0]['zuordnungsmethode'],
            'is_independently_legally_effective_confirmed':False,
        } for line,text,item in (
            (first,a,first_hits),(last,b,last_hits))]
        records.append({
            **episode_summary(session),
            'case_id':f'wp21-{session:03d}-{first}-{last}',
            'original_pdf':f'{HOST}/21{session:03d}.pdf',
            'original_xml':f'{HOST}/21{session:03d}.xml',
            'intervening_comment':{
                'xml_line':mid,
                'original_excerpt':excerpt,
                'sha256':hashlib.sha256(excerpt.encode()).hexdigest(),
            },
            'original_chair_issuance_phrases':entries,
            'distinct_legal_measures':None,
            'requires_independent_individual_legal_outcome':True,
        })
    if len(records)!=3 or any(
            len(item['original_chair_issuance_phrases'])!=2 for item in records):
        raise ValueError('Drei Episoden müssen getrennt bleiben')
    return {
        'status':'source_bound_multi_paragraph_episodes_unverified',
        'wahlperiode':21,
        'protocols':3,
        'episodes':3,
        'source_issuance_phrases':6,
        'distinct_effective_sanctions':None,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'warning':('Zwei ausgesprochene Absätze sind weder automatisch zwei '
                   'Ordnungsrufe noch automatisch eine Maßnahme. '
                   'Neue Zwischenrufe und die späteren Einspruchs- und '
                   'Rechtsfolgenentscheidungen müssen separat geprüft werden.'),
        'cases':records,
    }


def run(cache,output):
    roots={}
    for session in sorted(PAIRS):
        data=fetch(session,Path(cache))
        if data is None:
            raise ValueError(f'Amtliches Original-XML 21/{session:03d} nicht verfügbar')
        roots[session]=safe_parse(data,session)
    report=inspect(roots)
    out=Path(output)
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix(out.suffix+'.tmp')
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',
                   encoding='utf-8')
    tmp.replace(out)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,default=Path('.audit/targeted_xml'))
    p.add_argument('--output',type=Path,default=Path('.audit/wp21_episoden.json'))
    a=p.parse_args()
    result=run(a.cache,a.output)
    print(f"WP21: {result['episodes']} Episoden mit je zwei präsidialen "
          "Originaltextstellen, 3 quellenbelegte Empfänger und "
          "0 automatisch bestätigte wirksame Maßnahmen.")


if __name__=='__main__':
    main()
