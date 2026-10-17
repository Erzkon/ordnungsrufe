#!/usr/bin/env python3
"""Diff fully verified official minutes against a fixed, reviewed source baseline.

The immutable 21/042–21/100 snapshot comes from the successful Bundestag
original-PDF audit. Every future official minute, revised PDF byte stream or
newly named objection context becomes a *manual* source-review task. A hit
does not establish an objection decision or a sanction's legal effectiveness.
The public counter must remain byte-identical.
"""
import argparse
import json
import re
from pathlib import Path

from wp21_amtliche_protokolle_katalog import PDF_URL, FIRST

BASELINE_SCHEMA = 'wp21-official-minutes-verified-baseline-v1'
SOURCE_SCHEMA = 'wp21-all-published-official-resolution-minutes-v1'
RESULT_SCHEMA = 'wp21-official-minutes-manual-change-triage-v1'
HEX = re.compile(r'[0-9a-f]{64}\Z')


def valid_source(row):
    if not isinstance(row, dict):
        raise ValueError('Amtliche PDF-Quelle kein Objekt')
    sid, url, digest = row.get('session'), row.get('official_url'), row.get('pdf_sha256')
    if (type(sid) is not int or not FIRST <= sid <= 150
            or not isinstance(url, str) or not (m := PDF_URL.fullmatch(url))
            or int(m.group(1)) != sid
            or not isinstance(digest, str) or not HEX.fullmatch(digest)
            or type(row.get('pages_checked')) is not int
            or not 1 <= row['pages_checked'] <= 55
            or not isinstance(row.get('name_appeal_contexts'), list)
            or row.get('possible_later_context_count') !=
                (len(row['name_appeal_contexts']) if sid != FIRST else 0)):
        raise ValueError('Amtliche Einzelquelle ungültig oder mit fremder Sitzung')
    for item in row['name_appeal_contexts']:
        if (not isinstance(item, dict)
                or item.get('session') != sid
                or item.get('source') != url
                or item.get('public_count_delta') != 0
                or item.get('automatic_legal_conclusion') is not False
                or not isinstance(item.get('pdf_page'), int)
                or not 1 <= item['pdf_page'] <= row['pages_checked']):
            raise ValueError('Prüfkandidat ohne überprüfbaren amtlichen Seitenbeleg')


def validate(baseline, current):
    if (not isinstance(baseline, dict)
            or baseline.get('schema') != BASELINE_SCHEMA
            or baseline.get('public_counter_delta') != 0
            or baseline.get('recorded_date') != '2026-10-17'
            or baseline.get('source_report_sha256') !=
                'ceb870a52658b46993f468433abcb722be3d4a78cb5d672e0301064a14fa207d'
            or not isinstance(baseline.get('records'), dict)
            or set(baseline['records']) != {str(s) for s in range(42, 101)}):
        raise ValueError('Ungeprüfte oder veränderte amtliche Referenzstichprobe')
    for sid in range(42, 101):
        entry = baseline['records'][str(sid)]
        if (not isinstance(entry, dict)
                or not isinstance(entry.get('url'), str)
                or not (m := PDF_URL.fullmatch(entry['url']))
                or int(m.group(1)) != sid
                or not isinstance(entry.get('sha256'), str)
                or not HEX.fullmatch(entry['sha256'])):
            raise ValueError('Unvollständige amtliche Baseline-Originalquelle')
    if (not isinstance(current, dict) or current.get('schema') != SOURCE_SCHEMA
            or current.get('public_counter_delta') != 0
            or current.get('automatically_confirmed_effective_sanctions') != 0
            or current.get('automatically_rescinded_sanctions') != 0
            or current.get('no_publication_after_latest_does_not_prove_legal_absence') is not True
            or current.get('second_gottschalk_measure_legality_unresolved') is not True
            or not isinstance(current.get('source_reports'), list)):
        raise ValueError('Unvollständig validierter amtlicher Gesamtbericht')
    rows = current['source_reports']
    ids = [r.get('session') for r in rows if isinstance(r, dict)]
    if (len(ids) != len(rows) or len(set(ids)) != len(ids)
            or not ids or ids != list(range(ids[0], FIRST - 1, -1))
            or ids[0] < 100
            or current.get('minutes_checked') != len(ids)
            or current.get('pages_checked') !=
                sum(r.get('pages_checked', 0) for r in rows)
            or current.get('later_review_context_count') !=
                sum(r.get('possible_later_context_count', 0) for r in rows)
            or current.get('official_catalogue', {}).get(
                'latest_published_official_minute') != ids[0]):
        raise ValueError('Amtlicher Katalog nicht vollständig/eindeutig')
    for row in rows:
        valid_source(row)
    reference = rows[-1]
    if (reference['session'] != FIRST
            or len(reference['name_appeal_contexts']) != 1
            or reference['name_appeal_contexts'][0].get('known_first_objection_only') is not True):
        raise ValueError('Erste bekannte Einspruchsentscheidung 21/042 fehlt')
    return {r['session']: r for r in rows}


def compare(baseline, current):
    by_session = validate(baseline, current)
    additions, revised, contexts = [], [], []
    for sid, row in sorted(by_session.items()):
        previous = baseline['records'].get(str(sid))
        if previous is None:
            additions.append({
                'session': sid, 'source': row['official_url'],
                'pdf_sha256': row['pdf_sha256'],
                'pages': row['pages_checked'],
                'manual_review_reason': 'newly_published_official_resolution_pdf',
            })
        elif (previous['url'] != row['official_url']
              or previous['sha256'] != row['pdf_sha256']):
            revised.append({
                'session': sid, 'source': row['official_url'],
                'previous_url': previous['url'], 'pdf_sha256': row['pdf_sha256'],
                'previous_sha256': previous['sha256'],
                'url_changed': previous['url'] != row['official_url'],
                'bytes_changed': previous['sha256'] != row['pdf_sha256'],
                'manual_review_reason': 'previously_published_original_pdf_changed',
            })
        if sid > FIRST:
            for hit in row['name_appeal_contexts']:
                contexts.append({
                    'session': sid, 'source': row['official_url'],
                    'pdf_page': hit['pdf_page'],
                    'context_excerpt': hit.get('context_excerpt', '')[:650],
                    'possible_second_in_named_section':
                        hit.get('second_measure_explicitly_named') is True,
                    'requires_manual_source_review': True,
                    'automatic_decision_status': 'unverified',
                })
    # A later context is never automatically classified as a valid decision.
    return {
        'schema': RESULT_SCHEMA,
        'baseline_run': baseline['source_run'],
        'baseline_session_range': '21/042–21/100',
        'latest_published_official_minute': max(by_session),
        'complete_official_minutes_checked': len(by_session),
        'new_official_minutes': additions,
        'revised_historical_pdf_sources': revised,
        'later_named_appeal_contexts': contexts,
        'manual_review_required': bool(additions or revised or contexts),
        'other_nonplenary_documents_and_unpublished_sessions_not_excluded': True,
        'no_automatic_legal_outcome': True,
        'second_gottschalk_measure_legality_unresolved': True,
        'protected_public_counter_delta': 0,
        'automatically_confirmed_effective_sanctions': 0,
        'automatically_rescinded_sanctions': 0,
        'reference_baseline_not_updated_by_this_scan': True,
    }


def markdown(r):
    if (r.get('schema') != RESULT_SCHEMA
            or r.get('other_nonplenary_documents_and_unpublished_sessions_not_excluded') is not True
            or r.get('no_automatic_legal_outcome') is not True
            or r.get('second_gottschalk_measure_legality_unresolved') is not True
            or r.get('protected_public_counter_delta') != 0
            or r.get('automatically_confirmed_effective_sanctions') != 0
            or r.get('automatically_rescinded_sanctions') != 0
            or r.get('reference_baseline_not_updated_by_this_scan') is not True):
        raise ValueError('Amtlicher Vergleich darf keine Rechtsfolgen genehmigen')
    lines = ['# Neue amtliche Beschlussprotokolle: quellenscharfe Triage', '',
             f"Vergleichsbasis: [verifizierter CI-Lauf]({r['baseline_run']}).",
             f"Geprüfte aktuelle PDFs: {r['complete_official_minutes_checked']}, "
             f"letzte veröffentlichte Sitzung: 21/{r['latest_published_official_minute']:03d}.",
             f"Neue amtliche PDFs: {len(r['new_official_minutes'])}; "
             f"veränderte bestehende PDFs: {len(r['revised_historical_pdf_sources'])}; "
             f"spätere Textkandidaten: {len(r['later_named_appeal_contexts'])}.", '']
    for key, title in (
            ('new_official_minutes', 'Neu veröffentlicht'),
            ('revised_historical_pdf_sources', 'Veränderte amtliche Original-PDFs'),
            ('later_named_appeal_contexts', 'Nur manuell zu prüfende spätere Einspruchskontexte')):
        lines += ['## ' + title, '']
        for hit in r[key]:
            lines.append(
                f"- [21/{hit['session']:03d}]({hit['source']})"
                + (f" PDF-Seite {hit['pdf_page']}" if 'pdf_page' in hit else '')
                + ' – manuelle Prüfung, keine automatische Entscheidung')
        if not r[key]:
            lines.append('- Keine neuen Hinweise im überprüften Bereich')
        lines.append('')
    lines += ['**Kein Zählerupdate, keine automatische Anerkennung der '
              'Wirksamkeit der zweiten Gottschalk-Maßnahme.** '
              'Künftige Veröffentlichungen und weitere amtliche '
              'Dokumentengattungen bleiben offen.', '']
    return '\n'.join(lines)


def run(current, baseline, output, brief):
    current_data = json.loads(Path(current).read_text(encoding='utf-8'))
    baseline_data = json.loads(Path(baseline).read_text(encoding='utf-8'))
    report = compare(baseline_data, current_data)
    prose = markdown(report)
    for name, content in (
            (Path(output), json.dumps(report, ensure_ascii=False, indent=2)+'\n'),
            (Path(brief), prose)):
        name.parent.mkdir(parents=True, exist_ok=True)
        tmp = name.with_suffix(name.suffix+'.tmp')
        tmp.write_text(content, encoding='utf-8')
        tmp.replace(name)
    if report['manual_review_required']:
        print('::warning::Neue/veränderte Bundestags-Original-PDFs '
              'oder Einspruchskontexte entdeckt; manuell prüfen, keine Zählerfreigabe')
    print('WP21_OFFICIAL_MINUTES_DELTA_OK:',
          len(report['new_official_minutes']), 'new PDFs,',
          len(report['revised_historical_pdf_sources']), 'revised PDFs,',
          len(report['later_named_appeal_contexts']), 'named candidate contexts,',
          'zero legal count changes')
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--current', type=Path, required=True)
    cli.add_argument('--baseline', type=Path, default=Path('daten/wp21_amtliche_protokolle_baseline.json'))
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--brief', type=Path, required=True)
    opts = cli.parse_args()
    run(opts.current, opts.baseline, opts.output, opts.brief)
