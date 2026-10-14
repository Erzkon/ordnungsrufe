"""Update 7 tests. These validate conservatism, not parliamentary truth."""
from html import escape
from pathlib import Path

from parser import candidates, events, document, speaker_index
from ereignis_register import (build_register, quality_summary,
                               is_group_grant, write_csv, read_csv, EVENT_COLUMNS)


def fixture(tmp_path, lines, names=()):
    names_xml = ''.join(
        f'<redner id="{100+i}"><name><vorname>{escape(first)}</vorname>'
        f'<nachname>{escape(surname)}</nachname><fraktion>Test</fraktion>'
        '</name></redner>' for i, (first, surname) in enumerate(names))
    para_xml = '\n'.join('<p>' + escape(line) + '</p>' for line in lines)
    file = tmp_path / '20214.xml'
    file.write_text('<dbtplenarprotokoll wahlperiode="20" sitzung-nr="214" '
                    'sitzung-datum="18.03.2025"><vorspann>' + names_xml +
                    '</vorspann><sitzungsverlauf>' + para_xml +
                    '</sitzungsverlauf></dbtplenarprotokoll>', encoding='utf-8')
    return file


def run(file):
    root = document(file)
    index = speaker_index([root])
    return build_register(list(candidates(file, root)), list(events(file, index, root)), index)


def test_one_order_one_event_person_not_count(tmp_path):
    file = fixture(tmp_path, [
        'Ich erteile dem Kollegen Muster und der Kollegin Test einen Ordnungsruf.'
    ], [('Anton', 'Muster'), ('Bea', 'Test')])
    register, people, rel = run(file)
    assert len(register) == 1
    assert len(people) == 2
    assert {p['ereignis_id'] for p in people} == {register[0]['ereignis_id']}
    assert register[0]['gruppenvorgang'] == 'ja'
    assert register[0]['ereignisstatus'] == 'review_required'


def test_speaker_list_linked_to_previous_anonymous_group_once(tmp_path):
    file = fixture(tmp_path, [
        'So, ich erteile jetzt allen Abgeordneten, welche Transparente hochhalten, einen Ordnungsruf.',
        'Ich halte fest, dass die Abgeordneten Alpha, Beta und Gamma einen Ordnungsruf erhalten haben.'
    ])
    register, people, rel = run(file)
    assert len(register) == 1
    assert len(people) == 3
    assert register[0]['weitere_belegzeilen']
    assert 'Alpha' in register[0]['zusatzbeleg_text']
    assert register[0]['empfaenger_zuordnung'] == 'nachtraegliche_namensliste_ungeprueft'
    assert any(x['prueftyp'] == 'namensliste_als_beleg_verknuepft' for x in rel)


def test_ambiguous_group_links_not_merged(tmp_path):
    file = fixture(tmp_path, [
        'Ich erteile jetzt allen Abgeordneten, die Plakate halten, einen Ordnungsruf.',
        'Ich erteile jetzt allen Abgeordneten, die Banner halten, einen Ordnungsruf.',
        'Ich halte fest, dass die Abgeordneten Alpha und Beta einen Ordnungsruf erhalten haben.'
    ])
    register, people, rel = run(file)
    assert len(register) == 3
    assert register[-1]['ereignisart'] == 'namensliste_ohne_eindeutige_vorherige_erteilung'
    assert not any(x['prueftyp'] == 'namensliste_als_beleg_verknuepft' for x in rel)


def test_separate_people_in_separate_paragraphs_not_deduplicated(tmp_path):
    file = fixture(tmp_path, [
        'Herr Muster, ich erteile Ihnen einen Ordnungsruf.',
        'Frau Beispiel, ich erteile Ihnen einen Ordnungsruf.'
    ], [('Anton','Muster'), ('Bea','Beispiel')])
    register, people, rel = run(file)
    assert len(register) == 2
    assert len(people) == 2
    assert not [x for x in rel if x['prueftyp'] == 'moegliche_wiederholung']


def test_adjacent_possible_repeats_flagged_not_merged(tmp_path):
    file = fixture(tmp_path, [
        'und dafür erteile ich Ihnen einen Ordnungsruf.',
        'Ich erteile Ihnen für diesen Begriff einen Ordnungsruf.'
    ])
    register, people, rel = run(file)
    assert len(register) == 2
    assert people == []
    assert len(rel) == 1 and rel[0]['prueftyp'] == 'moegliche_wiederholung'
    assert all(x['pruefung'] == 'offen' and x['entscheidung'] == '' for x in rel)


def test_second_penalty_not_silently_collapsed(tmp_path):
    file = fixture(tmp_path, [
        'Frau Muster, ich erteile Ihnen einen Ordnungsruf.',
        'Ich erteile Ihnen einen zweiten Ordnungsruf.'
    ], [('Bea','Muster')])
    register, people, rel = run(file)
    assert len(register) == 2
    assert register[1]['ordnungsruf_nummer'] == 'zweiter'
    assert rel[0]['prueftyp'] == 'ausdruecklich_weiterer_ordnungsruf'
    assert rel[0]['aktion'] == 'nicht_automatisch_zusammengelegt'


def test_two_people_two_sentences_one_paragraph_are_split(tmp_path):
    file = fixture(tmp_path, [
        'Herr Muster, ich erteile Ihnen einen Ordnungsruf. '
        'Frau Beispiel, ich erteile Ihnen einen Ordnungsruf.'
    ], [('Anton','Muster'), ('Bea','Beispiel')])
    register, people, rel = run(file)
    assert len(register) == 2
    assert len(people) == 2
    assert len({x['ereignis_id'] for x in register}) == 2
    assert {r['person'] for r in people} == {'Anton Muster', 'Bea Beispiel'}
    assert not rel


def test_second_order_same_person_same_paragraph_explicitly_separate(tmp_path):
    file = fixture(tmp_path, [
        'Herr Muster, ich erteile Ihnen einen Ordnungsruf. '
        'Herr Muster, ich erteile Ihnen einen zweiten Ordnungsruf.'
    ], [('Anton','Muster')])
    register, people, rel = run(file)
    assert len(register) == 2
    assert len(people) == 2
    assert register[1]['ordnungsruf_nummer'] == 'zweiter'


def test_repeated_order_same_person_within_paragraph_is_not_split(tmp_path):
    file = fixture(tmp_path, [
        'Frau Muster, ich erteile Ihnen einen Ordnungsruf. '
        'Ich erteile Ihnen dafür einen Ordnungsruf.'
    ], [('Bea','Muster')])
    register, people, rel = run(file)
    assert len(register) == 1
    assert len(people) == 1
    assert register[0]['mehrere_formulierungen'] == 'ja'
    assert register[0]['pruefprioritaet'] == 'hoch'


def test_threats_retrospectives_and_general_mentions_not_events(tmp_path):
    file = fixture(tmp_path, [
        'Herr Muster, wenn Sie nicht ruhig sind, erteile ich einen Ordnungsruf.',
        'Gestern haben wir den Ordnungsruf besprochen.',
        'Ich nehme den Ordnungsruf nicht zurück.'
    ])
    register, people, _ = run(file)
    assert register == [] and people == []


def test_event_ids_repeatable_and_csv_with_bom(tmp_path):
    file = fixture(tmp_path, ['Frau Muster, ich erteile Ihnen einen Ordnungsruf.'], [('Bea','Muster')])
    a = run(file)[0]
    b = run(file)[0]
    assert a == b
    assert a[0]['ereignis_id'].startswith('20-214-')
    out = tmp_path / 'event.csv'
    write_csv(out, EVENT_COLUMNS, a)
    assert read_csv(out)[0]['ereignis_id'] == a[0]['ereignis_id']


def test_original_20_214_links_group_not_double_counted():
    original = Path('/mnt/data/20214.xml')
    if not original.exists():
        return
    reg, people, rel = run(original)
    assert len(reg) == 2
    assert len(people) == 9
    assert sum(e['gruppenvorgang'] == 'ja' for e in reg) == 1
    assert len([r for r in rel if r['prueftyp'] == 'namensliste_als_beleg_verknuepft']) == 1
    assert all(e['ereignisstatus'] == 'review_required' for e in reg)
