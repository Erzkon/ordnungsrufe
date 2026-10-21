#!/usr/bin/env python3
"""Read-only crosswalk: original spoken grants and parliamentary appeal votes.

Three independently inspected official original and voting PDF pages.
The result identifies an appeal decision, NOT the total of independently
effective sanctions or absence of later changes. No counters may be written.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from wp21_autopruefung import norm, read_reviewed
from wp21_dip_kontrolle import reference
from wp21_einspruchsbelege import validated_index
from wp21_hochprioritaet_18 import ORIGINAL_LINES, validate_scope

ROOT=Path(__file__).resolve().parent
LEDGER=ROOT/'daten/wirksame_ordnungsrufe_21wp.csv'
SNAPSHOT=ROOT/'tests/fixtures/official_dip_wp21_positive_snapshot.json'

# Original PDFs: physical PDF page number (1-based #page), printed page number,
# independent original-XML source anchor and verified parliamentary-vote PDF.
SOURCE_CASES=(
    {
        'person':'Martin Hess','session':52,'original_date':'2026-01-14',
        'original_page':6222,'original_pdf_page':54,'original_xml_lines':(3749,),
        'original_reason':'Personal attack on fellow member during debate on Berlin power outage',
        'presiding_officer':'Andrea Lindholz',
        'decision_date':'2026-01-15','decision_session':53,
        'decision_page':6329,'decision_pdf_page':71,
        'vote_for_appeal':'AfD',
        'vote_against_appeal':'CDU/CSU, Gruene, SPD, Linke',
        'decision_outcome':'einspruch_zurueckgewiesen',
        'original_issuance_wording':'one direct, individualized spoken issuance',
    },
    {
        'person':'Kerstin Przygodda','session':67,'original_date':'2026-03-25',
        'original_page':8065,'original_pdf_page':41,'original_xml_lines':(3079,),
        'original_reason':'Personal accusation toward Kathrin Gebel during debate on violence against women',
        'presiding_officer':'Andrea Lindholz',
        'decision_date':'2026-03-26','decision_session':68,
        'decision_page':8226,'decision_pdf_page':108,
        'vote_for_appeal':'AfD',
        'vote_against_appeal':'CDU/CSU, SPD, Gruene, Linke',
        'decision_outcome':'einspruch_zurueckgewiesen',
        'original_issuance_wording':'one direct, individualized spoken issuance',
    },
    {
        'person':'Fabian Fahl','session':69,'original_date':'2026-03-27',
        'original_page':8381,'original_pdf_page':51,'original_xml_lines':(2204,),
        'original_reason':'Chair treated comparison of AfD with NSDAP as an unparliamentary interjection',
        'presiding_officer':'Andrea Lindholz',
        'decision_date':'2026-04-15','decision_session':70,
        'decision_page':8478,'decision_pdf_page':66,
        'vote_for_appeal':'Gruene, Linke',
        'vote_against_appeal':'AfD, CDU/CSU, SPD',
        'decision_outcome':'einspruch_zurueckgewiesen',
        'original_issuance_wording':'original and confirming restatement within same chair intervention; not two approved sanctions',
    },
)

def official_pdf(session,page):
    if type(session)!=int or not 1<=session<=450 or type(page)!=int or not 1<=page<=250:
        raise ValueError('Ungültige amtliche Originalseitenzuordnung')
    return f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf#page={page}'


def build(source_cases=SOURCE_CASES, appeals=None, snapshot=None, known=None):
    validate_scope()
    if appeals is None:
        appeals=validated_index()
    if snapshot is None:
        snapshot=reference(SNAPSHOT)
    if known is None:
        known,total=read_reviewed(LEDGER)
        if total!=8:
            raise ValueError('Bestätigter 8er-Teilbestand verändert')
    if (len(source_cases)!=3
            or len({(x['session'],norm(x['person'])) for x in source_cases})!=3
            or len(appeals)!=4
            or len(snapshot['entries'])!=24
            or sum(e['reported_grants'] for e in snapshot['entries'])!=25
            or sum(known.values())!=8):
        raise ValueError('Unvollständige amtliche Quellengrundlage')
    dip={(x['session'],norm(x['person'])):x for x in snapshot['entries']}
    out=[]
    for item in source_cases:
        row=dict(item)
        key=(row['session'],norm(row['person']))
        official=appeals.get(key)
        positive=dip.get(key)
        if not official or not positive or key in known:
            raise ValueError('Einspruch oder Original nicht eindeutig dem offenen Fall zugeordnet')
        if (tuple(row['original_xml_lines'])!=ORIGINAL_LINES[key]
                or len(row['original_xml_lines'])!=1
                or positive['reported_grants']!=1
                or row['decision_session']<=row['session']
                or row['decision_outcome']!='einspruch_zurueckgewiesen'
                or row['decision_date']!=official['decision_date']
                or row['original_date']!=__import__('datetime').datetime.strptime(
                    positive['date'],'%d.%m.%Y').date().isoformat()
                or not row['vote_for_appeal'] or not row['vote_against_appeal']
                or row['presiding_officer']!='Andrea Lindholz'):
            raise ValueError('Originalquelle, DIP-Referenz oder Einspruchsabstimmung widersprüchlich')
        decision_link=official_pdf(row['decision_session'],row['decision_pdf_page'])
        original_link=official_pdf(row['session'],row['original_pdf_page'])
        if (positive['official_transcript']!=original_link.split('#')[0]
                or not 6000<=row['original_page']<=9000
                or not 6000<=row['decision_page']<=9000
                or not re.fullmatch(r'https://www\.bundestag\.de/dokumente/textarchiv/2026/kw\d{2}-de-einspruch-ordnungsruf-\d+',official['source'])):
            raise ValueError('Nichtamtlicher Ursprung oder Entscheidungsbeleg')
        # Normalize immutable source tuples into JSON-native arrays so the
        # generated crosswalk agrees with the public review-data contract.
        row['original_xml_lines']=list(row['original_xml_lines'])
        out.append({
            **row,'original_pdf_url':original_link,
            'original_xml_url':f'https://dserver.bundestag.de/btp/21/21{row["session"]:03d}.xml',
            'decision_pdf_url':decision_link,
            'editorial_appeal_report_url':official['source'],
            'official_dip_original_reference':snapshot['official_index'],
            'appeal_rejection_supported_by_independent_plenary_vote':True,
            'separately_effective_sanctions_confirmed_by_this_crosswalk':0,
            'additional_original_grants_approved':0,
            'no_later_reversal_proven':False,
            'requires_independent_later_legal_outcome_review':True,
        })
    if {(x['session'],norm(x['person'])) for x in out}!={(52,norm('Martin Hess')),(67,norm('Kerstin Przygodda')),(69,norm('Fabian Fahl'))}:
        raise ValueError('Nicht alle drei Original-Einspruchspaare identifiziert')
    return {
        'schema':'wp21-three-independent-original-vote-crosswalk-v1',
        'scope':'three_selected_person_session_originals_not_full_period',
        'source_snapshot':snapshot['last_manual_snapshot'],
        'cases':out,
        'individual_origins_checked':3,
        'individually_linked_parliamentary_appeal_rejections':3,
        'independently_newly_approved_effective_sanctions':0,
        'protected_public_counters_changed':False,
        'warning':('Originalerteilung und namentlich zugeordnete Einspruchszurückweisung '
                   'sind durch Original-Plenarprotokolle belegt. Eine mögliche spätere '
                   'Korrektur/Aufhebung, zusätzliche eigenständige Maßnahmen und ihre '
                   'endgültige Rechtswirkung sind damit nicht abschließend geprüft.'),
    }


def render(report):
    if (report['independently_newly_approved_effective_sanctions']!=0
            or report['protected_public_counters_changed']
            or len(report['cases'])!=3):
        raise ValueError('Keine automatischen Wirksamkeitsentscheidungen zulässig')
    lines=['# WP21: Drei Originalerteilungen und drei Einspruchsabstimmungen','',
           'Originalsitzungen **21/052, 21/067, 21/069**.',
           'Alle drei Einsprüche wurden durch den Bundestag zurückgewiesen.',
           '**Keine automatische Zähleränderung oder umfassende spätere Rechtsfolgenfreigabe.**','']
    for item in report['cases']:
        lines.extend([
            f"## {item['person']} · 21/{item['session']:03d}",
            '',
            f"- [Amtliche Originalerteilung, Druckseite {item['original_page']}]({item['original_pdf_url']}), "
            f"Original-XML L{item['original_xml_lines'][0]}.",
            f"- Anlass: {item['original_reason']}.",
            f"- Wortlautrelation: {item['original_issuance_wording']}.",
            f"- [Parlamentarische Einspruchsabstimmung am {item['decision_date']}, "
            f"gedruckte Seite {item['decision_page']}]({item['decision_pdf_url']}).",
            f"- Für den Einspruch: {item['vote_for_appeal']}; dagegen: {item['vote_against_appeal']}.",
            f"- [Zusätzlicher amtlicher Bundestagsbericht]({item['editorial_appeal_report_url']}).",
            '- Offene Grenze: spätere Rechtsfolgen sowie eigenständige '
            'Wirksamkeit der Einzelmaßnahme nicht durch diesen Abgleich entschieden.',
            '',
        ])
    lines.extend(['**Die Quellen sind gerichtete Belege für ein Original und '
                  'dessen Einspruchsabstimmung, keine unabhängige Zählerfreigabe.**',''])
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,
                   default=ROOT/'.audit/wp21_three_decisions')
    args=p.parse_args()
    destination=args.output_dir.resolve()
    safe=(ROOT/'.audit').resolve()
    if destination!=safe and safe not in destination.parents:
        raise ValueError('Quellennachweise nur unter .audit/ schreiben')
    report=build()
    destination.mkdir(parents=True,exist_ok=True)
    for file,data in [('crosswalk.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
                      ('crosswalk.md',render(report))]:
        target=destination/file
        tmp=target.with_suffix(target.suffix+'.tmp')
        tmp.write_text(data,encoding='utf-8')
        tmp.replace(target)
    print('WP21_THREE_VOTES_CROSSWALK_PASS: 3 original sources + 3 parliamentary '
          'rejections, 0 approved new effective sanctions.')

if __name__=='__main__':
    main()
