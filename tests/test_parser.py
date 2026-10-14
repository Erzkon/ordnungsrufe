"""Regression tests based on real phrasings observed in 20th-term XML/CSV.

The small XML fixtures do not imply that every Bundestag record is validated.
"""
from html import escape
from parser import candidates, events, speaker_index, document


def xml_file(tmp_path, lines, people=()):
    speakers = ''.join(f'<redner id="{100+i}"><name><vorname>{escape(first)}</vorname>'
                       f'<nachname>{escape(last)}</nachname><fraktion>Test</fraktion>'
                       f'</name></redner>' for i, (first,last) in enumerate(people))
    paragraphs = '\n'.join(f'<p>{escape(t)}</p>' for t in lines)
    path = tmp_path / 'test.xml'
    path.write_text('<dbtplenarprotokoll wahlperiode="20" sitzung-nr="214" '
                    'sitzung-datum="18.03.2025"><vorspann>' + speakers +
                    '</vorspann><sitzungsverlauf>' + paragraphs +
                    '</sitzungsverlauf></dbtplenarprotokoll>', encoding='utf-8')
    return path


def people(path):
    return [x['person'] for x in events(path)]


def test_candidate_marks_review(tmp_path):
    path = xml_file(tmp_path, ['Ich erteile Ihnen einen Ordnungsruf.', 'Anderer Text.'])
    rows = list(candidates(path))
    assert len(rows) == 1
    assert rows[0]['status'] == 'review_required'
    assert rows[0]['classification'] == 'possible_grant'


def test_group_not_double_counted(tmp_path):
    path = xml_file(tmp_path, [
        'So, ich erteile jetzt allen Abgeordneten einen Ordnungsruf.',
        'Ich halte fest, dass die Abgeordneten Alpha, Beta und Gamma '
        'einen Ordnungsruf erhalten haben.',
        'Ein zweiter Ordnungsruf hätte Konsequenzen.'
    ])
    assert people(path) == ['Alpha', 'Beta', 'Gamma']


def test_full_name_from_xml(tmp_path):
    path = xml_file(tmp_path, ['Herr Muster, dafür bekommen Sie einen Ordnungsruf.'],
                    [('Alex', 'Muster')])
    rows = list(events(path))
    assert len(rows) == 1 and rows[0]['person_id'] == '100'
    assert rows[0]['person'] == 'Alex Muster'


def test_direct_dative_recipient_not_named_victim(tmp_path):
    path = xml_file(tmp_path, [
        'Dem Abgeordneten Brandner erteile ich für seinen beleidigenden '
        'Zwischenruf „Herr Dobrindt, Sie sind eine Pfeife“ einen Ordnungsruf.'
    ], [('Stephan', 'Brandner'), ('Alexander', 'Dobrindt')])
    assert people(path) == ['Stephan Brandner']


def test_direct_address_not_named_victim(tmp_path):
    path = xml_file(tmp_path, [
        'Herr Stegner, ich muss Ihnen leider für einen Zwischenruf gegenüber '
        'der Abgeordneten Weidel einen Ordnungsruf erteilen.',
        'Herr Brandner, Sie haben Herrn Steffen einen „Hetzer“ genannt. '
        'Dafür bekommen Sie einen Ordnungsruf.'
    ], [('Ralf','Stegner'),('Alice','Weidel'),('Stephan','Brandner'),('Frank','Steffen')])
    assert people(path) == ['Ralf Stegner', 'Stephan Brandner']


def test_actual_grant_after_preserved_threat(tmp_path):
    path = xml_file(tmp_path, [
        'Präsidentin Özoğuz hatte sich ja einen Ordnungsruf vorbehalten. '
        'Das Protokoll wurde geprüft, und im Namen von Frau Özoğuz möchte '
        'ich dem Herrn Abgeordneten Christian Petry einen Ordnungsruf erteilen.'
    ], [('Christian', 'Petry')])
    assert people(path) == ['Christian Petry']


def test_no_threat_or_hypothesis_counted(tmp_path):
    path = xml_file(tmp_path, [
        'Herr Hilse, ich behalte mir einen Ordnungsruf vor.',
        'Wenn Sie das nächste Mal fotografieren, erteile ich Ihnen einen Ordnungsruf.',
        'Auch auf die Gefahr hin, dass ich einen Ordnungsruf kassiere, sage ich:',
        'Für diese Bemerkung hätten Sie einen Ordnungsruf verdient.',
        'Herr Brandner, sonst gibt es einen Ordnungsruf.',
    ], [('Karsten','Hilse'), ('Stephan', 'Brandner')])
    assert people(path) == []


def test_appeal_not_counted(tmp_path):
    path = xml_file(tmp_path, [
        'Die Abgeordnete Beatrix von Storch hat Einspruch gegen den '
        'in der letzten Sitzung erteilten Ordnungsruf eingelegt.',
        'Ich nehme diesen Ordnungsruf nicht zurück.'
    ])
    assert people(path) == []


def test_order_phrase_and_particle_surname(tmp_path):
    path = xml_file(tmp_path, [
        'Frau von Storch, Sie rufe ich jetzt zur Ordnung wegen Missachtung.',
        'Frau von Storch, ich erteile Ihnen einen Ordnungsruf.'
    ], [('Beatrix','von Storch')])
    # Two separate sanctions on two lines are kept distinct, not automatically merged.
    assert people(path) == ['Beatrix von Storch', 'Beatrix von Storch']


def test_two_people_in_single_grant(tmp_path):
    path = xml_file(tmp_path, [
        'Insofern erteile ich dem Kollegen Schneider und der Kollegin von Storch '
        'einen Ordnungsruf.'
    ], [('Jens','Schneider'),('Beatrix','von Storch')])
    assert people(path) == ['Jens Schneider', 'Beatrix von Storch']


def test_named_people_after_action(tmp_path):
    path = xml_file(tmp_path, [
        'Sie bekommen jetzt einen zweiten Ordnungsruf, Herr Nietan.',
        'erhält Herr Janich einen Ordnungsruf.'
    ], [('Dietmar','Nietan'),('Steffen','Janich')])
    assert people(path) == ['Dietmar Nietan','Steffen Janich']


def test_generic_titles_without_name_do_not_generate_people(tmp_path):
    path = xml_file(tmp_path, ['Herr Abgeordneter, ich erteile Ihnen einen Ordnungsruf.',
                               'Herr Kollege, ich erteile Ihnen einen Ordnungsruf.'])
    assert people(path) == []


def test_all_events_review_only(tmp_path):
    path = xml_file(tmp_path, ['Herr Muster, ich erteile Ihnen einen Ordnungsruf.'],
                    [('Alex','Muster')])
    assert list(events(path))[0]['status'] == 'review_required'



def test_identity_can_be_resolved_across_sessions(tmp_path):
    previous = xml_file(tmp_path, ['Keine Sanktion.'], [('Beatrix','von Storch')])
    shared_index = speaker_index([document(previous)])
    # Next session lacks any speaker entry, but shares the previous speaker ID.
    target = xml_file(tmp_path, ['Frau von Storch, ich erteile Ihnen einen Ordnungsruf.'])
    row = list(events(target, index=shared_index))[0]
    assert row['person'] == 'Beatrix von Storch'
    assert row['identity_status'] == 'matched_xml_person'


def test_two_people_same_last_name_are_not_arbitrarily_assigned(tmp_path):
    path = xml_file(tmp_path, ['Herr Muster, ich erteile Ihnen einen Ordnungsruf.'],
                    [('Alex','Muster'),('Bea','Muster')])
    row = list(events(path))[0]
    assert row['person'] == 'Muster'
    assert row['person_id'] == ''
    assert row['identity_status'] == 'ambiguous_xml_person'


def test_warning_not_counted_even_when_it_contains_grant_verb(tmp_path):
    path = xml_file(tmp_path, ['Als Nächstes muss ich Ihnen dann einen Ordnungsruf erteilen.'])
    assert people(path) == []
    assert list(candidates(path))[0]['classification'] == 'warning_or_conditional'


def test_realistic_group_confirmation_expands_to_eight(tmp_path):
    names = ['Al-Dailami', 'Dağdelen', 'Ernst', 'Hunko', 'Leye',
             'Mohamed Ali', 'Tatti', 'Wagenknecht']
    path = xml_file(tmp_path, [
        'Herr Brandner, dafür kriegen Sie jetzt einen Ordnungsruf.',
        'So, ich erteile jetzt allen Abgeordneten, welche diese Transparente '
        'hochhalten, einen Ordnungsruf.',
        'Ich halte fest, dass die Abgeordneten ' + ', '.join(names[:-1]) +
        ' und ' + names[-1] + ' einen Ordnungsruf erhalten haben.'
    ], [('Stephan','Brandner'), ('Sahra','Wagenknecht')])
    rows = list(events(path))
    assert len(rows) == 9
    assert rows[0]['person'] == 'Stephan Brandner'
    assert rows[-1]['person'] == 'Sahra Wagenknecht'

# Update 5: real phrasing-based regression cases; recipient != first name

def test_vocative_switch_before_sanction(tmp_path):
    path = xml_file(tmp_path, [
        'Ganz kurz, Frau Kollegin Reichinnek. – Frau von Storch, für den '
        'Zwischenruf „Kindermörderin!“ bekommen Sie einen Ordnungsruf.',
        'Herr Kuhle, sorry. Ich muss das leider durchziehen. – Frau von Storch, '
        'ich hatte deutlich gemacht: Bei Zwischenrufen wird die Maske '
        'aufbehalten. Das steht so in der Allgemeinverfügung. '
        'Das ist jetzt ein Ordnungsruf für Sie.'
    ], [('Heidi', 'Reichinnek'), ('Beatrix', 'von Storch'),
        ('Konstantin', 'Kuhle')])
    assert people(path) == ['Beatrix von Storch', 'Beatrix von Storch']


def test_affected_person_after_order_not_another_recipient(tmp_path):
    path = xml_file(tmp_path, [
        'Bevor ich den letzten Redner aufrufe, muss ich dem Abgeordneten '
        'Krichbaum einen Ordnungsruf erteilen; denn er hat dem Abgeordneten '
        'Frohnmaier nach seiner Rede etwas hinterhergerufen.',
        'Der Abgeordneten von Storch erteile ich einen Ordnungsruf für die '
        'persönliche Beschimpfung der Abgeordneten Alt eben.',
        'Ich rüge ausdrücklich die nonverbale Entgleisung der Abgeordneten '
        'Fester nach der Rede des Abgeordneten Reichardt. Dem Abgeordneten '
        'Reichardt erteile ich einen Ordnungsruf für seine Äußerung.'
    ], [('Gunther', 'Krichbaum'), ('Markus', 'Frohnmaier'),
        ('Beatrix', 'von Storch'), ('Renata', 'Alt'),
        ('Emilia', 'Fester'), ('Martin', 'Reichardt')])
    assert people(path) == ['Gunther Krichbaum', 'Beatrix von Storch',
                            'Martin Reichardt']


def test_last_direct_address_is_recipient(tmp_path):
    path = xml_file(tmp_path, [
        'Herr Kollege Gründer, kann ich Sie einen kleinen Augenblick '
        'unterbrechen? – Herr Kollege Hilse, ich erteile Ihnen einen '
        'Ordnungsruf, weil Sie im Plenarsaal telefoniert haben.'
    ], [('Nils', 'Gründer'), ('Karsten', 'Hilse')])
    assert people(path) == ['Karsten Hilse']


def test_review_queue_contains_unmatched_and_other_mentions(tmp_path):
    from parser import build_review_queue, save_quality_report
    import json
    path = xml_file(tmp_path, [
        'Herr Muster, ich erteile Ihnen einen Ordnungsruf.',
        'Ich erteile Ihnen jetzt einen Ordnungsruf.',
        'Wenn Sie so weitermachen, bekommen Sie einen Ordnungsruf.',
        'Gestern haben wir einen Ordnungsruf besprochen.'
    ], [('Alex', 'Muster')])
    found = list(candidates(path))
    extracted = list(events(path))
    queue = build_review_queue(found, extracted)
    assert len(queue) == len(found) == 4
    assert all(x['pruefung'] == 'offen' and x['entscheidung'] == '' for x in queue)
    assert len({x['pruef_id'] for x in queue}) == 4
    assert sum(x['prioritaet'] == 'hoch' for x in queue) >= 1
    missing = next(x for x in queue if x['klassifikation'] == 'possible_grant'
                   and x['parser_personenzahl'] == 0)
    assert 'ohne automatisch erkannten' in missing['grund']
    quality = tmp_path / 'qualitaetsbericht.json'
    save_quality_report(quality, queue, extracted, 1)
    stats = json.loads(quality.read_text(encoding='utf-8'))
    assert stats['protokolle_verarbeitet'] == 1
    assert stats['pruefung_abgeschlossen'] == 0
    assert stats['textfundstellen'] == 4


def test_20_214_original_xml_when_present():
    """Real original transcript included with chat, not required on GitHub."""
    from pathlib import Path
    original = Path('/mnt/data/20214.xml')
    if not original.exists():
        return
    assert len(list(events(original))) == 9
