#!/usr/bin/env python3
"""Read-only discovery of DIP source candidates beyond 18 pinned WP21 parents.

This inventory never adjudicates sanctions, creates counters or modifies source
data. A parent absent from PINS is NOT necessarily a new/valid Ordnungsruf.
The scan only covers documents returned by the chosen DIP update window.
"""
import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wp21_18_dip_original_beschluesse import PINS
from wp21_autopruefung import norm, read_reviewed
from wp21_dip_positionen import fetch_positions, normalize_position
from wp21_dip_kontrolle import reference
from wp21_dip_monitor import (
    PUBLIC_KEY, START, iso, paginate, relevant_item, request_page,
)

ROOT = Path(__file__).resolve().parent
AUDIT_ROOT = ROOT / '.audit'
DEFAULT_DAYS = 45
ORIGINAL = re.compile(
    r'\b(?:erteilung\s+(?:eines(?:\s+(?:zweiten|weiteren|erneuten))?|'
    r'einer|zweier|dreier|mehrerer|von(?:\s+(?:zwei|drei|mehreren))?)'
    r'\s+ordnungsruf\w*|'
    r'ordnungsruf\w*\s+(?:an|gegen|für|fuer)\b)', re.I)
FOLLOWUP = re.compile(
    r'\b(?:einspruch\w*|beschwerde\w*|zurückgenomm\w*|aufheb\w*|'
    r'zurückgewiesen\w*|ordnungsgeld\w*)', re.I)
WARNING = (
    'DIP-Vorgangstitel/Abstract und ein vollständiger Abruf innerhalb des '
    'angegebenen Aktualisierungsfensters beweisen weder ursprüngliche '
    'selbständige Erteilung noch aktuelle Rechtswirksamkeit oder '
    'Vollständigkeit der Wahlperiode. Unbekannt bedeutet nur: keine der '
    '18 fest verankerten DIP-Eltern-IDs. Ein Treffer kann bereits in der '
    'acht Maßnahmen umfassenden geprüften Teilmenge liegen. '
    'Kein automatischer Zählerwechsel.'
)


def possible_reference_overlap(doc, sample):
    """Conservative name/date hint, not a verified identity or deduplication."""
    title = norm(doc.get('titel') or '')
    date = doc.get('datum')
    matches = []
    for entry in sample['entries']:
        expected = datetime.strptime(entry['date'], '%d.%m.%Y').date().isoformat()
        person = norm(entry['person'])
        if date == expected and re.search(
                r'(?<!\w)' + re.escape(person) + r'(?!\w)', title):
            matches.append({'session':entry['session'], 'person':entry['person']})
    return matches


def classify(doc):
    title = doc['titel']
    # Do not treat an appeal/retraction/penalty as an original grant even if
    # the phrase "Ordnungsruf" occurs elsewhere in the title.
    if FOLLOWUP.search(title):
        return 'procedure_or_other_sanction_not_original_proof'
    if ORIGINAL.search(title):
        return 'possible_original_grant_metadata'
    return 'other_ordnungsruf_metadata_review'


def build(documents, *, since, now, pages, snapshot=None):
    snapshot = reference() if snapshot is None else snapshot
    if (snapshot.get('$schema') != 'ordnungsruf-dip-positive-control-v1'
            or len(snapshot.get('entries', [])) != 24
            or len(PINS) != 18 or len(set(PINS.values())) != 18):
        raise ValueError('Kuratierte DIP-Ausgangsreferenz wurde verändert')
    if (since.tzinfo is None or now.tzinfo is None or
            not START <= since <= now or now > datetime.now(timezone.utc) +
            timedelta(days=2) or type(pages) is not int or pages < 1):
        raise ValueError('DIP-Entdeckungszeitfenster ungültig')
    if not isinstance(documents, list) or len(documents) > 120000:
        raise ValueError('Kein vollständiger überschaubarer DIP-Dokumentensatz')
    pinned_ids = set(PINS.values())
    seen = set()
    pinned_seen = []
    possible = []
    related = []
    for doc in documents:
        if not isinstance(doc, dict):
            raise ValueError('DIP-Vorgang ohne Rohdaten')
        ident = str(doc.get('id', ''))
        if (not re.fullmatch(r'[1-9]\d{0,11}', ident) or
                doc.get('wahlperiode') != 21 or ident in seen):
            raise ValueError('DIP-Quelle fremder Wahlperiode oder doppelt')
        seen.add(ident)
        item = relevant_item(doc)
        if item is None:
            continue
        if ident in pinned_ids:
            pinned_seen.append(ident)
            continue
        kind = classify(doc)
        entry = {
            'official_dip_parent_id': ident,
            'official_dip_parent_url': item['source'],
            'title': item['title'],
            'source_date': item['date'],
            'updated_utc': item['updated'],
            'classification_for_manual_review': kind,
            'possible_overlap_with_dated_positive_sample':
                possible_reference_overlap(doc, snapshot),
            'original_issue_individually_verified': False,
            'subsequent_legal_effect_verified': False,
            'confirmed_additional_sanctions': 0,
        }
        if kind == 'possible_original_grant_metadata':
            possible.append(entry)
        else:
            related.append(entry)
    for group in (possible, related):
        group.sort(key=lambda row:(row['updated_utc'], int(row['official_dip_parent_id'])),
                   reverse=True)
    return {
        'schema':'wp21-dip-outside-pins-discovery-v1',
        'status':'source_discovery_only_no_effectiveness_decision',
        'since_utc':iso(since), 'observed_until_utc':iso(now),
        'full_legislative_period_update_window':since == START,
        'api_pages_completely_fetched':pages,
        'total_dip_documents_in_update_window':len(documents),
        'pinned_18_parents_seen_in_window':len(pinned_seen),
        'possible_original_parent_ids_outside_18_pins':len(possible),
        'other_relevant_parent_ids_outside_18_pins':len(related),
        'possible_originals_for_individual_review':possible,
        'other_metadata_for_individual_review':related,
        'automatically_confirmed_new_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'protected_counters_changed':False,
        'warning':WARNING,
    }



def corroborate_original_positions(report, *, key=None, fetch=fetch_positions,
                                   snapshot=None, reviewed=None):
    """Source-level original session crosswalk; still no legal-effect decision.

    Parent dates may reflect a later appeal vote, as for Sichert 21/090.
    Only the official Bundestag plenary position identifies the original
    sitting and its source page. A candidate can match the dated positive
    sample and/or the protected eight-case preview without being newly counted.
    """
    if (report.get('schema')!='wp21-dip-outside-pins-discovery-v1'
            or report.get('automatically_confirmed_new_sanctions')!=0
            or report.get('protected_counters_changed') is not False):
        raise ValueError('DIP-Discovery-Ausgangsbasis unsicher')
    candidates=report.get('possible_originals_for_individual_review')
    if not isinstance(candidates,list) or len(candidates)>150:
        raise ValueError('Zu viele neue DIP-Eltern für eine sichere Einzelprüfung')
    snapshot = reference() if snapshot is None else snapshot
    if reviewed is None:
        reviewed,count=read_reviewed(ROOT/'daten/wirksame_ordnungsrufe_21wp.csv')
        if count!=8:
            raise ValueError('Bestätigte WP21-Teilauswahl verändert')
    if len(snapshot.get('entries',[]))!=24 or sum(reviewed.values())!=8:
        raise ValueError('Referenzbasis für den Einzelfall-Abgleich verändert')
    api_key=key or os.getenv('DIP_API_KEY') or PUBLIC_KEY
    seen_parents=set()
    detailed=[]
    for c in candidates:
        parent=c['official_dip_parent_id']
        if parent in seen_parents or parent in set(PINS.values()):
            raise ValueError('DIP-Eltern-Identität doppelt oder bereits verankert')
        seen_parents.add(parent)
        positions=fetch(parent, api_key)
        if not isinstance(positions,list) or not 1<=len(positions)<=20:
            raise ValueError('DIP-Verfahrenspositionsliste unvollständig oder zu groß')
        original=[]
        later=[]
        seen_position_ids=set()
        for raw in positions:
            p=normalize_position(raw)
            if p['parent_id']!=parent or p['id'] in seen_position_ids:
                raise ValueError('DIP-Verfahrensposition gehört nicht zum Originalvorgang')
            seen_position_ids.add(p['id'])
            source={
                'official_position_id':p['id'],
                'official_position_api':
                    'https://search.dip.bundestag.de/api/v1/vorgangsposition/'+p['id'],
                'step':p['step'], 'date':p['date'],
                'official_plenary_session':p['official_plenary_session'],
                'official_plenary_pdf_url':p['official_plenary_pdf_url'],
            }
            if p['step'].strip().casefold()=='ordnungsruf':
                if (p['official_plenary_chamber']!='Bundestag'
                        or not p['official_plenary_session']
                        or not p['official_plenary_xml_url']
                        or not p['official_plenary_pdf_url']
                        or not p['date']):
                    raise ValueError('Amtliche Erteilungsposition ohne Bundestags-Original')
                original.append(source)
            else:
                later.append(source)
        reference_matches=[]
        confirmed_overlap=[]
        title=norm(c['title'])
        for position in original:
            session=position['official_plenary_session']
            day=position['date']
            for item in snapshot['entries']:
                person=norm(item['person'])
                if (item['session']==session
                        and datetime.strptime(item['date'],'%d.%m.%Y').date().isoformat()==day
                        and re.search(r'(?<!\w)'+re.escape(person)+r'(?!\w)',title)):
                    reference_matches.append({
                        'session':session,'person':item['person'],
                        'original_date':day,
                        'matching_official_position_id':position['official_position_id'],
                    })
                    if (session,person) in reviewed:
                        confirmed_overlap.append({'session':session,'person':item['person']})
        # These are metadata crosswalks; the actual number of grants and
        # subsequent revocations cannot be decided without independent review.
        detailed.append({
            **c,
            'all_official_parent_positions_fetched':True,
            'official_parent_position_count':len(positions),
            'official_original_position_count':len(original),
            'original_position_sources':original,
            'other_position_sources_needing_legal_review':later,
            'matched_dated_positive_sample_by_original_position':reference_matches,
            'possible_overlap_with_confirmed_preview':confirmed_overlap,
            'parent_display_date_is_not_original_position_date':
                bool(original and c['source_date'] not in
                     {x['date'] for x in original}),
            'separate_original_grants_and_legal_effect_not_inferred':True,
            'confirmed_additional_sanctions':0,
        })
    return {
        **report,
        'possible_originals_for_individual_review':detailed,
        'original_position_enrichment_status':'all_possible_parents_positions_refreshed',
        'fully_refreshed_possible_parent_count':len(detailed),
        'candidates_matched_to_existing_positive_sample':sum(
            bool(c['matched_dated_positive_sample_by_original_position'])
            for c in detailed),
        'candidates_without_positive_sample_original_match':sum(
            not c['matched_dated_positive_sample_by_original_position']
            for c in detailed),
        'candidates_with_possible_confirmed_preview_overlap':sum(
            bool(c['possible_overlap_with_confirmed_preview']) for c in detailed),
        'automatically_confirmed_new_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'protected_counters_changed':False,
    }


def markdown(report):
    if (report['automatically_confirmed_new_sanctions'] != 0 or
            report['automatically_rescinded_sanctions'] != 0 or
            report['protected_counters_changed']):
        raise ValueError('Statistische Freigabe im Quellenscan verboten')
    lines = [
        '# WP21: weitere DIP-Quellen außerhalb von 18 bekannten Eltern-IDs',
        '',
        '**Keine bestätigten neuen Maßnahmen. Keine Wahlperiodengesamtzahl.**',
        '',
        'Aktualisierungsfilter: ' + report['since_utc'] +
        ' bis ' + report['observed_until_utc'],
        '',
        'Vollständige Wahlperioden-Zeitspanne als Filter: ' +
        ('ja' if report['full_legislative_period_update_window'] else 'nein'),
        '',
        '| DIP-Eltern-ID | Amtlicher Vorgangstitel | Vorläufige Einordnung | '
        'Originalprotokoll | Bereits in der datierten Stichprobe? |',
        '|---|---|---|---|---|',
    ]
    for c in (report['possible_originals_for_individual_review'] +
              report['other_metadata_for_individual_review']):
        title = c['title'].replace('|','\\|').replace('\n',' ')[:180]
        sources=c.get('original_position_sources',[])
        original=', '.join(
            '[21/'+str(p['official_plenary_session'])+']('+
            p['official_plenary_pdf_url']+')' for p in sources
        ) if sources else 'keine quellengebundene Originalposition'
        overlaps=c.get('matched_dated_positive_sample_by_original_position',[])
        previous=', '.join(
            '21/'+str(m['session'])+' '+m['person'] for m in overlaps
        ) if overlaps else 'keine exakt zugeordnete Stichprobenquelle'
        lines.append(
            '| [' + c['official_dip_parent_id'] + '](' +
            c['official_dip_parent_url'] + ') | ' + title + ' | ' +
            c['classification_for_manual_review'] + ' | ' + original + ' | ' +
            previous + ' |')
    lines.extend(['', report['warning'], '',
                  '**Keine Änderungen bestätigter CSV-/JSON-Daten.**', ''])
    return '\n'.join(lines)


def save(report, folder):
    path = Path(folder).resolve()
    root = AUDIT_ROOT.resolve()
    if root not in path.parents or path.is_symlink():
        raise ValueError('DIP-Discovery-Ausgaben nur im privaten .audit-Unterordner')
    path.mkdir(parents=True, exist_ok=True)
    for name, contents in (
        ('outside_pins.json', json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
        ('outside_pins.md', markdown(report))):
        temporary = path / (name + '.tmp')
        temporary.write_text(contents, encoding='utf-8')
        temporary.replace(path / name)


def run(*, since=None, now=None, key=None, load=request_page,
        fetch=fetch_positions,
        output_dir=AUDIT_ROOT/'wp21_dip_discovery', max_pages=1200):
    now = now or datetime.now(timezone.utc)
    since = since or max(START, now - timedelta(days=DEFAULT_DAYS))
    if since.tzinfo is None or now.tzinfo is None or not START <= since <= now:
        raise ValueError('DIP-Abfragezeitfenster ungültig')
    api_key=key or os.getenv('DIP_API_KEY') or PUBLIC_KEY
    docs, pages = paginate(since, api_key, load=load, max_pages=max_pages)
    report = build(docs,since=since,now=now,pages=pages)
    report = corroborate_original_positions(report,key=api_key,fetch=fetch)
    save(report, output_dir)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days',type=int,default=DEFAULT_DAYS)
    parser.add_argument('--full-term',action='store_true')
    parser.add_argument('--output-dir',type=Path,default=AUDIT_ROOT/'wp21_dip_discovery')
    options = parser.parse_args()
    if not 1 <= options.days <= 365:
        raise ValueError('DIP-Entdeckungsfenster muss 1 bis 365 Tage betragen')
    now = datetime.now(timezone.utc)
    since = START if options.full_term else max(START, now-timedelta(days=options.days))
    report = run(since=since, now=now, output_dir=options.output_dir)
    print(f"Crosswalk: {report['candidates_matched_to_existing_positive_sample']} "
          f"moegliche Urspruenge bereits in datierter Positivstichprobe; "
          f"{report['candidates_without_positive_sample_original_match']} "
          'noch nicht zugeordnet. Kein automatisches Zaehlen.')
    print(f"WP21 DIP: {report['total_dip_documents_in_update_window']} Dokumente "
          f"vollständig auf {report['api_pages_completely_fetched']} Seiten, "
          f"{report['possible_original_parent_ids_outside_18_pins']} "
          'mögliche neue Quellen außerhalb der 18 verankerten DIP-IDs; '
          'null automatische Zähleränderungen.')


if __name__=='__main__':
    main()
