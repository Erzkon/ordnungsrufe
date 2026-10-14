"""Provisional EVENT register, separate from the legacy person-based extraction.

IMPORTANT: These are unverified text-derived hypotheses, not official counts.
One event represents one apparent issuing decision (potentially several people).
A later list confirming a group decision is supporting evidence, not a second
sanction. Near repetitions are REVIEW FLAGS, never silently collapsed.
"""

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from parser import _grant_scopes, persons_for_grant, speaker_index, document, normal

EVENT_COLUMNS = [
    'ereignis_id', 'wahlperiode', 'sitzung', 'datum', 'datei', 'xml_zeile',
    'ereignisstatus', 'ereignisart', 'gruppenvorgang', 'mehrere_formulierungen',
    'ordnungsruf_nummer', 'empfaenger_anzahl_ungeprueft', 'empfaenger_zuordnung',
    'weitere_belegzeilen', 'zusatzbeleg_text', 'pruefprioritaet', 'pruefgrund', 'quell_url',
    'originaltext', 'pruefung', 'entscheidung', 'bemerkung',
]
RECIPIENT_COLUMNS = [
    'ereignis_id', 'person', 'person_id', 'fraktion', 'identity_status',
    'zuordnungsmethode', 'zuordnungs_belegzeile', 'status', 'pruefung',
]
DUPLICATE_COLUMNS = [
    'vorgang_id_1', 'vorgang_id_2', 'wahlperiode', 'sitzung',
    'zeile_1', 'zeile_2', 'abstand_xml_zeilen', 'prueftyp',
    'hinweis', 'aktion', 'pruefung', 'entscheidung',
]


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, columns, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def is_group_grant(text):
    return bool(re.search(
        r'\ballen\s+Abgeordneten\b|\b(?:den|die)\s+Abgeordneten\b.{0,130}'
        r'\b(?:jeweils\s+)?(?:einen\s+)?Ordnungsruf\b|'
        r'\bOrdnungsrufe\s+gehen\s+an\b', text, re.I))


def ordinal(text):
    """A *new* second/third/further sanction may be independent."""
    if re.search(r'\b(?:zweiten|zweiter|zweites)\s+Ordnungsruf', text, re.I):
        return 'zweiter'
    if re.search(r'\b(?:dritten|dritter|drittes)\s+Ordnungsruf', text, re.I):
        return 'dritter'
    if re.search(r'\b(?:weiteren|weiterer|noch\s+einen)\s+Ordnungsruf', text, re.I):
        return 'weiterer'
    return ''


def person_key(person):
    return (person.get('person_id') or person.get('person', '')).strip().casefold()


def _legacy_recipients(people_by_line, hit):
    return [dict(person=row['person'], person_id=row.get('person_id', ''),
                 fraktion=row.get('fraktion', ''),
                 identity_status=row.get('identity_status', ''),
                 zuordnungsmethode=row.get('zuordnungsmethode', ''),
                 zuordnungs_belegzeile=str(hit['line']))
            for row in people_by_line.get((hit['file'], str(hit['line'])), [])]


def split_unambiguous_grants(text, index):
    """Split only clear, separate utterances addressed to distinct people.

    Unresolved, overlapping or repeated utterances stay ONE flagged candidate;
    guessing a separate sanction would be worse than manual review.
    """
    scopes = _grant_scopes(text)
    if len(scopes) < 2 or index is None:
        return None
    scoped_people = []
    for scope in scopes:
        found = persons_for_grant(scope, index)
        if len(found) != 1:
            return None
        scoped_people.append(found[0])
    ordered = sorted(zip(scopes, scoped_people), key=lambda pair: text.find(pair[0]))
    keys = [person_key(row) for _, row in ordered]
    if len(set(keys)) == len(keys):
        return ordered
    # Two distinct penalties for the same person in the *same* paragraph
    # require an explicitly numbered follow-up (not mere repeated wording).
    if (len(ordered) == 2 and keys[0] == keys[1] and
            not ordinal(ordered[0][0]) and ordinal(ordered[1][0])):
        return ordered
    return None


def build_register(hits, legacy_people, index=None):
    """Pure event construction: return events, recipients, relation-review rows.

    `hits` and `legacy_people` are existing parser outputs; the optional
    cross-session speaker index permits SAFE splitting of distinct addresses.
    """
    hits = sorted(hits, key=lambda row: (
        int(row['wahlperiode']), int(row['sitzung']), int(row['line'])))
    people_by_line = defaultdict(list)
    for row in legacy_people:
        people_by_line[(row['file'], str(row['line']))].append(row)
    events, recipients, relations = [], [], []
    named_confirmations = []
    by_event = {}

    def add_event(hit, number, text, recipient_rows, multi_formulas=False, subtype='erteilungskandidat'):
        event_id = f"{hit['wahlperiode']}-{int(hit['sitzung']):03d}-{hit['line']}-{number:02d}"
        unique, seen = [], set()
        for person in recipient_rows:
            key = person_key(person)
            if key and key not in seen:
                unique.append(person)
                seen.add(key)
        group = is_group_grant(text) or len(unique) > 1
        reasons = []
        if not unique:
            reasons.append('Keine sicher erkannte empfangende Person')
        if multi_formulas:
            reasons.append('Mehrere Vergabeformulierungen im selben Absatz: Anzahl manuell pruefen')
        if group:
            reasons.append('Gruppenmassnahme: jede betroffene Person und die Anzahl pruefen')
        if ordinal(text):
            reasons.append('Ausdruecklich weiterer Ordnungsruf: gegen fruehere Massnahme abgrenzen')
        if any(p.get('identity_status') != 'matched_xml_person' for p in unique):
            reasons.append('Nicht eindeutiger Abgleich mit XML-Person')
        if not reasons:
            reasons.append('Wortlaut und erstmalige Erteilung pruefen')
        event = dict(
            ereignis_id=event_id, wahlperiode=hit['wahlperiode'], sitzung=hit['sitzung'],
            datum=hit.get('datum', ''), datei=hit['file'], xml_zeile=hit['line'],
            ereignisstatus='review_required', ereignisart=subtype,
            gruppenvorgang='ja' if group else 'nein',
            mehrere_formulierungen='ja' if multi_formulas else 'nein',
            ordnungsruf_nummer=ordinal(text), empfaenger_anzahl_ungeprueft=len(unique),
            empfaenger_zuordnung='offen' if not unique else 'parser_zugeordnet_ungeprueft',
            weitere_belegzeilen='', zusatzbeleg_text='', pruefprioritaet='hoch' if (
                not unique or multi_formulas or group or ordinal(text) or
                any(p.get('identity_status') != 'matched_xml_person' for p in unique)) else 'mittel',
            pruefgrund='; '.join(reasons),
            quell_url=f"https://dserver.bundestag.de/btp/{hit['wahlperiode']}/{hit['file']}",
            originaltext=text, pruefung='offen', entscheidung='', bemerkung='')
        events.append(event)
        by_event[event_id] = event
        for person in unique:
            recipients.append(dict(ereignis_id=event_id, **person,
                                   status='review_required', pruefung='offen'))
        return event

    for hit in hits:
        classification = hit['classification']
        if classification == 'named_group_confirmation':
            named_confirmations.append(hit)
            continue
        if classification != 'possible_grant':
            continue
        text = hit['text']
        scopes = _grant_scopes(text)
        split = split_unambiguous_grants(text, index)
        if split:
            for n, (scope, identified) in enumerate(split, 1):
                assigned = {**identified, 'zuordnungsmethode':
                            identified.get('zuordnungsmethode', 'getrennte_direkte_erteilung'),
                            'zuordnungs_belegzeile': str(hit['line'])}
                add_event(hit, n, scope, [assigned],
                          subtype='getrennte_erteilung_im_absatz')
        else:
            legacy = _legacy_recipients(people_by_line, hit)
            add_event(hit, 1, text, legacy, multi_formulas=len(scopes) > 1)

    # A later named roll-call is EVIDENCE for an earlier clearly anonymous
    # group grant, not a new event. Only link if exactly ONE plausible prior
    # group candidate in the same session and in a bounded document distance.
    for hit in named_confirmations:
        line = int(hit['line'])
        plausible = [e for e in events if e['wahlperiode'] == hit['wahlperiode']
                     and e['sitzung'] == hit['sitzung']
                     and 0 < line - int(e['xml_zeile']) <= 350
                     and e['gruppenvorgang'] == 'ja'
                     and int(e['empfaenger_anzahl_ungeprueft']) == 0]
        verified_link = len(plausible) == 1
        group_people = _legacy_recipients(people_by_line, hit)
        if verified_link:
            event = plausible[0]
            event_id = event['ereignis_id']
            event['weitere_belegzeilen'] = str(hit['line'])
            event['zusatzbeleg_text'] = hit['text']
            event['empfaenger_zuordnung'] = 'nachtraegliche_namensliste_ungeprueft'
            event['pruefgrund'] = event['pruefgrund'].replace(
                'Keine sicher erkannte empfangende Person; ', '').replace(
                'Keine sicher erkannte empfangende Person', '').strip('; ')
            event['pruefgrund'] += '; Namentliche Bestaetigung zu frueherer Gruppenmassnahme pruefen'
            seen_group = set()
            group_people = [p for p in group_people if not (person_key(p) in seen_group or seen_group.add(person_key(p)))]
            event['empfaenger_anzahl_ungeprueft'] = len(group_people)
            for person in group_people:
                recipients.append(dict(ereignis_id=event_id, **person,
                                       status='review_required', pruefung='offen'))
            relations.append(dict(
                vorgang_id_1=event_id, vorgang_id_2=(
                    f"{hit['wahlperiode']}-{int(hit['sitzung']):03d}-{hit['line']}-beleg"),
                wahlperiode=hit['wahlperiode'], sitzung=hit['sitzung'],
                zeile_1=event['xml_zeile'], zeile_2=hit['line'],
                abstand_xml_zeilen=line - int(event['xml_zeile']),
                prueftyp='namensliste_als_beleg_verknuepft',
                hinweis='Einzige nahe anonyme Gruppenvergabe: spaetere Namensliste '
                        'als Beleg zugeordnet; Originaltexte vergleichen',
                aktion='beleg_zugeordnet_aber_manuelle_pruefung_offen',
                pruefung='offen', entscheidung=''))
        else:
            # Avoid silently throwing away an otherwise informative roll-call.
            standalone = add_event(hit, 1, hit['text'], group_people,
                                   subtype='namensliste_ohne_eindeutige_vorherige_erteilung')
            standalone['pruefprioritaet'] = 'hoch'
            standalone['pruefgrund'] += '; Vorherige Gruppenvergabe nicht eindeutig verknuepfbar'

    # Flag neighboring repetitions. Do NOT automatically remove either event.
    # XML line proximity is only a review heuristic, not proof of identity.
    by_session = defaultdict(list)
    for event in events:
        by_session[(event['wahlperiode'], event['sitzung'])].append(event)
    people_keys = defaultdict(set)
    for person in recipients:
        people_keys[person['ereignis_id']].add(person_key(person))
    for (_, _), session_events in by_session.items():
        session_events.sort(key=lambda e: (int(e['xml_zeile']), e['ereignis_id']))
        for idx, a in enumerate(session_events):
            for b in session_events[idx+1:]:
                distance = int(b['xml_zeile']) - int(a['xml_zeile'])
                if distance > 12:
                    break
                if a['ereignis_id'] == b['ereignis_id']:
                    continue
                pa, pb = people_keys[a['ereignis_id']], people_keys[b['ereignis_id']]
                if pa and pb and pa.isdisjoint(pb):
                    continue  # Explicitly different recipients.
                if distance == 0:
                    continue  # Already split as distinct recipients in one paragraph.
                if ordinal(b['originaltext']):
                    typ = 'ausdruecklich_weiterer_ordnungsruf'
                    msg = 'Spaetere Formulierung sagt zweiter/weiterer: getrennte Massnahme moeglich; NICHT automatisch zusammenlegen'
                else:
                    typ = 'moegliche_wiederholung'
                    msg = 'Nahe Vergabeformulierungen: identische oder unbekannte Empfaenger; gleiche Massnahme oder zwei Vergaben?'
                relations.append(dict(
                    vorgang_id_1=a['ereignis_id'], vorgang_id_2=b['ereignis_id'],
                    wahlperiode=a['wahlperiode'], sitzung=a['sitzung'],
                    zeile_1=a['xml_zeile'], zeile_2=b['xml_zeile'],
                    abstand_xml_zeilen=distance, prueftyp=typ, hinweis=msg,
                    aktion='nicht_automatisch_zusammengelegt',
                    pruefung='offen', entscheidung=''))
                a['pruefprioritaet'] = 'hoch'
                b['pruefprioritaet'] = 'hoch'
                flag = 'Moegliche unmittelbare Wiederholung: Dublettenpruefung beachten'
                for e in (a, b):
                    if flag not in e['pruefgrund']:
                        e['pruefgrund'] += '; ' + flag

    return events, recipients, relations


def quality_summary(events, recipients, relations, hits):
    counts = defaultdict(int)
    for rel in relations:
        counts[rel['prueftyp']] += 1
    return {
        'hinweis': 'UNGEPRUEFTE Ereignishypothesen, KEINE amtlichen Ordnungsrufzahlen.',
        'textfundstellen': len(hits),
        'ereigniskandidaten_ungeprueft': len(events),
        'personen_zuordnungen_ungeprueft': len(recipients),
        'ereignisse_ohne_person': sum(not e['empfaenger_anzahl_ungeprueft'] for e in events),
        'mehrfachformeln_im_absatz_zur_pruefung': sum(
            e['mehrere_formulierungen'] == 'ja' for e in events),
        'dubletten_und_belegbeziehungen_nach_typ': dict(sorted(counts.items())),
        'ereignisse_mit_pruefung_abgeschlossen': 0,
    }


def main():
    ap = argparse.ArgumentParser(description='Ungeprueftes Ereignisregister mit Dublettenpruefung')
    ap.add_argument('--candidates', type=Path, default=Path('kandidaten.csv'))
    ap.add_argument('--people', type=Path, default=Path('ordnungsrufe.csv'))
    ap.add_argument('--source-folder', type=Path, default=Path('protokolle'))
    ap.add_argument('--out', type=Path, default=Path('ereignisse.csv'))
    ap.add_argument('--recipients-out', type=Path, default=Path('ereignis_empfaenger.csv'))
    ap.add_argument('--duplicates-out', type=Path, default=Path('dubletten_pruefung.csv'))
    ap.add_argument('--report-out', type=Path, default=Path('ereignisbericht.json'))
    args = ap.parse_args()
    hits = read_csv(args.candidates)
    people = read_csv(args.people)
    sources = sorted(args.source_folder.rglob('*.xml')) if args.source_folder.exists() else []
    index = speaker_index(document(path) for path in sources) if sources else None
    register, recipients, relations = build_register(hits, people, index=index)
    write_csv(args.out, EVENT_COLUMNS, register)
    write_csv(args.recipients_out, RECIPIENT_COLUMNS, recipients)
    write_csv(args.duplicates_out, DUPLICATE_COLUMNS, relations)
    report = quality_summary(register, recipients, relations, hits)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"Ereigniskandidaten: {len(register)}; Personen-Zuordnungen: {len(recipients)}; "
          f"Pruefbeziehungen: {len(relations)}. ALLE UNGEPRUEFT.")


if __name__ == '__main__':
    main()
