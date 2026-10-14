"""Human-review gate for Bundestag order-of-call candidates.

Only explicit human review records can produce verified person sanctions.
The review inputs in the repository are NEVER written or modified here.
No automated finding (including an XML speaker match) is a verification.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from ereignis_register import read_csv, write_csv

EVENT_DECISION_COLUMNS = [
    'ereignis_id', 'quelle_fingerabdruck', 'entscheidung',
    'empfaengerliste_vollstaendig', 'dublette_von', 'beleg', 'kommentar',
]
PERSON_DECISION_COLUMNS = [
    'ereignis_id', 'person_id', 'person', 'fraktion_zur_sitzung',
    'entscheidung', 'beleg', 'kommentar',
]
RELATION_DECISION_COLUMNS = [
    'vorgang_id_1', 'vorgang_id_2', 'entscheidung', 'beleg', 'kommentar',
]
EVENT_TEMPLATE_COLUMNS = EVENT_DECISION_COLUMNS + [
    'datum', 'wahlperiode', 'sitzung', 'datei', 'xml_zeile', 'quell_url',
    'parser_personen', 'originaltext', 'pruefgrund',
]
PERSON_TEMPLATE_COLUMNS = PERSON_DECISION_COLUMNS + [
    'datum', 'fraktion_parser_ungeprueft', 'identity_status',
    'quell_url', 'originaltext',
]
RELATION_TEMPLATE_COLUMNS = RELATION_DECISION_COLUMNS + [
    'prueftyp', 'sitzung', 'zeile_1', 'zeile_2', 'hinweis',
]
VERIFIED_COLUMNS = [
    'ereignis_id', 'datum', 'wahlperiode', 'sitzung', 'person_id', 'person',
    'fraktion_zur_sitzung', 'quell_url', 'beleg',
]
EVENT_CHOICES = {'bestaetigt', 'keine_erteilung', 'dublette', 'unklar'}
PERSON_CHOICES = {'bestaetigt', 'nicht_betroffen', 'unklar'}
RELATION_CHOICES = {
    'gleiche_massnahme', 'getrennte_massnahmen', 'beleg_bestaetigt',
    'beleg_nicht_zuordenbar', 'unklar',
}
SOURCE_FIELDS = [
    'wahlperiode', 'sitzung', 'datum', 'datei', 'xml_zeile', 'originaltext',
    'zusatzbeleg_text', 'weitere_belegzeilen', 'gruppenvorgang',
    'mehrere_formulierungen', 'ordnungsruf_nummer', 'ereignisart', 'quell_url',
]


class ReviewError(ValueError):
    """Unsafe/invalid review input: fail closed, not a published statistic."""


def _require(condition, message):
    if not condition:
        raise ReviewError(message)


def _unique(rows, keys, label):
    data = {}
    for row in rows:
        key = tuple(row.get(column, '').strip() for column in keys)
        _require(all(key), f'{label}: unvollstaendiger Schluessel {key}')
        _require(key not in data, f'{label}: doppelte Entscheidung {key}')
        data[key] = row
    return data


def _read_decisions(directory, name, columns):
    path = Path(directory) / name
    _require(path.is_file(), f'Entscheidungsdatei fehlt: {path}')
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        _require(reader.fieldnames is not None, f'CSV-Kopfzeile fehlt: {path}')
        missing = set(columns) - set(reader.fieldnames)
        _require(not missing, f'CSV-Spalten fehlen in {path}: {sorted(missing)}')
        return [{k: (v or '').strip() for k, v in row.items() if k is not None}
                for row in reader]


def fingerprint(event, recipients):
    """Digest of source AND parser grouping for this event; deliberate fail-closed drift."""
    snapshot = {
        'source': {field: str(event.get(field, '')) for field in SOURCE_FIELDS},
        'suggested_recipients': sorted([
            {key: str(row.get(key, '')) for key in
             ('person_id', 'person', 'fraktion', 'zuordnungs_belegzeile')}
            for row in recipients
        ], key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True)),
    }
    canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return 'sha256:' + hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _validate_date(value, event_id):
    try:
        dt = datetime.strptime(value, '%d.%m.%Y')
        _require(dt.strftime('%d.%m.%Y') == value, f'{event_id}: Datum unplausibel: {value}')
    except ValueError as exc:
        raise ReviewError(f'{event_id}: ungueltiges Sitzungsdatum {value!r}') from exc


def _normalize_relation_key(a, b):
    return tuple(sorted((a, b)))


def verify(events, candidates, relations, sessions, event_decisions,
           person_decisions, relation_decisions):
    """Pure, conservative review evaluation. Returns review templates & outputs.

    Decisions are human-authored, never prepopulated/approved from parser data.
    A verified event requires full confirmed recipient list, resolved relations,
    intact source fingerprint and source/date presence.
    """
    event_map = {key[0]: row for key, row in
                 _unique(events, ['ereignis_id'], 'Ereignisregister').items()}
    sessions_by_key = _unique(sessions, ['wahlperiode', 'sitzung'], 'Sitzungen')
    suggested = defaultdict(list)
    for row in candidates:
        _require(row['ereignis_id'] in event_map,
                 f'Parserempfaenger ohne Ereignis: {row["ereignis_id"]}')
        suggested[row['ereignis_id']].append(row)

    e_review = _unique(event_decisions, ['ereignis_id'], 'Ereignisentscheidung')
    p_review = _unique(person_decisions, ['ereignis_id', 'person_id'], 'Personenentscheidung')
    r_review = {}
    for row in relation_decisions:
        key = _normalize_relation_key(row.get('vorgang_id_1', ''), row.get('vorgang_id_2', ''))
        _require(all(key) and key[0] != key[1], f'Ungueltiges Beziehungspaar: {key}')
        _require(key not in r_review, f'Doppelte Beziehungsentscheidung: {key}')
        r_review[key] = row

    relation_map = {}
    for row in relations:
        key = _normalize_relation_key(row['vorgang_id_1'], row['vorgang_id_2'])
        _require(key not in relation_map, f'Doppelte Beziehung im Register: {key}')
        relation_map[key] = row
        _require(row['vorgang_id_1'] in event_map,
                 f'Beziehung mit unbekannter erster Ereignis-ID: {key}')
        if row['prueftyp'] == 'namensliste_als_beleg_verknuepft':
            _require(row['vorgang_id_2'].endswith('-beleg'),
                     f'Beziehung: erwartet eindeutige Beleg-ID: {key}')
        else:
            _require(row['vorgang_id_2'] in event_map,
                     f'Beziehung mit unbekannter zweiter Ereignis-ID: {key}')

    for key in r_review:
        _require(key in relation_map, f'Beziehungsentscheidung ohne aktuellen Registereintrag: {key}')
    for key, decision in e_review.items():
        _require(key[0] in event_map, f'Veraltete/unbekannte Ereignisentscheidung: {key[0]}')
        _require(decision['entscheidung'] in EVENT_CHOICES,
                 f'{key[0]}: ungueltige Ereignisentscheidung')
        _require(decision['quelle_fingerabdruck'] == fingerprint(event_map[key[0]], suggested[key[0]]),
                 f'{key[0]}: QUELLEN-AENDERUNG! Fingerabdruck passt nicht; Entscheidung manuell neu pruefen')
        _require(decision['beleg'], f'{key[0]}: Quelle/Beleg muss manuell dokumentiert werden')
        if decision['entscheidung'] == 'bestaetigt':
            _require(decision['empfaengerliste_vollstaendig'] == 'ja',
                     f'{key[0]}: bestaetigt erfordert empfaengerliste_vollstaendig=ja')
            _require(not decision['dublette_von'], f'{key[0]}: bestaetigter Fall darf keine Dublette sein')
        elif decision['entscheidung'] == 'dublette':
            other = decision['dublette_von']
            _require(other in event_map and other != key[0],
                     f'{key[0]}: Dublette verweist auf ungueltiges Ziel {other!r}')
            _require((event_map[other]['wahlperiode'], event_map[other]['sitzung']) ==
                     (event_map[key[0]]['wahlperiode'], event_map[key[0]]['sitzung']),
                     f'{key[0]}: Dublette muss in derselben Sitzung liegen')
            _require(decision['empfaengerliste_vollstaendig'] != 'ja',
                     f'{key[0]}: Dubletten nicht als vollstaendig bestaetigt kennzeichnen')
        else:
            _require(not decision['dublette_von'],
                     f'{key[0]}: dublette_von nur bei entscheidung=dublette')
            _require(decision['empfaengerliste_vollstaendig'] != 'ja',
                     f'{key[0]}: keine Freigabe der Empfaengerliste ohne Bestaetigung')

    for (eid, pid), row in p_review.items():
        _require(eid in event_map, f'Personenentscheidung: unbekanntes Ereignis {eid}')
        _require(row['entscheidung'] in PERSON_CHOICES,
                 f'{eid}/{pid}: ungueltige Personenentscheidung')
        _require(row['person'] and row['beleg'], f'{eid}/{pid}: Name und Beleg fehlen')
        _require(bool(re.fullmatch(r'\d{8}', pid)),
                 f'{eid}/{pid}: Person-ID muss eine 8-stellige Bundestags-ID sein')
        if row['entscheidung'] == 'bestaetigt':
            _require(row['fraktion_zur_sitzung'],
                     f'{eid}/{pid}: historische Fraktion/Fraktionslosigkeit muss manuell bestaetigt sein')
        _require((eid,) in e_review,
                 f'{eid}/{pid}: Personenentscheidung ohne Ereignisentscheidung')
        _require(e_review[(eid,)]['entscheidung'] == 'bestaetigt',
                 f'{eid}/{pid}: Personenentscheidung zu nicht bestaetigtem Ereignis')

    for key, row in r_review.items():
        rel = relation_map[key]
        d = row['entscheidung']
        _require(d in RELATION_CHOICES, f'{key}: ungueltige Beziehungsentscheidung')
        _require(row['beleg'], f'{key}: Beleg fehlt')
        if rel['prueftyp'] == 'namensliste_als_beleg_verknuepft':
            _require(d in {'beleg_bestaetigt', 'beleg_nicht_zuordenbar', 'unklar'},
                     f'{key}: unpassende Entscheidung fuer Namensliste')
        else:
            _require(d in {'gleiche_massnahme', 'getrennte_massnahmen', 'unklar'},
                     f'{key}: unpassende Entscheidung fuer Dublettenpaar')
        if d == 'gleiche_massnahme':
            ids = (rel['vorgang_id_1'], rel['vorgang_id_2'])
            _require(sum(e_review.get((eid,), {}).get('entscheidung') == 'dublette' and
                         e_review[(eid,)]['dublette_von'] in ids for eid in ids) == 1,
                     f'{key}: gleiche_massnahme verlangt exakt ein Ereignis als Dublette des anderen')
        if d == 'getrennte_massnahmen':
            ids = (rel['vorgang_id_1'], rel['vorgang_id_2'])
            _require(not any(e_review.get((eid,), {}).get('entscheidung') == 'dublette' and
                             e_review[(eid,)]['dublette_von'] in ids for eid in ids),
                     f'{key}: getrennte_massnahmen widerspricht Dublettenentscheidung')

    for (eid,), row in e_review.items():
        if row['entscheidung'] == 'dublette':
            target = row['dublette_von']
            pair = _normalize_relation_key(eid, target)
            _require(pair in relation_map and relation_map[pair]['prueftyp'] != 'namensliste_als_beleg_verknuepft',
                     f'{eid}: Dublette muss als Beziehung im Import dokumentiert sein')
            _require(r_review.get(pair, {}).get('entscheidung') == 'gleiche_massnahme',
                     f'{eid}: Dublette erfordert bestaetigte Entscheidung gleiche_massnahme')
            _require(e_review.get((target,), {}).get('entscheidung') in {'bestaetigt', 'unklar'},
                     f'{eid}: Dubletten-Ziel darf nicht selbst Dublette/verworfener Fall sein')

    touching = defaultdict(list)
    for pair, rel in relation_map.items():
        touching[rel['vorgang_id_1']].append((pair, rel))
        if rel['vorgang_id_2'] in event_map:
            touching[rel['vorgang_id_2']].append((pair, rel))

    blocked = defaultdict(list)
    for (eid,), decision in e_review.items():
        if decision['entscheidung'] != 'bestaetigt':
            continue
        event = event_map[eid]
        session = sessions_by_key.get((event['wahlperiode'], event['sitzung']))
        _require(session is not None, f'{eid}: Sitzung fehlt in sitzungen.csv')
        _require(event['datum'] and event['datum'] == session['datum'],
                 f'{eid}: Ereignisdatum passt nicht zur Sitzung')
        _validate_date(event['datum'], eid)
        for pair, rel in touching[eid]:
            d = r_review.get(pair, {}).get('entscheidung', '')
            allowed = ({'beleg_bestaetigt'} if rel['prueftyp'] == 'namensliste_als_beleg_verknuepft'
                       else {'gleiche_massnahme', 'getrennte_massnahmen'})
            if d not in allowed:
                blocked[eid].append(f'Offene/widerspruechliche Beziehung: {pair}')
            if d == 'gleiche_massnahme':
                other = rel['vorgang_id_2'] if rel['vorgang_id_1'] == eid else rel['vorgang_id_1']
                if e_review.get((other,), {}).get('entscheidung') != 'dublette':
                    blocked[eid].append(f'Gleiche Massnahme ohne bereinigte Dublette: {pair}')
        persons = [row for (other, _), row in p_review.items() if other == eid]
        confirmed = [row for row in persons if row['entscheidung'] == 'bestaetigt']
        if not confirmed:
            blocked[eid].append('Kein explizit bestaetigter Empfaenger mit Person-ID')
        if any(row['entscheidung'] == 'unklar' for row in persons):
            blocked[eid].append('Ungeklaerte einzelne Personenentscheidung')

    verified = []
    for (eid, pid), person in sorted(p_review.items()):
        if person['entscheidung'] != 'bestaetigt' or eid in blocked:
            continue
        event = event_map[eid]
        verified.append({
            'ereignis_id': eid, 'datum': event['datum'], 'wahlperiode': event['wahlperiode'],
            'sitzung': event['sitzung'], 'person_id': pid, 'person': person['person'],
            'fraktion_zur_sitzung': person['fraktion_zur_sitzung'],
            'quell_url': event['quell_url'], 'beleg': person['beleg'],
        })

    event_templates = []
    for eid, event in sorted(event_map.items(), key=lambda item: (
            int(item[1]['wahlperiode']), int(item[1]['sitzung']), int(item[1]['xml_zeile']), item[0])):
        review = e_review.get((eid,), {})
        row = {column: review.get(column, '') for column in EVENT_DECISION_COLUMNS}
        row.update({'ereignis_id': eid, 'quelle_fingerabdruck': fingerprint(event, suggested[eid]),
                    'datum': event['datum'], 'wahlperiode': event['wahlperiode'],
                    'sitzung': event['sitzung'], 'datei': event['datei'],
                    'xml_zeile': event['xml_zeile'], 'quell_url': event['quell_url'],
                    'parser_personen': '; '.join(p['person'] for p in suggested[eid]),
                    'originaltext': event['originaltext'], 'pruefgrund': event['pruefgrund']})
        event_templates.append(row)

    person_templates = []
    for row in sorted(candidates, key=lambda p: (p['ereignis_id'], p['person_id'], p['person'])):
        event = event_map[row['ereignis_id']]
        review = p_review.get((row['ereignis_id'], row['person_id']), {})
        out = {column: review.get(column, '') for column in PERSON_DECISION_COLUMNS}
        out.update({
            'ereignis_id': row['ereignis_id'], 'person_id': row['person_id'],
            'person': review.get('person', row['person']), 'datum': event['datum'],
            'fraktion_parser_ungeprueft': row['fraktion'],
            'identity_status': row['identity_status'], 'quell_url': event['quell_url'],
            'originaltext': event['originaltext'],
        })
        person_templates.append(out)

    # Human-corrected recipients must remain visible even if the parser did not
    # suggest them (e.g., a pronoun-only order later resolved from context).
    parser_keys = {(row['ereignis_id'], row['person_id']) for row in candidates}
    for (eid, pid), review in sorted(p_review.items()):
        if (eid, pid) in parser_keys:
            continue
        event = event_map[eid]
        out = {column: review.get(column, '') for column in PERSON_DECISION_COLUMNS}
        out.update({'ereignis_id': eid, 'person_id': pid, 'datum': event['datum'],
                    'fraktion_parser_ungeprueft': '',
                    'identity_status': 'manuell_zugeordnet',
                    'quell_url': event['quell_url'],
                    'originaltext': event['originaltext']})
        person_templates.append(out)

    relation_templates = []
    for key, rel in sorted(relation_map.items()):
        review = r_review.get(key, {})
        out = {column: review.get(column, '') for column in RELATION_DECISION_COLUMNS}
        out.update({'vorgang_id_1': rel['vorgang_id_1'],
                    'vorgang_id_2': rel['vorgang_id_2'],
                    'prueftyp': rel['prueftyp'], 'sitzung': rel['sitzung'],
                    'zeile_1': rel['zeile_1'], 'zeile_2': rel['zeile_2'],
                    'hinweis': rel['hinweis']})
        relation_templates.append(out)

    reviewed_names = defaultdict(set)
    for item in verified:
        reviewed_names[item['person_id']].add(item['person'])
    for pid, names in reviewed_names.items():
        _require(len(names) == 1,
                 f'{pid}: widerspruechliche bestaetigte Personennamen: {sorted(names)}')
    people_total = Counter(r['person_id'] for r in verified)
    parties_total = Counter(r['fraktion_zur_sitzung'] for r in verified)
    event_statuses = Counter(row['entscheidung'] for row in event_decisions)
    stats = {
        'stand': 'Ausschliesslich manuell verifizierte Einzelfaelle; KEINE vollstaendige amtliche Statistik',
        'gesamtzahl_verifizierter_personenmassnahmen': len(verified),
        'anzahl_ereignisse_mit_verifizierten_massnahmen': len(set(v['ereignis_id'] for v in verified)),
        'vollstaendigkeit_aller_ordnungsrufe_bestaetigt': False,
        'nach_person': [
            {'person_id': pid, 'person': next(r['person'] for r in verified if r['person_id'] == pid),
             'anzahl': amount}
            for pid, amount in sorted(people_total.items())],
        'nach_fraktion_zum_zeitpunkt': [
            {'fraktion': party, 'anzahl': amount} for party, amount in sorted(parties_total.items())],
    }
    report = {
        'hinweis': 'Ohne explizite manuelle Freigabe werden keine Ereignisse als bestaetigt gezaehlt.',
        'ereigniskandidaten': len(events),
        'ereignisentscheidungen': len(event_decisions),
        'ereignisse_offen_ohne_entscheidung': len(events) - len(event_decisions),
        'ereignisentscheidungen_nach_typ': dict(sorted(event_statuses.items())),
        'personenentscheidungen': len(person_decisions),
        'beziehungen': len(relations),
        'beziehungen_offen_ohne_entscheidung': len(relations) - len(relation_decisions),
        'manuell_bestaetigte_ereignisse_wegen_offener_beziehungen_oder_personen_blockiert': len(blocked),
        'blockierte_ereignisse': {key: val for key, val in sorted(blocked.items())},
        'zaehlbare_bestaetigte_personenmassnahmen': len(verified),
        'gesamterhebung_abgeschlossen': False,
        'warnung': '0 bestaetigte Faelle bedeutet NICHT 0 erteilte Ordnungsrufe.',
    }
    return {
        'vorlage_ereignisse': event_templates, 'vorlage_personen': person_templates,
        'vorlage_beziehungen': relation_templates, 'verifiziert': verified,
        'statistik': stats, 'bericht': report,
    }


def generate(args):
    events = read_csv(args.events)
    suggested = read_csv(args.recipients)
    relations = read_csv(args.relations)
    sessions = read_csv(args.sessions)
    decision_directory = Path(args.decisions)
    e = _read_decisions(decision_directory, 'ereignisse.csv', EVENT_DECISION_COLUMNS)
    p = _read_decisions(decision_directory, 'personen.csv', PERSON_DECISION_COLUMNS)
    r = _read_decisions(decision_directory, 'beziehungen.csv', RELATION_DECISION_COLUMNS)
    result = verify(events, suggested, relations, sessions, e, p, r)
    destination = Path(args.out_folder)
    write_csv(destination / 'pruefvorlage_ereignisse.csv', EVENT_TEMPLATE_COLUMNS, result['vorlage_ereignisse'])
    write_csv(destination / 'pruefvorlage_personen.csv', PERSON_TEMPLATE_COLUMNS, result['vorlage_personen'])
    write_csv(destination / 'pruefvorlage_beziehungen.csv', RELATION_TEMPLATE_COLUMNS, result['vorlage_beziehungen'])
    write_csv(destination / 'bestaetigte_ordnungsrufe.csv', VERIFIED_COLUMNS, result['verifiziert'])
    for name, data in [('bestaetigte_statistik.json', result['statistik']),
                       ('verifikationsbericht.json', result['bericht'])]:
        (destination / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    p = argparse.ArgumentParser(description='Manuell verifizierbare Ordnungsruf-Statistik, ohne automatische Freigabe')
    p.add_argument('--events', type=Path, default=Path('ereignisse.csv'))
    p.add_argument('--recipients', type=Path, default=Path('ereignis_empfaenger.csv'))
    p.add_argument('--relations', type=Path, default=Path('dubletten_pruefung.csv'))
    p.add_argument('--sessions', type=Path, default=Path('sitzungen.csv'))
    p.add_argument('--decisions', type=Path, default=Path('pruefentscheidungen'))
    p.add_argument('--out-folder', type=Path, default=Path('.'))
    args = p.parse_args()
    result = generate(args)
    print(f"Verifizierte personenbezogene Massnahmen: {len(result['verifiziert'])}; "
          f"offene Ereigniskandidaten: {result['bericht']['ereignisse_offen_ohne_entscheidung']}. "
          'Kein Anspruch auf amtliche Vollstaendigkeit.')


if __name__ == '__main__':
    main()
