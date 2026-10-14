import csv
import json
from pathlib import Path

import pytest

from dip_abgleich import classify, clean, iter_pages, row_for, run, session_numbers


def doc(id_, title, wp=20):
    return {'id': str(id_), 'wahlperiode': wp, 'titel': title, 'datum': '2023-01-26', 'vorgangstyp': 'Geschäftsordnung'}


def test_classify_grants_and_appeals():
    assert classify('Erteilung von zwei Ordnungsrufen an den Abg Dietmar Nietan') == 'moegliche_erteilung'
    assert classify('Einspruch gegen einen Ordnungsruf') == 'einspruch_ruecknahme_oder_folge'
    assert classify('Ordnungsruf im Bundestag') == 'sonstiger_ordnungsrufbezug'


def test_normalize_german_and_honorifics():
    assert clean('Dr. Beatrix von Storch') == 'beatrix von storch'
    assert clean('Bärbel Bas') == 'barbel bas'


def test_session_identification_in_nested_positions():
    obj = {'fundstelle': {'dokumentnummer': '20/187', 'pdf_url': 'https://x/20187.pdf'},
           'wahlperiode': 20, 'unrelated': ['21/10', '20/001']}
    assert session_numbers(obj) == {187, 1}


def test_position_links_to_same_session_and_person():
    p = [{'fundstelle': {'dokumentnummer': '20/187'}}]
    r = row_for(doc(315959, 'Erteilung eines Ordnungsrufes an den Abg Dr. Hendrik Hoppenstedt (CDU/CSU)'),
                p, {187: [{'person': 'Hendrik Hoppenstedt'}]})
    assert r['sitzungen_aus_dip'] == '187'
    assert r['abgleichstatus'] == 'person_und_sitzung_vorhanden_manuell_abgleichen'


def test_same_session_not_same_person():
    r = row_for(doc(1, 'Erteilung eines Ordnungsrufes an Caren Lay'),
                [{'fundstelle': {'dokumentnummer': '20/153'}}],
                {153: [{'person': 'Stephan Brandner'}]})
    assert r['abgleichstatus'] == 'sitzung_vorhanden_empfaenger_pruefen'


def test_multi_sanctions_requires_count_check():
    r = row_for(doc(1, 'Erteilung von zwei Ordnungsrufen an den Abg Dietmar Nietan'),
                [{'fundstelle': {'dokumentnummer': '20/82'}}],
                {82: [{'person': 'Dietmar Nietan'}]})
    assert r['mehrfachvergabe_hinweis'] == 'ja'
    assert r['abgleichstatus'] == 'mehrfachvergabe_anzahl_pruefen'


def test_missing_session_flagged():
    r = row_for(doc(1, 'Ordnungsruf an Abg Alice'), [], {})
    assert r['abgleichstatus'] == 'protokollfundstelle_fehlt'


def test_paginate_success_and_completion():
    calls = []
    def fetch(endpoint, params, key):
        calls.append(params.copy())
        if 'cursor' not in params:
            return {'numFound': 3, 'documents': [doc(1, 'A'), doc(2, 'B')], 'cursor': 'next1'}
        return {'numFound': 3, 'documents': [doc(3, 'C')], 'cursor': 'next2'}
    rows = list(iter_pages('/vorgang', {'f.wahlperiode': '20'}, 'key', fetch=fetch))
    assert len(rows) == 3 and calls[1]['cursor'] == 'next1'


def test_paginate_truncation_is_error():
    def fetch(endpoint, params, key):
        return {'numFound': 2, 'documents': [doc(1, 'A')], 'cursor': 'same'}
    with pytest.raises(ValueError, match='mehrfach'):
        list(iter_pages('/vorgang', {}, 'key', fetch=fetch))


def test_paginate_zero_found_valid():
    def fetch(endpoint, params, key):
        return {'numFound': 0, 'documents': [], 'cursor': ''}
    assert list(iter_pages('/vorgang', {}, 'key', fetch=fetch)) == []


def test_reject_wp_mismatch(tmp_path):
    path = tmp_path / 'verified.csv'
    path.write_text('sitzung,person,ereignis_id\n187,Hendrik Hoppenstedt,e1\n')
    def fetch(endpoint, params, key):
        return {'numFound': 1, 'documents': [doc(1, 'Ordnungsruf an Person', wp=19)], 'cursor': ''}
    with pytest.raises(ValueError, match='Wahlperiode'):
        run(path, tmp_path, 'key', fetch=fetch)


def test_end_to_end_no_auto_approval(tmp_path):
    path = tmp_path / 'verified.csv'
    path.write_text('sitzung,person,ereignis_id\n82,Dietmar Nietan,e1\n187,Hendrik Hoppenstedt,e2\n')
    def fetch(endpoint, params, key):
        if endpoint == '/vorgang':
            docs = [doc(315959, 'Erteilung eines Ordnungsrufes an den Abg Dr. Hendrik Hoppenstedt (CDU/CSU)'),
                    doc(12345, 'Erteilung von zwei Ordnungsrufen an den Abg Dietmar Nietan'),
                    doc(6789, 'Mietpreisbremse')]
        else:
            ses = '20/187' if params['f.vorgang'] == '315959' else '20/82'
            docs = [{'id': '1' if ses == '20/187' else '2', 'fundstelle': {'dokumentnummer': ses}}]
        return {'numFound': len(docs), 'documents': docs, 'cursor': 'next'}
    report = run(path, tmp_path, 'key', fetch=fetch)
    assert report['dip_vorgaenge_insgesamt_geprueft'] == 3
    assert report['dip_vorgaenge_mit_ordnungsruf_im_titel'] == 2
    assert report['dip_eintraege_in_pruefliste'] == 1
    assert (tmp_path / 'dip_pruefliste.csv').exists()
    assert not (tmp_path / 'bestaetigte_ordnungsrufe.csv').exists()
    with (tmp_path / 'dip_pruefliste.csv').open() as f:
        data = list(csv.DictReader(f))
    assert 'Dietmar Nietan' in data[0]['dip_titel']


def test_api_reject_unexpected_fields():
    def fetch(endpoint, params, key):
        return {'numFound': '100', 'documents': [], 'cursor': ''}
    with pytest.raises(ValueError, match='format'):
        list(iter_pages('/vorgang', {}, 'k', fetch=fetch))
