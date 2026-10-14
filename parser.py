"""Bundestag XML: extract review candidates and conservative person-linked Ordnungsrufe.

No text match alone establishes a final official count. The events output has a
review status and is not a public-facing verified dataset.
"""
import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path
from lxml import etree

PATTERN = re.compile(r'\bOrdnungsruf(?:e|es|en)?\b|\brufe\s+ich\s+.{0,100}?\bzur\s+Ordnung\b|\bzur\s+Ordnung\s+gerufen\b', re.I)
# Lists such as "die Abgeordneten X, Y und Z einen Ordnungsruf erhalten haben"
LIST_GRANT = re.compile(
    r'\bdie\s+Abgeordneten\s+([\wÀ-žÄÖÜäöüß ,.-]{3,240}?)\s+'
    r'(?:jeweils\s+)?(?:einen\s+Ordnungsruf\s+erhalten\s+haben|'
    r'(?:einen\s+)?Ordnungsruf\s+erhalten\s+haben)', re.I)
DIRECT_GRANT = re.compile(
    r'\b(?:Herr|Frau)\s+([A-ZÄÖÜ][\wÀ-žÄÖÜäöüß-]{1,50})\b'
    r'[^.!?]{0,150}?\b(?:einen\s+Ordnungsruf|zur\s+Ordnung\s+gerufen)\b', re.I)


def normal(text):
    return ' '.join(text.split())


def document(path):
    safe = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True,
                           recover=False, huge_tree=False)
    return etree.parse(str(path), safe).getroot()


def candidates(path):
    root = document(path)
    session, period = root.get('sitzung-nr', ''), root.get('wahlperiode', '')
    # Only actual session events; not introductory or appendix text.
    for element in root.iter():
        if element.tag not in ('p', 'kommentar') or element.getparent() is None:
            continue
        if element.getparent().tag not in ('rede', 'tagesordnungspunkt', 'sitzungsbeginn', 'sitzungsende', 'sitzungsverlauf'):
            continue
        raw = normal(''.join(element.itertext()))
        if PATTERN.search(raw):
            yield dict(file=path.name, wahlperiode=period, sitzung=session,
                       line=element.sourceline, text=raw[:1200], status='review_required')


def speaker_index(root):
    by_surname = defaultdict(dict)
    for node in root.iter('redner'):
        name = node.find('name')
        if name is None:
            continue
        surname = normal(name.findtext('nachname', default=''))
        first = normal(name.findtext('vorname', default=''))
        if surname and first:
            by_surname[surname.casefold()][node.get('id') or first] = {
                'person': f'{first} {surname}', 'person_id': node.get('id') or '',
                'fraktion': normal(name.findtext('fraktion', default=''))}
    return by_surname


def person_lookup(surname, index, context=''):
    matches = list(index.get(surname.casefold(), {}).values())
    if len(matches) == 1:
        return {**matches[0], 'identity_status': 'matched_xml_person'}
    # For names missing from a <redner> record, try the nearest attributed
    # interjection, but do not guess first names or party affiliation.
    alternatives = re.findall(
        r'([A-ZÄÖÜ][\wÀ-žÄÖÜäöüß-]+)\s+' + re.escape(surname) + r'\s*\[([^\]]+)\]', context)
    if len(set(alternatives)) == 1:
        first, party = alternatives[0]
        return dict(person=f'{first} {surname}', person_id='', fraktion=party,
                    identity_status='context_name_review')
    return dict(person=surname, person_id='', fraktion='',
                identity_status='surname_only_review')


def make_event(path, root, element, surname, kind, index, context=''):
    identified = person_lookup(surname, index, context)
    return dict(file=path.name, wahlperiode=root.get('wahlperiode', ''),
                sitzung=root.get('sitzung-nr', ''), datum=root.get('sitzung-datum', ''),
                person=identified['person'], person_id=identified['person_id'],
                fraktion=identified['fraktion'], identity_status=identified['identity_status'],
                event_type='Ordnungsruf', evidence_type=kind,
                line=element.sourceline, text=normal(''.join(element.itertext()))[:1200],
                status='review_required')


def events(path):
    """Extract named individual events, preferring explicit retrospective lists.

    An earlier unnamed group grant is deliberately not counted again.
    Unresolved grants are still visible in candidates.csv for manual review.
    """
    root = document(path)
    index = speaker_index(root)
    course = root.find('sitzungsverlauf')
    if course is None:
        return
    found = []
    for element in course.iter('p'):
        text = normal(''.join(element.itertext()))
        for match in LIST_GRANT.finditer(text):
            names = [x.strip() for x in re.split(r'\s*,\s*|\s+und\s+', match.group(1))]
            if not 2 <= len(names) <= 40 or any(len(x.split()) > 4 for x in names):
                continue
            for surname in names:
                found.append(make_event(path, root, element, surname, 'named_group_confirmation', index))
        for match in DIRECT_GRANT.finditer(text):
            # Collect nearby interjection, which often gives the full name.
            context = ''
            sib = element.getprevious()
            for _ in range(4):
                if sib is None: break
                if sib.tag == 'kommentar': context += ' ' + normal(''.join(sib.itertext()))
                sib = sib.getprevious()
            found.append(make_event(path, root, element, match.group(1),
                                    'direct_address', index, context))
    # Deduplicate repeated same-text hits only. Repeat sanctions on different
    # lines are possible and must NOT be automatically merged.
    seen = set()
    for item in found:
        key = (item['line'], item['person'].casefold())
        if key not in seen:
            seen.add(key)
            yield item


def save_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder', type=Path)
    ap.add_argument('--out', type=Path, default=Path('kandidaten.csv'))
    ap.add_argument('--events-out', type=Path, default=Path('ordnungsrufe.csv'))
    args = ap.parse_args()
    paths = sorted(args.folder.rglob('*.xml'))
    if not paths:
        ap.error('No XML files found')
    hits, sanctions = [], []
    for path in paths:
        hits.extend(candidates(path))
        sanctions.extend(events(path))
    save_csv(args.out, ['file', 'wahlperiode', 'sitzung', 'line', 'text', 'status'], hits)
    save_csv(args.events_out,
             ['file','wahlperiode','sitzung','datum','person','person_id','fraktion',
              'identity_status','event_type','evidence_type','line','text','status'], sanctions)
    print(f'{len(hits)} Textkandidaten; {len(sanctions)} personenbezogene, noch zu '
          f'pruefende Ordnungsrufe; {len(paths)} Protokolle.')
    print(f'Dateien: {args.out}, {args.events_out}. Nicht als amtliche Statistik verwenden.')


if __name__ == '__main__':
    main()
