"""Three bounded WP21 chair episodes: source recipients, NOT legal counts.

An original XML <p> is not necessarily a distinct legally effective
Ordnungsruf. 49/3278+3280, 51/3979+3981 and 65/2044+2046 must be read
as three pairs of original spoken paragraphs. This module links a recipient
for review only and leaves the number of individual effective measures
undecided. No main data, partial ledger or public counter is written.

Critical 49/3278 parser error: literal "Abgeordneten Stephan Brandner"
was incorrectly interpreted as surname "Stephan" and assigned XML speaker
Thomas Stephan. For this *specific direct-recipient clause*, prefer the
explicit full name; if absent from speaker XML, preserve an official-text
name WITHOUT a fabricated XML person ID.
"""
import re

CHAIRS={
    49:'Vizepräsident Omid Nouripour',
    51:'Vizepräsidentin Andrea Lindholz',
    65:'Präsidentin Julia Klöckner',
}
PAIRS={
    49:(3278,3279,3280,'Stephan Brandner',
        'same_issuance_continuation_possible'),
    51:(3979,3980,3981,'Markus Frohnmaier',
        'additional_issuance_requires_individual_legal_review'),
    65:(2044,2045,2046,'Martin Reichardt',
        'same_issuance_repetition_possible'),
}


def _indexed_or_original_person(fullname,index):
    """Use exact full-name XML identity or source name without invented ID."""
    candidates=index[1].get(fullname.casefold(),{})
    if len(candidates)==1:
        return {**next(iter(candidates.values())),
                'identity_status':'matched_xml_person'}
    if candidates:
        return None
    return {
        'person':fullname,'person_id':'','fraktion':'',
        'identity_status':'named_official_source_reference',
    }


def corrected_explicit_brandner(root,element,text,index,issuer_context):
    """Return replacement people only for the fully quoted official direct grant.

    None means no special handling. When the named original wording
    drifts, independent source regression MUST fail rather than guessing
    a different XML 'Stephan' as the victim.
    """
    if (root.get('wahlperiode')!='21'
            or int(root.get('sitzung-nr') or 0)!=49
            or int(element.sourceline)!=3278):
        return None
    chair,kind=issuer_context(element)
    if kind!='chair_marker' or chair!=CHAIRS[49]:
        return None
    if (not re.search(r'\bmöchte\s+ich\s+dem\s+Abgeordneten\s+'
                      r'Stephan\s+Brandner\s+von\s+der\s+AfD\s+'
                      r'einen\s+Ordnungsruf\s+erteilen\b',text,re.I)
            or not re.search(r'für\s+den\s+Zwischenruf\s+„Heul\s+doch!“',text,re.I)):
        return None
    person=_indexed_or_original_person('Stephan Brandner',index)
    if not person:
        return None
    return [{**person,
             'zuordnungsmethode':'expliziter_vollname_49_3278_kein_namensprefix'}]


def _same_chair(element,chair,issuer_context):
    who,kind=issuer_context(element)
    return kind=='chair_marker' and who==chair


def episode_recipient_hints(paragraphs,index,excluded):
    """Link only original 49/3280, 51/3981, 65/2044 to a person for review.

    Require two original chair paragraphs, exact intervening XML comment,
    and the name in a semantically identified original paragraph. No
    generic 'previous/next speaker is recipient' rule is used.
    """
    from parser import classify,issuer_context,_with_method
    if not paragraphs:
        return []
    root=paragraphs[0][0].getroottree().getroot()
    if root.get('wahlperiode')!='21':
        return []
    try:
        session=int(root.get('sitzung-nr') or '')
    except (ValueError,TypeError):
        return []
    spec=PAIRS.get(session)
    if not spec:
        return []
    first,mid,last,name,_relation=spec
    focus=3280 if session==49 else 3981 if session==51 else 2044
    if focus in excluded:
        return []
    byline={int(el.sourceline):(el,txt) for el,txt in paragraphs}
    if first not in byline or last not in byline or focus not in byline:
        return []
    el1,t1=byline[first]
    el2,t2=byline[last]
    if (not _same_chair(el1,CHAIRS[session],issuer_context)
            or not _same_chair(el2,CHAIRS[session],issuer_context)
            or classify(t1)!='possible_grant'
            or classify(t2)!='possible_grant'
            or el1.getparent() is not el2.getparent()):
        return []
    # Genuine immediate XML element must separate original paragraph
    # parts; prevent arbitrary earlier unrelated MP interjections.
    next_to_first=el1.getnext()
    prior_to_last=el2.getprevious()
    if (next_to_first is None or prior_to_last is not next_to_first
            or next_to_first.tag!='kommentar'
            or int(next_to_first.sourceline)!=mid):
        return []
    comment=' '.join(''.join(next_to_first.itertext()).split())
    if session==49:
        if (not re.search(r'\bdem\s+Abgeordneten\s+Stephan\s+Brandner'
                          r'\s+von\s+der\s+AfD\s+einen\s+Ordnungsruf\s+erteilen'
                          r'\s+für\s+den\s+Zwischenruf\s+„Heul\s+doch!“',t1,re.I)
                or not re.search(r'\bDas\s+ist\s+eine\s+eindeutige\s+'
                                 r'Herabsetzung\s+eines\s+Kollegen\s*$',t1,re.I)
                or not re.fullmatch(r'\(Lachen\s+bei\s+der\s+AfD\)',comment)
                or not re.fullmatch(
                    r'–\s*lustig\s+ist\s+daran\s+überhaupt\s+nichts\s*–,'
                    r'\s*und\s+deshalb\s+bekommen\s+Sie\s+einen\s+Ordnungsruf\.',
                    t2,re.I)):
            return []
        person=_indexed_or_original_person(name,index)
        if not person:
            return []
        return [(el2,_with_method(
            [person],'fortsetzung_benannter_erteilungsrede_xmlzeile_3278')[0])]
    if session==51:
        if (not re.search(r'\bIch\s+erteile\s+einen\s+Ordnungsruf\s+'
                          r'für\s+den\s+Begriff\s+„Lügen-Stegner“,\s+'
                          r'den\s+Sie,\s+Herr\s+Frohnmaier,\s+gerade\s+'
                          r'verwendet\s+haben',t1,re.I)
                or not re.fullmatch(
                    r'\(Markus\s+Frohnmaier\s+\[AfD\]:\s*'
                    r'Das\s+war\s+eine\s+Lüge,\s+die\s+er\s+gerade\s+'
                    r'geäußert\s+hat!\)',comment,re.I)
                or not re.search(
                    r'^\s*–\s*Ich\s+erteile\s+Ihnen\s+dafür\s+'
                    r'einen\s+Ordnungsruf\.\s*Das\s+ist\s+ein\s+'
                    r'persönlicher\s+Angriff\s+gegen\s+Herrn\s+Stegner',
                    t2,re.I)):
            return []
        person=_indexed_or_original_person(name,index)
        if not person:
            return []
        return [(el2,_with_method(
            [person],f'neuer_benannter_zwischenruf_xmlzeile_{mid}')[0])]
    # 65: Reichardt's *named* interruption is in 2042. The separate
    # remark from chair at 2046 explicitly names him. No new named
    # interruption occurs between chair passages 2044 and 2046.
    nearby=next((el for el in el1.itersiblings(preceding=True)
                 if el.tag=='kommentar' and el.sourceline==2042),None)
    if (nearby is None or nearby.getparent() is not el1.getparent()
            or not re.search(
                r'\(Martin\s+Reichardt\s+\[AfD\],\s+an\s+die\s+CDU/CSU'
                r'\s+gewandt:', ' '.join(''.join(nearby.itertext()).split()),re.I)
            or not re.fullmatch(
                r'Ich\s+erteile\s+Ihnen\s+jetzt\s+einen\s+Ordnungsruf\.',
                t1,re.I)
            or not re.fullmatch(
                r'\(Beifall\s+bei\s+Abgeordneten\s+der\s+CDU/CSU,\s+'
                r'der\s+SPD,\s+des\s+BÜNDNISSES\s+90/DIE\s+GRÜNEN\s+'
                r'und\s+der\s+Linken\)',comment)
            or not re.search(
                r'\bHerr\s+Reichardt,\s+Sie\s+können\s+Ihre\s+'
                r'Performance\s+gleich\s+draußen\s+machen\.',t2,re.I)
            or not re.search(r'\bJetzt\s+kriegen\s+Sie\s+einen\s+'
                             r'Ordnungsruf\s+von\s+mir\b',t2,re.I)):
        return []
    person=_indexed_or_original_person(name,index)
    if not person or person['identity_status']!='matched_xml_person':
        return []
    return [(el1,_with_method(
        [person],'gleiche_erteilungsepisode_spaetere_anrede_xmlzeile_2046')[0])]


def episode_summary(session):
    """Category names are review hypotheses, never legal-event counts."""
    first,mid,last,person,relation=PAIRS[session]
    return {
        'session':session,'first_xml_line':first,
        'intervening_xml_line':mid,'last_xml_line':last,
        'recipient_review_reference':person,
        'source_relation_hypothesis':relation,
        'individual_legal_event_count_verified':False,
        'needs_appeal_and_rescission_review':True,
    }
