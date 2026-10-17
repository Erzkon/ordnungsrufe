#!/usr/bin/env python3
"""Source-limited v1.0 release candidate gate: not a merge or count approval.

Historical 20th term: reviewed 135 sanction occurrences / 123 event IDs
and an explicitly disclosed one-person discrepancy. 21st term: exactly the
currently approved eight-row *incomplete* sample, never a population
total. No automatic DIP/XML findings enter either reviewed ledger.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import re
from pathlib import Path

from export_webdaten import build as build20
from export_wp21 import build as build21

PROTECTED=(
    'daten/wirksame_ordnungsrufe_20wp.csv',
    'daten/wirksame_ordnungsrufe_21wp.csv',
    'docs/data/ordnungsrufe.json',
    'docs/data/ordnungsrufe_21.json',
)
SCHEMA='ordnungsrufe-public-v1-scope-limited-release-gate'
EXPECTED=(135,123,8)
STATUS='ready_for_manual_review_not_automatically_published'


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.scripts=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if values.get('id'):
            self.ids.append(values['id'])
        if tag=='script' and values.get('src'):
            self.scripts.append(values['src'])


def evaluate(root):
    root=Path(root)
    from20=build20(root/PROTECTED[0],root/'daten/korrekturbericht_20wp.json')
    from21=build21(root/PROTECTED[1])
    published20=json.loads((root/PROTECTED[2]).read_text(encoding='utf-8'))
    published21=json.loads((root/PROTECTED[3]).read_text(encoding='utf-8'))
    if from20!=published20 or from21!=published21:
        raise ValueError('Einzeln geprüfte CSV/JSON-Publikation weicht vom Export ab')
    m20,m21=published20['meta'],published21['meta']
    if ((m20['count'],m20['events'],m21['count'])!=EXPECTED
            or m20['official_total']!=135
            or m20['official_beatrix_von_storch']!=19
            or m20['verified_beatrix_von_storch']!=18
            or not m20['provisional']
            or m21['incomplete'] is not True or m21['provisional'] is not True
            or 'KEINE vollständige Statistik' not in m21['note']):
        raise ValueError('v1-Umfang oder ungeklärte Differenz wird verschleiert')
    html=(root/'docs/index.html').read_text(encoding='utf-8')
    js=(root/'docs/app.js').read_text(encoding='utf-8')
    contract=(root/'docs/verified_contract.js').read_text(encoding='utf-8')
    markup=Markup()
    markup.feed(html)
    if (len(markup.ids)!=len(set(markup.ids))
            or 'wp20-note' not in markup.ids
            or 'wp21-note' not in markup.ids
            or 'hero-snapshot' not in markup.ids
            or markup.scripts!=['verified_contract.js','app.js']):
        raise ValueError('Release-JavaScript-Reihenfolge, Datum oder Warnhinweis fehlt')
    if ('function validatePublishedDataset' not in contract
            or 'validatePublishedDataset(period, payload)' not in js
            or 'DATENSTAND 14.10.2026' in js
            or 'DATENSTAND 14.10.2026' in html
            or 'meta.incomplete !== true' not in contract
            or 'meta.official_total !== meta.count' not in contract
            or 'DIE' not in html.upper()
            or 'noch nicht repräsentativ' not in html
            or 'nicht abschließend geklärt' not in html):
        raise ValueError('Datums-/Quellenhinweis oder Client-Integritätsprüfung fehlt')
    # A candidate report is not a certification of completeness of current term.
    # Only the four trusted ledger files are named as protected statistics.
    files={}
    for name in PROTECTED:
        raw=(root/name).read_bytes()
        if not raw or len(raw)>3_000_000:
            raise ValueError('Geprüfte Zählerdatei fehlt oder ist zu groß')
        files[name]=hashlib.sha256(raw).hexdigest()
    return {
        'schema':SCHEMA,
        'status':STATUS,
        'release_scope':{
            'twentieth_term':'historical_reviewed_135_measures_123_events',
            'twentieth_term_person_discrepancy_remains_open':True,
            'twenty_first_term':'eight_item_nonrepresentative_manual_sample',
            'twenty_first_term_full_census_claim':False,
        },
        'verified_20th_term_measures':m20['count'],
        'verified_20th_term_events':m20['events'],
        'verified_21st_term_partial_items':m21['count'],
        'approved_snapshot_dates':{
            '20':m20['snapshot_date'],'21':m21['snapshot_date'],
        },
        'public_source_files_sha256':files,
        'all_published_records_equal_reviewed_csv_export':True,
        'frontend_provenance_and_population_warning_required':True,
        'automatically_imported_unverified_measures':0,
        'automatic_merge_or_publish_authorized':False,
        'requires_explicit_human_merging_decision':True,
        'not_an_exhaustive_legal_effect_confirmation':True,
    }


def markdown(report):
    if (report.get('schema')!=SCHEMA
            or report.get('status')!=STATUS
            or report.get('automatically_imported_unverified_measures')!=0
            or report.get('automatic_merge_or_publish_authorized') is not False
            or report.get('requires_explicit_human_merging_decision') is not True
            or report.get('not_an_exhaustive_legal_effect_confirmation') is not True
            or report.get('release_scope',{}).get('twenty_first_term_full_census_claim') is not False):
        raise ValueError('Unerlaubte automatische Veröffentlichungsfreigabe')
    return '\n'.join([
        '# Version 1.0 – begrenzter Release-Kandidat','',
        f"**20. WP:** {report['verified_20th_term_measures']} individuell "
        f"geprüfte Maßnahmen in {report['verified_20th_term_events']} Vorgängen. "
        'Die Beatrix-von-Storch-Differenz 18/19 ist weiterhin offen.',
        f"**21. WP:** {report['verified_21st_term_partial_items']} "
        'einzeln geprüfte Maßnahmen, **keine vollständige Gesamtstatistik**.',
        'Beide veröffentlichte JSONs entsprechen den jeweiligen geprüften CSV-Exporten.',
        'Die Website zeigt die maßgeblichen Snapshot-Daten aus JSON und '
        'prüft alle amtlichen Protokoll-Links vor der Rankinganzeige.','',
        '**Nicht freigegeben:** automatischer Merge, Übernahme ungeprüfter '
        'DIP/XML-Treffer, rechtliche Wirksamkeit aller weiteren Funde.',
        'Eine Veröffentlichung von PR #4 erfordert eine ausdrückliche '
        'Freigabe; diese Prüfung ändert keine der vier Zählerdateien.','',
    ])


def run(root,output,brief):
    report=evaluate(root)
    text=markdown(report)
    # Only write to audit locations after the entire gate passed.
    for target,body in (
            (Path(output),json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
            (Path(brief),text)):
        target.parent.mkdir(parents=True,exist_ok=True)
        tmp=target.with_suffix(target.suffix+'.tmp')
        tmp.write_text(body,encoding='utf-8')
        tmp.replace(target)
    print('V1_RELEASE_CANDIDATE_PASS',
          report['verified_20th_term_measures'],
          'reviewed WP20 records,',
          report['verified_21st_term_partial_items'],
          'WP21 sample records; merge/publish still manual')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--output',type=Path,default=Path('.audit/v1_release.json'))
    p.add_argument('--brief',type=Path,default=Path('.audit/v1_release.md'))
    a=p.parse_args()
    run(a.root,a.output,a.brief)
