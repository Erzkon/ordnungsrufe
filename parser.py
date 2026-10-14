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
    r'\b(?:Das\s+ist\s+jetzt|das\s+ist)\s+ein\s+Ordnungsruf\s+für\s+Sie\b', re.I)
THREAT = re.compile(
    r'\b(?:behalte\s+(?:ich\s+)?mir|vorbehalten|drohe|angedroht|'
    r'würde|würden|könnte|könnten|hätte|hätten|'
    r'falls|wenn|sonst|andernfalls|im\s+Wiederholungsfall|'
    r'nächste[nmrs]?\s+Mal|das\s+nächste\s+Mal|als\s+Nächstes)\b', re.I)
APPEAL = re.compile(r'\b(?:Einspruch|zurücknehmen|nicht\s+zurück|zurückgenommen|zurückgezogen|aufgehoben|gegen\s+den\s+Ordnungsruf)\b', re.I)
PAST = re.compile(r'\b(?:letzten\s+Sitzung|vorigen\s+Sitzung|damals|bereits\s+erteilt|vorhin\s+erteilt|soeben\s+erteilt|früher\s+erteilt)\b', re.I)
# Names begin with an actual capital letter even when the surrounding prefix is
# matched case-insensitively. Do not consume arbitrary following prose.
NAME_WORD = r'(?-i:[A-ZÄÖÜ][a-zA-ZÄÖÜäöüß\-]+)'
NAME_PARTICLE = r'(?-i:von|de|der|van)'
NAME_SPAN = r'(?:' + NAME_PARTICLE + r'\s+)?' + NAME_WORD + r'(?:\s+(?:' + NAME_PARTICLE + r'|' + NAME_WORD + r')){0,3}'
RECIPIENT = re.compile(
    r'\b(?:dem|der|den|einem|einer)\s+(?:(?:fraktionslosen?|fraktionslose[nr]?|Herrn|Frau)\s+)?'
    r'(?:Abgeordneten|Abgeordnete|Kollegen|Kollegin)\s+', re.I)
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
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÄÖÜ])', text)
    positive = []
    for sentence in sentences:
        if not ACTION.search(sentence):
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
    if THREAT.search(text):
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


def _grant_scope(text):
    """Pick the clause carrying the last explicit grant, not its explanation.

    The whole paragraph is retained separately for the audit. This scope is
    only used to find grammatical recipients; it must not be treated as proof.
    """
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZÄÖÜ])', text)
    grants = [s for s in sentences if ACTION.search(s) and not THREAT.search(s)]
    return grants[-1] if grants else text


def _object_people(text, index):
    results = []
    action = ACTION.search(text)
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
        # Recipient must be syntactically connected to the issuing verb:
        # "erteile ... dem Kollegen X" or "dem Kollegen X erteile ...".
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


def persons_for_grant(text, index):
    # Confirmation of a specific group sanction, not an extra sanction on top
    # of the original anonymous grant.
    listed = LIST_GRANT.search(text)
    if listed:
        return [candidate_name(s, index) for s in SPLIT_NAMES.split(listed.group(1))]
    group = ORDER_TO.search(text)
    if group:
        names = re.split(r'[.;]', group.group(1), maxsplit=1)[0]
        if ' und ' in names:
            return [candidate_name(re.sub(r'^(?:an\s+)?(?:den|dem)\s+(?:Kollegen|Abgeordneten)\s+', '', s, flags=re.I), index)
                    for s in SPLIT_NAMES.split(names)]
    scope = _grant_scope(text)
    objects = _object_people(scope, index)
    # When there is a direct addressee, object references in the explanation
    # are generally people affected by the insult, not sanction recipients.
    addresses = _vocative_people(text, index)
    action = ACTION.search(scope)
    if not action:
        return []
    # "ich erteile ihm ...": a woman mentioned elsewhere cannot be inferred
    # to be the target. Wait for an explicit antecedent in a different source.
    third_person = re.search(r'\b(?:erteile\s+ihm|erteile\s+ihr)\b', scope, re.I)
    if third_person and not objects:
        return []
    if objects:
        return objects
    if addresses:
        # Choose the nearest direct address to the act; an address positioned
        # after the act ("Sie bekommen ..., Herr Nietan") is also legitimate.
        # A comma-marked early vocative remains the addressee even if
        # another person is referenced in the explanation of the insult.
        # Last vocative preceding the grant overrides an earlier unrelated
        # address (e.g. 'Frau Reichinnek. – Frau von Storch, ... Ordnungsruf').
        # The action position belongs to `scope`, so use the full paragraph's
        # last grant-bearing sentence to locate the selected vocative.
        last_scope_at = text.rfind(scope)
        position = last_scope_at + action.start() if last_scope_at >= 0 else len(text)
        before_action = [a for a in addresses if a[0] <= position]
        nearest = (before_action[-1] if before_action else addresses[-1])
        return [nearest[1]]
    # "erhält Herr Janich ..." without a vocative comma.
    for pattern in (
        r'\b(?:erhält|bekommt|kriegt)\s+(?:Herr|Frau|Herrn)\s+',
        r'\b(?:erhält|bekommt|kriegt)\s+(?:der|die)\s+Abgeordnete\s+',
    ):
        m = re.search(pattern, scope, re.I)
        if m:
            p = _name_at(scope, m.end(), index)
            if p:
                return [p]
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
                issuer=issuer, issuer_evidence=evidence)


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


def build_review_queue(hits, events):
    """A human-auditable row for *every* candidate, including missed grants.

    No entry becomes 'confirmed' here: identity resolution is not validation.
    Identifiers are scoped to Wahlperiode, Sitzung, and XML source line.
    """
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
        elif category == 'possible_grant' and any(e['identity_status'] != 'matched_xml_person' for e in matched):
            priority, reason = 'hoch', 'Empfaengeridentitaet nicht eindeutig abgeglichen'
        elif category == 'possible_grant' and len(re.findall(r'\b(?:Herrn?|Frau|Abgeordnet(?:e|en|er))\b', hit['text'], re.I)) >= 2:
            priority, reason = 'hoch', 'Mehrere Personen im selben Text: Adressat pruefen'
        elif category == 'possible_grant':
            priority, reason = 'mittel', 'Automatisch erkannte Erteilung: amtlichen Wortlaut pruefen'
        else:
            priority, reason = 'niedrig', 'Automatisch als Hinweis oder unsicher klassifiziert: Ausschluss pruefen'
        rows.append(dict(
            pruef_id=f"{hit['wahlperiode']}-{str(hit['sitzung']).zfill(3)}-{hit['line']}",
            prioritaet=priority, grund=reason, wahlperiode=hit['wahlperiode'],
            sitzung=hit['sitzung'], datei=hit['file'], xml_zeile=hit['line'],
            klassifikation=category, parser_personenzahl=number,
            parser_personen=' | '.join(e['person'] for e in matched),
            parser_personen_ids=' | '.join(e['person_id'] for e in matched),
            quell_url=(f"https://dserver.bundestag.de/btp/{hit['wahlperiode']}/"
                       f"{hit['file']}"),
            protokolltext=hit['text'], pruefung='offen',
            entscheidung='', korrekte_personen='', bemerkung=''))
    order = {'hoch': 0, 'mittel': 1, 'niedrig': 2}
    return sorted(rows, key=lambda x: (order[x['prioritaet']], int(x['sitzung']), int(x['xml_zeile'])))


def save_quality_report(path, reviews, events, protocol_count):
    """Coverage and triage ONLY. Never present raw parser events as verified."""
    by_priority = defaultdict(int)
    by_class = defaultdict(int)
    for row in reviews:
        by_priority[row['prioritaet']] += 1
        by_class[row['klassifikation']] += 1
    report = {
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
    args = ap.parse_args()
    paths = sorted(args.folder.rglob('*.xml'))
    if not paths:
        ap.error('No XML files found')
    # Create a shared index from ALL sessions; it substantially improves name
    # matching without downloading a separate or version-changing identity file.
    index = speaker_index(document(path) for path in paths)
    hits, sanctions, sessions = [], [], []
    for path in paths:
        root = document(path)
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
              'issuer','issuer_evidence'], sanctions)
    save_csv(args.summary_out, ['wahlperiode','sitzung','datum','datei','quelle',
                                'textfundstellen','erkannte_personenereignisse','status'], sessions)
    reviews = build_review_queue(hits, sanctions)
    save_csv(args.review_out, ['pruef_id','prioritaet','grund','wahlperiode','sitzung',
                               'datei','xml_zeile','klassifikation','parser_personenzahl',
                               'parser_personen','parser_personen_ids','quell_url',
                               'protokolltext','pruefung','entscheidung',
                               'korrekte_personen','bemerkung'], reviews)
    save_quality_report(args.quality_out, reviews, sanctions, len(paths))
    by_class = defaultdict(int)
    for hit in hits:
        by_class[hit['classification']] += 1
    print(f'{len(hits)} Kandidaten; {len(sanctions)} PERSONENBEZOGENE PRUEFFÄLLE; '
          f'{len(paths)} Protokolle. Noch keine amtliche Statistik.')
    print('Klassen:', dict(sorted(by_class.items())))
    print(f'Dateien: {args.out}, {args.events_out}, {args.summary_out}, {args.review_out}, {args.quality_out}.')


if __name__ == '__main__':
    main()
