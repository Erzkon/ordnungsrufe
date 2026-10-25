#!/usr/bin/env python3
"""Five additional original PDF issuances, read-only and not a legal-effects audit."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from wp21_autopruefung import norm, read_reviewed
from wp21_dip_kontrolle import reference
from wp21_hochprioritaet_18 import ORIGINAL_LINES, EXPECTED_KEYS, validate_scope
from wp21_three_decisions import ROOT, SNAPSHOT, LEDGER, official_pdf

# Physical PDF page numbers (one-based); print page confirmed by visual read
# of the official Bundestag PDF. Source anchors from earlier curated full XML.
PRIMARY_PAGES=(
    ('Heidi Reichinnek',53,6149,6417,159,'2026-01-15',
     'Bodo Ramelow','retrospective grant for the interjection "Lügnerin"'),
    ('Bernd Baumann',57,1487,6867,31,'2026-01-30',
     'Andrea Lindholz','grant for attacking the chair impartiality during debate'),
    ('Ulrich von Zons',61,4557,7394,76,'2026-03-04',
     'Bodo Ramelow','grant for characterization of Brosius-Gersdorf as extremist'),
    ('Luigi Pantisano',65,5104,7874,114,'2026-03-19',
     'Josephine Ortleb','explicit retrospective grant for interjection "Faschisten seid ihr"'),
    ('Kathrin Gebel',67,3164,8068,44,'2026-03-25',
     'Andrea Lindholz','grant for personally accusing Chancellor of racist rhetoric'),
)


def build(sources=PRIMARY_PAGES, snapshot=None, known=None):
    validate_scope()
    if snapshot is None:
        snapshot=reference(SNAPSHOT)
    if known is None:
        known,total=read_reviewed(LEDGER)
        if total!=8:
            raise ValueError('Acht bestätigte Einträge des WP21-Teilbestands verändert')
    if (len(sources)!=5 or
            len({(s,norm(p)) for p,s,*_ in sources})!=5
            or len(snapshot['entries'])!=24
            or sum(x['reported_grants'] for x in snapshot['entries'])!=25
            or sum(known.values())!=8):
        raise ValueError('Original-PDF-Positivstichprobe unvollständig')
    official={(x['session'],norm(x['person'])):x for x in snapshot['entries']}
    out=[]
    for item in sources:
        if len(item)!=8:
            raise ValueError('Originalquelleneintrag fehlerhaft')
        person,session,line,printed,pdf_page,day,chair,context=item
        key=(session,norm(person))
        ref=official.get(key)
        if (key not in EXPECTED_KEYS or ref is None or key in known
                or ORIGINAL_LINES.get(key)!=(line,)
                or ref['reported_grants']!=1
                or datetime.strptime(ref['date'],'%d.%m.%Y').date().isoformat()!=day
                or ref['official_transcript']!=official_pdf(session,pdf_page).split('#')[0]
                or type(line)!=int or line<1 or type(printed)!=int or printed<6000
                or not chair or not context):
            raise ValueError('Unzuverlässige Originalfundstelle oder Stichprobe')
        out.append({
            'person':person,'session':session,'original_date':day,
            'original_xml_line':line,'printed_protocol_page':printed,
            'original_pdf_url':official_pdf(session,pdf_page),
            'original_xml_url':f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml',
            'presiding_officer':chair,'original_issuance_context':context,
            'original_source_individually_located':True,
            'curated_appeal_absence_is_no_evidence_of_no_appeal':True,
            'subsequent_effectiveness_and_appeals_independently_reviewed':False,
            'newly_approved_effective_sanctions':0,
        })
    if {x['session'] for x in out}!={53,57,61,65,67}:
        raise ValueError('Fehlende Fälle im zweiten Bearbeitungsbündel')
    return {
        'schema':'wp21-five-second-batch-original-pdf-sources-v1',
        'scope':'five_dated_original_issuances_not_full_term',
        'source_snapshot':snapshot['last_manual_snapshot'],
        'origin_issuances_individually_located_in_official_pdfs':5,
        'individual_effectiveness_reviews_completed':0,
        'newly_approved_effective_sanctions':0,
        'protected_counters_changed':False,
        'cases':out,
        'warning':('Fünf ursprüngliche Erteilungen in amtlichen Protokollen '
                   'identifiziert. Die vollständige Einspruchs-/Rücknahme-/'
                   'Rechtsfolgenprüfung ist noch ausstehend; kein Schluss '
                   'aus fehlenden kuratierten Einspruchshinweisen.'),
    }


def markdown(report):
    if report['newly_approved_effective_sanctions']!=0 or report['protected_counters_changed']:
        raise ValueError('Automatische Zählerfreigabe nicht zulässig')
    lines=[
        '# WP21: zweites Fünferbündel – amtliche Ursprungssätze',
        '',
        '**Originalwortlaute lokalisierbar; endgültiger individueller '
        'Rechtsfolgenstatus noch offen. Keine zusätzlichen bestätigten Maßnahmen.**',
        '',
        '| Person / Sitzung | Original-PDF | XML-Linie | Kontext |',
        '|---|---|---|---|',
    ]
    for c in report['cases']:
        lines.append(
            f"| {c['person']} / 21/{c['session']:03d} "
            f"| [Druckseite {c['printed_protocol_page']}]({c['original_pdf_url']}) "
            f"| L{c['original_xml_line']} | {c['original_issuance_context']} |")
    lines.extend(['',report['warning'],''])
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=ROOT/'.audit/wp21_five_origins')
    args=p.parse_args()
    output=args.output_dir.resolve()
    safe=(ROOT/'.audit').resolve()
    if output!=safe and safe not in output.parents:
        raise ValueError('Nur das nichtöffentliche .audit/ Verzeichnis erlaubt')
    result=build()
    output.mkdir(parents=True,exist_ok=True)
    for name,data in [
        ('source_records.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n'),
        ('source_records.md',markdown(result)),
    ]:
        path=output/name
        temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(data,encoding='utf-8')
        temp.replace(path)
    print('WP21_FIVE_ORIGINALS_PASS: 5 independently located original PDF pages; '
          '0 new approved effective sanctions.')


if __name__=='__main__':
    main()
