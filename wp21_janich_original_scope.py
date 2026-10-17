#!/usr/bin/env python3
"""Bounded annotated ORIGINAL 21/040 context around Janich's conditional warning.

Even a separately evidenced FIRST reprimand in the later 21/042 decision
does not license fabricating an unconditional first issuing utterance. Keep
every paragraph in this XML neighbourhood with line numbers and raw-text
digests for human source inspection. Exclude other speakers' grants and
future conditional warnings from any automated attribution.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from parser import iter_session_text
from wp21_scan import fetch, safe_parse
from wp21_janich_erste_quellenkritik import inspect as inspect_known

BEFORE = 60
AFTER = 20
MAX_TEXT = 1350
KNOWN_CONDITIONAL = 8717
KNOWN_SECOND = 8719
ORIGINAL = 'https://dserver.bundestag.de/btp/21/21040.xml'
ISSUANCE = re.compile(
    r'\b(?:Ordnungsruf\w*|zur\s+Ordnung\s+ruf\w*)\b', re.I)
PERSON = re.compile(r'\b(?:Steffen\s+)?Janich\b', re.I)
CONTINGENT = re.compile(
    r'\b(?:wenn|falls|würde|werde|könnte|gleich\s+fürs\s+Lachen)\b', re.I)


def review(paragraphs, evidence, *, before=BEFORE, after=AFTER):
    if (not isinstance(paragraphs, list) or
            type(before) is not int or not 1 <= before <= 100
            or type(after) is not int or not 1 <= after <= 50):
        raise ValueError('Unerlaubte Änderung am amtlichen Prüfkontext')
    if (not isinstance(evidence, dict)
            or evidence.get('schema') !=
                'wp21-janich-first-conditional-versus-second-grant-v1'
            or evidence.get('first_independent_unconditional_issuance_xml_line')
                is not None
            or evidence.get('conditional_notice_is_not_unconditional_issuance_proof') is not True
            or evidence.get('documented_separately_rejected_objections') != 2
            or evidence.get('public_counter_delta') != 0):
        raise ValueError('Unverifizierte Janich-Erteilungs-/Einspruchsakte')
    anchors = {}
    for label, name in (
            ('janich_conditional_laughter_warning', 'conditional'),
            ('janich_explicit_second_issuance', 'second')):
        record = evidence['source_passages'][label]
        anchors[name] = record['xml_line']
    if anchors != {'conditional': KNOWN_CONDITIONAL, 'second': KNOWN_SECOND}:
        raise ValueError('Amtliche Janich-Zeilenidentitäten verändert')
    locations = [i for i, item in enumerate(paragraphs)
                 if isinstance(item, tuple) and len(item) == 2
                 and item[0] == KNOWN_CONDITIONAL]
    if len(locations) != 1:
        raise ValueError('Bedingte Warnung nicht eindeutig auffindbar')
    i = locations[0]
    span = paragraphs[max(0, i-before):min(len(paragraphs),i+after+1)]
    documented = []
    seen = set()
    for line, text in span:
        if (type(line) is not int or line <= 0 or line in seen
                or not isinstance(text, str) or not text.strip()
                or len(text) > 12000):
            raise ValueError('Unzuverlässige Original-XML-Passage')
        seen.add(line)
        label = ('known_conditional_warning' if line == KNOWN_CONDITIONAL
                 else 'known_explicit_second_grant' if line == KNOWN_SECOND
                 else 'other_source_context_no_attribution')
        documented.append({
            'xml_line':line, 'original_source':ORIGINAL,
            'paragraph_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'text_excerpt':' '.join(text.split())[:MAX_TEXT],
            'contains_order_words':bool(ISSUANCE.search(text)),
            'contains_janich_name':bool(PERSON.search(text)),
            'has_conditional_wording':bool(CONTINGENT.search(text)),
            'source_role':label,
            'automatic_first_issuance_attribution':False,
            'requires_manual_recipient_check':label.startswith('other_'),
        })
    if (KNOWN_CONDITIONAL not in seen or KNOWN_SECOND not in seen
            or len(documented) < 5):
        raise ValueError('Amtlicher Kontext um Warnung und zweiten Ruf fehlt')
    first = next(x for x in documented
                 if x['xml_line'] == KNOWN_CONDITIONAL)
    second = next(x for x in documented if x['xml_line'] == KNOWN_SECOND)
    if (first['paragraph_sha256'] != evidence['source_passages'][
            'janich_conditional_laughter_warning']['paragraph_sha256']
            or second['paragraph_sha256'] != evidence['source_passages'][
            'janich_explicit_second_issuance']['paragraph_sha256']
            or not first['has_conditional_wording']
            or not second['contains_order_words']):
        raise ValueError('Belegte Original-XML-Warnung/Zweiterteilung stimmt nicht')
    return {
        'schema':'wp21-janich-first-original-neighbourhood-v1',
        'session':40,'known_conditional_warning_xml_line':KNOWN_CONDITIONAL,
        'known_second_grant_xml_line':KNOWN_SECOND,
        'first_original_unconditional_issuance_xml_line':None,
        'first_measure_documented_only_in_later_decision':True,
        'second_measure_original_utterance_verified':True,
        'separate_first_and_second_appeals_rejected':True,
        'scope_only_bounded_neighbourhood_not_whole_sitting':True,
        'speaker_recipient_not_automatically_inferred':True,
        'source_paragraphs':documented,
        'potential_manual_review_paragraphs':[
            x for x in documented
            if x['contains_order_words']
            and x['source_role'] == 'other_source_context_no_attribution'],
        'automatic_legal_measure_count':0,
        'public_counter_delta':0,
    }


def markdown(r):
    if (r.get('schema') != 'wp21-janich-first-original-neighbourhood-v1'
            or r.get('first_original_unconditional_issuance_xml_line') is not None
            or r.get('first_measure_documented_only_in_later_decision') is not True
            or r.get('scope_only_bounded_neighbourhood_not_whole_sitting') is not True
            or r.get('speaker_recipient_not_automatically_inferred') is not True
            or r.get('public_counter_delta') != 0
            or r.get('automatic_legal_measure_count') != 0):
        raise ValueError('Original-Kontext darf keine erste Erteilung erfinden')
    lines = [
        '# Janich 21/040: begrenzter ORIGINAL-Wortlaut um die bedingte Warnung',
        '',
        'Bekannte bedingte Warnung: XML 8717; eindeutige zweite Erteilung: XML 8719.',
        'Die erste unbedingte Erteilung ist NICHT als Wortlaut lokalisiert.',
        'Erster und zweiter Ruf sind durch getrennte amtliche '
        'Einspruchsentscheidungen aus 21/042 belegt.', '',
        f"Vollständig geprüfte unmittelbare Originalabsätze: "
        f"{len(r['source_paragraphs'])}.",
        f"Weitere Ordnungsruf-Wortlaute ohne geprüfte Zuordnung: "
        f"{len(r['potential_manual_review_paragraphs'])}.", '',
    ]
    for item in r['potential_manual_review_paragraphs']:
        lines.append(
            f"- [XML 21/040 L{item['xml_line']}]({item['original_source']}): "
            f"{item['text_excerpt'][:320]} "
            '**nur Quellkontext, keine zugeordnete erste Erteilung**')
    lines.extend([
        '', '**Kein automatischer Empfänger- oder Rechtsfolgenbeweis.** '
        'Auch diese Untersuchung eines begrenzten Umfelds ersetzt keine '
        'personenscharfe vollständige Originalaktenprüfung.',''])
    return '\n'.join(lines)


def run(cache,output,brief,*,load=fetch):
    roots = {}
    for session in (40,42):
        raw = load(session,Path(cache))
        if raw is None:
            raise ValueError('Amtliches Original-XML fehlt')
        roots[session] = safe_parse(raw,session)
    verified = inspect_known(roots)
    rows = [(int(p.sourceline),text)
            for p,text in iter_session_text(roots[40])]
    result = review(rows,verified)
    rendered = markdown(result)
    for dest,content in (
            (Path(output),json.dumps(result,ensure_ascii=False,indent=2)+'\n'),
            (Path(brief),rendered)):
        dest.parent.mkdir(parents=True,exist_ok=True)
        tmp = dest.with_suffix(dest.suffix+'.tmp')
        tmp.write_text(content,encoding='utf-8')
        tmp.replace(dest)
    print('WP21_JANICH_ORIGINAL_NEIGHBOURHOOD_OK',
          len(result['source_paragraphs']), 'original paragraphs,',
          len(result['potential_manual_review_paragraphs']),
          'unattributed keyword sources, first literal issuance still unlocated,',
          'zero count changes')
    return result


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--cache',type=Path,required=True)
    cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--brief',type=Path,required=True)
    opts = cli.parse_args()
    run(opts.cache,opts.output,opts.brief)
