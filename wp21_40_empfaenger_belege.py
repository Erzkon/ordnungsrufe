#!/usr/bin/env python3
"""Recipient context evidence for the official 21/040 Gottschalk/Mixl episode.

Preserve BOTH parliamentary speech ("name") and stenographic interjection
("kommentar") nodes: normal spoken-paragraph scans omit the latter.
Reconstruct guarded evidence from exact source line, tag, speech container,
speaker-change markers and original-text SHA-256.

A contextual attribution is NOT a final legally effective sanction, formal
person-linked decision, or authorization to modify the public counters.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from parser import normal
from wp21_scan import fetch, safe_parse
from wp21_janich_erste_quellenkritik import inspect as verify_21_040_and_042
from wp21_janich_full_original import OTHER_ANCHORS

SOURCE = 'https://dserver.bundestag.de/btp/21/21040.xml'
CONTAINER = 'ID214014100'
GOTTSCHALK_ID = '11004731'
TARGETS = {
    8989: 'name',
    8990: 'p',
    8992: 'p',
    8994: 'p',
    9002: 'kommentar',
    9004: 'name',
    9005: 'p',
    9006: 'kommentar',
    9007: 'p',
}
CHAIR = re.compile(r'\bVizepräsidentin\s+Andrea\s+Lindholz\b', re.I)
GOTTSCHALK_ADDRESS = re.compile(
    r'Herr\s+Kollege\s+Gottschalk,\s+ich\s+erteile\s+Ihnen\s+jetzt\s+'
    r'einen\s+Ordnungsruf', re.I)
SECOND = re.compile(r'ich\s+erteile\s+Ihnen\s+einen\s+zweiten\s+Ordnungsruf', re.I)
UNKNOWN = re.compile(r'Ich\s+weiß\s+nicht,\s+wer\s+es\s+war', re.I)
MIXL_PFUI = re.compile(r'Reinhard\s+Mixl\s*\[AfD\]\s*:\s*Pfui', re.I)
MIXL_ADMISSION = re.compile(r'Reinhard\s+Mixl\s*\[AfD\]\s*:\s*Ich\s+war', re.I)


def extract_speech_nodes(root):
    """Source-order nodes, including editorial interjection comments."""
    course = root.find('sitzungsverlauf')
    if course is None:
        raise ValueError('Amtlicher gesprochener Sitzungsverlauf fehlt')
    rows = []
    for node in course.iter():
        if not 8989 <= (node.sourceline or 0) <= 9007:
            continue
        if node.tag not in ('p', 'name', 'kommentar'):
            continue
        if node.tag == 'name' and any(
                parent.tag == 'redner' for parent in node.iterancestors()):
            continue
        parent_rede = next(
            (parent for parent in node.iterancestors() if parent.tag == 'rede'),
            None)
        # P element with klasse=redner is a speech attribution node.
        speaker = node.find('redner') if node.tag == 'p' else None
        rows.append({
            'xml_line': int(node.sourceline),
            'tag': node.tag,
            'class': node.get('klasse'),
            'speech_id': parent_rede.get('id') if parent_rede is not None else None,
            'redner_id': speaker.get('id') if speaker is not None else None,
            'text': normal(''.join(node.itertext())),
        })
    return rows


def review(rows, verified):
    if (not isinstance(rows, list) or not isinstance(verified, dict)
            or verified.get('schema') !=
               'wp21-janich-first-conditional-versus-second-grant-v1'
            or verified.get('first_independent_unconditional_issuance_xml_line') is not None
            or verified.get('documented_separately_rejected_objections') != 2
            or verified.get('public_counter_delta') != 0):
        raise ValueError('Ungeprüfte ursprüngliche Janich/Gottschalk-Quellen')
    source = {}
    previous = 0
    for row in rows:
        if (not isinstance(row, dict) or type(row.get('xml_line')) is not int
                or row['xml_line'] < previous
                or row['xml_line'] not in range(8989, 9008)
                or row.get('tag') not in ('p', 'kommentar', 'name')
                or not isinstance(row.get('text'), str)
                or not 0 < len(row['text']) < 8000):
            raise ValueError('Originalkommentare oder Redeabfolge beschädigt')
        previous = row['xml_line']
        if row['xml_line'] in TARGETS:
            if row['xml_line'] in source:
                raise ValueError('Doppelte amtliche Sprecher-/Zwischenrufzeile')
            source[row['xml_line']] = row
    if (set(source) != set(TARGETS)
            or any(source[n]['tag'] != tag for n,tag in TARGETS.items())):
        raise ValueError('Amtliche Quellenstruktur oder Sprecherzeile fehlt')
    for line in TARGETS:
        row = source[line]
        if row['speech_id'] != CONTAINER:
            raise ValueError('Rede-/Sprechergrenzen widersprechen amtlicher Sitzung')
    for line in (8990, 8992, 9005):
        if hashlib.sha256(source[line]['text'].encode()).hexdigest() != OTHER_ANCHORS[line]:
            raise ValueError('Amtliche Originalaussage nicht bytegleich zum belegten Kontext')
    for line in (8989, 9004):
        if not CHAIR.search(source[line]['text']):
            raise ValueError('Präsidium als sprechende Person nicht belegt')
    if (source[8994]['redner_id'] != GOTTSCHALK_ID
            or source[9007]['redner_id'] != GOTTSCHALK_ID
            or not re.search(r'Kay\s*Gottschalk',source[8994]['text'],re.I)
            or not re.search(r'Kay\s*Gottschalk',source[9007]['text'],re.I)
            or not GOTTSCHALK_ADDRESS.search(source[8990]['text'])
            or not SECOND.search(source[8992]['text'])):
        raise ValueError('Gottschalk-Anrede, zweiter Ruf oder dokumentierte Antwort fehlt')
    # In the raw transcript, there must be no intervening new chair/speaker
    # node between the directly addressed and continuing second issuance.
    if any(row['tag'] == 'name' or row.get('class') == 'redner'
           for row in rows if 8990 < row['xml_line'] < 8992):
        raise ValueError('Unbelegter Sprecherwechsel vor dem zweiten Ruf')
    if (not MIXL_PFUI.search(source[9002]['text'])
            or not MIXL_ADMISSION.search(source[9006]['text'])
            or not UNKNOWN.search(source[9005]['text'])):
        raise ValueError('Mixl-Zwischenruf, Selbsteinräumung oder Unkenntnis fehlt')
    if (not source[8994]['class'] == 'redner'
            or not source[9007]['class'] == 'redner'
            or not source[9002]['tag'] == source[9006]['tag'] == 'kommentar'):
        raise ValueError('Amtliche Redner- und Zwischenrufmarkierung fehlt')
    def cite(n):
        row=source[n]
        return {
            'xml_line':n,'original_source':SOURCE,'source_tag':row['tag'],
            'source_speech_id':row['speech_id'],
            'source_speaker_id':row.get('redner_id'),
            'source_sha256':hashlib.sha256(row['text'].encode()).hexdigest(),
            'original_excerpt':row['text'][:1100],
        }
    return {
        'schema':'wp21-21_040-gottschalk-mixl-speaker-and-interjection-review-v1',
        'official_original':SOURCE,
        'session':40,
        'gottschalk_immediate_second_issuance':{
            'initial_explicit_recipient':cite(8990),
            'same_chair_second_issuance':cite(8992),
            'immediate_recipient_reply':cite(8994),
            'context_supported_recipient':'Kay Gottschalk',
            'second_sentence_names_recipient_explicitly':False,
            'speech_continuity_and_reply_verified':True,
            'original_text_shows_two_separate_issuance_sentences':True,
            'appeal_or_legal_effect_confirmed':False,
        },
        'mixl_anonymous_interjection_and_admission':{
            'original_interjection_name_and_word':cite(9002),
            'chair_warning_did_not_identify_person':cite(9005),
            'immediate_self_admission':cite(9006),
            'context_supported_speaker':'Reinhard Mixl',
            'speaker_attribution_from_official_comments':True,
            'formal_recipient_named_at_issuance':False,
            'separate_appeal_or_legal_effect_confirmed':False,
        },
        'chair_speakers': [cite(8989),cite(9004)],
        'janich_first_unconditional_issuance_not_found_here':True,
        'no_attribution_of_9005_to_gottschalk_or_janich':True,
        'all_attributions_require_manual_legal_review':True,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'public_counter_delta':0,
    }


def markdown(report):
    if (report.get('schema') !=
            'wp21-21_040-gottschalk-mixl-speaker-and-interjection-review-v1'
            or report.get('janich_first_unconditional_issuance_not_found_here') is not True
            or report.get('no_attribution_of_9005_to_gottschalk_or_janich') is not True
            or report.get('all_attributions_require_manual_legal_review') is not True
            or report.get('automatically_confirmed_effective_sanctions') != 0
            or report.get('automatically_rescinded_sanctions') != 0
            or report.get('public_counter_delta') != 0
            or report.get('gottschalk_immediate_second_issuance',{}).get(
                'appeal_or_legal_effect_confirmed') is not False
            or report.get('mixl_anonymous_interjection_and_admission',{}).get(
                'separate_appeal_or_legal_effect_confirmed') is not False):
        raise ValueError('Sprecherkommentar ist keine Zähler- oder Rechtsfolgenfreigabe')
    return '\n'.join([
        '# 21/040: Zuordnung zweier zuvor unklarer Erteilungsformulierungen',
        '',
        '**XML 8992:** Unmittelbarer zweiter Ruf der Sitzungsleitung im '
        'selben Redebeitrag direkt nach der namentlichen Anrede an '
        'Kay Gottschalk (XML 8990); Gottschalk antwortet in XML 8994.',
        'Damit ist der direkte Adressatenkontext aus der Original-XML-Struktur '
        'gut belegt, der Empfänger steht aber nicht noch einmal im '
        'Wortlaut von XML 8992 selbst.',
        '',
        '**XML 9005:** Die Sitzungsleitung sagt, sie kenne den Zwischenrufer '
        'nicht. Der amtliche Stenografiekommentar identifiziert den '
        'vorangegangenen „Pfui“-Zwischenruf in XML 9002 mit Reinhard Mixl; '
        'der folgende Kommentar XML 9006 dokumentiert Mixls '
        'Selbsteinräumung. Eine namentliche Nennung durch die '
        'Sitzungsleitung im eigentlichen Erteilungssatz fehlt.',
        '',
        '**Keine neue automatisch bestätigte rechtswirksame Maßnahme.** '
        'Keine Änderung der öffentlichen Zähler, keine vermeintliche '
        'wörtliche erste Janich-Erteilung. Original-SHA-256 und Zeilen '
        'stehen in der getrennten JSON-Fallakte.',
        '',
    ])


def run(cache, output, brief, *, loader=fetch):
    roots = {}
    for sid in (40, 42):
        xml = loader(sid, Path(cache))
        if xml is None:
            raise ValueError('Amtliches Original-XML fehlt')
        roots[sid] = safe_parse(xml, sid)
    baseline = verify_21_040_and_042(roots)
    report = review(extract_speech_nodes(roots[40]), baseline)
    prose = markdown(report)
    for dest, content in (
            (Path(output), json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
            (Path(brief), prose)):
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_suffix(dest.suffix+'.tmp')
        temp.write_text(content, encoding='utf-8')
        temp.replace(dest)
    print('WP21_ORIGINAL_SPEAKER_CONTEXT_OK: Gottschalk 8990/8992/8994;',
          'Mixl 9002/9005/9006; zero count changes')
    return report


if __name__ == '__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--cache',type=Path,required=True)
    a.add_argument('--output',type=Path,required=True)
    a.add_argument('--brief',type=Path,required=True)
    args=a.parse_args()
    run(args.cache,args.output,args.brief)
