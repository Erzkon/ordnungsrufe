"""Narrow original-WP21 recipient hints from direct utterance evidence.

These exact-scoped three source patterns are NOT legal determinations.
21/014: Martin Reichardt's personally signed "Schwätzer!" interjection.
21/037: Ates Gürpinar's own original words before a direct rebuke.
21/039: Dr. Anna Rathert's actual question and "Lügen" allegation.

No general 'previous redner = sanctioned recipient' rule: the Janich
interjection in 21/040 proves that heuristic is unsafe. Speaker IDs,
strict original offence text, chair, turn proximity and session MUST agree.
"""
import re

from wp21_rueckbezug import _identity_from_xml_speech

CONTEXT = {
    37: {
        'person':'Ates Gürpinar',
        'grant':r'\bHerr\s+Kollege,\s+ich\s+erteile\s+Ihnen\s+hiermit\s+'
                r'einen\s+Ordnungsruf\s+für\s+die\s+Verwendung\s+'
                r'[„"]braunes\s+Gelaber[“"]',
        'offence':r'\bbraunes\s+Zeug\s+zu\s+labern\b',
        'max_lines':15,
    },
    39: {
        'person':'Anna Rathert',
        'grant':r'\bFrau\s+Kollegin,\s+kommen\s+Sie\s+jetzt\s+bitte\s+'
                r'zu\s+Ihrer\s+Frage\.\s*[–—-]\s*Im\s+Übrigen\s+'
                r'erteile\s+ich\s+Ihnen\s+einen\s+Ordnungsruf\s+'
                r'dafür,\s+dass\s+Sie\s+den\s+Kollegen\s+der\s+'
                r'Lüge\s+bezichtigen',
        'offence':r'\bLügen\s+über\s+uns\s+auskippen\b',
        'max_lines':19,
    },
}
CHAIR='Vizepräsidentin Andrea Lindholz'


def source_recipient_links(paragraphs,index,excluded):
    """Return unconfirmed (original grant element, recipient hint) pairs.

    A refusal to attach is preferable to inferring a named recipient from
    the entire enclosing MP speech; the exact linked XML <redner> is
    required, and a different speaker's insult is not borrowed.
    """
    from parser import (candidate_name,classify,issuer_context,_with_method)
    if not paragraphs:
        return []
    root=paragraphs[0][0].getroottree().getroot()
    if root.get('wahlperiode')!='21':
        return []
    try:
        session=int(root.get('sitzung-nr') or '')
    except ValueError:
        return []
    output=[]
    if session==14:
        for i,(grant,txt) in enumerate(paragraphs):
            line=int(grant.sourceline)
            if line in excluded or classify(txt)!='possible_grant':
                continue
            marker,kind=issuer_context(grant)
            if (kind!='chair_marker' or marker!=CHAIR or
                    not re.search(r'\bHerr\s+Kollege,\s+dann\s+muss\s+ich\s+'
                      r'Ihnen\s+leider\s+einen\s+Ordnungsruf\s+'
                      r'erteilen\s+dafür,\s+dass\s+Sie\s+die\s+'
                      r'Rednerin\s+als\s+[„"]Schwätzer[“"]'
                      r'\s+bezeichnet\s+haben',txt,re.I)):
                continue
            previous=grant.getprevious()
            if previous is None or previous.tag!='kommentar':
                continue
            comment=' '.join(''.join(previous.itertext()).split())
            if (previous.getparent() is not grant.getparent() or
                int(grant.sourceline)-int(previous.sourceline)>3 or
                not re.fullmatch(r'\(Martin\s+Reichardt\s+\[AfD\]:'
                                 r'\s*Schwätzer!\)',comment,re.I)):
                continue
            who=candidate_name('Martin Reichardt',index)
            if not who or who['identity_status']!='matched_xml_person':
                continue
            # The real speaker of the intervening short intervention
            # must independently bear the same XML person ID.
            speakers=[
                (_identity_from_xml_speech(el,index),el)
                for el,_ in paragraphs[max(0,i-9):i]
                if 0<line-int(el.sourceline)<=17
                   and issuer_context(el)[1]=='speech_marker'
            ]
            if (not speakers or
                    not any(p and p['person_id']==who['person_id']
                            for p,_ in speakers)
                    or any(p and p['person_id']!=who['person_id']
                           for p,_ in speakers)):
                continue
            output.append((grant,_with_method(
                [who],f'namenszwischenruf_schwaetzer_xmlzeile_{int(previous.sourceline)}')[0]))
        return output
    spec=CONTEXT.get(session)
    if spec is None:
        return output
    for i,(grant,txt) in enumerate(paragraphs):
        line=int(grant.sourceline)
        if (line in excluded or classify(txt)!='possible_grant'
                or not re.search(spec['grant'],txt,re.I)):
            continue
        marker,kind=issuer_context(grant)
        if kind!='chair_marker' or marker!=CHAIR:
            continue
        # A completed *own* MP speech in a distinct <rede> must directly
        # precede the president's named direct reply. Prevent long-range
        # random heckler names from being treated as recipient evidence.
        possible=[
            (p,t) for p,t in paragraphs[max(0,i-12):i]
            if 0<line-int(p.sourceline)<=spec['max_lines']
               and issuer_context(p)[1]=='speech_marker'
        ]
        if not possible:
            continue
        previous,previous_text=possible[-1]
        if (grant.getparent() is previous.getparent()
                or not 0<line-int(previous.sourceline)<=5):
            continue
        unique={}
        for p,t in possible:
            person=_identity_from_xml_speech(p,index)
            if person and person['person_id']:
                unique[person['person_id']]=person
        if len(unique)!=1:
            continue
        who=next(iter(unique.values()))
        if who['person'].casefold()!=spec['person'].casefold():
            continue
        offence=[(p,t) for p,t in possible
                 if re.search(spec['offence'],t,re.I)
                 and (_identity_from_xml_speech(p,index) or {}).get(
                     'person_id')==who['person_id']]
        if len(offence)!=1:
            continue
        # No new speaker turns are permitted after the last linked MP
        # speech and before this chair rebuke.
        if any(issuer_context(p)[1]=='speech_marker'
               for p,t in paragraphs[paragraphs.index((previous,previous_text))+1:i]):
            continue
        output.append((grant,_with_method(
            [who],f'wortgleiche_rede_und_anrede_xmlzeile_{int(offence[0][0].sourceline)}')[0]))
    return output
