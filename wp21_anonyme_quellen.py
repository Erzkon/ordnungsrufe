#!/usr/bin/env python3
"""Read-only source dossiers for four previously anonymous original-XML grants.

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
    8: (1419,), 23: (2649,),
    28: (4468,),
    46: (4473,),
}
# Checked against the four original Bundestag XML grant paragraphs on 2026-10-16.
# These are TEXT anchors only. They do not identify recipients or legal effects.
ORIGINAL_ANCHORS = {
    (8, 1419): 'Ich erteile Ihnen dafür einen Ordnungsruf.',
    (23, 2649): 'Sie bekommen jetzt von mir einen Ordnungsruf',
    (28, 4468): 'Dafür erteile ich jetzt auch einen Ordnungsruf.',
    (46, 4473): 'für dieses „Warum nicht?“ von mir einen Ordnungsruf.',
}

MAX_BEFORE = 9
MAX_AFTER = 5
MAX_TEXT = 650
COMMENT_WINDOW_BEFORE = 32
COMMENT_WINDOW_AFTER = 9
MAX_COMMENTS = 24


def validate_original_anchor(session, line, text):
    """Fail closed on changed original wording instead of reusing stale labels."""
    expected = ORIGINAL_ANCHORS.get((session, line))
    if expected is None:
        raise ValueError(f'Nicht geprüfter Quellenanker: 21/{session:03d} L{line}')
    if normal(expected).casefold() not in normal(text).casefold():
        raise ValueError(f'Originalwortlaut/Quellenanker verändert: 21/{session:03d} L{line}')


def speaker_provenance(element):
    """Speaker-marker information, never a recipient attribution."""
    parent=element.getparent()
    if parent is None or parent.tag!='rede':
        return {'speaker_type':'unknown','speaker_id':None,'speaker_name':None}
    for prior in element.itersiblings(preceding=True):
        if prior.tag=='name':
            name=normal(''.join(prior.itertext())).rstrip(':')
            # A presidium marker is the SOURCE of the sanction wording,
            # not a named interjection and never evidence of its recipient.
            if re.search(r'\b(?:Präsident(?:in)?|Vizepräsident(?:in)?)\b',name,re.I):
                return {'speaker_type':'presiding_chair',
                        'speaker_id':None,'speaker_name':None}
            return {'speaker_type':'named_interjection',
                    'speaker_id':None,'speaker_name':name[:100]}
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


def nearby_original_reactions(root, line, grant):
    """Source-line-limited original XML reactions; NEVER recipient assertions.

    Comments may be outside the grant's <rede> (e.g. final lines of
    a previous speech). Neither a name in a comment nor adjacency alone
    proves who received a legal measure.
    """
    result=[]
    used=set()
    course=root.find('sitzungsverlauf')
    if course is None:
        raise ValueError('Sitzungsverlauf für Kontext nicht verfügbar')
    for node in course.iter('kommentar'):
        at=int(node.sourceline or 0)
        if line-COMMENT_WINDOW_BEFORE<=at<=line+COMMENT_WINDOW_AFTER:
            if at in used:
                raise ValueError('Kontextkommentar ohne eindeutige Originalzeile')
            used.add(at)
            txt=normal(''.join(node.itertext()))
            if not txt or len(txt)>3000:
                raise ValueError('Originalreaktion leer oder zu lang')
            result.append({
                'xml_line':at,
                'original_text':txt[:MAX_TEXT],
                'text_sha256':hashlib.sha256(txt.encode('utf-8')).hexdigest(),
                'same_xml_rede_as_grant':node.getparent() is grant.getparent(),
                'recipient_proved':False,
            })
    if len(result)>MAX_COMMENTS:
        raise ValueError('Kontextfenster mit zu vielen Originalreaktionen')
    return sorted(result,key=lambda item:item['xml_line'])


def inspect(root,session,lines,require_original_anchors=False):
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
        source_hint=None
        if require_original_anchors:
            from wp21_vier_quellenbelege import SOURCES
            expected_person=SOURCES[session][2]
            matches=linked.get(line,[])
            if (len(matches)!=1 or matches[0]['person']!=expected_person
                    or matches[0]['status']!='review_required'
                    or not matches[0]['zuordnungsmethode'].startswith(
                        ('original_karte_rednerid_xmlzeile_',
                         'original_kommentar_name_xmlzeile_'))):
                raise ValueError(f'Original-XML-Personenbeleg nicht eindeutig: 21/{session:03d} L{line}')
            event=matches[0]
            source_hint={
                'person_for_review':event['person'],
                'identity_status':event['identity_status'],
                'original_xml_person_id_if_known':event['person_id'],
                'source_method':event['zuordnungsmethode'],
                'status':'review_required',
                'legally_effective_confirmed':False,
            }
        elif linked.get(line):
            raise ValueError(f'Anonyme Fundstelle schon einer Person zugeordnet: 21/{session:03d} L{line}')
        near_before=paras[max(0,idx-MAX_BEFORE):idx]
        near_after=paras[idx+1:idx+1+MAX_AFTER]
        if require_original_anchors:
            validate_original_anchor(session,line,txt)
        grant=paragraph_record(element,txt)
        if grant['issuer_type']!='chair_marker':
            raise ValueError(f'Ohne präsidialen XML-Quellenbezug: 21/{session:03d} L{line}')
        record={
            'case_id':f'xml-{session:03d}-L{line}',
            'session':session, 'xml_line':line,
            'original_pdf':f'{HOST}/21{session:03d}.pdf',
            'original_xml':f'{HOST}/21{session:03d}.xml',
            'text_sha256':hashlib.sha256(txt.encode('utf-8')).hexdigest(),
            'original_wording_anchor_checked':bool(require_original_anchors),
            'original_grant':grant,
            'source_linked_recipient_review_hint':source_hint,
            'nearby_original_xml_reactions':nearby_original_reactions(root,line,element),
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
    if len(targets)!=4 or sum(len(x) for x in targets.values())!=4:
        raise ValueError('Prüfstichprobe verändert: Neuprüfung erforderlich')
    expected={(session,line) for session,lines in targets.items() for line in lines}
    if set(ORIGINAL_ANCHORS)!=expected:
        raise ValueError('Quellenanker und vier Prüffundstellen stimmen nicht überein')
    output=[]
    for session,lines in sorted(targets.items()):
        if type(session)!=int or not 1<=session<=450:
            raise ValueError('Ungültige Sitzung')
        data=fetch(session,Path(folder))
        if data is None:
            raise ValueError(f'Amtliches XML 21/{session:03d} nicht verfügbar')
        root=safe_parse(data,session)
        section=inspect(root,session,lines,require_original_anchors=True)
        output.extend(section)
        print(f'QUELLENKONTEXT {session:03d}: '+', '.join(
              f'L{x["xml_line"]}={x["original_grant"]["text"][:140]!r}'
              for x in section),flush=True)
        for case in section:
            relevant=[x for x in case['nearby_original_xml_reactions']
                      if 0<case['xml_line']-x['xml_line']<=12]
            for item in relevant[-4:]:
                print(f"QUELLENREAKTION {session:03d} "
                      f"L{item['xml_line']} zu L{case['xml_line']}: "
                      f"{item['original_text'][:210]!r} "
                      f"(gleiche Rede={item['same_xml_rede_as_grant']})",
                      flush=True)
    if len(output)!=4 or len({x['case_id'] for x in output})!=4:
        raise ValueError('Original-XML-Prüfziele unvollständig')
    return {
        'status':'historisch_anonyme_originalstellen_mit_personen_pruefhinweisen',
        'wahlperiode':21,
        'protocols_examined':len(targets),
        'anonymous_review_cases':len(output),
        'source_linked_recipient_review_hints':sum(
            bool(x['source_linked_recipient_review_hint']) for x in output),
        'still_unattributed_original_locations':sum(
            not x['source_linked_recipient_review_hint'] for x in output),
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
          'zuvor anonyme Fundstellen, '
          f'{obj["source_linked_recipient_review_hints"]} '
          'unbestätigte Empfängerhinweise, 0 bestätigte Maßnahmen.',flush=True)


if __name__=='__main__':
    main()
