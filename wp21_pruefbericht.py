#!/usr/bin/env python3
"""Produce a deterministic, evidence-linked WP21 high-priority review brief.

The complete audit includes unverified original-grant DIP controls, parser
mentions and XML text locations. This file NEVER approves, rejects, rescinds,
or changes an individual measure or published counter.
"""
import argparse
import html
import json
from pathlib import Path

from wp21_vollstaendigkeit import FIELDS, csv_rows
from wp21_einspruchsbelege import find, validated_index


def category(row):
    if row['typ']=='xml_textstelle_ohne_person_parser':
        return 'Textstellen ohne sichere Personenidentität'
    if row['typ']!='person_sitzung_ohne_einzelereignisabgleich':
        raise ValueError('Unbekannter Typ eines hochpriorisierten Falls')
    verified=int(row['bestaetigte_massnahmen_teilbestand'] or '0')
    dip=int(row['dip_urspruengliche_erteilungen_stichprobe'] or '0')
    if verified>0 and row['parser_person_sitzung_vorhanden']=='nein':
        return 'Bekannte Referenz vom Parser nicht erkannt'
    if dip>verified:
        return 'DIP-Positivstichprobe ohne einzeln bestätigten Vollbeleg'
    if verified>1 or dip>1:
        return 'Mehrfachvergabe: Einzelereignisse nicht automatisch erkennbar'
    return 'Weitere offene Zuordnungsfragen'


ORDER=[
    'Bekannte Referenz vom Parser nicht erkannt',
    'DIP-Positivstichprobe ohne einzeln bestätigten Vollbeleg',
    'Mehrfachvergabe: Einzelereignisse nicht automatisch erkennbar',
    'Textstellen ohne sichere Personenidentität',
    'Weitere offene Zuordnungsfragen',
]


def create_brief(rows,report):
    validated_index()  # Fail closed on malformed official appeal references.
    if (report.get('wahlperiode')!=21
            or report.get('status')!='quellenvollstaendigkeit_ohne_automatische_freigabe'
            or report.get('automatically_confirmed_sanctions')!=0
            or report.get('automatically_rescinded_sanctions')!=0
            or report.get('review_cases_total')!=len(rows)):
        raise ValueError('Inkonsistenter Vollständigkeitsbericht')
    ids=set()
    groups={name:[] for name in ORDER}
    for row in rows:
        if set(row)!=set(FIELDS) or row['prioritaet'] not in ('hoch','mittel','niedrig'):
            raise ValueError('Unerwartete Spalten/Priorität in der Prüfliste')
        try:
            session=int(row['sitzung'])
            line=int(row['xml_zeile']) if row['xml_zeile'] else None
        except (TypeError,ValueError) as exc:
            raise ValueError('Ungültige Sitzung oder Quellzeile') from exc
        if (not 1<=session<=report['sessions_scanned'] or
                (line is not None and line<1) or
                row['protokoll']!=f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf'
                or not row['fall_id'] or row['fall_id'] in ids):
            raise ValueError('Doppelte/unpassende Fall-ID oder Quelle')
        ids.add(row['fall_id'])
        if row['prioritaet']=='hoch':
            groups[category(row)].append(row)
    high=sum(map(len,groups.values()))
    if high!=report.get('high_priority_cases'):
        raise ValueError('Unvollständige Hochprioritäts-Prüfqueue')
    lines=[
        '# Bundestag 21. Wahlperiode – fachliche Hochprioritäts-Prüfqueue',
        '',
        f"**Quellenstand:** {html.escape(str(report['last_success_utc']))}  ",
        f"**Amtliche XML-Sitzungen gescannt:** {report['sessions_scanned']}  ",
        f"**Offene Hochprioritäts-Prüffälle:** {high}",
        '',
        '> **Keine bestätigten Ordnungsrufe:** Diese Fälle enthalten nur '
        'amtliche Textstellen, Parserhinweise und eine **kuratierte** DIP-'
        'Positivstichprobe. DIP-Erteilungen können später aufgehoben worden '
        'sein. Weder die Fallzahl noch die Anzahl der XML-Zeilen ist eine '
        'rechtswirksame Ordnungsruf-Gesamtzahl.',
        '',
        '## Prüfblöcke',
        '',
    ]
    for title in ORDER:
        subset=groups[title]
        lines.append(f'- {title}: **{len(subset)}**')
    lines.append('')
    for title in ORDER:
        group=groups[title]
        if not group:
            continue
        lines += [f'## {title} ({len(group)})','']
        for row in group:
            session=int(row['sitzung'])
            person=html.escape(row['person'] or 'Noch keine sichere Person')
            snippet=html.escape(' '.join(row['textauszug'].split())[:350])
            label=f'21/{session:03d} – {person}'
            if row['xml_zeile']:
                label+=f" – XML-Zeile {int(row['xml_zeile'])}"
            verified=row['bestaetigte_massnahmen_teilbestand'] or 'nicht bestimmt'
            dip=row['dip_urspruengliche_erteilungen_stichprobe'] or 'keine DIP-Positivkontrolle'
            lines += [
                f"### {label}",
                '',
                f"**Belege:** [Amtliches Sitzungsprotokoll]({row['protokoll']}) "
                f"· Fall `{html.escape(row['fall_id'])}`",
                '',
                f"**Teilbestand einzeln bestätigt:** {verified} "
                f"· **DIP ursprünglich erwähnt:** {dip} "
                f"· **Parser-Hinweise:** {html.escape(row['parser_fundstellen'])}",
                '',
                '**Warum prüfen:** '+html.escape(row['grund']),
                '',
            ]
            official_appeal=find(session,row['person']) if row['person'] else None
            if official_appeal:
                evidence_date=html.escape(official_appeal['decision_date'])
                evidence_url=official_appeal['source']
                lines += [
                    '**Separat nachgewiesene Einspruchsentscheidung:** '
                    'Einspruch am '+evidence_date+
                    ' vom Bundestag zurückgewiesen '
                    '([amtlicher Beschlussbericht]('+evidence_url+')).',
                    '',
                    '**Beweisgrenze:** Der Beschluss betrifft die '
                    'Einspruchsentscheidung zu einer ursprünglich '
                    'erteilten Maßnahme. Er ersetzt weder den '
                    'Einzelereignisabgleich noch eine umfassende '
                    'Prüfung späterer Rechtsfolgen oder Rücknahmen.',
                    '',
                ]
            if snippet:
                lines += ['**Originalauszug (gekürzt):**', '', '> '+snippet,'']
            lines += ['**Manuelle Entscheidung:** offen; Originalkontext, betroffene '
                      'Person, einzelne Erteilungen und mögliche Einsprüche/'
                      'Rücknahmen unabhängig prüfen.','']
    lines += ['---','','Automatisch erzeugter **Arbeitsbericht**, keine Änderung '
              'der geprüften Zähler. Vollständige Fälle inklusive mittlerer '
              'Priorität stehen in `wp21_vollstaendigkeit_faelle.csv`.','']
    return '\n'.join(lines)


def run(cases,report,target):
    rows=csv_rows(cases,FIELDS)
    snapshot=json.loads(Path(report).read_text(encoding='utf-8'))
    document=create_brief(rows,snapshot)
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(target.suffix+'.tmp')
    tmp.write_text(document,encoding='utf-8')
    tmp.replace(target)
    return snapshot['high_priority_cases']


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cases',type=Path,default=Path('wp21_vollstaendigkeit_faelle.csv'))
    ap.add_argument('--report',type=Path,default=Path('docs/data/vollstaendigkeit_21.json'))
    ap.add_argument('--output',type=Path,default=Path('wp21_hochprioritaet_bericht.md'))
    a=ap.parse_args()
    count=run(a.cases,a.report,a.output)
    print(f'Quellengeprüfte Triage-Ausgabe mit {count} Hochprioritäts-Prüffällen; '
          '0 automatisch bestätigte Maßnahmen.')


if __name__=='__main__':
    main()
