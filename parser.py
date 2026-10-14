"""Conservative candidate extractor for Bundestag plenary XML.

Candidates are NOT verified Ordnungsrufe. Review each candidate manually.
"""
import argparse
import csv
import re
from pathlib import Path
from lxml import etree

PATTERN = re.compile(r'\bOrdnungsruf(?:e|es|en)?\b|\brufe\s+ich\s+.{0,100}?\bzur\s+Ordnung\b|\bzur\s+Ordnung\s+gerufen\b', re.I)


def candidates(path):
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=False)
    root = etree.parse(str(path), parser)
    session = root.getroot().get('sitzung-nr', '')
    period = root.getroot().get('wahlperiode', '')
    for element in root.iter():
        # XML format uses <p> for prose and <kommentar> for editorial remarks.
        if etree.QName(element).localname not in ('p', 'kommentar'):
            continue
        # Avoid duplicate matches when nested elements also contain text.
        if any(etree.QName(a).localname in ('p', 'kommentar') for a in element.iterancestors()):
            continue
        raw = ' '.join(' '.join(element.itertext()).split())
        if PATTERN.search(raw):
            yield {'file': path.name, 'wahlperiode': period, 'sitzung': session,
                   'line': element.sourceline, 'text': raw[:1200],
                   'status': 'review_required'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder', type=Path, help='Directory containing downloaded Bundestag XML files')
    ap.add_argument('--out', type=Path, default=Path('candidates.csv'))
    args = ap.parse_args()
    paths = sorted(args.folder.rglob('*.xml'))
    if not paths:
        ap.error('No XML files found')
    rows = []
    for path in paths:
        try:
            rows.extend(candidates(path))
        except etree.XMLSyntaxError as exc:
            print(f'Skipping invalid XML {path}: {exc}')
    with args.out.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['file','wahlperiode','sitzung','line','text','status'])
        writer.writeheader()
        writer.writerows(rows)
    print(f'{len(rows)} text candidates across {len(paths)} files; not verified counts. Saved to {args.out}')

if __name__ == '__main__':
    main()
