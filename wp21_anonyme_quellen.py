#!/usr/bin/env python3
"""Read-only, source-bound dossiers for the 13 remaining high-priority anonymous grants.

Every dossier preserves the original XML grant line and neighboring speaker
turns. A preceding speaker marker, nearby personal name, or repeated phrase
is NOT automatically evidence that this person was sanctioned.
No confirmed sanction, legal outcome, or public counter is ever changed.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from parser import (classify, events, issuer_context, iter_session_text,
                    normal, speaker_index)
from wp21_scan import HOST, fetch, safe_parse

# Reviewed original 100-session source-audit high-priority grant *locations*,
# not verified effective individual sanctions. Retain unresolved sites until
# source-linked person and subsequent legal effect are independently checked.
TARGETS = {
    8: (1419,), 14: (2311,), 23: (2649,), 26: (3436,),
    28: (4468,), 37: (5923,), 39: (4341,),
    43: (2405, 3497),
    46: (4473,), 49: (3280,), 51: (3981,), 65: (2044,),
}
MAX_BEFORE = 9
MAX_AFTER = 5
MAX_TEXT = 650


def speaker_provenance(element):
    """Speaker-marker information, never a recipient attribution."""
    parent=element.getparent()
    if parent is None or parent.tag!='rede':
        return {'speaker_type':'unknown','speaker_id':None,'speaker_name':None}
    for prior in element.itersiblings(preceding=True):
        if prior.tag=='name':
            return {'speaker_type':'named_interjection',
                    'speaker_id':None,'speaker_name':normal(''.join(prior.itertext()))[:100]}
        if prior.tag=='p' and prior.get('klasse')=='redner':
            speakers=prior.xpath('.//redner[@id]')
            if len(speakers)!=1:
                return {'speaker_type':'unknown','speaker_id':None,'speaker_name':None}
            person=speakers[0]
            first=normal(person.findtext('name/vorname',default=''))
            last=normal(person.findtext('name/nachname',default=''))
            return {'speaker_type':'redner_id',
                    'speaker_id':person.get('id'),
                    'speaker_name':(' '.join([first,last])).strip()[:100] or None}
    return {'speaker_type':'unknown','speaker_id':None,'speaker_name':None}


def paragraph_record(element,text):
    chair,kind=issuer_context(element)
    return {
        'line':int(element.sourceline),
        'text':text[:MAX_TEXT],
        'classification':classify(text),
        'issuer_marker':chair[:100],
        'issuer_type':kind,
        'speaker_marker':speaker_provenance(element),
    }


def inspect(root,session,lines):
    if root.get('wahlperiode')!='21' or int(root.get('sitzung-nr') or 0)!=session:
        raise ValueError('Fremdes oder beschädigtes XML-Protokoll')
    paras=list(iter_session_text(root))
    byline={int(node.sourceline):i for i,(node,_) in enumerate(paras)}
    if len(byline)!=len(paras):
        raise ValueError('Doppelte Original-XML-Zeilen')
    index=speaker_index([root])
    linked={}
    for row in events(Path(f'21{session:03d}.xml'),index=index,root=root):
        linked.setdefault(int(row['line']),[]).append(row)
    records=[]
    if len(set(lines))!=len(lines):
        raise ValueError('Doppeltes Prüfziel')
    for line in lines:
        if not isinstance(line,int) or line<1 or line not in byline:
            raise ValueError(f'Angekündigte Originalfundstelle fehlt: 21/{session:03d} L{line}')
        idx=byline[line]
        element,txt=paras[idx]
        if classify(txt)!='possible_grant':
            raise ValueError(f'Erteilungstext nicht mehr als Prüffall erkannt: 21/{session:03d} L{line}')
        if linked.get(line):
            # A source link added by a later parser fix must be explicitly
            # reviewed before this *anonymous* legacy queue is updated.
            raise ValueError(f'Anonyme Fundstelle schon einer Person zugeordnet: 21/{session:03d} L{line}')
        near_before=paras[max(0,idx-MAX_BEFORE):idx]
        near_after=paras[idx+1:idx+1+MAX_AFTER]
        grant=paragraph_record(element,txt)
        if grant['issuer_type']!='chair_marker':
            raise ValueError(f'Ohne präsidialen XML-Quellenbezug: 21/{session:03d} L{line}')
        record={
            'case_id':f'xml-{session:03d}-L{line}',
            'session':session, 'xml_line':line,
            'original_pdf':f'{HOST}/21{session:03d}.pdf',
            'original_xml':f'{HOST}/21{session:03d}.xml',
            'text_sha256':hashlib.sha256(txt.encode('utf-8')).hexdigest(),
            'original_grant':grant,
            'previous_paragraphs':[paragraph_record(e,t) for e,t in near_before],
            'following_paragraphs':[paragraph_record(e,t) for e,t in near_after],
            'other_anonymous_grant_lines_nearby':sorted(
                other for other in lines if other!=line and abs(other-line)<=50),
            'needs_manual_recipient_review':True,
            'needs_manual_separate_grant_and_appeal_review':True,
            'recipient_automatically_identified':False,
            'legally_effective_sanction_automatically_confirmed':False,
        }
        records.append(record)
    return records


def collect(folder,targets=TARGETS):
    if len(targets)!=12 or sum(len(x) for x in targets.values())!=13:
        raise ValueError('Prüfstichprobe verändert: Neuprüfung erforderlich')
    output=[]
    for session,lines in sorted(targets.items()):
        if type(session)!=int or not 1<=session<=450:
            raise ValueError('Ungültige Sitzung')
        data=fetch(session,Path(folder))
        if data is None:
            raise ValueError(f'Amtliches XML 21/{session:03d} nicht verfügbar')
        root=safe_parse(data,session)
        section=inspect(root,session,lines)
        output.extend(section)
        print(f'QUELLENKONTEXT {session:03d}: '+', '.join(
              f'L{x["xml_line"]}={x["original_grant"]["text"][:140]!r}'
              for x in section),flush=True)
    if len(output)!=13 or len({x['case_id'] for x in output})!=13:
        raise ValueError('Original-XML-Prüfziele unvollständig')
    return {
        'status':'nur_anonyme_original_xml_pruefhinweise',
        'wahlperiode':21,
        'protocols_examined':len(targets),
        'anonymous_review_cases':len(output),
        'auto_confirmed_sanctions':0,
        'auto_identified_recipients':0,
        'warning':('Vorherige Redner-IDs, nachfolgende Äußerungen und '
                   'Protokolltext ohne gesonderte rechtliche Prüfung '
                   'sind keine wirksamen Ordnungsrufe oder sichere Empfänger.'),
        'cases':output,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,default=Path('.audit/anonymous_xml'))
    p.add_argument('--output',type=Path,default=Path('.audit/anonymous_context.json'))
    args=p.parse_args()
    obj=collect(args.cache)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    dest=args.output
    temp=dest.with_suffix(dest.suffix+'.tmp')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(dest)
    print(f'QUELLENKONTEXT_OK {obj["anonymous_review_cases"]} '
          'anonyme Fundstellen, 0 bestätigte Maßnahmen, 0 '
          'automatisch zugeschriebene Personen.',flush=True)


if __name__=='__main__':
    main()
