#!/usr/bin/env python3
"""DIP procedure-position shadow monitor linked to already discovered WP21 cases.

The official /vorgangsposition endpoint supports f.vorgang=<DIP Vorgang ID>.
It is queried for every previously observed relevant Vorgang, including
entries later renamed/retired. Fetch ALL pages for a parent before accepting
its updated positions. An API failure does not change any published state.

Neither the wording nor the existence of a position determines whether a
sanction was legally upheld or rescinded. No verified ledger is modified.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from wp21_dip_monitor import (PUBLIC_KEY, MAX_MATCHES, digest, iso, load_state,
                              request_page, utc)

API_POSITIONS = 'https://search.dip.bundestag.de/api/v1/vorgangsposition'
MAX_PARENTS = 350
MAX_POSITIONS = 5000
MAX_PER_PARENT = 300
LEGAL = re.compile(r'\b(?:einspruch\w*|widerspruch\w*|zur[uü]ck\w*|'
                   r'aufheb\w*|widerruf\w*|anfecht\w*|'
                   r'abgelehnt\w*|abgewiesen\w*|'
                   r'stattgegeben\w*|zur[uü]ckgewiesen\w*)', re.I)


def position_page(params, key):
    return request_page(params, key, endpoint=API_POSITIONS)


def fetch_positions(parent_id, key, load=position_page):
    """Follow official cursor semantics, rejecting incomplete or mixed lists."""
    ident = str(parent_id)
    if not re.fullmatch(r'[1-9]\d{0,11}', ident):
        raise ValueError('DIP-Vorgang-ID ungültig')
    cursor = None
    visited = set()
    seen = set()
    found = []
    total = None
    for _ in range(10):  # at most 1000 rows, also checked against MAX_PER_PARENT
        query = {'f.vorgang': ident, 'f.wahlperiode': '21'}
        if cursor is not None:
            query['cursor'] = cursor
        response = load(query, key)
        if not isinstance(response, dict):
            raise ValueError('DIP-Position: ungültige JSON-Struktur')
        docs = response.get('documents')
        size = response.get('numFound')
        next_cursor = response.get('cursor')
        if (not isinstance(docs, list) or len(docs) > 100
                or type(size) is not int or not 0 <= size <= MAX_PER_PARENT
                or not isinstance(next_cursor, (str, type(None)))):
            raise ValueError('DIP-Position: ungültige Seite oder zu große Ergebnismenge')
        if total is not None and total != size:
            raise ValueError('DIP-Position: wechselnde Trefferzahl')
        total = size
        for doc in docs:
            if not isinstance(doc, dict):
                raise ValueError('DIP-Position: Eintrag kein Objekt')
            position_id = str(doc.get('id', ''))
            belongs = str(doc.get('vorgang_id', ''))
            if (not re.fullmatch(r'[1-9]\d{0,11}', position_id)
                    or belongs != ident
                    or (doc.get('wahlperiode') is not None
                        and doc['wahlperiode'] != 21)
                    or position_id in seen):
                raise ValueError('DIP-Position: falscher Vorgang, Wahlperiode oder Dublette')
            seen.add(position_id)
            found.append(doc)
        if len(found) == size:
            return found
        if not docs or not next_cursor or next_cursor == cursor or next_cursor in visited:
            raise ValueError('DIP-Position: Cursor unvollständig oder zyklisch')
        visited.add(next_cursor)
        cursor = next_cursor
    raise ValueError('DIP-Position: Seitenlimit erreicht')


def position_document_evidence(raw):
    """Preserve validated Bundestag and Bundesrat DIP plenary references.

    DIP uses dokumentart="Plenarprotokoll" for both chambers. Bundesrat
    records have a numerical document number (e.g. 1058), a /brp/ PDF,
    and no Bundestag XML. Never map a Bundesrat session to a Bundestag
    sitting or infer legal effectiveness from the referenced protocol.
    """
    fund=raw.get('fundstelle')
    session=None
    bundesrat_session=None
    chamber=None
    docdate=None
    pdf=None
    xml=None
    if fund is not None:
        if not isinstance(fund,dict):
            raise ValueError('DIP-Fundstelle ist kein Objekt')
        if fund.get('dokumentart')=='Plenarprotokoll':
            number=fund.get('dokumentnummer')
            docdate=fund.get('datum')
            pdf=fund.get('pdf_url')
            xml=fund.get('xml_url')
            if type(docdate)!=str:
                raise ValueError('Kein amtliches Protokolldatum')
            datetime.strptime(docdate,'%Y-%m-%d')
            if raw.get('datum') and raw['datum']!=docdate:
                raise ValueError('DIP-Position und Protokolltag widersprechen sich')
            if not isinstance(number,str):
                raise ValueError('Unerwartete Fundstellen-Sitzungsnummer')
            if re.fullmatch(r'21/[1-9]\d{0,2}',number):
                chamber='Bundestag'
                session=int(number.split('/')[1])
                expected=f'https://dserver.bundestag.de/btp/21/21{session:03d}'
                if (xml!=expected+'.xml' or type(pdf)!=str
                        or not re.fullmatch(re.escape(expected)+r'\.pdf#P\.[1-9]\d{0,5}',pdf)):
                    raise ValueError('DIP-Fundstelle hat nichtamtliche oder fremde Links')
            elif re.fullmatch(r'[1-9]\d{2,3}',number):
                # Actual official DIP records 670644, 678924 and 678887
                # reference Bundesrat plenary documents 1054 and 1058.
                # Keep that evidence separate from WP21 Bundestag sittings.
                chamber='Bundesrat'
                bundesrat_session=int(number)
                expected=f'https://dserver.bundestag.de/brp/{number}'
                if (xml is not None or type(pdf)!=str
                        or not re.fullmatch(re.escape(expected)+r'\.pdf#P\.[1-9]\d{0,5}',pdf)):
                    raise ValueError('DIP-Bundesratsfundstelle hat nichtamtliche oder fremde Links')
            else:
                raise ValueError('Unerwartete Fundstellen-Sitzungsnummer')
    raw_tenors=raw.get('beschlussfassung') or []
    if not isinstance(raw_tenors,list) or len(raw_tenors)>10:
        raise ValueError('DIP-Beschlussfassung ungültig')
    tenors=[]
    for entry in raw_tenors:
        if not isinstance(entry,dict):
            raise ValueError('Beschlussfassung muss strukturierter Eintrag sein')
        text=entry.get('beschlusstenor')
        if not isinstance(text,str) or not text or len(text)>300:
            raise ValueError('DIP-Beschlusstenor fehlt oder ist ungültig')
        tenors.append(' '.join(text.split()))
    if len(tenors)!=len(set(tenors)):
        raise ValueError('Doppelte DIP-Beschlusstenöre')
    abstract=raw.get('abstract') or ''
    if not isinstance(abstract,str) or len(abstract)>5000:
        raise ValueError('DIP-Positionsabstract ungültig')
    return {
        'official_plenary_chamber':chamber,
        'official_bundesrat_session':bundesrat_session,
        'official_plenary_session':session,
        'official_plenary_date':docdate,
        'official_plenary_pdf_url':pdf,
        'official_plenary_xml_url':xml,
        'official_decision_tenors':tenors,
        'official_position_abstract_excerpt':' '.join(abstract.split())[:500],
        'source_metadata_is_only_a_review_hint':True,
    }


def normalize_position(raw):
    ident = str(raw['id'])
    parent = str(raw['vorgang_id'])
    title = raw.get('titel') or ''
    step = raw.get('vorgangsposition') or ''
    if not isinstance(title, str) or not isinstance(step, str):
        raise ValueError('DIP-Position: unerwartete Textfelder')
    # Only use the explicit description of the procedural step.
    text = ' '.join(step.split())[:650]
    # The official endpoint's "vorgangsposition" field is often only a
    # category ("Ordnungsruf"). The actual description is in "titel" and
    # sometimes in nested "aktivitaet_anzeige" entries. Check all three
    # metadata sources, but never infer legal outcome from a keyword.
    activities = raw.get('aktivitaet_anzeige') or []
    if not isinstance(activities,list) or len(activities)>50:
        raise ValueError('DIP-Position: Aktivitäten im unerwarteten Format')
    activity_text=[]
    for activity in activities:
        if not isinstance(activity,dict):
            raise ValueError('DIP-Position: Aktivität kein Objekt')
        for field in ('titel','aktivitaetsart'):
            fragment=activity.get(field) or ''
            if not isinstance(fragment,str):
                raise ValueError('DIP-Position: Aktivitätsbeschreibung ungültig')
            activity_text.append(fragment[:500])
    signal_fields=[]
    if LEGAL.search(step):
        signal_fields.append('vorgangsposition')
    if LEGAL.search(title):
        signal_fields.append('titel')
    if LEGAL.search(' '.join(activity_text)):
        signal_fields.append('aktivitaet_anzeige')
    extra=position_document_evidence(raw)
    if LEGAL.search(' '.join(extra['official_decision_tenors'])):
        signal_fields.append('beschlussfassung')
    if LEGAL.search(extra['official_position_abstract_excerpt']):
        signal_fields.append('abstract')
    updated = iso(utc(raw['aktualisiert']))
    date = raw.get('datum') or ''
    if date:
        datetime.strptime(date, '%Y-%m-%d')
    return {
        'id': ident, 'parent_id': parent, 'updated': updated, 'date': date,
        'title': ' '.join(title.split())[:250], 'step': text,
        'kind': 'moegliche_rechtsfolge' if signal_fields else 'verfahrensschritt',
        'signal_fields':signal_fields,
        'afterword': bool(raw.get('nachtrag', False)),
        'source': 'https://dip.bundestag.de/vorgang/' + parent,
        **extra,
    }


def read_position_state(path):
    target = Path(path)
    if not target.exists():
        return {'schema': 'dip21-positionen-v1', 'last_success_utc': None, 'items': {}}
    raw = json.loads(target.read_text(encoding='utf-8'))
    if raw.get('schema') != 'dip21-positionen-v1' or not isinstance(raw.get('items'), dict):
        raise ValueError('DIP-Positions-Cache ungültig')
    if raw.get('last_success_utc'):
        utc(raw['last_success_utc'])
    if len(raw['items']) > MAX_POSITIONS:
        raise ValueError('DIP-Positions-Cache zu groß')
    for key, doc in raw['items'].items():
        if (not re.fullmatch(r'[1-9]\d{0,11}', key)
                or doc.get('id') != key
                or not re.fullmatch(r'[1-9]\d{0,11}', str(doc.get('parent_id','')))
                or doc.get('source') !=
                'https://dip.bundestag.de/vorgang/' + doc['parent_id']):
            raise ValueError('DIP-Positions-Cache enthält ungültigen Quelllink')
    return raw


def evaluate(current, raw_positions, parents, now):
    """Classify added, changed and disappeared positions without legal judgment."""
    seen = set()
    changes = []
    previous = current['items']
    merged = dict(previous)
    for p in raw_positions:
        record = normalize_position(p)
        ident = record['id']
        if ident in seen:
            raise ValueError('DIP-Position über mehrere Vorgänge doppelt')
        if record['parent_id'] not in parents:
            raise ValueError('DIP-Position ohne überwachten Ursprungs-Vorgang')
        seen.add(ident)
        was = previous.get(ident)
        record['active'] = True
        if was is None:
            change = 'neu'
        elif digest({k: v for k,v in was.items() if k != 'active'}) != digest(
                {k: v for k,v in record.items() if k != 'active'}) or not was.get('active', True):
            change = 'aktualisiert'
        else:
            change = None
        merged[ident] = record
        if change:
            changes.append({'id':ident,'vorgang_id':record['parent_id'],
                            'change':change,'kind':record['kind'],
                            'step':record['step'][:230], 'source':record['source']})
    for ident, was in previous.items():
        if was['parent_id'] in parents and ident not in seen and was.get('active',True):
            merged[ident] = {**was, 'active': False}
            changes.append({'id':ident,'vorgang_id':was['parent_id'],
                            'change':'nicht_mehr_gefunden','kind':was['kind'],
                            'step':was['step'][:230],'source':was['source']})
    if len(merged) > MAX_POSITIONS:
        raise ValueError('DIP-Positionen: zu viele Datensätze')
    changes.sort(key=lambda r:(int(r['vorgang_id']),int(r['id'])))
    snapshot={'schema':'dip21-positionen-v1','last_success_utc':iso(now),'items':merged}
    report={
        'wahlperiode':21,'status':'dip_positionen_ohne_rechtswirkung',
        'last_success_utc':iso(now),
        'monitored_parent_vorgaenge':len(parents),
        'tracked_positions':sum(v.get('active',True) for v in merged.values()),
        'legal_wording_positions':sum(v.get('active',True) and v['kind']=='moegliche_rechtsfolge'
                                       for v in merged.values()),
        'new_positions':sum(v['change']=='neu' for v in changes),
        'changed_positions':sum(v['change']=='aktualisiert' for v in changes),
        'missing_positions':sum(v['change']=='nicht_mehr_gefunden' for v in changes),
        'recent_changes':changes[-25:],
        'automatically_rescinded_sanctions':0,
        'automatically_confirmed_sanctions':0,
        'warning':('Schritte und Schlagwörter sind keine bestätigten Rechtsfolgen. '
                   'Erfasste Positionen gehören zu beobachteten Vorgängen; '
                   'andere oder erst später in DIP sichtbare Entscheidungen fehlen möglicherweise.'),
    }
    return snapshot, report, changes


def atomic_json(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp = target.with_suffix(target.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(target)


def run(vorgang_state, position_state, report_file, changes_file, *,
        key=PUBLIC_KEY, fetch=fetch_positions, now=None):
    now = now or datetime.now(timezone.utc)
    if not key or '\r' in key or '\n' in key:
        raise ValueError('DIP-Key ungültig')
    source = load_state(vorgang_state)
    if source['last_success_utc'] is None:
        raise ValueError('DIP-Vorgangsmonitor noch nicht erfolgreich')
    parents = sorted(source['items'], key=int)
    if len(parents) > MAX_PARENTS:
        raise ValueError('DIP-Positionen: Sicherheitslimit relevanter Vorgänge')
    old = read_position_state(position_state)
    documents = []
    for parent in parents:
        # IDs are individually queried via the official f.vorgang filter.
        positions = fetch(parent,key)
        documents.extend(positions)
        if len(documents) > MAX_POSITIONS:
            raise ValueError('DIP-Positionen: Sicherheitslimit')
    snapshot, report, changes = evaluate(old,documents,set(parents),now)
    # No publication if any parent request above failed or returned a partial page.
    atomic_json(position_state,snapshot)
    atomic_json(report_file,report)
    atomic_json(changes_file,changes)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vorgang-state',type=Path,default=Path('.cache/dip21/state.json'))
    ap.add_argument('--position-state',type=Path,default=Path('.cache/dip21/positionen.json'))
    ap.add_argument('--report',type=Path,default=Path('docs/data/dip_positionen_21.json'))
    ap.add_argument('--changes',type=Path,default=Path('wp21_dip_positionen_aenderungen.json'))
    args=ap.parse_args()
    import os
    key=os.environ.get('DIP_API_KEY') or PUBLIC_KEY
    result=run(args.vorgang_state,args.position_state,args.report,args.changes,key=key)
    print(f"DIP-Positionen: {result['tracked_positions']} Schritte für "
          f"{result['monitored_parent_vorgaenge']} Vorgänge; "
          f"{result['legal_wording_positions']} wortlautbezogene Rechtsfolgen-Hinweise; "
          "keine automatische Änderung bestätigter Ordnungsrufe.")


if __name__=='__main__':
    main()
