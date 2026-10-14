"""Independent recall-oriented audit of Bundestag transcript texts.

No new sanctions are ever confirmed by this program. It looks for text missed
by the restrictive extraction and flags questionable already-approved counts.
Use it after the normal parser/verifier in the GitHub workflow.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from lxml import etree

# Broad, intentionally different from parser.TERM_RE and parser.ACTION.
# These are SEARCH prompts, not evidence that an Ordnungsruf was imposed.
FIND_PATTERNS = {
    'ordnungsruf_wort': re.compile(r'\bOrdnungs\s*[-‐‑–—]?\s*ruf(?:e|es|en|s)?\b', re.I),
    'zur_ordnung': re.compile(r'\bzur\s+Ordnung\b', re.I),
    'ordnungs_call': re.compile(r'\b(?:in|zur)\s+Ordnung\s+(?:gerufen|rufe|rufen)\b', re.I),
    'ruf_zur_ordnung': re.compile(r'\b(?:Ruf|Rufe|Rufen)\s+zur\s+Ordnung\b', re.I),
    'ordnungs_massnahme': re.compile(r'\bOrdnungs\s*[-‐‑–—]?\s*maßnahm\w*\b', re.I),
}
RETURN_RE = re.compile(r'\b(?:zurück(?:genommen|gezogen|nehmen|nahme)|aufgehoben|widerrufen|wieder\s+aufgehoben|nicht\s+aufrechterhalten)\b', re.I)
APPEAL_RE = re.compile(r'\b(?:Einspruch|Einsprüche|Widerspruch|zurückweis\w*|zurückgewies\w*|abgelehnt|stattgegeben)\b', re.I)
CROSS_RE = re.compile(r'\b(?:gestrigen|gestern|vorgestern|vorigen|vorherigen|letzten|nachträglich|rückwirkend|in\s+der\s+vorangegangenen|am\s+Vortag)\b', re.I)
DIRECT_RE = re.compile(r'\b(?:ich\s+erteile|erteile\s+ich|einen\s+Ordnungsruf\s+erhält|bekommen\s+Sie|rufe\s+ich|ich\s+rufe)\b', re.I)

OFFICIAL = {
    'ordnungsrufe_20_wp': 135,
    'zurueckgenommene_zusaetzlich': 2,
    'top_personen': {'Stephan Brandner': 20, 'Beatrix von Storch': 19, 'Martin Reichardt': 7},
    'quelle': 'https://www.bundestag.de/resource/blob/196296/Kapitel_07_16_Ordnungsma__nahmen.pdf',
    'namens_quelle': 'https://www.bundestag.de/dokumente/textarchiv/1949-09-20-ordnungsruf-1086652',
}


def _normal(s):
    return ' '.join(s.split())


def load_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def save_csv(path, rows, fields):
    with Path(path).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def _element_text(elem):
    return _normal(''.join(elem.itertext()))


def scan_xml(path: Path):
    """Scan ALL p elements including appendices, rather than parser's handpicked parents.

    Paragraphs in the sitzungsverlauf receive higher scrutiny. Findings in
    footnotes/appendices are still included, explicitly marked as such.
    """
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False,
                             no_network=True, recover=False, huge_tree=False)
    root = etree.parse(str(path), parser).getroot()
    if (root.tag != 'dbtplenarprotokoll' or root.get('wahlperiode') != '20'
            or not root.get('sitzung-nr')):
        raise ValueError(f'Unerwartete XML-Datei: {path}')
    rows = []
    # Some XML texts omit direct p wrappers; scan standalone comments too.
    for p in root.iter():
        if p.tag not in ('p', 'kommentar'):
            continue
        if p.tag == 'kommentar' and any(a.tag == 'p' for a in p.iterancestors()):
            continue  # Avoid re-reading comment contained in a p paragraph.
        text = _element_text(p)
        if not text:
            continue
        matched = [key for key, expr in FIND_PATTERNS.items() if expr.search(text)]
        if not matched:
            continue
        within = any(a.tag == 'sitzungsverlauf' for a in p.iterancestors())
        rows.append({
            'datei': path.name,
            'sitzung': root.get('sitzung-nr'),
            'datum': root.get('sitzung-datum', ''),
            'xml_zeile': str(p.sourceline),
            'bereich': 'sitzungsverlauf' if within else 'ausserhalb_sitzungsverlauf',
            'xml_tag': p.tag,
            'klasse': p.get('klasse', ''),
            'suchmuster': ';'.join(matched),
            'ruecknahme_signal': 'ja' if RETURN_RE.search(text) else 'nein',
            'einspruch_signal': 'ja' if APPEAL_RE.search(text) else 'nein',
            'rueckbezug_signal': 'ja' if CROSS_RE.search(text) else 'nein',
            'direkte_formel': 'ja' if DIRECT_RE.search(text) else 'nein',
            'quell_url': f'https://dserver.bundestag.de/btp/20/{path.name}',
            'originaltext': text[:1600],
        })
    return rows


def compare(audit_rows, candidates, verified):
    """Produce *review queues*, never inferred confirmations."""
    known = {(r['file'], str(r['line'])) for r in candidates}
    new_rows, all_rows = [], []
    for r in audit_rows:
        entry = dict(r)
        entry['in_bisherigen_kandidaten'] = 'ja' if (r['datei'], r['xml_zeile']) in known else 'nein'
        # Priority indicates auditing urgency, not likelihood of a sanction.
        entry['pruefprioritaet'] = ('hoch' if entry['in_bisherigen_kandidaten'] == 'nein'
                                  and r['bereich'] == 'sitzungsverlauf' else 'mittel')
        if r['ruecknahme_signal'] == 'ja' or r['einspruch_signal'] == 'ja':
            entry['pruefprioritaet'] = 'hoch'
        if (r['bereich'] != 'sitzungsverlauf' or r['xml_tag'] == 'kommentar') and r['ruecknahme_signal'] == 'nein':
            entry['pruefprioritaet'] = 'niedrig'
        all_rows.append(entry)
        if entry['in_bisherigen_kandidaten'] == 'nein':
            new_rows.append(entry)
    alerts = [dict(r) for r in all_rows if any(r[k] == 'ja' for k in
              ('ruecknahme_signal', 'einspruch_signal', 'rueckbezug_signal'))]
    # Raw hits are NOT sanctions: repeats, legal explanations and remarks common.
    return all_rows, new_rows, alerts


def official_comparison(verified):
    by_name = Counter(r['person'] for r in verified)
    rows = [
        {'kennzahl': 'alle', 'person': '', 'amtlich_nach_ruecknahmen': 135,
         'bisher_bestaetigt_roh': len(verified),
         'differenz_amtlich_minus_roh': 135 - len(verified),
         'hinweis': 'Zaehlweisen noch NICHT gleichgesetzt; Rohfreigaben koennen Ruecknahmen enthalten'},
    ]
    for name, official in OFFICIAL['top_personen'].items():
        rows.append({'kennzahl': 'person', 'person': name,
                     'amtlich_nach_ruecknahmen': official,
                     'bisher_bestaetigt_roh': by_name[name],
                     'differenz_amtlich_minus_roh': official - by_name[name],
                     'hinweis': 'Unterschied kann Ruecknahmen, fehlende oder doppelte Faelle bedeuten'})
    return rows


def audit(folder: Path, candidates, verified):
    paths = sorted(folder.glob('20[0-9][0-9][0-9].xml'))
    session_ids = [int(p.stem[2:]) for p in paths]
    if session_ids != list(range(1, 215)):
        missing = sorted(set(range(1,215)) - set(session_ids))
        raise ValueError(f'Nicht alle 214 Protokolle vorhanden; fehlen: {missing[:30]}')
    raw = []
    for path in paths:
        raw.extend(scan_xml(path))
    all_rows, new_rows, alerts = compare(raw, candidates, verified)
    mismatch = official_comparison(verified)
    return {
        'treffer': all_rows,
        'neue_fundstellen': new_rows,
        'ruecknahmen_einsprueche_rueckbezuege': alerts,
        'amtlicher_abgleich': mismatch,
        'bericht': {
            'wahlperiode': 20,
            'protokolle_volltext_geprueft': len(paths),
            'audit_textstellen_insgesamt': len(all_rows),
            'gegen_kandidaten_neue_textstellen': len(new_rows),
            'neue_textstellen_im_sitzungsverlauf': sum(r['bereich'] == 'sitzungsverlauf' for r in new_rows),
            'hinweise_auf_ruecknahme_einspruch_oder_sitzungsuebergreifenden_bezug': len(alerts),
            'bisherige_verifizierte_rohmassnahmen': len(verified),
            'amtlich_gezaehlte_nicht_zurueckgenommene_ordnungsrufe': 135,
            'amtlich_weitere_zurueckgenommene': 2,
            'amtliche_personen_und_differenzen': mismatch,
            'hinweis': 'Audit-Treffer sind KEINE bestaetigten Massnahmen. Die 123 bisherigen Freigaben sind NICHT auf Ruecknahmen bereinigt.',
            'quellen': OFFICIAL,
        },
    }


def main():
    p = argparse.ArgumentParser(description='Unabhaengiger Recall- und Ruecknahmen-Audit der 20. Wahlperiode')
    p.add_argument('--source-folder', type=Path, default=Path('protokolle'))
    p.add_argument('--candidates', type=Path, default=Path('kandidaten.csv'))
    p.add_argument('--verified', type=Path, default=Path('bestaetigte_ordnungsrufe.csv'))
    p.add_argument('--out-folder', type=Path, default=Path('.'))
    args = p.parse_args()
    args.out_folder.mkdir(parents=True, exist_ok=True)
    result = audit(args.source_folder, load_csv(args.candidates), load_csv(args.verified))
    cols = ['datei', 'sitzung', 'datum', 'xml_zeile', 'bereich', 'xml_tag', 'klasse',
            'suchmuster', 'ruecknahme_signal', 'einspruch_signal', 'rueckbezug_signal',
            'direkte_formel', 'in_bisherigen_kandidaten', 'pruefprioritaet',
            'quell_url', 'originaltext']
    for filename, key in (
        ('audit_alle_fundstellen.csv', 'treffer'),
        ('audit_neue_fundstellen.csv', 'neue_fundstellen'),
        ('audit_ruecknahmen_einsprueche.csv', 'ruecknahmen_einsprueche_rueckbezuege'),
    ):
        save_csv(args.out_folder / filename, result[key], cols)
    save_csv(args.out_folder / 'audit_amtlicher_abgleich.csv',
             result['amtlicher_abgleich'],
             ['kennzahl','person','amtlich_nach_ruecknahmen','bisher_bestaetigt_roh',
              'differenz_amtlich_minus_roh','hinweis'])
    (args.out_folder / 'audit_bericht.json').write_text(
        json.dumps(result['bericht'], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['bericht'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
