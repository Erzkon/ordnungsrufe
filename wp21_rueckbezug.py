"""Strict source-linked PERSON review hypotheses across original XML paragraphs.

These are not counted sanctions. A later explicit parliamentary statement can
name a previously unnamed recipient. A direct personal address by the same
chair immediately before "ich erteile Ihnen" can be a review hint. Both need
independent legal/effectiveness review. Never link across different chairs,
unrelated grant lines, unknown identities or inconsistent numbers of grants.
"""
import re

WINDOW_XML_LINES = 110
DIRECT_XML_LINES = 45
DIRECT_MAX_PARAGRAPHS = 14

# Retrospective statements in original sessions 21/077 and 21/094:
# "der Ordnungsruf von mir vorhin an Herrn Reichardt gegangen ist"
# "zwei Ordnungsrufe an Frau Köktürk gegangen sind"
RETRO_SINGLE = re.compile(
    r'\bOrdnungsruf\b[^.!?]{0,90}?\bvorhin\s+an\s+Herrn\s+'
    r'(?P<name>[\wÄÖÜäöüß\-]+)\s+gegangen\s+ist\b', re.I)
RETRO_TWO = re.compile(
    r'\bzwei\s+Ordnungsrufe\s+an\s+Frau\s+'
    r'(?P<name>[\wÄÖÜäöüß\-]+)\s+gegangen\s+sind\b', re.I)
CHAIR = re.compile(r'\b(?:Präsident(?:in)?|Vizepräsident(?:in)?)\b',re.I)
DIRECT_GRANT = re.compile(
    r'\b(?:Deshalb|Dafür)\s+erteile\s+ich\s+Ihnen\b'
    r'[^.!?]{0,105}?\bOrdnungsruf\b',re.I)
# Only a *direct* address, "Herr Sichert, Sie ...", not any name mentioned
# in a speech, and never an arbitrary named victim of misconduct.
DIRECT_ADDRESSEE = re.compile(
    r'\bHerr\s+(?:Kollege\s+)?(?P<name>[A-ZÄÖÜ][\wÄÖÜäöüß\-]+)\s*,\s*Sie\b')


def _chair(element, issuer_context):
    name, kind=issuer_context(element)
    return name if kind == 'chair_marker' and CHAIR.search(name) else None


def infer_source_linked_hints(paragraphs, index, local_lines):
    """Yield (original grant element, identified person), never recap events.

    local_lines: XML line numbers already assigned by strict same-paragraph
    parsing. Source-linked hypotheses are emitted only for unassigned grant
    lines. Provenance is embedded in method, with the corroborating XML line.
    """
    from parser import (classify, issuer_context, candidate_name,
                        persons_for_grant, _with_method)

    if not isinstance(paragraphs, list):
        raise TypeError('Transcript paragraphs must be a stable ordered list')
    if len({int(el.sourceline) for el,_ in paragraphs}) != len(paragraphs):
        raise ValueError('Duplicate XML paragraph source line')
    assigned=set(int(value) for value in local_lines)
    issued=[]
    for element,txt in paragraphs:
        line=int(element.sourceline)
        if line not in assigned and classify(txt)=='possible_grant' and not persons_for_grant(txt,index):
            chair=_chair(element,issuer_context)
            if chair:
                issued.append((element,txt,chair))
    used=set()
    proposals=[]

    # Retrospective named confirmations are NOT issuing events. Link them only
    # when exactly N otherwise anonymous issuance locations of the same
    # presiding chair precede the confirmation within a tightly bounded window.
    for element,txt in paragraphs:
        matches=[]
        for pattern,count in ((RETRO_SINGLE,1),(RETRO_TWO,2)):
            m=pattern.search(txt)
            if m:
                matches.append((m,count))
        if len(matches)!=1:
            continue
        marker=_chair(element,issuer_context)
        if not marker:
            continue
        match,expected=matches[0]
        who=candidate_name(match.group('name'),index)
        if not who or who['identity_status']!='matched_xml_person':
            continue
        recap_line=int(element.sourceline)
        nearby=[el for el,_,chair in issued
                if chair==marker and 0<recap_line-int(el.sourceline)<=WINDOW_XML_LINES]
        # Do not take arbitrary N from a bigger candidate set: that would
        # silently misattribute a different person's grant.
        if len(nearby)!=expected or any(int(el.sourceline) in used for el in nearby):
            continue
        # Reject if there are other named issuance proposals by the same
        # chair within the window, which may make recap scope ambiguous.
        named_recent=[
            int(el.sourceline) for el,text in paragraphs
            if 0<recap_line-int(el.sourceline)<=WINDOW_XML_LINES
            and _chair(el,issuer_context)==marker
            and classify(text)=='possible_grant'
            and int(el.sourceline) in assigned
        ]
        if named_recent:
            continue
        for grant in nearby:
            line=int(grant.sourceline)
            linked=_with_method([who],f'namensbestaetigung_xmlzeile_{recap_line}')[0]
            proposals.append((grant,linked))
            used.add(line)

    # A direct "Herr Sichert, Sie ..." in the same continuous presiding
    # turn directly preceding a pronoun-only "Deshalb erteile ich Ihnen ..."
    # is an *identity review hint*; any intervening speaker/chair change
    # or another grant invalidates it. No recaps or generic surname mentions.
    for i,(element,txt) in enumerate(paragraphs):
        line=int(element.sourceline)
        if line in used or line in assigned or not DIRECT_GRANT.search(txt):
            continue
        marker=_chair(element,issuer_context)
        if not marker or classify(txt)!='possible_grant':
            continue
        found=None
        for prev_el,prev_txt in reversed(paragraphs[max(0,i-DIRECT_MAX_PARAGRAPHS):i]):
            diff=line-int(prev_el.sourceline)
            if diff<=0 or diff>DIRECT_XML_LINES:
                break
            if _chair(prev_el,issuer_context)!=marker:
                break
            if classify(prev_txt)=='possible_grant':
                break
            addresses=list(DIRECT_ADDRESSEE.finditer(prev_txt))
            if not addresses:
                continue
            # Multiple addressees in a paragraph cannot identify which "Sie".
            if len(addresses)!=1:
                break
            who=candidate_name(addresses[0].group('name'),index)
            if who and who['identity_status']=='matched_xml_person':
                found=(who,int(prev_el.sourceline))
            break
        if found:
            who,source_line=found
            proposals.append((element,_with_method(
                [who],f'vorherige_direkte_anrede_xmlzeile_{source_line}')[0]))
            used.add(line)
    return proposals
