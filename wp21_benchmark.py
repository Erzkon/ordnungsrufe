#!/usr/bin/env python3
"""Deterministic, source-attributed parser regression benchmark (not a full audit).

The fixture preserves short excerpts from the official 20/214 XML and their
verified recipients from the existing 20th-term reviewed ledger. It deliberately
does NOT claim external, unseen holdout accuracy or validate WP21 end-to-end.
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from html import escape
from pathlib import Path

from lxml import etree

from parser import candidates, events, speaker_index

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / 'tests/fixtures/official_20_214_annotations.json'
LEDGER = ROOT / 'daten/wirksame_ordnungsrufe_20wp.csv'
GRANT_CLASSES = frozenset({'possible_grant', 'named_group_confirmation'})


def load_fixture(fixture=FIXTURE, ledger=LEDGER):
    meta = json.loads(Path(fixture).read_text(encoding='utf-8'))
    if (meta.get('$schema') != 'ordnungsruf-source-excerpts-v1'
            or meta.get('wahlperiode') != 20 or meta.get('sitzung') != 214
            or not meta.get('source', '').startswith(
                'https://dserver.bundestag.de/btp/20/20214.xml')):
        raise ValueError('Ungültiger Quellenbezug für diesen Benchmark')
    cases = meta['cases']
    roster = meta['people_index']
    if len(cases) < 4 or len(roster) < 9:
        raise ValueError('Quellenproben unerwartet unvollständig')
    seen = set()
    with Path(ledger).open(encoding='utf-8', newline='') as file:
        truth = list(csv.DictReader(file))
    for case in cases:
        code = case['case_id']
        line = case['original_xml_line']
        if (code in seen or code != f'20-214-{line}'
                or not isinstance(case['actionable'], bool)
                or not case['text'] or 'Ordnungsruf' not in case['text']
                or not re.fullmatch(
                    r'https://dserver\.bundestag\.de/btp/20/20214\.pdf#page=\d+',
                    case['pdf'])):
            raise ValueError('Ungültige Quellenprobe')
        seen.add(code)
        expected = case['expected_people']
        if len(expected) != len(set(expected)):
            raise ValueError('Doppelter erwarteter Empfänger')
        for person in expected:
            linked = [r for r in truth if r.get('wahlperiode') == '20'
                      and r.get('sitzung') == '214'
                      and r.get('person') == person
                      and r.get('ereignis_id') == case['evidence']
                      and r.get('beleg') == case['pdf']]
            if len(linked) != 1:
                raise ValueError(f'Nicht belegte Testzuordnung: {code}, {person}')
        if not case['actionable'] and expected:
            raise ValueError('Negativkontrolle mit Empfängern')
    return meta


def build_small_xml(meta):
    """Construct an offline XML excerpt document, not a claim of full session."""
    first_lines = [
        '<dbtplenarprotokoll wahlperiode="20" sitzung-nr="214" '
        'sitzung-datum="18.03.2025">',
        '<vorspann>'
    ]
    for item in meta['people_index']:
        # External roster is a TEST HINT built from historical verified ledger,
        # not the literal speaker roster contained in session 214.
        firstname, last = item['name'].split(' ', 1)
        first_lines.append(
            f'<redner id="{escape(item["id"])}"><name>'
            f'<vorname>{escape(firstname)}</vorname>'
            f'<nachname>{escape(last)}</nachname>'
            f'<fraktion>{escape(item["group"])}</fraktion>'
            '</name></redner>')
    first_lines += ['</vorspann>', '<sitzungsverlauf><tagesordnungspunkt>']
    first_lines += [f'<p>{escape(case["text"])}</p>' for case in meta['cases']]
    first_lines += ['</tagesordnungspunkt></sitzungsverlauf>', '</dbtplenarprotokoll>']
    root = etree.fromstring('\n'.join(first_lines).encode('utf-8'),
                            parser=etree.XMLParser(resolve_entities=False,
                                                   no_network=True, load_dtd=False))
    nodes = root.xpath('./sitzungsverlauf/tagesordnungspunkt/p')
    assert len(nodes) == len(meta['cases'])
    return root, dict(zip((node.sourceline for node in nodes), meta['cases']))


def calculate(meta):
    root, by_line = build_small_xml(meta)
    hints = list(candidates(Path('20214.xml'), root=root))
    person_rows = list(events(Path('20214.xml'),
                              index=speaker_index([root]), root=root))
    hits = defaultdict(list)
    for item in person_rows:
        hits[item['line']].append(item['person'])
    positive_lines = {line for line, item in by_line.items() if item['actionable']}
    predicted_lines = {int(item['line']) for item in hints
                       if item['classification'] in GRANT_CLASSES}
    if any(line not in by_line for line in predicted_lines | set(hits)):
        raise ValueError('Parser hat nicht abgedeckte XML-Stelle ausgegeben')
    tps = len(predicted_lines & positive_lines)
    fps = len(predicted_lines - positive_lines)
    fns = len(positive_lines - predicted_lines)
    tns = len(by_line) - tps - fps - fns
    person_tp = person_fp = person_fn = 0
    mistakes = []
    for line, item in by_line.items():
        expected = set(item['expected_people'])
        got = set(hits.get(line, []))
        person_tp += len(expected & got)
        person_fp += len(got - expected)
        person_fn += len(expected - got)
        if (line in positive_lines) != (line in predicted_lines) or expected != got:
            mistakes.append({
                'case_id': item['case_id'],
                'expected_actionable': item['actionable'],
                'observed_actionable': line in predicted_lines,
                'expected_recipients': sorted(expected),
                'observed_recipients': sorted(got),
            })
    return {
        'type': 'curated_official_xml_regression_not_external_validation',
        'source_session': '20/214',
        'source_xml': meta['source'],
        'number_of_source_excerpts': len(by_line),
        'number_of_distinct_verified_events': 2,
        'verified_person_sanctions_in_excerpts': sum(len(v['expected_people'])
                                                   for v in by_line.values()),
        'text_positive_true': tps,
        'text_positive_false': fps,
        'text_positive_missed': fns,
        'text_negative_true': tns,
        'recipients_matched': person_tp,
        'recipients_false': person_fp,
        'recipients_missed': person_fn,
        'regression_passed': not mistakes,
        'failures': mistakes,
        'limitations': ('Die vier Originalausschnitte stammen aus nur einer historischen Sitzung. '
                        'Die Namen wurden aus einer belegten Referenzliste als Test-Roster bereitgestellt. '
                        'Dies ist ein Regressionstest, keine unabhängige Goldstandard-Stichprobe '
                        'und keine Schätzung der Fehlerquote des Gesamtparlaments.'),
        'automatically_verified_sanctions': 0,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--fixture', type=Path, default=FIXTURE)
    ap.add_argument('--verified', type=Path, default=LEDGER)
    ap.add_argument('--output', type=Path, default=Path('wp21_regression_audit.json'))
    a = ap.parse_args()
    report = calculate(load_fixture(a.fixture, a.verified))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                        encoding='utf-8')
    print(f"Quellenregression: {report['number_of_source_excerpts']} Originalausschnitte "
          f"aus 20/214; Texte TP={report['text_positive_true']}, "
          f"FP={report['text_positive_false']}, FN={report['text_positive_missed']}; "
          f"Empfänger korrekt={report['recipients_matched']}, "
          f"falsch={report['recipients_false']}, "
          f"übersehen={report['recipients_missed']}. "
          "Keine automatische Freigabe.")
    if not report['regression_passed']:
        raise SystemExit('Quellenbasierte Parser-Regression fehlgeschlagen')


if __name__ == '__main__':
    main()
