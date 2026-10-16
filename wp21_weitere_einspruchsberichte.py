#!/usr/bin/env python3
"""Additional independently sourced WP21 parliamentary Ordnungsruf objections.

Outside the 18 high-priority XML dossiers, official Bundestag publications
document 13 *separate rejected objections* relating to earlier Ordnungsrufe.
This is an intentionally bounded research sample, NOT an exhaustive list.
A rejected objection must never create another measure, double-count an
already verified one, or establish that some other grant is still effective.

2025-11-13: one Bundestag publication explicitly documents FOUR appeals
concerning Martin Sichert (1), Steffen Janich (2), Kay Gottschalk (1).
For Janich, two independently rejected appeals are evidenced, but the
original XML line identities still require separate person/event review.
"""
import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from wp21_autopruefung import norm, read_reviewed
from wp21_einspruchsbelege import validated_index as high_priority_appeals

PREFIX='https://www.bundestag.de/dokumente/textarchiv/'
SOURCE_RE=re.compile(
    r'https://www\.bundestag\.de/dokumente/textarchiv/(2025|2026)/'
    r'kw\d{2}-de-einspruch-ordnungsruf(?:-2)?-\d{5,9}\Z')
SAFE_PERSON=re.compile(r'[A-ZÄÖÜ][A-Za-zÄÖÜäöüß -]{3,95}\Z')

SOURCES={
    '2025jun05':PREFIX+'2025/kw23-de-einspruch-ordnungsruf-1084838',
    '2025jun06':PREFIX+'2025/kw26-de-einspruch-ordnungsruf-1094990',
    '2025jun27':PREFIX+'2025/kw28-de-einspruch-ordnungsruf-1098806',
    '2025sep18':PREFIX+'2025/kw39-de-einspruch-ordnungsruf-1110374',
    '2025nov13':PREFIX+'2025/kw48-de-einspruch-ordnungsruf-1127758',
    '2025nov26':PREFIX+'2025/kw48-de-einspruch-ordnungsruf-2-1128096',
    '2025dec17':PREFIX+'2025/kw51-de-einspruch-ordnungsruf-1134106',
    '2025dec18':PREFIX+'2025/kw51-de-einspruch-ordnungsruf-2-1134402',
    '2026may07':PREFIX+'2026/kw19-de-einspruch-ordnungsruf-1174812',
    '2026jul10':PREFIX+'2026/kw37-de-einspruch-ordnungsruf-1210768',
}

def objection(source,original,decided,person,ordinal=1,session=None):
    return {'source':SOURCES[source], 'original_date':original,
            'decision_date':decided,'person':person,
            'individual_objection_ordinal':ordinal,
            'original_session':session,
            'sanction_type':'ordnungsruf',
            'decision':'einspruch_zurueckgewiesen'}

# 10 official articles, 13 separately rejected objections, including two
# Janich objections in the SAME Bundestag decision article.
EVIDENCE=(
    objection('2025jun05','2025-06-05','2025-06-06','Stephan Brandner'),
    objection('2025jun06','2025-06-06','2025-06-24','Stephan Brandner'),
    objection('2025jun27','2025-06-27','2025-07-08','Luigi Pantisano'),
    objection('2025sep18','2025-09-18','2025-09-23','Mirze Edis'),
    objection('2025nov13','2025-11-13','2025-11-25','Martin Sichert'),
    objection('2025nov13','2025-11-13','2025-11-25','Steffen Janich',1),
    objection('2025nov13','2025-11-13','2025-11-25','Steffen Janich',2),
    objection('2025nov13','2025-11-13','2025-11-25','Kay Gottschalk'),
    objection('2025nov26','2025-11-26','2025-11-28','Martin Reichardt'),
    objection('2025dec17','2025-12-17','2025-12-18','Stephan Brandner'),
    objection('2025dec18','2025-12-18','2025-12-19','Martin Reichardt'),
    objection('2026may07','2026-05-07','2026-05-08','Martin Reichardt',session=77),
    objection('2026jul10','2026-07-10','2026-09-08','Martin Sichert',session=90),
)

# Exact article-specific evidence tuples; changing a date, person or source
# without independently verifying that article must fail closed.
OFFICIAL_ARTICLE_CASES={
    SOURCES['2025jun05']:{('2025-06-05','2025-06-06','Stephan Brandner',1,None)},
    SOURCES['2025jun06']:{('2025-06-06','2025-06-24','Stephan Brandner',1,None)},
    SOURCES['2025jun27']:{('2025-06-27','2025-07-08','Luigi Pantisano',1,None)},
    SOURCES['2025sep18']:{('2025-09-18','2025-09-23','Mirze Edis',1,None)},
    SOURCES['2025nov13']:{
        ('2025-11-13','2025-11-25','Martin Sichert',1,None),
        ('2025-11-13','2025-11-25','Steffen Janich',1,None),
        ('2025-11-13','2025-11-25','Steffen Janich',2,None),
        ('2025-11-13','2025-11-25','Kay Gottschalk',1,None)},
    SOURCES['2025nov26']:{('2025-11-26','2025-11-28','Martin Reichardt',1,None)},
    SOURCES['2025dec17']:{('2025-12-17','2025-12-18','Stephan Brandner',1,None)},
    SOURCES['2025dec18']:{('2025-12-18','2025-12-19','Martin Reichardt',1,None)},
    SOURCES['2026may07']:{('2026-05-07','2026-05-08','Martin Reichardt',1,77)},
    SOURCES['2026jul10']:{('2026-07-10','2026-09-08','Martin Sichert',1,90)},
}


# Different sanction type: rejected appeal against an *Ordnungsgeld*
# imposed on 2026-10-15, decided on 2026-10-16. It is NOT an Ordnungsruf.
OTHER_MEASURE={
    'person':'Martin Reichardt',
    'original_date':'2026-10-15',
    'decision_date':'2026-10-16',
    'sanction_type':'ordnungsgeld',
    'decision':'einspruch_zurueckgewiesen',
    'source':PREFIX+'2026/kw42-de-einspruch-ordnungsgeld-1225202',
}


def validate(items=EVIDENCE,other=OTHER_MEASURE):
    if len(items)!=13 or len(SOURCES)!=10:
        raise ValueError('Nicht genau 13 zusätzliche Einsprüche und 10 Quellen')
    high=high_priority_appeals()
    if len(high)!=4:
        raise ValueError('Vier bereits separat belegte Hochprioritätsfälle fehlen')
    if len(set(SOURCES.values()))!=10:
        raise ValueError('Amtliche Einspruchsartikel doppelt referenziert')
    keys=set()
    found_sources=Counter()
    group=[]
    found_with_sessions={}
    for entry in items:
        if not isinstance(entry,dict) or set(entry)!={
                'source','original_date','decision_date','person',
                'individual_objection_ordinal','original_session',
                'sanction_type','decision'}:
            raise ValueError('Einspruchsbeleg-Schema unvollständig')
        person=entry['person']
        if type(person)!=str or not SAFE_PERSON.fullmatch(person):
            raise ValueError('Ungültiger amtlicher Personenname')
        original=date.fromisoformat(entry['original_date'])
        decision=date.fromisoformat(entry['decision_date'])
        if not date(2025,3,25)<=original<decision<=date(2026,10,16):
            raise ValueError('Einspruchsdatum oder Ursprungsdatum unplausibel')
        if (entry['source'] not in SOURCES.values()
                or not SOURCE_RE.fullmatch(entry['source'])
                or entry['sanction_type']!='ordnungsruf'
                or entry['decision']!='einspruch_zurueckgewiesen'):
            raise ValueError('Fremde/ungeprüfte Maßnahme oder Quelle')
        ordinal=entry['individual_objection_ordinal']
        if type(ordinal)!=int or not 1<=ordinal<=2:
            raise ValueError('Einspruchsnummer muss explizit 1 oder 2 sein')
        key=(entry['original_date'],norm(person),ordinal)
        if key in keys:
            raise ValueError('Einzelner Einspruch ohne unterscheidbare Identität')
        keys.add(key)
        sitting=entry['original_session']
        if sitting is not None:
            if type(sitting)!=int or sitting not in (77,90):
                raise ValueError('Ursprungssitzung nicht im geprüften Teilbestand')
            match=(sitting,norm(person))
            if match in high or match in found_with_sessions:
                raise ValueError('Einspruch verwechselt andere ursprüngliche Sitzung')
            found_with_sessions[match]=entry
        if ordinal==2 and (
                entry['original_date']!='2025-11-13'
                or person!='Steffen Janich'):
            raise ValueError('Zweiter Einspruch nur für Janich 13.11.2025 belegt')
        if entry['source']==SOURCES['2025nov13']:
            group.append((person,ordinal))
        found_sources[entry['source']]+=1
    if set(found_sources)!=set(SOURCES.values()):
        raise ValueError('Nicht alle 10 unabhängig recherchierten Beschlussberichte')
    by_article={}
    for entry in items:
        by_article.setdefault(entry['source'],set()).add((
            entry['original_date'],entry['decision_date'],
            entry['person'],entry['individual_objection_ordinal'],
            entry['original_session']))
    if by_article!=OFFICIAL_ARTICLE_CASES:
        raise ValueError('Amtlicher Artikel/Originaldatum/Person nicht eindeutig belegt')
    if found_sources[SOURCES['2025nov13']]!=4 or (
            set(group)!={('Martin Sichert',1),('Steffen Janich',1),
                         ('Steffen Janich',2),('Kay Gottschalk',1)}):
        raise ValueError('Vier ausdrücklich getrennte Einsprüche 13.11.2025 fehlen')
    if found_with_sessions.keys()!={(77,norm('Martin Reichardt')),
                                    (90,norm('Martin Sichert'))}:
        raise ValueError('Zwei bereits belegte 2026-Ursprungssitzungen fehlen')
    if (not isinstance(other,dict) or set(other)!={
            'person','original_date','decision_date','sanction_type',
            'decision','source'} or other['person']!='Martin Reichardt'
            or other['sanction_type']!='ordnungsgeld'
            or other['decision']!='einspruch_zurueckgewiesen'
            or other['original_date']!='2026-10-15'
            or other['decision_date']!='2026-10-16'
            or other['source']!=PREFIX+'2026/kw42-de-einspruch-ordnungsgeld-1225202'):
        raise ValueError('Ordnungsgeld-Negativkontrolle fehlt/ist umgewidmet')
    return {key:dict(x) for key,x in zip(
        [(e['original_date'],norm(e['person']),e['individual_objection_ordinal'])
         for e in items],items)}


def build_report(ledger='daten/wirksame_ordnungsrufe_21wp.csv'):
    index=validate()
    reviewed,reviewed_count=read_reviewed(ledger)
    existing={(77,norm('Martin Reichardt')),
              (90,norm('Martin Sichert'))}
    if not all(reviewed.get(key,0)>=1 for key in existing):
        raise ValueError('Bereits bestätigte 77/90er Referenz darf nicht fehlen')
    rows=[]
    for key,row in sorted(index.items()):
        ref=(row['original_session'],norm(row['person']))
        prior=(reviewed.get(ref,0) if row['original_session'] else None)
        rows.append({
            **row,'reviewed_effective_measures_in_existing_partial_ledger':prior,
            'prior_verified_counter_reference_present':bool(prior),
            'report_identifies_individual_rejected_objection':True,
            'unique_original_xml_issuance_line_verified':False,
            'verified_individual_effective_sanction_from_this_appeal':False,
        })
    if sum(x['prior_verified_counter_reference_present'] for x in rows)!=2:
        raise ValueError('Genau zwei bekannte vorbestätigte Ursprungsfälle')
    return {
        'schema':'wp21-official-independent-additional-objections-v1',
        'status':'read_only_official_bundestag_appeal_reports_not_sanction_count',
        'additional_official_articles':len(SOURCES),
        'additional_separately_rejected_objections':len(rows),
        'previously_curated_priority_rejections':4,
        'documented_total_objections_in_both_corpus_snapshots':len(rows)+4,
        'reports_explicitly_distinguishing_two_steffen_janich_sanctions':1,
        'already_individually_verified_originals_in_partial_ledger':2,
        'existing_partial_ledger_size_not_modified':reviewed_count,
        'excluded_distinct_ordnungsgeld_appeal':dict(OTHER_MEASURE),
        'automatically_confirmed_additional_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'public_counters_modified':False,
        'historical_coverage_is_complete':False,
        'all_original_xml_line_links_reviewed':False,
        'warning':(
            '13 zusätzliche amtliche Einspruchszurückweisungen sind nicht 13 '
            'zusätzliche rechtswirksame Einzelrufe. Die 77/90er Fälle sind '
            'bereits separat bestätigt; Janich hat zwei vom Bundestag selbst '
            'unterschiedene Einsprüche, aber ohne hier einzeln geprüfte XML-Zeilen. '
            'Fehlende Berichte schließen weitere Einsprüche oder Rücknahmen nicht aus.'),
        'cases':rows,
    }


def render_markdown(report):
    if (report.get('schema')!='wp21-official-independent-additional-objections-v1'
            or len(report.get('cases',[]))!=13
            or report.get('additional_separately_rejected_objections')!=13
            or report.get('previously_curated_priority_rejections')!=4
            or report.get('documented_total_objections_in_both_corpus_snapshots')!=17
            or report.get('automatically_confirmed_additional_sanctions')!=0
            or report.get('automatically_rescinded_sanctions')!=0
            or report.get('public_counters_modified')):
        raise ValueError('Amtlicher Einspruchsbericht unvollständig/gefährlich')
    lines=[
        '# Zusätzlich belegte Bundestags-Einspruchsentscheidungen (21. WP)',
        '',
        '**13 weitere eigenständig dokumentierte, zurückgewiesene',
        'Einsprüche aus 10 amtlichen Artikeln** außerhalb der vier',
        'bereits einzeln kuratierten Hochprioritätsfälle. Zusammen sind',
        'dies 17 quellengebundene Einspruchsentscheidungen, kein',
        'vollständiger historischer Gesamtbestand.',
        '',
        '| Erteilungstag | Person | Original-Sitzung | Einspruch Nr. | Entscheidung | Bundestagsquelle | Teilbestand |',
        '| --- | --- | --- | ---: | --- | --- | --- |',
    ]
    for row in report['cases']:
        sess=(f"21/{row['original_session']:03d}"
              if row['original_session'] else 'noch nicht unabhängig mit XML verknüpft')
        pre=('bereits bestätigt (keine Doppelzählung)'
             if row['prior_verified_counter_reference_present']
             else 'weitere Einzelprüfung erforderlich')
        lines.append(
            f"| {row['original_date']} | {row['person']} | {sess} | "
            f"{row['individual_objection_ordinal']} | "
            f"{row['decision_date']}: zurückgewiesen | "
            f"[Amtlicher Bundestagsbericht]({row['source']}) | {pre} |")
    other=report['excluded_distinct_ordnungsgeld_appeal']
    lines.extend([
        '',
        '## Drei besonders wichtige Abgrenzungen',
        '',
        '1. **13.11.2025: Steffen Janich** – zwei ausdrücklich unterschiedliche',
        '   Ordnungsrufe, über deren Einsprüche der Bundestag am 25.11.',
        '   zweimal gesondert entschied. Bis zur Prüfung der beiden',
        '   ursprünglichen XML-Zeilen keine automatische Zählfreigabe.',
        '2. **07.05./10.07.2026:** Reichardt (21/077) und Sichert (21/090)',
        '   stehen schon im einzeln geprüften öffentlichen Teilbestand.',
        '   Ihre Einspruchsentscheidungen sind lediglich zusätzliche',
        '   Quellen, keine neuen Maßnahmen.',
        '3. **Ordnungsgeld strikt getrennt:** '
        f"[Reichardt, 15./16.10.2026]({other['source']})"
        ' betrifft ein Ordnungsgeld, keinen Ordnungsruf.',
        '',
        '**Nicht ableiten:** Eine Zurückweisung des Einspruchs ist keine',
        ' zusätzliche Ordnungsruferteilung. Weder diese Berichtssammlung',
        ' noch der DIP-Positionsmonitor sind ein vollständiger Beweis',
        ' über alle späteren Rechtsfolgen. Vier geschützte bestätigte',
        ' Zählerquellen bleiben unverändert.',
        '',
    ])
    return '\n'.join(lines)


def run(output,brief,ledger='daten/wirksame_ordnungsrufe_21wp.csv'):
    report=build_report(ledger)
    markdown=render_markdown(report)
    for path,contents in ((Path(output),json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
                          (Path(brief),markdown)):
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(path.suffix+'.tmp')
        tmp.write_text(contents,encoding='utf-8')
        tmp.replace(path)
    print('WP21_ADDITIONAL_APPEALS_OK: 10 independent reports, '
          '13 rejected objections, 4 previously curated, '
          '2 existing-verified originals, 1 separately excluded fine, '
          '0 newly confirmed sanctions')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('.audit/wp21_weitere_einsprueche.json'))
    p.add_argument('--brief',type=Path,default=Path('.audit/wp21_weitere_einsprueche.md'))
    p.add_argument('--ledger',type=Path,
                   default=Path('daten/wirksame_ordnungsrufe_21wp.csv'))
    args=p.parse_args()
    run(args.output,args.brief,args.ledger)
