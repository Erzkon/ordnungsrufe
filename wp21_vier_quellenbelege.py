#!/usr/bin/env python3
"""Four original XML recipient clues; never automatically verified sanctions.

An independent source-evidence layer, intentionally separate from parser
identity and from the four protected public counter CSV/JSON files.
Only exact, pre-reviewed Bundestag original locations and comments qualify.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from parser import classify, issuer_context, iter_session_text, normal, speaker_index
from wp21_rueckbezug import _identity_from_xml_speech
from wp21_scan import fetch, safe_parse, HOST

# Session: grant XML line, evidence comment line, reviewed named candidate,
# actual presiding speaker, grant substring, exact comment name/conduct regex.
SOURCES={
    8:(1419,1415,'Carolin Bachmann','Vizepräsident Omid Nouripour',
       'Ich erteile Ihnen dafür einen Ordnungsruf.',
       r'^\(Die\s+Rednerin\s+hält\s+eine\s+Plastikkarte\s+hoch\)$'),
    23:(2649,2648,'Carolin Bachmann','Vizepräsidentin Andrea Lindholz',
        'Sie bekommen jetzt von mir einen Ordnungsruf dafür, dass Sie die Sitzungsleitung kritisiert haben',
        r'Carolin\s+Bachmann\s+\[AfD\]:\s*Hätte\s+das\s+nicht\s+warten\s+können\s+bis\s+zum\s+Ende\s+der\s+Debatte\?'),
    28:(4468,4466,'René Bochmann','Vizepräsidentin Andrea Lindholz',
        'Nein, das haben nicht Sie zu entscheiden. Dafür erteile ich jetzt auch einen Ordnungsruf.',
        r'René\s+Bochmann\s+\[AfD\],\s+an\s+die\s+Abg\.\s+Nicole\s+Gohlke\s+\[Die\s+Linke\]\s+gewandt:\s*Ich\s+würde\s+jetzt\s+sitzen\s+bleiben\s+und\s+schweigen!'),
    46:(4473,4472,'Mirze Edis','Vizepräsidentin Andrea Lindholz',
        'Sie bekommen jetzt für dieses „Warum nicht?“ von mir einen Ordnungsruf.',
        r'Mirze\s+Edis\s+\[Die\s+Linke\]:\s*Warum\s+nicht\?'),
}


def verify_original(root,session):
    """Fail closed: changed line/wording, missing remark, chair or identity."""
    if root.get('wahlperiode')!='21' or int(root.get('sitzung-nr') or 0)!=session:
        raise ValueError('Falsches Originalprotokoll')
    line,prior,name,chair,grant_anchor,comment_pattern=SOURCES[session]
    paras=[(el,t) for el,t in iter_session_text(root) if el.sourceline==line]
    if len(paras)!=1:
        raise ValueError('Originale Erteilungszeile fehlt oder doppelt')
    grant,text=paras[0]
    if (classify(text)!='possible_grant'
            or normal(grant_anchor).casefold() not in normal(text).casefold()
            or issuer_context(grant)!=(chair,'chair_marker')):
        raise ValueError('Originale Erteilung oder Vorsitz nicht bestätigt')
    comments=[el for el in grant.itersiblings(preceding=True)
              if el.tag=='kommentar' and el.sourceline==prior
              and el.getparent() is grant.getparent()]
    if len(comments)!=1 or not 0<line-prior<=6:
        raise ValueError('Unmittelbarer Originalkommentar fehlt')
    comment=comments[0]
    remark=normal(''.join(comment.itertext()))
    if not re.search(comment_pattern,remark,re.I):
        raise ValueError('Namentlicher Zwischenruf oder Kartenbeleg verändert')
    for node in comment.itersiblings():
        if node is grant:
            break
        if node.tag=='p' and node.get('klasse')=='redner':
            raise ValueError('Anderer Redner vor dem Ordnungsruf')
        if node.tag=='name' and normal(''.join(node.itertext())).rstrip(':')!=chair:
            raise ValueError('Andere Sitzungsleitung dazwischen')
    else:
        raise ValueError('Kommentar und Erteilung nicht im selben Redeblock')
    identity='explicit_named_original_xml_comment_without_redner_id'
    xml_id=''
    if session==8:
        who=_identity_from_xml_speech(grant,speaker_index([root]))
        if (not who or who['person']!=name or not who.get('person_id')
                or who['identity_status']!='matched_xml_person'):
            raise ValueError('Hochgehaltene Karte nicht derselben Rednerin zuordenbar')
        identity='original_same_speech_redner_id_and_card_action'
        xml_id=who['person_id']
    return {
        'case_id':f'21-{session:03d}-L{line}',
        'session':session,'grant_xml_line':line,'evidence_xml_line':prior,
        'person_for_manual_review':name,
        'person_xml_id_when_originally_verified':xml_id,
        'source_attribution_method':identity,
        'original_comment_excerpt':remark[:650],
        'original_comment_sha256':hashlib.sha256(remark.encode()).hexdigest(),
        'original_grant_excerpt':text[:650],
        'original_grant_sha256':hashlib.sha256(text.encode()).hexdigest(),
        'original_pdf':f'{HOST}/21{session:03d}.pdf',
        'original_xml':f'{HOST}/21{session:03d}.xml',
        'individual_effective_sanction_confirmed':False,
        'individual_appeal_and_rescission_review_required':True,
        'recipient_review_only':True,
    }


def parser_recipient_review_links(paragraphs,index,excluded):
    """Source-proven PERSON review hints only; no verified legal measures.

    The parser reuses the strict source validator instead of inferring
    identities from adjacent paragraphs. Drift yields no hint, while
    official-XML regressions separately surface a source change.
    """
    from parser import candidate_name, _with_method
    if not paragraphs:
        return []
    root=paragraphs[0][0].getroottree().getroot()
    if root.get('wahlperiode')!='21':
        return []
    try:
        session=int(root.get('sitzung-nr') or 0)
    except (TypeError,ValueError):
        return []
    if session not in SOURCES:
        return []
    line,comment_line,name,_,_,_=SOURCES[session]
    if line in excluded:
        return []
    try:
        evidence=verify_original(root,session)
    except (ValueError,KeyError):
        return []
    if evidence['person_for_manual_review']!=name:
        return []
    grants=[el for el,txt in paragraphs if el.sourceline==line]
    if len(grants)!=1:
        return []
    grant=grants[0]
    if session==8:
        person=_identity_from_xml_speech(grant,index)
        if (not person or person['person']!=name
                or not person.get('person_id')
                or person['person_id']!=
                   evidence['person_xml_id_when_originally_verified']
                or person['identity_status']!='matched_xml_person'):
            return []
        method='original_karte_rednerid_xmlzeile_'
    else:
        person=candidate_name(name,index)
        if (not person or person['person'].casefold()!=name.casefold()
                or person['identity_status']!='matched_xml_person'):
            # Never invent an XML speaker ID for a named heckler.
            person={'person':name,'person_id':'','fraktion':'',
                    'identity_status':'named_official_source_reference'}
        method='original_kommentar_name_xmlzeile_'
    return [(grant,_with_method([person],method+str(comment_line))[0])]


def collect(cache):
    if len(SOURCES)!=4:
        raise ValueError('Die vier festen Originalziele wurden verändert')
    cases=[]
    for session in sorted(SOURCES):
        data=fetch(session,Path(cache))
        if data is None:
            raise ValueError(f'Amtliches XML 21/{session:03d} fehlt')
        cases.append(verify_original(safe_parse(data,session),session))
    if len({c['case_id'] for c in cases})!=4:
        raise ValueError('Doppelte Originalfälle')
    return {
        'status':'four_source_bound_recipient_review_hints_only',
        'wahlperiode':21,
        'previously_anonymous_source_locations':4,
        'unverified_person_source_hints':4,
        'independently_legally_effective_sanctions_confirmed':0,
        'automatically_changed_public_counts':0,
        'warning':'Original-XML-Personenhinweise sind keine individuell geprüften wirksamen Maßnahmen oder endgültigen Einspruchsentscheidungen.',
        'cases':cases,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,default=Path('.audit/anonymous_xml'))
    p.add_argument('--output',type=Path,default=Path('.audit/four_source_recipient_hints.json'))
    args=p.parse_args()
    result=collect(args.cache)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    tmp=args.output.with_suffix(args.output.suffix+'.tmp')
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(args.output)
    print('VIER_QUELLENBELEGE_OK: 4 unbestätigte Empfängerhinweise aus vier Original-XMLs; '
          '0 automatisch bestätigte oder aufgehobene Maßnahmen.',flush=True)


if __name__=='__main__':
    main()
