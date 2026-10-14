"""Independent DIP cross-check of Bundestag Ordnungsruf decisions.

Reads the public DIP API's *complete* Vorgang list for one electoral term and
finds all titles mentioning an Ordnungsruf. For each matching Vorgang it reads
Vorgangspositionen to locate the plenary session. No entries are approved or
changed by this script. The API's metadata is not necessarily exhaustive and
its document counts are NOT comparable to individual sanctions.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = 'https://search.dip.bundestag.de/api/v1'
# The Bundestag publishes this *public* key at https://dip.bundestag.de/über-dip/hilfe/api
# It is currently announced as valid only through May 2027. Override with DIP_API_KEY.
PUBLIC_DIP_KEY = 'R2BZaee.DjdCyihKZMf8AOjtScubP2EVydegzjmBIQ'
ORDNUNG_RE = re.compile(r'\bordnungs[\s-]*ruf\w*', re.IGNORECASE)
MEHRFACH_RE = re.compile(r'\b(?:zwei|drei|vier|fünf|sechs|sieben|acht|mehrere)\s+ordnungs[\s-]*ruf', re.I)
SESS_RE = re.compile(r'(?<!\d)20\s*/\s*0*(\d{1,3})(?!\d)')


def load_verified(path: Path) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8-sig', newline='') as h:
        rows = list(csv.DictReader(h))
    if not rows or not {'sitzung', 'person', 'ereignis_id'}.issubset(rows[0]):
        raise ValueError('Verifizierte Personenmassnahmen fehlen oder Kopfzeile passt nicht')
    return rows


def clean(text: str) -> str:
    text = text.lower().replace('ß', 'ss')
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'\b(?:dr|prof|abg|abgeordneten|abgeordnete|herr|frau)\b', ' ', text)
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def session_numbers(obj: object) -> set[int]:
    """Find explicit 20/NNN references in metadata without inferring a session."""
    found: set[int] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ('wahlperiode', 'id', 'vorgang_id'):
                continue
            found.update(session_numbers(value))
    elif isinstance(obj, list):
        for value in obj:
            found.update(session_numbers(value))
    elif isinstance(obj, str):
        found.update(int(s) for s in SESS_RE.findall(obj) if 1 <= int(s) <= 214)
    return found


def request_json(endpoint: str, params: dict[str, str], key: str, sleep=time.sleep,
                 opener=urlopen) -> dict:
    url = BASE + endpoint + '?' + urlencode(params)
    last = None
    for attempt in range(5):
        try:
            req = Request(url, headers={
                'Authorization': 'ApiKey ' + key,
                'User-Agent': 'ordnungsrufe-public-audit/1.0 (noncommercial; GitHub Actions)',
                'Accept': 'application/json',
            })
            with opener(req, timeout=45) as response:
                data = response.read(8_000_000 + 1)
                if len(data) > 8_000_000:
                    raise ValueError('DIP-Antwort ist unerwartet gross')
                payload = json.loads(data)
            if not isinstance(payload, dict):
                raise ValueError('DIP-Antwort ist kein JSON-Objekt')
            return payload
        except HTTPError as e:
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
        except (URLError, TimeoutError) as e:
            last = e
        if attempt < 4:
            sleep(min(2 ** attempt, 15))
    raise RuntimeError(f'DIP-Antwort nach fuenf Versuchen fehlgeschlagen: {type(last).__name__}') from last


def iter_pages(endpoint: str, filters: dict[str, str], key: str, fetch=request_json,
               max_pages: int = 5000):
    """Cursor pagination; fail closed on truncation, duplicates or invalid cursors."""
    seen_ids: set[str] = set()
    cursor = None
    total_expected = None
    for page_no in range(max_pages):
        params = dict(filters)
        if cursor:
            params['cursor'] = cursor
        payload = fetch(endpoint, params, key)
        docs = payload.get('documents')
        found = payload.get('numFound')
        next_cursor = payload.get('cursor')
        if not isinstance(docs, list) or not isinstance(found, int) or found < 0:
            raise ValueError('DIP-Paginierung: ungueltiges Dokumentenformat')
        if total_expected is None:
            total_expected = found
        elif found != total_expected:
            raise ValueError('DIP-Paginierung: Gesamtzahl hat sich geaendert; bitte neu starten')
        if not isinstance(next_cursor, str):
            raise ValueError('DIP-Paginierung: Cursor fehlt')
        for doc in docs:
            if not isinstance(doc, dict) or not str(doc.get('id', '')).isdigit():
                raise ValueError('DIP-Vorgang ohne gueltige ID')
            id_ = str(doc['id'])
            if id_ in seen_ids:
                raise ValueError(f'DIP lieferte dieselbe ID mehrfach: {id_}')
            seen_ids.add(id_)
            yield doc
        if len(seen_ids) == total_expected:
            return
        if not docs or not next_cursor or next_cursor == cursor:
            raise ValueError(f'DIP-Abfrage vorzeitig beendet: {len(seen_ids)}/{total_expected}')
        cursor = next_cursor
    raise ValueError('DIP-Abfrage hat die Sicherheitsgrenze fuer Seiten erreicht')


def classify(title: str) -> str:
    t = clean(title)
    if any(w in t for w in ('einspruch', 'rucknahme', 'zurucknahme', 'aufhebung', 'widerruf')):
        return 'einspruch_ruecknahme_oder_folge'
    if 'ordnungsgeld' in t and 'ordnungsruf' not in t:
        return 'nur_ordnungsgeld'
    if any(w in t for w in ('erteilung', 'ordnungsruf an', 'ordnungsrufe an', 'ordnung gerufen', 'ordnungsruf gegen')):
        return 'moegliche_erteilung'
    return 'sonstiger_ordnungsrufbezug'


def row_for(doc: dict, positions: list[dict], by_session: dict[int, list[dict]]) -> dict:
    title = str(doc.get('titel') or '')
    numbers: set[int] = set()
    for pos in positions:
        numbers.update(session_numbers(pos))
    verified = [r for n in numbers for r in by_session.get(n, [])]
    persons = sorted({r['person'] for r in verified})
    title_norm = clean(title)
    probable_matches = sorted({p for p in persons if clean(p) in title_norm})
    multiple = bool(MEHRFACH_RE.search(title)) or 'je eines ordnungsruf' in title_norm
    if not numbers:
        status = 'protokollfundstelle_fehlt'
    elif not verified:
        status = 'in_keiner_geprueften_massnahme_dieser_sitzung'
    elif multiple:
        status = 'mehrfachvergabe_anzahl_pruefen'
    elif probable_matches:
        status = 'person_und_sitzung_vorhanden_manuell_abgleichen'
    else:
        status = 'sitzung_vorhanden_empfaenger_pruefen'
    return {
        'dip_id': str(doc['id']),
        'dip_url': f"https://dip.bundestag.de/vorgang/{doc['id']}",
        'dip_titel': title,
        'dip_datum': str(doc.get('datum') or ''),
        'dip_vorgangstyp': str(doc.get('vorgangstyp') or ''),
        'typ_hinweis': classify(title),
        'sitzungen_aus_dip': ';'.join(str(n) for n in sorted(numbers)),
        'anzahl_dip_positionen': str(len(positions)),
        'verifizierte_personen_in_sitzungen': '; '.join(persons),
        'im_titel_namentlich_gefundene_personen': '; '.join(probable_matches),
        'mehrfachvergabe_hinweis': 'ja' if multiple else 'nein',
        'abgleichstatus': status,
    }


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def run(verified_path: Path, out_dir: Path, api_key: str, fetch=request_json):
    verified = load_verified(verified_path)
    by_session: dict[int, list[dict]] = defaultdict(list)
    for r in verified:
        by_session[int(r['sitzung'])].append(r)
    all_count = 0
    candidates = []
    for doc in iter_pages('/vorgang', {'f.wahlperiode': '20'}, api_key, fetch=fetch):
        all_count += 1
        if int(doc.get('wahlperiode', 0)) != 20:
            raise ValueError('DIP lieferte Vorgang aus anderer Wahlperiode')
        title = str(doc.get('titel') or '')
        if ORDNUNG_RE.search(title):
            candidates.append(doc)
    if not candidates:
        raise ValueError('Kein einziger Ordnungsrufvorgang gefunden – Datenquelle pruefen')
    rows = []
    for i, doc in enumerate(candidates, 1):
        positions = list(iter_pages('/vorgangsposition', {'f.vorgang': str(doc['id'])}, api_key, fetch=fetch))
        rows.append(row_for(doc, positions, by_session))
        if i % 25 == 0:
            print(f'DIP: {i}/{len(candidates)} einschlaegige Vorgangspositionen abgefragt', flush=True)
    rows.sort(key=lambda r: (r['dip_datum'], r['dip_id']))
    urgent = [r for r in rows if r['abgleichstatus'] != 'person_und_sitzung_vorhanden_manuell_abgleichen']
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    write_csv(out_dir / 'dip_alle_ordnungsrufbezuege.csv', rows, fields)
    write_csv(out_dir / 'dip_pruefliste.csv', urgent, fields)
    counts = defaultdict(int)
    for r in rows:
        counts[r['abgleichstatus']] += 1
    report = {
        'wahlperiode': 20,
        'auswertung': 'Unabhaengiger Metadatenabgleich; keine automatische Freigabe',
        'dip_vorgaenge_insgesamt_geprueft': all_count,
        'dip_vorgaenge_mit_ordnungsruf_im_titel': len(rows),
        'nach_abgleichstatus': dict(sorted(counts.items())),
        'dip_eintraege_in_pruefliste': len(urgent),
        'bisher_personenmassnahmen': len(verified),
        'bisher_verschiedene_ereignisse': len({r['ereignis_id'] for r in verified}),
        'amtlicher_gesamtwert_nach_ruecknahmen': 135,
        'erlaeuterung': ('DIP-Vorgaenge und personenbezogene Massnahmen haben verschiedene Zaehleinheiten. '
                        'Metadaten koennen fehlen oder mehrere Massnahmen zusammenfassen. '
                        'Personenabgleich ist nur eine unsichere Namensheuristik. '
                        'Keine CSV-Zeile bestaetigt einen neuen Ordnungsruf.'),
        'quelle': 'https://dip.bundestag.de/über-dip/hilfe/api',
    }
    (out_dir / 'dip_bericht.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"DIP abgeschlossen: {all_count} Vorgänge; {len(rows)} Ordnungsruf-Bezüge; {len(urgent)} Prüffälle")
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verified', type=Path, required=True)
    p.add_argument('--out-folder', type=Path, default=Path('.'))
    args = p.parse_args()
    key = os.environ.get('DIP_API_KEY', PUBLIC_DIP_KEY).strip()
    if not key:
        raise SystemExit('DIP_API_KEY fehlt')
    run(args.verified, args.out_folder, key)


if __name__ == '__main__':
    main()
