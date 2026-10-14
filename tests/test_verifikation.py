"""Regression tests for review gate: fail closed and never infer a sanction."""
import copy
import csv
from pathlib import Path

import pytest

from ereignis_register import build_register
from verifikation import (EVENT_DECISION_COLUMNS, PERSON_DECISION_COLUMNS,
                          RELATION_DECISION_COLUMNS, ReviewError, fingerprint,
                          generate, verify)


def fixture(two=False, relation=False):
    first = dict(
        ereignis_id='20-009-2461-01', wahlperiode='20', sitzung='9',
        datum='16.12.2021', datei='20009.xml', xml_zeile='2461',
        originaltext='Herr Seitz, ich erteile Ihnen einen Ordnungsruf.',
        zusatzbeleg_text='', weitere_belegzeilen='', gruppenvorgang='nein',
        mehrere_formulierungen='nein', ordnungsruf_nummer='',
        ereignisart='erteilungskandidat', quell_url='https://dserver.bundestag.de/btp/20/20009.xml',
        pruefgrund='Pruefung offen',
    )
    people = [dict(ereignis_id=first['ereignis_id'], person='Thomas Seitz',
                   person_id='11004891', fraktion='fraktionslos',
                   zuordnungs_belegzeile='2461', identity_status='matched_xml_person')]
    events = [first]
    relations = []
    if two:
        other = dict(first, ereignis_id='20-009-2465-01', xml_zeile='2465',
                     originaltext='Herr Seitz, ich erteile Ihnen einen weiteren Ordnungsruf.')
        events.append(other)
        people.append(dict(people[0], ereignis_id=other['ereignis_id'], zuordnungs_belegzeile='2465'))
        if relation:
            relations.append(dict(vorgang_id_1=first['ereignis_id'],
                                  vorgang_id_2=other['ereignis_id'],
                                  prueftyp='moegliche_wiederholung',
                                  wahlperiode='20', sitzung='9', zeile_1='2461',
                                  zeile_2='2465', hinweis='Wiederholung?'))
    sessions = [dict(wahlperiode='20', sitzung='9', datum='16.12.2021')]
    return events, people, relations, sessions


def event_review(e, people, decision='bestaetigt', complete='ja', dup=''):
    return dict(ereignis_id=e['ereignis_id'],
                quelle_fingerabdruck=fingerprint(e, [p for p in people if p['ereignis_id'] == e['ereignis_id']]),
                entscheidung=decision, empfaengerliste_vollstaendig=complete,
                dublette_von=dup, beleg=e['quell_url'], kommentar='Manuell geprueft')


def person_review(e):
    return dict(ereignis_id=e['ereignis_id'], person_id='11004891',
                person='Thomas Seitz', fraktion_zur_sitzung='AfD',
                entscheidung='bestaetigt', beleg=e['quell_url'], kommentar='Originalprotokoll geprueft')


def run(fixture_data, er=(), pr=(), rr=()):
    return verify(*fixture_data, list(er), list(pr), list(rr))


def test_zero_manual_decisions_never_become_public_counts():
    data = fixture()
    out = run(data)
    assert out['statistik']['gesamtzahl_verifizierter_personenmassnahmen'] == 0
    assert out['statistik']['vollstaendigkeit_aller_ordnungsrufe_bestaetigt'] is False
    assert len(out['vorlage_ereignisse']) == 1
    assert not out['vorlage_ereignisse'][0]['entscheidung']
    assert not out['vorlage_personen'][0]['entscheidung']
    assert not out['vorlage_personen'][0]['fraktion_zur_sitzung']


def test_reviewed_event_and_person_count_exactly_once_with_historic_party():
    data = fixture()
    out = run(data, [event_review(data[0][0], data[1])], [person_review(data[0][0])])
    assert out['statistik']['gesamtzahl_verifizierter_personenmassnahmen'] == 1
    assert out['verifiziert'][0]['fraktion_zur_sitzung'] == 'AfD'
    assert out['statistik']['nach_fraktion_zum_zeitpunkt'] == [{'fraktion': 'AfD', 'anzahl': 1}]


def test_event_confirmation_without_person_is_not_counted():
    data = fixture()
    out = run(data, [event_review(data[0][0], data[1])])
    assert out['bericht']['manuell_bestaetigte_ereignisse_wegen_offener_beziehungen_oder_personen_blockiert'] == 1
    assert not out['verifiziert']


def test_parser_person_without_human_event_approval_is_not_counted():
    data = fixture()
    with pytest.raises(ReviewError, match='ohne Ereignisentscheidung'):
        run(data, [], [person_review(data[0][0])])


def test_stale_fingerprint_never_silently_reused():
    data = fixture()
    er = event_review(data[0][0], data[1])
    changed = copy.deepcopy(data)
    changed[0][0]['originaltext'] += ' Aenderung am Protokoll.'
    with pytest.raises(ReviewError, match='QUELLEN-AENDERUNG'):
        run(changed, [er], [person_review(data[0][0])])


def test_changed_parser_recipient_mapping_invalidates_review():
    data = fixture()
    er = event_review(data[0][0], data[1])
    changed = copy.deepcopy(data)
    changed[1][0]['person'] = 'Falscher Empfaenger'
    with pytest.raises(ReviewError, match='QUELLEN-AENDERUNG'):
        run(changed, [er], [person_review(data[0][0])])


def test_confirmation_requires_explicit_completeness_and_manual_party():
    data = fixture()
    er = event_review(data[0][0], data[1], complete='')
    with pytest.raises(ReviewError, match='empfaengerliste_vollstaendig'):
        run(data, [er], [person_review(data[0][0])])
    er['empfaengerliste_vollstaendig'] = 'ja'
    pr = person_review(data[0][0]); pr['fraktion_zur_sitzung'] = ''
    with pytest.raises(ReviewError, match='historische Fraktion'):
        run(data, [er], [pr])


def test_confirmed_event_with_unknown_relation_is_blocked():
    data = fixture(two=True, relation=True)
    er = event_review(data[0][0], data[1])
    out = run(data, [er], [person_review(data[0][0])])
    assert not out['verifiziert']
    assert out['bericht']['manuell_bestaetigte_ereignisse_wegen_offener_beziehungen_oder_personen_blockiert'] == 1


def test_explicit_second_order_is_counted_separately_after_relation_review():
    data = fixture(two=True, relation=True)
    e1, e2 = data[0]
    er = [event_review(e, data[1]) for e in (e1, e2)]
    people = [person_review(e) for e in (e1, e2)]
    rr = [dict(vorgang_id_1=e1['ereignis_id'], vorgang_id_2=e2['ereignis_id'],
               entscheidung='getrennte_massnahmen', beleg=e1['quell_url'])]
    out = run(data, er, people, rr)
    assert len(out['verifiziert']) == 2
    assert out['statistik']['gesamtzahl_verifizierter_personenmassnahmen'] == 2


def test_duplicate_requires_pair_confirmation_and_does_not_count_twice():
    data = fixture(two=True, relation=True)
    e1, e2 = data[0]
    er = [event_review(e1, data[1]),
          event_review(e2, data[1], decision='dublette', complete='', dup=e1['ereignis_id'])]
    rr = [dict(vorgang_id_1=e1['ereignis_id'], vorgang_id_2=e2['ereignis_id'],
               entscheidung='gleiche_massnahme', beleg=e1['quell_url'])]
    out = run(data, er, [person_review(e1)], rr)
    assert len(out['verifiziert']) == 1
    assert out['bericht']['ereignisentscheidungen_nach_typ']['dublette'] == 1


def test_duplicate_not_valid_without_relation():
    data = fixture(two=True, relation=False)
    e1, e2 = data[0]
    er = [event_review(e1, data[1]),
          event_review(e2, data[1], decision='dublette', complete='', dup=e1['ereignis_id'])]
    with pytest.raises(ReviewError, match='muss als Beziehung'):
        run(data, er, [person_review(e1)])


def test_relation_conflict_fails_closed():
    data = fixture(two=True, relation=True)
    e1, e2 = data[0]
    er = [event_review(e1, data[1]),
          event_review(e2, data[1], decision='dublette', complete='', dup=e1['ereignis_id'])]
    rr = [dict(vorgang_id_1=e1['ereignis_id'], vorgang_id_2=e2['ereignis_id'],
               entscheidung='getrennte_massnahmen', beleg=e1['quell_url'])]
    with pytest.raises(ReviewError, match='widerspricht Dublettenentscheidung'):
        run(data, er, [person_review(e1)], rr)


def test_group_confirmation_requires_link_review():
    events, people, _, sessions = fixture()
    events[0]['gruppenvorgang'] = 'ja'
    relations = [dict(vorgang_id_1=events[0]['ereignis_id'],
                      vorgang_id_2='20-009-2499-beleg', prueftyp='namensliste_als_beleg_verknuepft',
                      wahlperiode='20', sitzung='9', zeile_1='2461', zeile_2='2499',
                      hinweis='spaetere Liste')]
    data = events, people, relations, sessions
    er = event_review(events[0], people)
    pr = person_review(events[0])
    assert not run(data, [er], [pr])['verifiziert']
    rr = [dict(vorgang_id_1=events[0]['ereignis_id'], vorgang_id_2='20-009-2499-beleg',
               entscheidung='beleg_bestaetigt', beleg=events[0]['quell_url'])]
    assert len(run(data, [er], [pr], rr)['verifiziert']) == 1


def test_wrong_or_missing_date_never_passes_confirmation():
    data = fixture(); er = event_review(data[0][0], data[1])
    changed = copy.deepcopy(data)
    changed[3][0]['datum'] = '17.12.2021'
    with pytest.raises(ReviewError, match='passt nicht zur Sitzung'):
        run(changed, [er], [person_review(data[0][0])])


def test_speaker_party_is_not_automatically_historical():
    data = fixture()
    out = run(data)
    # The candidate says 'fraktionslos', although the human review might
    # establish membership in another faction on the historical meeting date.
    assert out['vorlage_personen'][0]['fraktion_parser_ungeprueft'] == 'fraktionslos'
    assert out['vorlage_personen'][0]['fraktion_zur_sitzung'] == ''


def test_duplicate_decisions_fail_closed():
    data = fixture(); er = event_review(data[0][0], data[1])
    with pytest.raises(ReviewError, match='doppelte Entscheidung'):
        run(data, [er, er], [person_review(data[0][0])])


def test_existing_decision_files_are_not_modified(tmp_path):
    data = fixture()
    e, p, r = tmp_path / 'ereignisse.csv', tmp_path / 'personen.csv', tmp_path / 'beziehungen.csv'
    for file, cols in ((e, EVENT_DECISION_COLUMNS), (p, PERSON_DECISION_COLUMNS),
                       (r, RELATION_DECISION_COLUMNS)):
        with file.open('w', newline='', encoding='utf-8') as s:
            csv.writer(s).writerow(cols)
    before = {f.name: f.read_bytes() for f in (e, p, r)}
    from ereignis_register import write_csv
    for file, cols, rows in (
        (tmp_path / 'input_events.csv', list(data[0][0]), data[0]),
        (tmp_path / 'input_people.csv', list(data[1][0]), data[1]),
        (tmp_path / 'input_relations.csv',
         ['vorgang_id_1','vorgang_id_2','prueftyp','wahlperiode','sitzung','zeile_1','zeile_2','hinweis'], data[2]),
        (tmp_path / 'input_sessions.csv', list(data[3][0]), data[3]),
    ):
        write_csv(file, cols, rows)
    args = type('Args', (), {
        'events': tmp_path / 'input_events.csv',
        'recipients': tmp_path / 'input_people.csv',
        'relations': tmp_path / 'input_relations.csv',
        'sessions': tmp_path / 'input_sessions.csv',
        'decisions': tmp_path, 'out_folder': tmp_path / 'out',
    })()
    out = generate(args)
    assert out['bericht']['ereignisse_offen_ohne_entscheidung'] == 1
    assert all(f.read_bytes() == before[f.name] for f in (e, p, r))
    assert (tmp_path / 'out' / 'bestaetigte_statistik.json').is_file()


def test_dates_are_joined_from_session_overview():
    hits = [{'file': '20009.xml', 'wahlperiode': '20', 'sitzung': '9',
             'line': '2461', 'text': 'Herr Seitz, ich erteile Ihnen einen Ordnungsruf.',
             'classification': 'possible_grant'}]
    ev, rec, rel = build_register(hits, [], session_dates={('20','9'): '16.12.2021'})
    assert ev[0]['datum'] == '16.12.2021'


def test_non_event_person_reviews_are_rejected():
    data = fixture(); pr = person_review(data[0][0]); pr['ereignis_id'] = 'unknown'
    with pytest.raises(ReviewError, match='unbekanntes Ereignis'):
        run(data, [], [pr])
