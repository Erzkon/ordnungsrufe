"""Review-only identities backed by separate official Bundestag explanations.

Never infer that a chair addresses the owner of the enclosing XML <rede>.
21/026: The chair explicitly identifies Steffen Janich later (XML L3541).
21/043: The chair retrospectively identifies Stefan Keuter (XML L2418).
21/043: DIP separately identifies Erhard Brucker at page 5015 A;
        original XML L3497 is one *unnamed* grant between named grants.

These are original source-location review hypotheses, not independently
verified effective sanctions or new countable events. No files are modified.
"""
import re

from parser import candidate_name, classify, issuer_context, _with_method

LINDHOLZ="Vizepräsidentin Andrea Lindholz"
NOURIPOUR="Vizepräsident Omid Nouripour"
DIP_BRUCKER="https://dip.bundestag.de/erweiterte-suche?f.deskriptor=Parlamentarische+Ordnung&rows=25&start=25"


def official_person(fullname,index,method):
    """Preserve source authority without manufacturing an XML speaker ID."""
    person=candidate_name(fullname,index)
    if (person is None or person['person'].casefold()!=fullname.casefold()
            or person['identity_status']!='matched_xml_person'):
        person={'person':fullname,'person_id':'','fraktion':'AfD',
                'identity_status':'named_official_source_reference'}
    return _with_method([person],method)[0]


def exact_chair(p,chair):
    who,kind=issuer_context(p)
    return kind=='chair_marker' and who==chair


def unique_later(paragraphs,line,chair,pattern,max_distance):
    """One later source passage from the SAME explicit chair; not a new grant."""
    matched=[]
    for node,txt in paragraphs:
        delta=int(node.sourceline)-line
        if 0<delta<=max_distance and exact_chair(node,chair):
            if re.search(pattern,txt,re.I):
                matched.append((node,txt))
    return matched[0] if len(matched)==1 else None


def official_source_recipient_links(paragraphs,index,excluded):
    """Return only 3 very narrowly corroborated original grant locations."""
    if not paragraphs:
        return []
    root=paragraphs[0][0].getroottree().getroot()
    if root.get('wahlperiode')!='21':
        return []
    try:
        session=int(root.get('sitzung-nr') or '')
    except ValueError:
        return []
    if session not in (26,43):
        return []
    by_line={int(p.sourceline):(p,txt) for p,txt in paragraphs}
    result=[]
    if session==26 and 3436 not in excluded and 3436 in by_line:
        grant,text=by_line[3436]
        retro=unique_later(
            paragraphs,3436,LINDHOLZ,
            r'^Fürs\s+Protokoll:\s+Der\s+Ordnungsruf\s+ging\s+an\s+'
            r'Herrn\s+Steffen\s+Janich\s+wegen\s+der\s+'
            r'Kommentierung\s+der\s+Sitzungsleitung\.?$',
            180)
        prior=grant.getprevious()
        if (retro and exact_chair(grant,LINDHOLZ)
                and re.fullmatch(
                    r'Herr\s+Kollege,\s+dafür\s+erteile\s+ich\s+Ihnen\s+'
                    r'einen\s+Ordnungsruf\.',text,re.I)
                and classify(text)=='possible_grant'
                and prior is not None and prior.tag=='name'
                and int(prior.sourceline)==3435
                and grant.getparent() is prior.getparent()
                and any(x.tag=='kommentar' and x.sourceline==3434
                        and re.search(r'\bZuruf\s+von\s+der\s+AfD\b',
                                      ''.join(x.itertext()),re.I)
                        for x in grant.itersiblings(preceding=True))):
            person=official_person(
                'Steffen Janich',index,
                f'namentliche_sitzungsleitungs_klarstellung_xmlzeile_{retro[0].sourceline}')
            result.append((grant,person))
    if session!=43:
        return result
    if 2405 not in excluded and 2405 in by_line:
        grant,text=by_line[2405]
        retro=unique_later(
            paragraphs,2405,NOURIPOUR,
            r'\bFür\s+das\s+Protokoll\s+noch\s+mal\s+präzisiert:'
            r'\s+Der\s+zweite\s+Ordnungsruf,\s+den\s+ich\s+'
            r'erteilt\s+habe,\s+ging\s+an\s+den\s+'
            r'Abgeordneten\s+Keuter\b',45)
        previous=grant.getprevious()
        comment=previous is not None and previous.tag=='kommentar'
        if (retro and exact_chair(grant,NOURIPOUR)
                and re.match(r'^–\s*Auch\s+Sie\s+kriegen\s+'
                             r'einen\s+Ordnungsruf,\s+weil\s+'
                             r'Sie\s+anscheinend\s+nicht\s+verstanden\s+haben',
                             text,re.I)
                and 'Ältestenrat' in text
                and classify(text)=='possible_grant'
                and comment and previous.sourceline==2404
                and 'Stefan Keuter [AfD]: Kurzintervention!' in
                    ' '.join(''.join(previous.itertext()).split())
                and 'Beatrix von Storch [AfD]: Kurzintervention!' in
                    ' '.join(''.join(previous.itertext()).split())
                and previous.getparent() is grant.getparent()):
            result.append((grant,official_person(
                'Stefan Keuter',index,
                f'zweitgenannte_erteilung_vorsitz_klaerung_xmlzeile_{retro[0].sourceline}')))
    if 3497 not in excluded and 3497 in by_line:
        grant,text=by_line[3497]
        named_before=by_line.get(3493)
        second_before=by_line.get(3495)
        previous=grant.getprevious()
        if (exact_chair(grant,NOURIPOUR)
                and re.fullmatch(
                    r'–\s*Auch\s+Ihnen\s+erteile\s+ich\s+einen\s+'
                    r'Ordnungsruf;\s*Namen\s+rufe\s+ich\s+gleich\s+aus\.',
                    text,re.I)
                and classify(text)=='possible_grant'
                and previous is not None
                and previous.tag=='kommentar'
                and previous.sourceline==3496
                and 'Lachen bei Abgeordneten der AfD' in
                    ' '.join(''.join(previous.itertext()).split())
                and named_before and second_before
                and all(exact_chair(x[0],NOURIPOUR) for x in
                        (named_before,second_before))
                and re.search(
                    r'Herrn\s+Frohnmaier\s+erteile\s+ich\s+'
                    r'einen\s+Ordnungsruf',named_before[1],re.I)
                and re.search(
                    r'\bzweiten\s+Ordnungsruf,\s+Herr\s+Keuter\b',
                    second_before[1],re.I)):
            # The XML paragraph has NO person. The official DIP catalog
            # attributes this single source passage (21/43 p.5015A)
            # to Erhard Brucker. Cite that independent catalog, not an
            # adjacent speaker/comment or an invented XML redner marker.
            result.append((grant,official_person(
                'Erhard Brucker',index,
                'amtliche_dip_person_fundstelle_21_43_5015A')))
    return result
