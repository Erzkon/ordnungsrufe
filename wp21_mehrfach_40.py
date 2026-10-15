#!/usr/bin/env python3
"""Read-only original-XML evidence dossier for two distinct WP21/040 pairs.

Four issuing *paragraphs*, involving exactly TWO different MPs; both
appear to receive a first and a separate explicitly labelled second grant.
No legal-effect determination: appeal proceedings and later reversals must
be examined separately, and no sanctioned-counter file is read or written.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from parser import classify,events,iter_session_text,speaker_index
from wp21_anonyme_quellen import paragraph_record
from wp21_scan import HOST,fetch,safe_parse

# Exact original official XML locations; changing a line is a source change
# requiring independent re-evaluation, never a silent automatic fallback.
OFFICIAL={
    'Martin Sichert':{
        'person_id':'11004892', 'first':8715,'second':8719,
        'first_phrase':'mit dem Finger auf Kollegen gezeigt',
        'second_phrase':'für den Widerspruch gerade',
    },
    'Kay Gottschalk':{
        'person_id':'11004731','first':8990,'second':8992,
        'first_phrase':'für die Verwendung des Wortes',
        'second_phrase':'Gleichsetzung mit dem Nationalsozialismus',
    },
}
WARNING_LINE=8717
MAX_TEXT=650


def inspect(root,expected=OFFICIAL,warning_line=WARNING_LINE):
    """Fail closed on line, speaker, attribution, warning and ordinal drift."""
    if (root.get('wahlperiode')!='21' or root.get('sitzung-nr') not in ('40','040')):
        raise ValueError('Fremdes oder beschädigtes Originalprotokoll')
    if len(expected)!=2 or len({r['person_id'] for r in expected.values()})!=2:
        raise ValueError('Nicht genau zwei unabhängige Abgeordnete')
    p=list(iter_session_text(root))
    by_line={int(node.sourceline):(node,txt) for node,txt in p}
    if len(by_line)!=len(p):
        raise ValueError('Original-XML-Quellzeilen nicht eindeutig')
    persons=speaker_index([root])
    linked={}
    for row in events(Path('21040.xml'),root=root,index=persons):
        linked.setdefault(int(row['line']),[]).append(row)
    warnings=by_line.get(warning_line)
    if (not warnings or classify(warnings[1])!='warning_or_conditional'
            or linked.get(warning_line)
            or not re.search(r'\bwenn\s+Sie\s+lachen\b',warnings[1],re.I)):
        raise ValueError('Bedingte Lachandrohung wird irrtümlich als Maßnahme behandelt')
    pairlist=[]
    seen=set()
    for name,reference in expected.items():
        first=reference['first'];second=reference['second']
        if (not isinstance(first,int) or not isinstance(second,int)
                or not first<second or second-first>12
                or first in seen or second in seen):
            raise ValueError('Erst-/Zweiterteilung ungültig, doppelt oder zu weit entfernt')
        seen.update((first,second))
        if first not in by_line or second not in by_line:
            raise ValueError(f'Originalfundstelle für {name} fehlt')
        one,one_txt=by_line[first]
        two,two_txt=by_line[second]
        if (classify(one_txt)!='possible_grant'
                or classify(two_txt)!='possible_grant'
                or not re.search(r'\beinen\s+Ordnungsruf\b',one_txt,re.I)
                or re.search(r'\beinen\s+zweiten\s+Ordnungsruf\b',one_txt,re.I)
                or not re.search(r'\beinen\s+zweiten\s+Ordnungsruf\b',two_txt,re.I)
                or reference['first_phrase'].casefold() not in one_txt.casefold()
                or reference['second_phrase'].casefold() not in two_txt.casefold()
                or one.getparent() is not two.getparent()):
            raise ValueError(f'Originaltext keine sichere getrennte Zweierfolge: {name}')
        a=linked.get(first,[]);b=linked.get(second,[])
        if (len(a)!=1 or len(b)!=1
                or any(event['person']!=name
                       or event['person_id']!=reference['person_id']
                       or event['identity_status']!='matched_xml_person'
                       or event['status']!='review_required'
                       for event in a+b)
                or a[0]['issuer']!=b[0]['issuer']
                or a[0]['issuer_evidence']!='chair_marker'
                or b[0]['issuer_evidence']!='chair_marker'):
            raise ValueError(f'XML-Sprecher nicht eindeutig oder Erteilung doppelt: {name}')
        pairlist.append({
            'recipient_review_hint':name,
            'xml_person_id':reference['person_id'],
            'presiding_chair':a[0]['issuer'],
            'first':{
                'source':paragraph_record(one,one_txt),
                'sha256':hashlib.sha256(one_txt.encode()).hexdigest(),
                'method':a[0]['zuordnungsmethode'],
                'ordinal_from_original':'erste_erteilungsformulierung',
            },
            'second':{
                'source':paragraph_record(two,two_txt),
                'sha256':hashlib.sha256(two_txt.encode()).hexdigest(),
                'method':b[0]['zuordnungsmethode'],
                'ordinal_from_original':'ausdruecklich_zweite_erteilung',
            },
            'two_distinct_original_xml_lines':True,
            'separate_event_and_legal_effect_review_required':True,
        })
    if len(seen)!=4:
        raise ValueError('Vier originalen Erteilungsstellen nicht eindeutig')
    return {
        'status':'source_linked_pairs_unverified_legal_effect',
        'wahlperiode':21,'sitzung':40,
        'protocol_pdf':f'{HOST}/21040.pdf',
        'protocol_xml':f'{HOST}/21040.xml',
        'paired_speaker_references':2,
        'original_issuing_passages':4,
        'conditional_warning_not_issued':{
            'xml_line':warning_line,
            'source_text_sha256':hashlib.sha256(warnings[1].encode()).hexdigest(),
        },
        'pairs':pairlist,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'warning':('Vier getrennte Original-Erteilungsformulierungen für zwei '
                   'Abgeordnete sind keine rechtliche Schlussprüfung. '
                   'Ohne dokumentierte individuelle Rechtswirkung und '
                   'mögliche Einspruchs-/Rücknahmefolgen keine Zähleränderung.'),
    }


def run(cache,output):
    from pathlib import Path
    data=fetch(40,Path(cache))
    if data is None:
        raise ValueError('Amtliches Original-XML 21/040 nicht verfügbar')
    report=inspect(safe_parse(data,40))
    out=Path(output)
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix(out.suffix+'.tmp')
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',
                   encoding='utf-8')
    tmp.replace(out)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache',type=Path,default=Path('.audit/targeted_xml'))
    ap.add_argument('--output',type=Path,default=Path('.audit/wp21_040_pairs.json'))
    a=ap.parse_args()
    report=run(a.cache,a.output)
    print(f"Original-XML 21/040: {report['original_issuing_passages']} "
          f"einzeln lokalisierte Erteilungsformulierungen für "
          f"{report['paired_speaker_references']} Personenzuordnungen; "
          "0 automatisch bestätigte wirksame Maßnahmen.")


if __name__=='__main__':
    main()
