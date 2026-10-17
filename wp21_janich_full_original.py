#!/usr/bin/env python3
"""Full-sitting, conservative first-Janich-source search in Bundestag XML 21/040.

This searches EVERY spoken paragraph, not just the 60-before/20-after
neighbourhood of the known 8717 conditional warning. The original 21/042
appeal decision is a separate cross-source anchor. An unattributed quotation,
a warning, or another member's issuance may NEVER prove Janich's first
unconditional grant or modify any public sanction counts.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from parser import iter_session_text, TERM_RE, action_match
from wp21_scan import fetch, safe_parse
from wp21_janich_erste_quellenkritik import inspect as official_review

SOURCE = 'https://dserver.bundestag.de/btp/21/21040.xml'
ORDER_WORDS = re.compile(
    r'\bOrdnungsruf\w*\b|\bOrdnungsma[ßs]nahme\w*\b|'
    r'\bzur\s+Ordnung\s+ruf\w*\b', re.I)
JANICH = re.compile(r'\b(?:Steffen\s+)?Janich\b', re.I)
CONDITIONAL = re.compile(
    r'\b(?:wenn|falls|würde|könnte|werde|werde\s+Ihnen|'
    r'gleich\s+fürs\s+Lachen)\b', re.I)
KNOWN = {
    8715: 'known_other_person_sichert_issuance',
    8717: 'known_janich_conditional_warning_not_issuance',
    8719: 'known_janich_explicit_second_issuance',
    8812: 'known_janich_second_retrospective_confirmation_only',
    8990: 'explicit_gottschalk_original_utterance_not_janich',
    8992: 'unattributed_followon_second_utterance',
    9005: 'anonymous_afD_interjection_recipient_unidentified',
}
# All four additions have been independently observed in the real official
# 21/040 original by the preceding whole-sitting forensic read. Guard their
# exact line and complete original paragraph bytes (not approximate keywords).
OTHER_ANCHORS = {
    8812: 'd0655635ab6216c5f1badabc01ba4481d72a7cdbbc444d404a30baf9b2d4a62f',
    8990: 'e36672d5ab7bce3cb950e0dcc2b392b3da6489d0d846ead8e0873f48eb4ec3cc',
    8992: 'f4c6d5ed55bf8d9b34f40566fca5944dd4f88f45c7de3626a18a5c3d6310ea80',
    9005: '9ce489e4baaf2781bbd03b194887f3d278d8a937f0f22b74bb8771e7c208962c',
}
MANUAL_RECIPIENT_LABELS = {
    'unattributed_original_sitting_context',
    'unattributed_followon_second_utterance',
    'anonymous_afD_interjection_recipient_unidentified',
}
SOURCE_KEYS = {
    8715: 'sichert_first_grant',
    8717: 'janich_conditional_laughter_warning',
    8719: 'janich_explicit_second_issuance',
}
MAX_EXCERPT = 1050


def inspect_all_rows(rows, official):
    """Require contiguous input *order*, unique real line numbers and anchors."""
    if (not isinstance(rows, list) or not 100 <= len(rows) <= 25000
            or not isinstance(official, dict)
            or official.get('schema') !=
               'wp21-janich-first-conditional-versus-second-grant-v1'
            or official.get('first_independent_unconditional_issuance_xml_line') is not None
            or official.get('documented_separately_rejected_objections') != 2
            or official.get('public_counter_delta') != 0
            or official.get('conditional_notice_is_not_unconditional_issuance_proof') is not True):
        raise ValueError('Unvollständige oder nicht verifizierte amtliche Originalakte')
    previous = 0
    all_rows = []
    for entry in rows:
        if (not isinstance(entry, tuple) or len(entry) != 2
                or type(entry[0]) is not int or entry[0] <= previous
                or not isinstance(entry[1], str)
                or not 0 < len(entry[1]) <= 12000):
            raise ValueError('Originalabsätze fehlen, sind doppelt oder unsortiert')
        previous = entry[0]
        all_rows.append(entry)
    by_line = dict(all_rows)
    for lineno, key in SOURCE_KEYS.items():
        info = official['source_passages'].get(key)
        value = by_line.get(lineno)
        if (value is None or not isinstance(info, dict)
                or info.get('xml_line') != lineno
                or info.get('source_url') != SOURCE
                or hashlib.sha256(value.encode('utf-8')).hexdigest() !=
                   info.get('paragraph_sha256')):
            raise ValueError('Geschützte amtliche Janich/Sichert-Originalzeile verändert')
    for lineno, digest in OTHER_ANCHORS.items():
        text = by_line.get(lineno)
        if text is None or hashlib.sha256(text.encode('utf-8')).hexdigest() != digest:
            raise ValueError('Weitere amtliche Janich/Gottschalk/Anonym-Originalquelle verändert')
    # Do not treat a clearly anonymous interjection as a Gottschalk or Janich
    # measure simply because Gottschalk was being addressed nearby.
    if (not re.search(r'zweite[rn]?\s+Ordnungsruf\s+an\s+Steffen\s+Janich',
                      by_line[8812], re.I)
            or not re.search(r'Herr\s+Kollege\s+Gottschalk.*?erteile\s+Ihnen',
                             by_line[8990], re.I)
            or not re.search(r'zweiten\s+Ordnungsruf', by_line[8992], re.I)
            or not re.search(r'Ich\s+weiß\s+nicht,\s+wer\s+es\s+war',
                             by_line[9005], re.I)):
        raise ValueError('Genaue amtliche Wortlautidentität für Nicht-Janich-Fälle fehlt')
    findings = []
    for i, (lineno, content) in enumerate(all_rows):
        if not (ORDER_WORDS.search(content) or TERM_RE.search(content)):
            continue
        # Other people and historical speech quotations are still shown but
        # can only become manual candidates, not person-attributed measures.
        label = KNOWN.get(lineno, 'unattributed_original_sitting_context')
        nearby = all_rows[max(0, i-2):min(len(all_rows), i+3)]
        findings.append({
            'xml_line': lineno,
            'source': SOURCE,
            'paragraph_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
            'excerpt': ' '.join(content.split())[:MAX_EXCERPT],
            'surrounding_source_lines': [x[0] for x in nearby],
            'surrounding_excerpts': [
                {'xml_line': l, 'excerpt': ' '.join(t.split())[:310]}
                for l, t in nearby if l != lineno],
            'literal_issuance_verb_detected': bool(action_match(content)),
            'conditional_wording_detected': bool(CONDITIONAL.search(content)),
            'janich_name_in_same_paragraph': bool(JANICH.search(content)),
            'source_class': label,
            'requires_independent_recipient_and_speaker_review':
                label in MANUAL_RECIPIENT_LABELS,
            'automatic_janich_first_grant_attribution': False,
            'automatic_legal_effect_confirmation': False,
            'public_count_delta': 0,
        })
    if (len(findings) < 7
            or {x['xml_line']:x['source_class'] for x in findings
                if x['xml_line'] in KNOWN} != KNOWN):
        raise ValueError('Bekannte drei amtliche Originalformulierungen fehlen')
    unknown = [x for x in findings
               if x['requires_independent_recipient_and_speaker_review']]
    return {
        'schema': 'wp21-janich-complete-original-sitting-audit-v1',
        'original_session': 40,
        'original_source': SOURCE,
        'verified_spoken_paragraphs_in_original': len(all_rows),
        'total_order_related_text_locations': len(findings),
        'known_other_person_sichert_line': 8715,
        'known_janich_conditional_warning_line': 8717,
        'known_janich_explicit_second_grant_line': 8719,
        'janich_second_retrospective_confirmation_line': 8812,
        'explicit_non_janich_gottschalk_utterance_line': 8990,
        'other_recipient_unresolved_lines': [8992, 9005],
        'independently_rejected_first_and_second_appeals_in_21_042': 2,
        'original_janich_first_issuance_literal_line': None,
        'source_scope_is_all_spoken_paragraphs_not_appendices': True,
        'explicit_other_sources_not_attributed_to_janich': True,
        'source_text_locations': findings,
        'unattributed_contexts_for_manual_review': unknown,
        'unattributed_explicit_issuance_wordings_for_manual_review': [
            x for x in unknown if x['literal_issuance_verb_detected']],
        'unattributed_janich_named_wordings_for_manual_review': [
            x for x in unknown if x['janich_name_in_same_paragraph']],
        'missing_first_literal_wording_is_not_proof_of_missing_measure': True,
        'no_person_attribution_by_keyword_proximity': True,
        'automatic_effective_ordinal_count': 0,
        'public_counter_delta': 0,
    }


def markdown(report):
    if (report.get('schema') != 'wp21-janich-complete-original-sitting-audit-v1'
            or report.get('original_janich_first_issuance_literal_line') is not None
            or report.get('known_other_person_sichert_line') != 8715
            or report.get('known_janich_conditional_warning_line') != 8717
            or report.get('known_janich_explicit_second_grant_line') != 8719
            or report.get('janich_second_retrospective_confirmation_line') != 8812
            or report.get('explicit_non_janich_gottschalk_utterance_line') != 8990
            or report.get('other_recipient_unresolved_lines') != [8992, 9005]
            or report.get('independently_rejected_first_and_second_appeals_in_21_042') != 2
            or report.get('source_scope_is_all_spoken_paragraphs_not_appendices') is not True
            or report.get('missing_first_literal_wording_is_not_proof_of_missing_measure') is not True
            or report.get('no_person_attribution_by_keyword_proximity') is not True
            or report.get('explicit_other_sources_not_attributed_to_janich') is not True
            or report.get('public_counter_delta') != 0
            or report.get('automatic_effective_ordinal_count') != 0):
        raise ValueError('Vollständige Ursprungsaktenbelege erlauben keine Zähleränderung')
    out = [
        '# Janich: vollständige Suche im gesprochenen Originaltext 21/040', '',
        f"Geprüfte gesprochene Absätze: **{report['verified_spoken_paragraphs_in_original']}**.",
        f"Alle textuellen Ordnungsruf-/Ordnungsmaßnahme-Stellen: "
        f"**{report['total_order_related_text_locations']}**.",
        f"Nicht zugeschriebene Wortlaute zur Prüfung: "
        f"{len(report['unattributed_contexts_for_manual_review'])}; "
        f"davon Erteilungsverben: "
        f"{len(report['unattributed_explicit_issuance_wordings_for_manual_review'])}.",
        '', 'XML 8715: Sichert; XML 8717: bedingte Janich-Warnung; '
        'XML 8719: ausdrücklich Janichs zweiter Ruf.',
        'XML 8812: zusätzliche wörtliche Bestätigung des zweiten Janich-Rufs.',
        'XML 8990: ausdrücklich an Gottschalk gerichteter weiterer Ruf.',
        'XML 8992: anschließender zweiter Ruf ohne namentliche Empfängerangabe.',
        'XML 9005: Ruf gegen einen ausdrücklich unbekannten Zwischenrufer.',
        'Sitzung 21/042 belegt zwei getrennt zurückgewiesene Janich-Einsprüche.',
        '', '## Weitere Wortlaute zur manuellen Zuordnung', '',
    ]
    for row in report['unattributed_contexts_for_manual_review']:
        out.append(
            f"- [L{row['xml_line']}]({row['source']}): "
            f"{row['excerpt'][:330]} "
            '(nur Originaltext, kein automatischer Empfängerbeleg)')
    out.extend(['', '**Weder die erste ursprüngliche Janich-Erteilung noch '
                'die juristische Wirksamkeit wird automatisiert bestätigt.** '
                'Die Suche betrifft gesprochene Protokollabsätze, '
                'nicht alle denkbaren PDF-Anlagen oder Verfahrensakten.', ''])
    return '\n'.join(out)


def run(cache, output, brief, *, load=fetch):
    roots = {}
    for session in (40, 42):
        data = load(session, Path(cache))
        if data is None:
            raise ValueError('Amtliches Original-XML fehlt')
        roots[session] = safe_parse(data, session)
    evidence = official_review(roots)
    rows = [(int(p.sourceline), text)
            for p,text in iter_session_text(roots[40])]
    report = inspect_all_rows(rows, evidence)
    rendered = markdown(report)
    for target, value in (
            (Path(output), json.dumps(report, ensure_ascii=False, indent=2)+'\n'),
            (Path(brief), rendered)):
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix+'.tmp')
        temp.write_text(value, encoding='utf-8')
        temp.replace(target)
    print('WP21_JANICH_FULL_ORIGINAL_OK',
          report['verified_spoken_paragraphs_in_original'], 'spoken paragraphs,',
          report['total_order_related_text_locations'], 'original order contexts,',
          len(report['unattributed_explicit_issuance_wordings_for_manual_review']),
          'unattributed issuance wordings, no first-Janich or public counter inference')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--brief', type=Path, required=True)
    args = parser.parse_args()
    run(args.cache, args.output, args.brief)
