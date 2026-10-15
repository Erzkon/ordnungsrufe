"""Review-oriented extractor for Bundestag XML (NOT an official count).

Extracts explicit person-linked grants conservatively. Ambiguous grants, threats,
appeals, and historical mentions remain in kandidaten.csv for human checking.
The public website must not treat these results as verified sanctions.
"""

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from lxml import etree

TERM_RE = re.compile(r'\bOrdnungsruf(?:e|es|en)?\b|\brufe\s+ich\s+.{0,100}?\bzur\s+Ordnung\b|\bzur\s+Ordnung\s+gerufen\b|\brufe\s+Sie\s+zur\s+Ordnung\b', re.I)
LIST_GRANT = re.compile(
    r'\bdie\s+Abgeordneten\s+([\wÀ-žÄÖÜäöüß ,.-]{3,240}?)\s+'
    r'(?:jeweils\s+)?(?:einen\s+Ordnungsruf\s+erhalten\s+haben)', re.I)
ACTION = re.compile(
    r'\b(?:erteile|erteilen|erteilt|erhält|erhalten|bekommen|bekommt|kriegen|kriegt|kriege)\b'
    r'[^.!?]{0,180}?\bOrdnungsruf\b|'
    r'\bOrdnungsruf\b[^.!?]{0,180}?\b(?:erteile|erteilen|erhält|erhalten|bekommen|bekommt|kriegen|kriegt)\b|'
    r'\b(?:rufe|rufen)\b[^.!?]{0,110}?\bzur\s+Ordnung\b|'
    r'\bOrdnungsrufe\s+gehen\s+an\b|'
    r'\b(?:Das\s+ist\s+jetzt|das\s+ist)\s+ein\s+Ordnungsruf\s+für\s+Sie\b|'
    r'\b(?:Sie\s+haben|haben\s+Sie)\s+(?:jetzt\s+)?(?:Ihren|einen)\s+Ordnungsruf\b|'
    r'\b(?:Dafür|deshalb)\s+gibt\s+es\s+(?:den\s+(?:nächsten|zweiten)|einen)\s+Ordnungsruf\b|'
    r'\bDas\s+belege\s+ich\s+(?:jetzt\s+)?(?:hiermit\s+)?mit\s+einem\s+Ordnungsruf\b', re.I)
THREAT = re.compile(
    r'\b(?:behalte\s+(?:ich\s+)?mir|vorbehalten|drohe|angedroht|'
    r'würde|würden|könnte|könnten|hätte|hätten|'
    r'falls|wenn|sonst|ansonsten|andernfalls|im\s+Wiederholungsfall|'
    r'nächste[nmrs]?\s+Mal|das\s+nächste\s+Mal|als\s+Nächstes)\b', re.I)
APPEAL = re.compile(r'\b(?:Einspruch|zurücknehmen|nicht\s+zurück|zurückgenommen|zurückgezogen|aufgehoben|gegen\s+den\s+Ordnungsruf)\b', re.I)
# A announced future sanction is not a sanction imposed. Preserve it for review.
FUTURE_ONLY = re.compile(
    r'\b(?:werde|werden|wird)\b[^.!?]{0,120}\b(?:Ordnungsruf\s+erteilen|'
    r'erteilen[^.!?]{0,60}Ordnungsruf)\b|'
    r'\bkönnen\s+Sie\s+(?:gleich\s+)?(?:auch\s+)?(?:einen\s+)?Ordnungsruf\s+bekommen\b|'
    r'\bwerden\s+Sie\b[^.!?]{0,100}\bOrdnungsruf\s+bekommen\b', re.I)
GENERIC_FUTURE = re.compile(
    r'\b(?:der\s+Nächste|jeder|wer\s+das\s+tut|jeder,?\s+der\s+das\s+tut)\b'
    r'[^.!?]{0,130}\b(?:bekommt|kriegt|erhält|erteilen)\b'
    r'[^.!?]{0,80}\bOrdnungsruf\b', re.I)
# Strict negative/hypothetical expressions are still reviewable mentions,
# but must not be reported as an actual issuing act (nor auto-verified).
# Each is tied to a sourced 21st-term XML paragraph.
NOT_ISSUED = re.compile(
    r'\b(?:kann\s+ich\s+keinen\s+Ordnungsruf\s+erteilen|'
    r'müsste\s+Ihnen\s+theoretisch\s+einen\s+Ordnungsruf\s+erteilen|'
    r'bekommt\s+man\s+ja\s+einen\s+Ordnungsruf|'
    r'Wer\s+dreimal\s+einen\s+Ordnungsruf\s+erhält|'
    r'ob\s+sie\s+dafür\s+(?:auch\s+)?schon\s+einen\s+Ordnungsruf)'
    r'\b', re.I)
ISSUANCE_QUESTION = re.compile(
    r'\bMuss\s+ich\s+Ihnen[^?]{0,85}\bOrdnungsruf\s+erteilen\s*\?', re.I)

PAST = re.compile(r'\b(?:letzten\s+Sitzung|vorigen\s+Sitzung|damals|bereits\s+erteilt|vorhin\s+erteilt|soeben\s+erteilt|früher\s+erteilt)\b', re.I)
# Names begin with an actual capital letter even when the surrounding prefix is
# matched case-insensitively. Do not consume arbitrary following prose.
NAME_WORD = r'(?-i:[A-ZÄÖÜ][a-zA-ZÄÖÜäöüß\-]+)'
NAME_PARTICLE = r'(?-i:von|de|der|van)'
NAME_SPAN = r'(?:' + NAME_PARTICLE + r'\s+)?' + NAME_WORD + r'(?:\s+(?:' + NAME_PARTICLE + r'|' + NAME_WORD + r')){0,3}'
RECIPIENT = re.compile(
    r'\b(?:dem|der|den|einem|einer)\s+(?:(?:fraktionslosen?|fraktionslose[nr]?|Herrn|Frau)\s+)?'
    r'(?:Bundestagsabgeordneten|Abgeordneten|Abgeordnete|Kollegen|Kollegin)\s+', re.I)
ADDRESS = re.compile(
    r'\b(?:Herr|Frau|Herrn)\s+(?:(?:Kollege|Kollegin|Kollegen|Abgeordneter|Abgeordnete)\s+)?'
    r'(' + NAME_SPAN + r')', re.I)
AN_THE = re.compile(r'\ban\s+(?:die|den)\s+(?:Kollegin|Kollegen|Abgeordnete[nr]?)\s+', re.I)
ORDER_TO = re.compile(r'\bOrdnungsrufe\s+gehen\s+an\s+(.+)', re.I)
SPLIT_NAMES = re.compile(r'\s*,\s*|\s+und\s+(?:an\s+)?')
TITLE = re.compile(r'^(?:Dr\.?|Prof\.?|Herrn?|Frau|Kollege(?:n|in)?|Abgeordnet(?:e|en|er))\s+', re.I)
STOPWORDS = {'ich', 'sie', 'ihnen', 'er', 'einen', 'ein', 'eine', 'einem', 'dem', 'der', 'den',
             'das', 'dafür', 'weil', 'wegen', 'für', 'erteile', 'bekommen', 'erhalten', 'kriegen',
             'jetzt', 'hiermit', 'kollege', 'kollegin', 'abgeordneter', 'abgeordnete', 'präsident', 'präsidentin', 'bundesministers', 'auch', 'bitte', 'wir', 'wird', 'werden', 'aus', 'noch', 'vor',
             'hat', 'haben', 'zur', 'ordnung', 'ordnungsruf', 'im', 'des', 'zu', 'diesen'}


def split_sentences(text):
    """Do not break a sanction clause at an abbreviated name or office.

    XML speeches routinely contain 'der Abgeordneten Dr. Paula Piechotta
    einen Ordnungsruf erteilen'. Splitting at Dr. loses the grammatical
    recipient and creates a false parser-negative.
    """
    return re.split(
        r'(?<!Dr\.)(?<!Prof\.)(?<!Abg\.)(?<=[.!?])\s+(?=[A-ZÄÖÜ])', text)


def action_match(text):
    """Keep punctuation inside quoted interjections from splitting a grant.

    Parliamentary grants can read 'Ordnungsruf für „Feigling!“ erteilen'.
    The quoted exclamation is evidence of the reason, not a sentence
    boundary between the sanction noun and its issuance verb. Substitute
    ONLY !/? within complete German quote pairs, preserving string length
    and match offsets. All other punctuation and warning guards stay.
    """
    quoted = re.compile(r'„[^“”]*[“”]')
    normalized = quoted.sub(
        lambda match: match.group().replace('!', ' ').replace('?', ' '), text)
    return ACTION.search(normalized)


def normal(text):
    return ' '.join(text.split())


def document(path):
    safe = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True,
                           recover=False, huge_tree=False)
    return etree.parse(str(path), safe).getroot()


def iter_session_text(root):
    """Only actual spoken session paragraphs (not contents/appendix/reactions)."""
    course = root.find('sitzungsverlauf')
    if course is None:
        return
    for element in course.iter('p'):
        if element.getparent() is not None and element.getparent().tag in (
                'rede', 'tagesordnungspunkt', 'sitzungsbeginn', 'sitzungsende', 'sitzungsverlauf'):
            if element.get('klasse') == 'redner':
                continue
            yield element, normal(''.join(element.itertext()))


def classify(text):
    """Classes are review hints, never a claim that a sanction is verified.

    A paragraph may first mention a threat, *then* contain an actual grant.
    Do not let "hatte sich vorbehalten" hide "möchte ... erteilen".
    """
    if LIST_GRANT.search(text):
        return 'named_group_confirmation'
    # Sentence-level classification avoids mixing independent historic and
    # current statements within a single long transcript paragraph.
    sentences = split_sentences(text)
    positive = []
    for sentence in sentences:
        if not action_match(sentence):
            continue
        if (FUTURE_ONLY.search(sentence) or GENERIC_FUTURE.search(sentence)
                or NOT_ISSUED.search(sentence) or ISSUANCE_QUESTION.search(sentence)):
            continue
        if THREAT.search(sentence):
            # If "vorbehalten" and a new grant appear in a single sentence,
            # retain the ambiguity rather than silently counting it.
            continue
        if re.search(r'\b(?:bleibt|bleiben)\s+(?:der|die|das)\s+Ordnungsruf', sentence, re.I):
            continue
        if PAST.search(sentence) and not re.search(
                r'\b(?:ich\s+erteile|erteile\s+ich|bekommen\s+Sie|kriegen\s+Sie|'
                r'erhält\s+Herr|rufe\s+ich)\b', sentence, re.I):
            continue
        positive.append(sentence)
    if positive:
        return 'possible_grant'
    if (THREAT.search(text) or FUTURE_ONLY.search(text)
            or GENERIC_FUTURE.search(text) or NOT_ISSUED.search(text)
            or ISSUANCE_QUESTION.search(text)):
        return 'warning_or_conditional'
    if APPEAL.search(text):
        return 'appeal_or_retrospective'
    if PAST.search(text):
        return 'retrospective_reference'
    return 'mention_or_unclear'


def candidates(path, root=None):
    if root is None:
        root = document(path)
    for element, text in iter_session_text(root):
        if TERM_RE.search(text):
            yield dict(file=path.name, wahlperiode=root.get('wahlperiode', ''),
                       sitzung=root.get('sitzung-nr', ''), line=element.sourceline,
                       text=text[:1200], status='review_required', classification=classify(text))


def speaker_index(roots):
    """Cross-session speaker evidence; a single surname must be unique to resolve."""
    by_surname, by_full = defaultdict(dict), defaultdict(dict)
    for root in roots:
        for node in root.iter('redner'):
            name = node.find('name')
            if name is None:
                continue
            surname = normal(name.findtext('nachname', default=''))
            first = normal(name.findtext('vorname', default=''))
            if not (surname and first):
                continue
            ident = node.get('id') or f'{first}|{surname}'
            item = {'person': f'{first} {surname}', 'person_id': node.get('id') or '',
                    'fraktion': normal(name.findtext('fraktion', default=''))}
            by_surname[surname.casefold()][ident] = item
            by_full[item['person'].casefold()][ident] = item
    return by_surname, by_full


def candidate_name(fragment, index):
    """Match longest prefix known to speaker IDs; never infer from a random mention."""
    cleaned = normal(fragment).strip(' ,.;:()–—')
    while TITLE.match(cleaned):
        cleaned = TITLE.sub('', cleaned, count=1)
    if not cleaned:
        return None
    words = [word.strip(',.!:;–—') for word in cleaned.split()]
    by_surname, by_full = index
    for n in range(min(len(words), 5), 0, -1):
        phrase = ' '.join(words[:n]).strip(',.')
        if any(w.casefold() in STOPWORDS for w in phrase.split()):
            continue
        direct = by_full.get(phrase.casefold(), {})
        surname = by_surname.get(phrase.casefold(), {})
        candidates_ = direct or surname
        if len(candidates_) == 1:
            return {**next(iter(candidates_.values())), 'identity_status': 'matched_xml_person'}
        if len(candidates_) > 1:
            return {'person': phrase, 'person_id': '', 'fraktion': '',
                    'identity_status': 'ambiguous_xml_person'}
    # Not in speaking index. Allow only explicit 1-3-token personal reference;
    # do not manufacture an identity from pronouns or common generic nouns.
    names = []
    for w in words[:4]:
        if w.casefold() in STOPWORDS or w[0].islower() and w not in ('von','de','der'):
            break
        names.append(w)
    if not names or names[-1] in ('von', 'de', 'der'):
        return None
    return {'person': ' '.join(names), 'person_id': '', 'fraktion': '',
            'identity_status': 'unmatched_name_review'}


def _name_at(text, start, index):
    """Resolve a name at a marker position, preferring longest known XML name."""
    tail = text[start:start+110]
    return candidate_name(tail, index)


def _grant_scopes(text):
    """Grant-bearing sentences in reading order, excluding warnings.

    A speech may issue a sanction and then reiterate it as 'rufe Sie zur
    Ordnung'. Looking only at the *last* sentence lost named recipients.
    """
    scopes = []
    for sentence in split_sentences(text):
        if (action_match(sentence) and not THREAT.search(sentence)
                and not FUTURE_ONLY.search(sentence) and not GENERIC_FUTURE.search(sentence)
                and not NOT_ISSUED.search(sentence)
                and not ISSUANCE_QUESTION.search(sentence)):
            scopes.append(sentence)
    # Prefer full 'Ordnungsruf' language over an immediate paraphrase.
    return sorted(scopes, key=lambda s: (0 if re.search(r'\bOrdnungsruf\b', s, re.I) else 1,
                                         text.find(s)))


def _grant_scope(text):
    """Compatibility helper: strongest actionable sentence, not the last one."""
    scopes = _grant_scopes(text)
    return scopes[0] if scopes else text


def _same_person_list(people):
    """Stable identity-based de-duplication only *within* a paragraph."""
    result = []
    seen = set()
    for person in people:
        if not person:
            continue
        key = (person['person_id'] or person['person']).casefold()
        if key not in seen:
            seen.add(key)
            result.append(person)
    return result


def _with_method(people, method):
    return [{**who, 'zuordnungsmethode': method} for who in people if who]


def _subject_antecedent(text, scope, index):
    """Strict grammatical subject linked to 'er/ihm/ihr/Sie' sanction.

    Must be a named subject of the reported misconduct, not the victim,
    chair, or arbitrary name mentioned near a pronoun.
    """
    if not re.search(r'\b(?:erteile\s+(?:ich\s+)?(?:ihm|ihr)|erteilt\s+(?:ihm|ihr)|'
                     r'bekommt\s+er|erhält\s+er|erteile\s+ich\s+Ihnen|(?:Sie\s+(?:kriegen|bekommen)))\b',scope,re.I):
        return []
    # Name may be in the same long sentence, as in 'hat Frau Kollegin
    # Schulz-Asche ... Dafür erteile ich ihr nachträglich ...'.
    grant = re.search(r'\b(?:erteile|erteilt|bekommt|kriegt|erhält)\b',scope,re.I)
    local_head = scope[:grant.start()] if grant else ''
    local_match = re.search(r'\bhat\s+(?:Herr|Frau(?:\s+Kollegin)?)\s+',local_head,re.I)
    if local_match:
        person = _name_at(local_head,local_match.end(),index)
        if person:
            return [person]
    prefix = text[:text.find(scope)] if text.find(scope) >= 0 else ''
    # Last two sentences only, and no inferencing across XML paragraphs.
    sentences = split_sentences(prefix.strip())
    near = ' '.join(sentences[-2:])[-650:]
    referents = []
    patterns = (
        r'(?:^|(?<=[.!?] ))\s*(?:Der\s+Abgeordnete|Die\s+Abgeordnete|Herr|Frau\s+Kollegin|Frau)\s+',
        r'\bhat\s+(?:Herr|Frau\s+Kollegin|Frau)\s+',
        r'\bdass\s+(?:Herr|Frau\s+Kollegin|Frau)\s+',
    )
    for pattern in patterns:
        for m in re.finditer(pattern,near,re.I):
            who = _name_at(near,m.end(),index)
            if who:
                referents.append(who)
    people = _same_person_list(referents)
    # Multiple actor candidates: refuse to guess.
    return people if len(people) == 1 else []


def _third_person_antecedent(text, scope, index):
    """Strict, paragraph-local subject evidence for 'ihm/ihr/er'.

    Works for 'Herr Brandner hat ... Ich erteile ihm ...' but refuses to
    extrapolate across paragraphs or from indirect victims ('Frau Ganserer').
    """
    if not re.search(r'\b(?:erteile\s+(?:ich\s+)?(?:ihm|ihr)|bekommt\s+er|erhält\s+er|'
                     r'erhält\s+sie|erteilt\s+(?:ihm|ihr))\b', scope, re.I):
        return []
    at = text.find(scope)
    prefix = text[:at].strip() if at >= 0 else ''
    sentences = split_sentences(prefix)
    prior = sentences[-1] if sentences else ''
    # Original 21/027: "Nach Durchsicht ... dass der Abgeordnete
    # Heinrich Koch ... [the Chancellor] einen Lügenbeutel genannt hat.
    # Dafür erteile ich ihm einen Ordnungsruf." The uniquely named actor of
    # the misconduct is the subject of "genannt hat", not the insulted
    # Chancellor. This is a *review hypothesis*, never a confirmed event.
    if re.match(r'^(?:Dafür|Deshalb)\s+erteile\s+ich\s+ihm\s+einen\s+Ordnungsruf\b',
                scope, re.I):
        actor = re.search(r'\bdass\s+der\s+Abgeordnete\s+', prior, re.I)
        if (actor and len(re.findall(r'\bdass\s+der\s+Abgeordnete\b',
                                     prior, re.I)) == 1
                and re.search(r'\bgenannt\s+hat\b', prior[actor.end():], re.I)):
            who = _name_at(prior, actor.end(), index)
            if who:
                return [who]
    # A subject must open that immediately preceding sentence, not be an
    # arbitrary mentioned injured party or the presiding officer.
    m = re.match(
        r'^(?:[–—-]\s*)?(?:Der\s+Abgeordnete|Die\s+Abgeordnete|'
        r'Herr|Frau(?:\s+Kollegin)?|Herr\s+Kollege)\s+', prior, re.I)
    if not m:
        return []
    person = _name_at(prior, m.end(), index)
    return [person] if person else []


def _sanction_against(text, index):
    """Explicit object: 'erteile ... gegen die Abgeordnete X einen Ordnungsruf'."""
    if not action_match(text):
        return []
    match = re.search(
        r'\bgegen\s+(?:die|den)\s+(?:Abgeordnete[nr]?|Kollegin|Kollegen)\s+',
        text, re.I)
    if match and re.search(r'\b(?:erteile|erteilt|verhänge|verhängt)\b', text[:match.start()], re.I):
        person = _name_at(text, match.end(), index)
        return [person] if person else []
    return []


def _object_people(text, index):
    results = []
    action = action_match(text)
    if not action:
        return []
    # People first mentioned AFTER 'Ordnungsruf' commonly appear in the reason
    # (the person who was insulted), not as recipients of the sanction.
    term = re.search(r'\bOrdnungsruf\b', text, re.I)
    recipient_part = text[:term.start()] if term else text
    for match in RECIPIENT.finditer(recipient_part):
        # e.g. "gegenüber der Abgeordneten Weidel" refers to the insulted
        # person, NOT the target of a sanction.
        previous = text[max(0, match.start()-25):match.start()].casefold()
        if re.search(r'(?:gegenüber|wegen|von|an|auf|mit|für)\s*$', previous):
            continue
        # A dative object of the reported insult is NOT the addressee of
        # the Ordnungsruf. Real XML 21/052 and 21/067 use "dass Sie der
        # Kollegin X ... vorgeworfen haben, erteile/erhalten Sie ...".
        prior_clause = text[max(0, match.start()-90):match.start()]
        offense_clause = text[match.end():(term.start() if term else len(text))]
        if (re.search(r'\b(?:dass|weil)\s+Sie\s*$', prior_clause, re.I)
                and re.search(r'\b(?:vorgeworfen|unterstellt|beleidigt|'
                              r'beschimpft|bezichtigt|angegriffen)\b',
                              offense_clause, re.I)):
            continue
        # Recipient must be syntactically connected to the issuing verb.
        between = text[max(0,match.start()-110):match.start()]
        after = text[match.end():match.end()+135]
        near_action = (
            re.search(r'\b(?:erteile|erteilt|erteilen|erhält|erhalten|bekommen|kriegen|muss|möchte)\b', between, re.I)
            or re.search(r'\b(?:erteile|erteilt|erteilen|erhält|erhalten|bekommen|kriegen)\b', after, re.I)
        )
        if not near_action:
            continue
        resolved = _name_at(text, match.end(), index)
        if resolved:
            results.append(resolved)
    # 'habe dem Abgeordneten Brandner ... einen Ordnungsruf ... zu erteilen'
    # is still an explicit dative despite the infinitive late in the clause.
    for match in RECIPIENT.finditer(recipient_part):
        following = text[match.end():match.end()+260]
        if not re.search(r'\bOrdnungsruf\b', following, re.I):
            continue
        if re.search(r'\b(?:habe|hat|haben)\b', text[max(0, match.start()-80):match.start()], re.I) and re.search(
                r'\bzu\s+erteilen\b', following, re.I):
            person = _name_at(text, match.end(), index)
            if person:
                results.append(person)
    for match in AN_THE.finditer(text):
        before = text[max(0, match.start()-80):match.start()]
        if re.search(r'\b(?:erteile|erteilt|erteilen|Ordnungsruf)\b', before, re.I):
            resolved = _name_at(text, match.end(), index)
            if resolved:
                results.append(resolved)
    return results


def _vocative_people(text, index):
    """Only direct forms of address, not an insult's quoted target."""
    results = []
    # Remove typographic quotes so the victim named *inside* an insult is not
    # mistaken for the addressee.
    clean = re.sub(r'[„“][^“”]+[“”]', ' ', text)
    for match in ADDRESS.finditer(clean):
        previous = clean[max(0, match.start()-20):match.start()].casefold()
        if re.search(r'(?:gegenüber|an|mit|von|für|über)\s*$', previous):
            continue
        resolved = _name_at(clean, match.start(1), index)
        if not resolved:
            continue
        # Prefer a vocative followed by a comma/colon, or a pronoun-directed
        # sanction shortly thereafter. "Herr Steffen einen ..." is not one.
        tail = clean[match.end():match.end()+90]
        if re.match(r'\s*[,!:.–—]', tail) or re.match(r'\s+(?:Sie|Ihnen)\b', tail):
            results.append((match.start(), resolved))
    return results


def _named_issuer_recipient(scope, index):
    """Only direct grammatical recipients of an issuance clause.

    Original 21/015: 'Ich erteile einen Ordnungsruf an Herrn Lamely'.
    21/023: 'Ich erteile ... einen nachträglichen Ordnungsruf, in dem
    Fall dem Abgeordneten Karsten Hilse'.
    21/043: 'Herrn Frohnmaier erteile ich einen Ordnungsruf'.
    An addressee inferred from a preceding paragraph is deliberately NOT used.
    """
    front = re.match(
        r'^\s*[–—-]?\s*Herrn\s+(' + NAME_SPAN +
        r')\s+erteile\s+ich\s+einen\s+Ordnungsruf\b', scope, re.I)
    if front:
        who = candidate_name(front.group(1), index)
        return _with_method([who], 'expliziter_empfaenger_vorangestellt') if who else []
    after = re.search(
        r'\b(?:ich\s+erteile|erteile\s+ich)\b[^.!?]{0,145}?'
        r'\beinen\s+(?:nachträglichen\s+)?Ordnungsruf\s*,?\s*'
        r'(?:in\s+dem\s+Fall\s+)?'
        r'(?:an\s+(?:Herrn|Frau)|(?:dem|der)\s+Abgeordneten)\s+', scope, re.I)
    if after:
        who = _name_at(scope, after.end(), index)
        return _with_method([who], 'expliziter_empfaenger_nach_erteilung') if who else []
    return []


def persons_for_grant(text, index):
    # The later, named roll-call confirms recipients of an earlier anonymous
    # group sanction; do not also emit people for its initial unnamed grant.
    listed = LIST_GRANT.search(text)
    if listed:
        return _same_person_list(candidate_name(s, index) for s in SPLIT_NAMES.split(listed.group(1)))
    group = ORDER_TO.search(text)
    if group:
        names = re.split(r'[.;]', group.group(1), maxsplit=1)[0]
        if ' und ' in names:
            return _same_person_list(candidate_name(
                re.sub(r'^(?:an\s+)?(?:den|dem)\s+(?:Kollegen|Abgeordneten)\s+', '', s, flags=re.I), index)
                for s in SPLIT_NAMES.split(names))

    scopes = _grant_scopes(text)
    if not scopes:
        return []

    # 21/065: named interrupter + demonstrative "Das belege ich ... mit
    # einem Ordnungsruf" within the same paragraph. A conservative REVIEW
    # candidate only; never count a legally effective act from this alone.
    sanction = re.search(
        r'\bDas\s+belege\s+ich\s+(?:jetzt\s+)?(?:hiermit\s+)?'
        r'mit\s+einem\s+Ordnungsruf\b', text, re.I)
    if sanction:
        prefix = text[:sanction.start()]
        interruption = re.search(
            r'\beinen\s+Zwischenruf\s+des\s+Abgeordneten\s+', prefix, re.I)
        if (interruption
                and len(re.findall(r'\bZwischenruf\b', prefix, re.I)) == 1
                and not re.search(r'\bund\s+des\s+Abgeordneten\b',
                                  prefix[interruption.end():], re.I)
                and re.search(r':\s*[„“]',prefix[interruption.end():])):
            person = _name_at(prefix, interruption.end(), index)
            if person:
                return _with_method([person], 'benannter_zwischenruf_im_absatz')

    for scope in scopes:
        # For 'Der Abgeordnete Brandner hat Herrn Merz ... bekommt er ...'
        # the subject and the grant occur in one sentence.
        same_subject = None
        if re.search(r'\b(?:bekommt\s+er|erhält\s+er|erteile\s+ihm)\b', scope, re.I):
            m_sub = re.match(r'^(?:[–—]\s*)?(?:Der\s+Abgeordnete|Die\s+Abgeordnete|Herr|Frau)\s+',scope,re.I)
            if m_sub:
                same_subject = _name_at(scope,m_sub.end(),index)
        # 'Herr Brandner wird sich das schon denken: ... erteile ich Ihnen'
        # is a direct, named lead-in to a present-tense sanction.
        pre_action = scope[:action_match(scope).start()]
        lead_in = re.match(r'^(?:[–—]\s*)?(?:Herr|Frau)\s+',pre_action,re.I)
        if lead_in and re.search(r'\bwird\s+sich\s+das\s+schon\s+denken\b',pre_action,re.I):
            named = _name_at(pre_action,lead_in.end(),index)
            if named:
                return _with_method([named], 'benannter_bezug_im_selben_satz')
        # Official 21/057: "Der Abgeordnete Kneller erhält von mir einen
        # Ordnungsruf." Grammatical subject and recipient are identical.
        direct_subject = re.match(
            r'^(?:Der|Die)\s+Abgeordnete(?:r|n)?\s+', scope, re.I)
        if direct_subject:
            remainder = scope[direct_subject.end():]
            verb = re.search(r'\s+(?:erhält|bekommt|kriegt)\b', remainder, re.I)
            if verb:
                name_fragment = remainder[:verb.start()].strip()
                tail = remainder[verb.end():]
                # The entire grammatical subject must look like a name, not
                # free prose that happens to mention a politician.
                if (1 <= len(name_fragment.split()) <= 4
                        and re.fullmatch(r'[\wÀ-žÄÖÜäöüß\- ]+', name_fragment)
                        and re.search(r'^[^.!?]{0,100}\beinen\s+Ordnungsruf\b', tail, re.I)):
                    who = _name_at(scope, direct_subject.end(), index)
                    if who:
                        return _with_method([who], 'explizites_empfaenger_subjekt')
        # An explicit recipient in the issuing clause outranks every name in
        # an explanation or later paraphrase.
        against = _sanction_against(scope, index)
        if against:
            return _with_method(_same_person_list(against), 'explizit_gegen')
        objects = _object_people(scope, index)
        if objects:
            return _with_method(_same_person_list(objects), 'expliziter_dativ')
        issued_recipient = _named_issuer_recipient(scope, index)
        if issued_recipient:
            return issued_recipient

        # Address may precede a reported interruption, with the actual grant
        # in the following sentence. Only consider direct vocatives BEFORE
        # the grant; never select names in the reason after the grant.
        grant_at = text.find(scope)
        preceding_addresses = [(pos, who) for pos, who in _vocative_people(text, index)
                               if pos < grant_at] if grant_at >= 0 else []
        if preceding_addresses:
            # A preceding vocative is eligible only inside the same paragraph
            # and not behind an intervening different addressee.
            preceding_person = preceding_addresses[-1][1]
        else:
            preceding_person = None

        if same_subject:
            return _with_method([same_subject], 'subjekt_im_selben_satz')

        # 'ich erteile ihm': require a syntactically identifiable subject in
        # the immediately preceding sentence. Otherwise leave unassigned.
        third_person = re.search(r'\b(?:erteile\s+(?:ich\s+)?(?:ihm|ihr)|erteilt\s+(?:ihm|ihr))\b', scope, re.I)
        if third_person:
            antecedent = _third_person_antecedent(text, scope, index)
            if antecedent:
                return _with_method(antecedent, 'pronomen_bezug_im_absatz')
            subject = _subject_antecedent(text,scope,index)
            if subject:
                return _with_method(subject, 'pronomen_bezug_im_absatz')
            continue

        # Direct addressees are only taken from the sanction clause itself,
        # or after an explicit transition into the sanction clause (the
        # named person may be in a separate immediately preceding clause).
        addresses = _vocative_people(scope, index)
        if addresses:
            before = [a for a in addresses if a[0] <= (action_match(scope).start())]
            return _with_method([(before[-1] if before else addresses[-1])[1]], 'direkte_anrede')

        for pattern in (
            r'\b(?:erhält|bekommt|kriegt)\s+(?:Herr|Frau|Herrn)\s+',
            r'\b(?:erhält|bekommt|kriegt)\s+(?:der|die)\s+Abgeordnete\s+',
        ):
            match = re.search(pattern, scope, re.I)
            if match:
                person = _name_at(scope, match.end(), index)
                if person:
                    return _with_method([person], 'benannter_empfaenger')

        # Subject before a pronoun-directed grant; e.g. 'Frau von Storch ...
        # Sie kriegen einen Ordnungsruf.' Direct present-tense only.
        if re.search(r'\b(?:Sie\s+kriegen|Sie\s+bekommen)\b', scope, re.I):
            prefix = text[:text.find(scope)]
            prior = split_sentences(prefix.strip())[-1]
            m = re.match(r'^(?:Der\s+Abgeordnete|Die\s+Abgeordnete|'
                         r'Herr|Frau(?:\s+Kollegin)?)\s+', prior, re.I)
            if m:
                person = _name_at(prior, m.end(), index)
                if person:
                    return _with_method([person], 'pronomen_bezug_im_absatz')

        antecedent = _third_person_antecedent(text, scope, index)
        if antecedent:
            return _with_method(antecedent, 'pronomen_bezug_im_absatz')
        subject = _subject_antecedent(text, scope, index)
        if subject:
            return _with_method(subject, 'pronomen_bezug_im_absatz')
        if preceding_person:
            return _with_method([preceding_person], 'anrede_vor_erteilung')
    return []


def issuer_context(element):
    """If transcript marks a presiding name, record it, not as the recipient."""
    previous = element.getprevious()
    while previous is not None:
        if previous.tag == 'name':
            name = normal(''.join(previous.itertext())).rstrip(':')
            if re.search(r'\b(?:Präsident(?:in)?|Vizepräsident(?:in)?)\b', name, re.I):
                return name, 'chair_marker'
            return name, 'speaker_marker'
        if previous.tag == 'p' and previous.get('klasse') == 'redner':
            return '', 'speech_marker'
        previous = previous.getprevious()
    return '', 'unknown'


def event_row(path, root, element, identified, kind):
    issuer, evidence = issuer_context(element)
    return dict(file=path.name, wahlperiode=root.get('wahlperiode', ''),
                sitzung=root.get('sitzung-nr', ''), datum=root.get('sitzung-datum', ''),
                person=identified['person'], person_id=identified['person_id'],
                fraktion=identified['fraktion'], identity_status=identified['identity_status'],
                event_type='Ordnungsruf', evidence_type=kind, line=element.sourceline,
                text=normal(''.join(element.itertext()))[:1200], status='review_required',
                issuer=issuer, issuer_evidence=evidence,
                zuordnungsmethode=identified.get('zuordnungsmethode', 'sonstige_namensnennung'))


def events(path, index=None, root=None):
    if root is None:
        root = document(path)
    if index is None:
        index = speaker_index([root])
    found, seen = [], set()
    for element, text in iter_session_text(root):
        if not TERM_RE.search(text):
            continue
        cls = classify(text)
        if cls not in ('possible_grant', 'named_group_confirmation'):
            continue
        # Avoid double output for multiple recipient patterns on one line.
        for identified in persons_for_grant(text, index):
            if not identified or identified['person'].casefold() in STOPWORDS:
                continue
            event = event_row(path, root, element, identified, cls)
            key = (event['line'], event['person'].casefold())
            if key not in seen:
                seen.add(key)
                found.append(event)
    yield from found


def neighboring_paragraphs(root):
    """Excerpt context, not a guessed speaker or confirmed recipient.

    Only text from the formal session course; excludes quoted reactions and
    other XML branches. Adjacent paragraphs may cross speaker boundaries!
    """
    paragraphs = list(iter_session_text(root))
    near = {}
    for i, (element, txt) in enumerate(paragraphs):
        prev_text = paragraphs[i-1][1] if i else ''
        next_text = paragraphs[i+1][1] if i+1 < len(paragraphs) else ''
        near[str(element.sourceline)] = {
            'vorheriger_absatz': prev_text[-550:],
            'naechster_absatz': next_text[:550],
        }
    return near


def review_hint(row):
    """Just a triage hint; never claim a confirmed grant or identity."""
    text = row['text']
    if row['classification'] == 'named_group_confirmation':
        return 'Namentliche Bestaetigung: fruehere namenlose Gruppenmassnahme derselben Sitzung suchen'
    if row['classification'] != 'possible_grant':
        return 'Erteilung nicht eindeutig: Text und angrenzende Absaetze pruefen'
    if re.search(r'\b(?:ihm|ihr|Ihnen|Sie)\b',text,re.I):
        return 'Pronomen: Adressat nur aus dem Originalkontext ermittelbar; moegliche Sprecherwechsel beachten'
    if re.search(r'\b(?:zweiten|zweiter|weiteren|weiterer)\s+Ordnungsruf\b',text,re.I):
        return 'Weitere Massnahme: von vorheriger Massnahme abgrenzen'
    return 'Erteilung und Identitaet anhand der Protokollstelle pruefen'


def build_review_queue(hits, events, context=None):
    """A human-auditable row for *every* candidate, including missed grants.

    No entry becomes 'confirmed' here: identity resolution is not validation.
    Identifiers are scoped to Wahlperiode, Sitzung, and XML source line.
    """
    context = context or {}
    located = defaultdict(list)
    for event in events:
        located[(event['file'], str(event['line']))].append(event)
    rows = []
    for hit in hits:
        matched = located.get((hit['file'], str(hit['line'])), [])
        category = hit['classification']
        number = len(matched)
        if category == 'named_group_confirmation':
            priority, reason = 'hoch', 'Gruppenmassnahme: Zuordnung und Dopplungen pruefen'
        elif category == 'possible_grant' and number == 0:
            priority, reason = 'hoch', 'Moegliche Erteilung ohne automatisch erkannten Empfaenger'
        elif category == 'possible_grant' and number > 1:
            priority, reason = 'hoch', 'Mehrere erfasste Empfaenger: jeden einzeln pruefen'
        elif category == 'possible_grant' and any(e.get('zuordnungsmethode', '').startswith(
                ('pronomen_', 'anrede_vor_', 'subjekt_', 'benannter_bezug_')) for e in matched):
            priority, reason = 'hoch', 'Kontextuelle Zuordnung: Referenz unbedingt manuell bestaetigen'
        elif category == 'possible_grant' and any(e['identity_status'] != 'matched_xml_person' for e in matched):
            priority, reason = 'hoch', 'Empfaengeridentitaet nicht eindeutig abgeglichen'
        elif category == 'possible_grant' and len(re.findall(r'\b(?:Herrn?|Frau|Abgeordnet(?:e|en|er))\b', hit['text'], re.I)) >= 2:
            priority, reason = 'hoch', 'Mehrere Personen im selben Text: Adressat pruefen'
        elif category == 'possible_grant':
            priority, reason = 'mittel', 'Automatisch erkannte Erteilung: amtlichen Wortlaut pruefen'
        else:
            priority, reason = 'niedrig', 'Automatisch als Hinweis oder unsicher klassifiziert: Ausschluss pruefen'
        neighbors = context.get(hit['file'], {}).get(str(hit['line']), {})
        rows.append(dict(
            pruef_id=f"{hit['wahlperiode']}-{str(hit['sitzung']).zfill(3)}-{hit['line']}",
            prioritaet=priority, grund=reason, wahlperiode=hit['wahlperiode'],
            sitzung=hit['sitzung'], datei=hit['file'], xml_zeile=hit['line'],
            klassifikation=category, parser_personenzahl=number,
            parser_personen=' | '.join(e['person'] for e in matched),
            parser_personen_ids=' | '.join(e['person_id'] for e in matched),
            quell_url=(f"https://dserver.bundestag.de/btp/{hit['wahlperiode']}/"
                       f"{hit['file']}"),
            protokolltext=hit['text'],
            parser_zuordnungsmethoden=' | '.join(e.get('zuordnungsmethode', '') for e in matched),
            vorheriger_absatz=neighbors.get('vorheriger_absatz', ''),
            naechster_absatz=neighbors.get('naechster_absatz', ''),
            pruefhinweis=review_hint(hit),
            pruefung='offen', entscheidung='', korrekte_personen='', bemerkung=''))
    order = {'hoch': 0, 'mittel': 1, 'niedrig': 2}
    return sorted(rows, key=lambda x: (order[x['prioritaet']], int(x['sitzung']), int(x['xml_zeile'])))


def save_quality_report(path, reviews, events, protocol_count):
    """Coverage and triage ONLY. Never present raw parser events as verified."""
    by_priority = defaultdict(int)
    by_class = defaultdict(int)
    for row in reviews:
        by_priority[row['prioritaet']] += 1
        by_class[row['klassifikation']] += 1
    by_method = defaultdict(int)
    for event in events:
        by_method[event.get('zuordnungsmethode', 'nicht_spezifiziert')] += 1
    clarify = [row for row in reviews if row['klassifikation'] == 'possible_grant'
               and row['parser_personenzahl'] == 0]
    report = {
        'klaerungsfaelle_moegliche_erteilung_ohne_person': len(clarify),
        'personen_nach_zuordnungsmethode': dict(sorted(by_method.items())),
        'hinweis': 'Ausschliesslich ungepruefte Parserergebnisse; keine amtliche Statistik.',
        'protokolle_verarbeitet': protocol_count,
        'textfundstellen': len(reviews),
        'personenereignisse_ungeprueft': len(events),
        'pruefung_abgeschlossen': 0,
        'pruefzeilen_nach_prioritaet': dict(sorted(by_priority.items())),
        'fundstellen_nach_klassifikation': dict(sorted(by_class.items())),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def save_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder', type=Path)
    ap.add_argument('--out', type=Path, default=Path('kandidaten.csv'))
    ap.add_argument('--events-out', type=Path, default=Path('ordnungsrufe.csv'))
    ap.add_argument('--summary-out', type=Path, default=Path('sitzungen.csv'))
    ap.add_argument('--review-out', type=Path, default=Path('pruefliste.csv'))
    ap.add_argument('--quality-out', type=Path, default=Path('qualitaetsbericht.json'))
    ap.add_argument('--clarification-out', type=Path, default=Path('klaerungsfaelle.csv'))
    args = ap.parse_args()
    paths = sorted(args.folder.rglob('*.xml'))
    if not paths:
        ap.error('No XML files found')
    # Create a shared index from ALL sessions; it substantially improves name
    # matching without downloading a separate or version-changing identity file.
    index = speaker_index(document(path) for path in paths)
    hits, sanctions, sessions, context = [], [], [], {}
    for path in paths:
        root = document(path)
        context[path.name] = neighboring_paragraphs(root)
        local_hits, local_sanctions = list(candidates(path, root)), list(events(path, index, root))
        hits.extend(local_hits)
        sanctions.extend(local_sanctions)
        sessions.append(dict(wahlperiode=root.get('wahlperiode', ''),
                             sitzung=root.get('sitzung-nr', ''), datum=root.get('sitzung-datum', ''),
                             datei=path.name,
                             quelle=f'https://dserver.bundestag.de/btp/{root.get("wahlperiode", "20")}/{path.name}',
                             textfundstellen=len(local_hits),
                             erkannte_personenereignisse=len(local_sanctions),
                             status='ungepruefte_parserergebnisse'))
    save_csv(args.out, ['file','wahlperiode','sitzung','line','text','status','classification'], hits)
    save_csv(args.events_out,
             ['file','wahlperiode','sitzung','datum','person','person_id','fraktion',
              'identity_status','event_type','evidence_type','line','text','status',
              'issuer','issuer_evidence','zuordnungsmethode'], sanctions)
    save_csv(args.summary_out, ['wahlperiode','sitzung','datum','datei','quelle',
                                'textfundstellen','erkannte_personenereignisse','status'], sessions)
    reviews = build_review_queue(hits, sanctions, context)
    review_fields = ['pruef_id','prioritaet','grund','wahlperiode','sitzung',
                     'datei','xml_zeile','klassifikation','parser_personenzahl',
                     'parser_personen','parser_personen_ids','quell_url',
                     'protokolltext','parser_zuordnungsmethoden','vorheriger_absatz',
                     'naechster_absatz','pruefhinweis',
                     'pruefung','entscheidung','korrekte_personen','bemerkung']
    save_csv(args.review_out, review_fields, reviews)
    unresolved = [r for r in reviews if r['klassifikation'] == 'possible_grant'
                  and r['parser_personenzahl'] == 0]
    save_csv(args.clarification_out, review_fields, unresolved)
    save_quality_report(args.quality_out, reviews, sanctions, len(paths))
    by_class = defaultdict(int)
    for hit in hits:
        by_class[hit['classification']] += 1
    print(f'{len(hits)} Kandidaten; {len(sanctions)} PERSONENBEZOGENE PRUEFFÄLLE; '
          f'{len(paths)} Protokolle. Noch keine amtliche Statistik.')
    print('Klassen:', dict(sorted(by_class.items())))
    print(f'Noch offene moegliche Erteilungen ohne Person: {len(unresolved)}. Die Auswertung bleibt UNGEPRUEFT.')
    print(f'Dateien: {args.out}, {args.events_out}, {args.summary_out}, {args.review_out}, {args.clarification_out}, {args.quality_out}.')


if __name__ == '__main__':
    main()
