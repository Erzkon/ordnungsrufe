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
CHAIR_VOCATIVE_XML_LINES = 17
CHAIR_VOCATIVE_MAX_PARAGRAPHS = 9
SPEAKER_INTRO_XML_LINES = 34
SPEAKER_INTRO_MAX_PARAGRAPHS = 30

# A chair addresses a person by name, but has not yet pronounced the sanction.
# This is distinct from naming somebody merely discussed/insulted:
# 21/057 "Sie können sich gerne aufregen, Herr Baumann."
# 21/061 "Herr von Zons."
# 21/093 "Sehr geehrte Frau Abgeordnete Bessin, für die Formulierung ..."
CHAIR_VOCATIVE = re.compile(
    r'\b(?:Herr|Frau)\s+(?:(?:Kollege|Kollegin|Abgeordnete|Abgeordneter'
    r'|Abgeordneten)\s+)?'
    r'(?P<name>(?:von\s+)?[A-ZÄÖÜ][\wÄÖÜäöüß\-]+)'
    r'\s*(?:,|\.|\s+Sie\b)')
PRONOUN_GRANT = re.compile(
    r'\b(?:erteile\s+ich\s+Ihnen|ich\s+Ihnen\s+einen\s+Ordnungsruf\s+erteilen|'
    r'ich\s+Ihnen\s+einen\s+Ordnungsruf\s+erteile|'
    r'Sie\s+kriegen\s+jetzt\s+von\s+mir|'
    r'bekommen\s+Sie\s+jetzt\s+von\s+mir|'
    r'erhalten\s+Sie\s+jetzt\s+von\s+mir)\b',re.I)
# A different speaking turn or distinct chair interjection can change who
# "Sie" addresses; stop rather than fill in a name.
SPEAKER_INTRO = re.compile(
    r'\b(?:hat\s+jetzt\s+das\s+Wort\s+der\s+Abgeordnete|'
    r'für\s+die\s+Fraktion\s+Die\s+Linke\s+hat\s+jetzt\s+das\s+Wort'
    r'\s+der\s+Abgeordnete|'
    r'Die\s+nächste\s+Rednerin\s+in\s+dieser\s+Debatte\s+ist)\s+',re.I)
QUOTED_REASON = re.compile(r'[„"](?P<reason>[^“"]{4,50})[“"]')


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



def _unique_prior_full_name(surname, index, paragraphs, grant_line):
    """Disambiguate identical surnames ONLY using a unique earlier full name.

    In 21/077 both Martin and Truels Reichardt occur. An unqualified chair
    confirmation naming 'Herr Reichardt' is ambiguous. Require one unique
    earlier full-name introduction, never a later one or random mentioned MP.
    """
    identities=list(index[0].get(surname.casefold(), {}).values())
    if len(identities)<2:
        return None
    found={}
    for element,text in paragraphs:
        line=int(element.sourceline)
        if not 0<grant_line-line<=180:
            continue
        for person in identities:
            full=person['person']
            if re.search(r'(?<!\w)'+re.escape(full)+r'(?!\w)',text,re.I):
                found[full.casefold()]=person
    if len(found)!=1:
        return None
    return {**next(iter(found.values())),'identity_status':'matched_xml_person'}


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
        recap_line=int(element.sourceline)
        nearby=[el for el,_,chair in issued
                if chair==marker and 0<recap_line-int(el.sourceline)<=WINDOW_XML_LINES]
        if len(nearby)!=expected:
            continue
        who=candidate_name(match.group('name'),index)
        if not who or who['identity_status']!='matched_xml_person':
            # With homonymous MPs, use only a unique preceding FULL name.
            who=_unique_prior_full_name(
                match.group('name'),index,paragraphs,min(
                    int(el.sourceline) for el in nearby))
        if not who or who['identity_status']!='matched_xml_person':
            continue
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
    # Direct named chair address (different from matching arbitrary MP
    # mentions), strictly before an unassigned pronoun-only issuance.
    for i,(element,txt) in enumerate(paragraphs):
        line=int(element.sourceline)
        if (line in used or line in assigned
                or classify(txt)!='possible_grant'
                or not PRONOUN_GRANT.search(txt)):
            continue
        marker=_chair(element,issuer_context)
        if not marker:
            continue
        candidate=None
        for previous,previous_text in reversed(
                paragraphs[max(0,i-CHAIR_VOCATIVE_MAX_PARAGRAPHS):i]):
            distance=line-int(previous.sourceline)
            if not 0<distance<=CHAIR_VOCATIVE_XML_LINES:
                break
            if _chair(previous,issuer_context)!=marker:
                break
            if classify(previous_text)=='possible_grant':
                break
            matches=list(CHAIR_VOCATIVE.finditer(previous_text))
            if not matches:
                continue
            # Direct vocative, not quoted text or a committee discussion.
            # When >1 direct address appears, the pronoun has no unique target.
            if len(matches)!=1:
                break
            match=matches[0]
            if ('Sie' not in previous_text and
                    not re.fullmatch(r'\s*[–—-]?\s*(?:Herr|Frau)\s+'
                    r'(?:(?:Abgeordnete|Abgeordneten|Kollege|Kollegin)\s+)?'
                    r'(?:von\s+)?[\wÄÖÜäöüß\-]+\s*[.]\s*',
                    previous_text,re.I)):
                break
            name=candidate_name(match.group('name'),index)
            if name and name['identity_status']=='matched_xml_person':
                candidate=(name,int(previous.sourceline))
            break
        if candidate:
            who,source_line=candidate
            proposals.append((element,_with_method(
                [who],f'vorsitz_direkte_anrede_xmlzeile_{source_line}')[0]))
            used.add(line)

    # 21/071: "Das Wort hat ... Mirze Edis" immediately before the
    # member's own "Faschisten" interruption and a chair response quoting
    # exactly the same specific wording. Both the chair introduction and
    # original interruption must be present, otherwise decline attribution.
    for i,(element,txt) in enumerate(paragraphs):
        line=int(element.sourceline)
        if (line in used or line in assigned
                or classify(txt)!='possible_grant'
                or not PRONOUN_GRANT.search(txt)):
            continue
        marker=_chair(element,issuer_context)
        if not marker:
            continue
        reasons=[m.group('reason').casefold() for m in QUOTED_REASON.finditer(txt)
                 if len(m.group('reason').strip())>=4]
        # The verbatim misconduct in the original 21/067 Gebel grant
        # ("rassistischen Dreck") is not surrounded by quotation marks.
        # Require the same marked phrase in a nearby actual speaker turn;
        # never infer Kathrin Gebel from the insult to her in earlier pages.
        if not reasons and re.search(
                r'\bfür\s+die\s+Bemerkung,\s+der\s+Kanzler\s+würde\s+'
                r'rassistischen\s+Dreck\b',txt,re.I):
            reasons=['rassistischen Dreck']
        if len(reasons)!=1:
            continue
        relevant_before=[
            (before,spoken) for before,spoken in paragraphs[max(0,i-5):i]
            if 0<line-int(before.sourceline)<=18 and
            any(re.search(r'(?<!\w)'+re.escape(reason)+r'(?!\w)',
                          spoken,re.I) for reason in reasons)
            and issuer_context(before)[1]=='speech_marker'
        ]
        if len(relevant_before)!=1:
            continue
        introductions=[]
        for before,spoken in paragraphs[max(0,i-SPEAKER_INTRO_MAX_PARAGRAPHS):i]:
            diff=line-int(before.sourceline)
            if not 0<diff<=SPEAKER_INTRO_XML_LINES:
                continue
            if _chair(before,issuer_context)!=marker:
                continue
            intro=SPEAKER_INTRO.search(spoken)
            if intro:
                person=candidate_name(spoken[intro.end():],index)
                if person and person['identity_status']=='matched_xml_person':
                    introductions.append((int(before.sourceline),person))
        # No competing introductions. A distinct speaking turn without a
        # named introduction may be an interjection: keep this provisional.
        if len(introductions)!=1:
            continue
        source_line,who=introductions[0]
        proposals.append((element,_with_method(
            [who],f'vorsitz_redeeinleitung_und_wortlaut_xmlzeile_{source_line}')[0]))
        used.add(line)
    return proposals
