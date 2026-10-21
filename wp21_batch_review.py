#!/usr/bin/env python3
"""Offline WP21 review batches; NO approval, publication, or ledger mutation."""
import argparse
import csv
import io
import json
from datetime import date
from pathlib import Path

from wp21_autopruefung import read_reviewed, norm
from wp21_dip_kontrolle import reference
from wp21_einspruchsbelege import validated_index
from wp21_three_decisions import build as original_vote_crosswalk
from wp21_five_origins import build as next_five_originals
from wp21_five_rechtsfolgen import historical_crosscheck as five_legal_followup
from wp21_hochprioritaet_18 import (
    EXPECTED_KEYS, ORIGINAL_LINES, MULTI_PHRASE_EPISODES, validate_scope,
)

ROOT=Path(__file__).resolve().parent
POSITIVE=ROOT/'tests/fixtures/official_dip_wp21_positive_snapshot.json'
LEDGER=ROOT/'daten/wirksame_ordnungsrufe_21wp.csv'
FROZEN_LIMIT="dated_2026_10_15_dip_partial_sample_NOT_term_total"
# Independently sourced, different procedural type. October penalty is not
# another March Ordnungsruf and must never inflate this review queue.
UNRELATED_PENALTY_REICHARDT={
    'date_of_sanction':'2026-10-15',
    'decision_date':'2026-10-16',
    'sanction_type':'ordnungsgeld_not_ordnungsruf',
    'source':'https://www.bundestag.de/dokumente/textarchiv/2026/'
             'kw42-de-einspruch-ordnungsgeld-1225202',
    'counts_as_21_065_ordnungsruf':False,
    'changes_protected_ledger':False,
}
# Separately documented procedural decision for a previously approved case;
# not a new grant and thus not added to the 17 open review cases.
PREEXISTING_SICHERT_APPEAL={
    'session':90, 'person':'Martin Sichert',
    'decision_date':'2026-09-08',
    'source':'https://www.bundestag.de/dokumente/textarchiv/2026/'
             'kw37-de-einspruch-ordnungsruf-1210768',
    'decision':'einspruch_zurueckgewiesen',
    'creates_another_ordnungsruf':False,
}
WARNING=("DIP-Originalerteilungen sind keine bestätigten wirksamen Ordnungsrufe. "
         "Ungeprüfte Mehrfachformulierungen, Einsprüche und spätere Rechtsfolgen "
         "bleiben einzeln und manuell zu prüfen. Fehlende Einspruchsquellen "
         "beweisen nicht, dass kein Einspruch vorliegt.")


def build(snapshot, known, reviewed_count, appeal_index=None):
    validate_scope()
    appeals=validated_index() if appeal_index is None else appeal_index
    entries=snapshot['entries']
    keys=[(x['session'],norm(x['person'])) for x in entries]
    if (snapshot.get('$schema')!='ordnungsruf-dip-positive-control-v1'
            or not snapshot.get('official_index','').startswith('https://dip.bundestag.de/suche?')
            or len(entries)!=24 or len(set(keys))!=24
            or sum(e['reported_grants'] for e in entries)!=25
            or reviewed_count!=8 or sum(known.values())!=8 or len(known)!=7):
        raise ValueError("Amtlicher DIP-Snapshot oder geprüfter Teilbestand hat sich geändert")
    if date.fromisoformat(snapshot['last_manual_snapshot'])>date.today():
        raise ValueError("DIP-Snapshot liegt in der Zukunft")
    if (set(keys)!=EXPECTED_KEYS|set(known)
            or len(EXPECTED_KEYS)!=18
            or EXPECTED_KEYS&set(known)!={(94,norm('Cansin Köktürk'))}
            or len(appeals)!=4 or not set(appeals).issubset(EXPECTED_KEYS)
            or sum(map(len,ORIGINAL_LINES.values()))!=21):
        raise ValueError("Kuratierte Originalquellen, Referenzfälle oder Einsprüche widersprüchlich")

    original_context={
        (51,norm('Markus Frohnmaier')):{
            'official_page':'https://dserver.bundestag.de/btp/21/21051.pdf#page=74',
            'preliminary_classification':'two_phrases_with_intervening_new_interjection',
            'separate_legal_grants_verified':False,
            'next_evidence_step':('Die ursprüngliche Erteilung und den folgenden '
                'neuen Zwischenruf mit zweiter Erteilungsformel abgrenzen; '
                'eine DIP-Erteilungsposition reicht nicht als Zahlbeweis'),
        },
        (65,norm('Martin Reichardt')):{
            'official_page':'https://dserver.bundestag.de/btp/21/21065.pdf#page=25',
            'preliminary_classification':'two_phrases_one_uninterrupted_chair_intervention',
            'separate_legal_grants_verified':False,
            'next_evidence_step':('Wiederholung des Ordnungsrufs im selben '
                'Präsidiumsredeabschnitt gegen den singularen Einspruch vom '
                '20.03.2026 abgleichen; keine automatische Zweitzaehlung'),
        },
    }
    crosswalk=original_vote_crosswalk(appeals=appeals,snapshot=snapshot,known=known)
    linked_votes={(x['session'],norm(x['person'])):x for x in crosswalk['cases']}
    five=next_five_originals(snapshot=snapshot,known=known)
    five_index={(x['session'],norm(x['person'])):x for x in five['cases']}
    followups=five_legal_followup(
        originals=five['cases'],snapshot=snapshot,known=known)
    followup_index={(x['session'],norm(x['person'])):x
                    for x in followups['cases']}
    pending=[]
    for row in entries:
        session,person=row['session'],row['person']
        key=(session,norm(person))
        reported=row['reported_grants']
        reviewed=known.get(key,0)
        if (type(reported)!=int or not 1<=reported<=3
                or reviewed>reported):
            raise ValueError("Unplausible Anzahl ursprünglicher Ordnungsrufe")
        expected_url=f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf'
        if row['official_transcript']!=expected_url:
            raise ValueError("Ursprünglicher Quellenlink nicht amtlich")
        if reviewed==reported:
            continue
        anchors=ORIGINAL_LINES.get(key)
        if not anchors or any(type(n)!=int or n<1 for n in anchors):
            raise ValueError("Offener Fall ohne kuratierte Original-XML-Fundstelle")
        multiple=key in MULTI_PHRASE_EPISODES
        if multiple!=(len(anchors)>1):
            raise ValueError("Mehrfach-Erteilungsformulierungen wurden verändert")
        decision=appeals.get(key)
        if multiple:
            tier=0
            action="Getrennte Erteilung oder Wiederholung? Jede Originalformulierung einzeln prüfen"
        elif decision:
            tier=1
            action="Einspruchszurückweisung dem Original zuordnen; spätere Folgen gesondert prüfen"
        else:
            tier=2
            action="Originalerteilung individuell und spätere Rechtsfolgen unabhängig prüfen"
        pending.append({
            'case_id':f'21-{session:03d}-{norm(person).replace(" ","-")}',
            'session':session,'person':person,
            'reported_original_grants':reported,
            'already_verified_measures':reviewed,
            'reported_but_not_individually_verified':reported-reviewed,
            'original_xml_lines':list(anchors),
            'source_pdf':expected_url,
            'source_xml':f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml',
            'source_dip_index':snapshot['official_index'],
            'multiple_wording_relation':MULTI_PHRASE_EPISODES.get(key),
            'official_appeal_decision':(
                {'date':decision['decision_date'],'source':decision['source'],
                 'outcome':'einspruch_zurueckgewiesen',
                 'confirms_effective_sanctions':False}
                if decision else None),
            'priority':('P0_mehrfachformulierung' if tier==0 else
                        'P1_einspruch_verknuepfen' if tier==1 else
                        'P2_original_und_rechtsfolge'),
            'manual_next_action':action,
            'later_effects_review':(
                {'parent_id':followup_index[key]['official_dip_parent_id'],
                 'bounded_appeals_exact_match_count':0,
                 'historical_appeal_coverage_complete':False,
                 'legal_effects_proven':False,
                 'manual_review_pending':True,
                 'new_effective_sanctions_automatically_approved':0}
                if key in followup_index else None),
            'additional_original_pdf_crosscheck':(
                {'original_pdf_url':five_index[key]['original_pdf_url'],
                 'original_xml_line':five_index[key]['original_xml_line'],
                 'original_individually_located':True,
                 'further_legal_outcome_review_required':True,
                 'new_effective_sanctions_automatically_approved':0}
                if key in five_index else None),
            'independent_original_and_vote_crosscheck':(
                {'original_pdf_url':linked_votes[key]['original_pdf_url'],
                 'decision_pdf_url':linked_votes[key]['decision_pdf_url'],
                 'confirmed_parliamentary_rejection':True,
                 'further_legal_outcome_review_required':True,
                 'new_effective_sanctions_automatically_approved':0}
                if key in linked_votes else None),
            'manual_original_context_hint':original_context.get(key),
            'independent_unrelated_proceeding':(
                dict(UNRELATED_PENALTY_REICHARDT)
                if key==(65,norm('Martin Reichardt')) else None),
            '_tier':tier,
        })
    if (len(pending)!=17 or
            sum(v['reported_but_not_individually_verified'] for v in pending)!=17):
        raise ValueError("Offene datierte DIP-Teilstichprobe verändert")
    pending.sort(key=lambda c:(c['_tier'],c['session'],norm(c['person'])))
    for n,item in enumerate(pending):
        item['batch']=n//5+1
        item.pop('_tier')
    batches=[{
        'number':idx+1,'case_ids':[x['case_id'] for x in pending[idx*5:idx*5+5]],
        'cases':len(pending[idx*5:idx*5+5]),
        'automatic_approved_sanctions':0,
    } for idx in range(4)]
    if [b['cases'] for b in batches]!=[5,5,5,2]:
        raise ValueError("Unvollständige Review-Bündel")
    return {
        'schema':'wp21-non-counting-research-batches-v1',
        'source_snapshot':snapshot['last_manual_snapshot'],
        'scope':FROZEN_LIMIT,
        'dip_person_session_pairs_in_sample':24,
        'dip_original_grants_reported_in_sample':25,
        'confirmed_partial_ledger_measures':reviewed_count,
        'pending_person_session_pairs':len(pending),
        'reported_original_grants_not_in_confirmed_partial_ledger':17,
        'curated_original_wording_locations_across_18_cases':21,
        'curated_rejected_appeals_across_18_cases':4,
        'independently_crosschecked_original_and_vote_pairs':len(linked_votes),
        'independently_located_additional_original_pdfs':len(five_index),
        'individual_later_effect_review_tasks_for_five_origins':len(followup_index),
        'curated_objection_matches_not_global_no_appeal_proof':True,
        'separate_preexisting_reviewed_case_appeal':
            dict(PREEXISTING_SICHERT_APPEAL),
        'separate_different_sanction_type':dict(UNRELATED_PENALTY_REICHARDT),
        'automatic_approved_sanctions':0,
        'automatic_rescinded_sanctions':0,
        'protected_ledgers_changed':False,
        'batches':batches,'cases':pending,'warning':WARNING,
    }


def markdown(report):
    if (report['automatic_approved_sanctions'] or report['protected_ledgers_changed']
            or len(report['cases'])!=17):
        raise ValueError("Review-Bericht darf keine Maßnahmen freigeben")
    lines=[
        '# WP21 – vier quellenbasierte Review-Bündel','',
        'Amtliche **datierte Teilstichprobe vom '+report['source_snapshot']+
        '**; kein Gesamtstand der 21. Wahlperiode.',
        '**17 offene Person-/Sitzungskombinationen** als Arbeitsaufträge; '
        'nicht 17 bestätigte zusätzliche wirksame Maßnahmen.','',
        report['warning'],'',
    ]
    for batch in report['batches']:
        lines.extend([f"## Bündel {batch['number']} ({batch['cases']} Fälle)",'',
            '| Originalprotokoll | Person | XML-Fundstellen | Einspruchquelle | Prüfschritt |',
            '|---|---|---|---|---|'])
        for item in report['cases']:
            if item['batch']!=batch['number']:
                continue
            appeal=item['official_appeal_decision']
            link=(f"[kuratierte Zurückweisung]({appeal['source']})" if appeal
                  else 'Kein kuratierter Entscheidungsbeleg; Status offen')
            lines.append(
                f"| [21/{item['session']:03d}]({item['source_pdf']}) "
                f"| {item['person']} | "+', '.join(
                    f"L{line}" for line in item['original_xml_lines'])+
                f" | {link} | {item['manual_next_action']} |")
        lines.append('')
    lines.extend([
        '## Erstes Bündel: geprüfte amtliche Originalkontexte', '',
        '- **21/051 Frohnmaier:** zwei Erteilungsformulierungen mit '
          'erneutem Zwischenruf dazwischen. '
          '[Original-PDF S. 6144](https://dserver.bundestag.de/btp/21/21051.pdf#page=74). '
          'DIP-Teilstichprobe: nur ein Ursprungsvorgang; Zahl getrennter '
          'Rechtsakte ungeklärt.',
        '- **21/065 Reichardt:** beide Formulierungen innerhalb einer '
          'durchgehenden Intervention. '
          '[Original-PDF S. 7785](https://dserver.bundestag.de/btp/21/21065.pdf#page=25). '
          'Amtlicher Einspruch/Entscheidung bezieht sich auf einen Ruf. '
          'Plausible Wiederholung, keine automatische rechtliche Feststellung.',
        '',
        '## Drei zusätzliche originalgebundene Einspruchsabstimmungen','',
        '- **Hess (21/052), Przygodda (21/067), Fahl (21/069):** '
          'Erteilungen und ihre jeweiligen parlamentarischen Abstimmungen '
          'sind mit amtlichen Original-PDF-Seiten individuell verknüpft.',
        '- Bei Fahl ist die umgehend wiederholte Erteilungsformulierung '
          'in derselben Intervention keine unabhängig freigegebene zweite Maßnahme.',
        '- [Einzelne Quellen- und Abstimmungsstellen](WP21_BATCH_1_APPEAL_VOTES.md) '
          'und die getrennten JSON-/Markdown-Gegenprüfungen im Actions-Artefakt.',
        '',
        '## Zweites Bündel: fünf amtliche Ursprungserteilungen lokalisiert', '',
        '- Reichinnek 21/053, Baumann 21/057, von Zons 21/061, '
          'Pantisano 21/065 und Gebel 21/067. Fünf eigenständige '
          'Original-PDF-Fundstellen, bisher **keine vollständige** '
          'individuelle Rechtsfolgenprüfung.',
        '- [Genaue PDF-Seiten und Empfänger-Kontext](WP21_BATCH_2_ORIGINALNOTIZEN.md) '
          'sowie getrennte JSON-/Markdown-Auditquellen. '
          'Kein Schluss aus fehlenden kuratierten Einsprüchen.',
        '',
        '## Fünf originale DIP-Vorgänge für spätere Rechtsfolgen gezielt prüfen','',
        '- Reichinnek, Baumann, von Zons, Pantisano und Gebel haben '
          'je eine separat geprüfte Original-DIP-Vorgangs-ID. '
          'In der begrenzten 17er-Einspruchsauswahl ist für die fünf '
          'kein exaktes Person-/Ursprungsdatum-Paar enthalten. '
          '**Dies beweist nicht, dass kein Einspruch oder keine '
          'spätere Aufhebung existiert.**',
        '- [Quellen-/Identitätsmatrix](WP21_FIVE_LATER_EFFECTS.md) und '
          'getrennte Live-DIP-Verfahrenspositionsprüfung; '
          'DIP-Metadaten sind keine rechtskräftigen Einzelfallzähler.',
        '',
        '## Amtliche Quellen mit ausdrücklich anderer Bedeutung','',
        '- **Martin Reichardt:** [Ordnungsgeld und Einspruch vom 15./16.10.2026]('+
          UNRELATED_PENALTY_REICHARDT['source']+
          ') sind weder ein weiterer Ordnungsruf noch ein Beleg zur '
          'Rechtsfolge der Originalerteilung aus 21/065.',
        '- **Martin Sichert:** [Zurückgewiesener Einspruch vom 08.09.2026]('+
          PREEXISTING_SICHERT_APPEAL['source']+
          ') betrifft einen bereits in der acht Fälle umfassenden Teilmenge '
          'belegten Ordnungsruf aus 21/090; kein weiterer Ursprungseintrag.',
        '',
    ])
    lines.extend(['**Keine automatische Zählerfreigabe, keine Schlussfolgerung '
                  'aus fehlenden Einspruchshinweisen.**',''])
    return '\n'.join(lines)


def write(report, folder):
    folder=Path(folder).resolve()
    allowed=(ROOT/'.audit').resolve()
    if folder!=allowed and allowed not in folder.parents:
        raise ValueError("Prüfberichte dürfen nur im Verzeichnis .audit/ entstehen")
    folder.mkdir(parents=True,exist_ok=True)
    columns=['batch','priority','session','person','original_xml_lines',
             'reported_original_grants','already_verified_measures',
             'reported_but_not_individually_verified','source_pdf','appeal_source',
             'manual_next_action']
    output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=columns)
    writer.writeheader()
    for c in report['cases']:
        writer.writerow({
            key:(','.join(map(str,c['original_xml_lines']))
                 if key=='original_xml_lines' else
                 c['official_appeal_decision']['source']
                 if key=='appeal_source' and c['official_appeal_decision'] else
                 '' if key=='appeal_source' else c[key])
            for key in columns
        })
    for filename,value in [
        ('review_queue.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
        ('review_queue.md',markdown(report)),
        ('review_queue.csv',output.getvalue()),
    ]:
        target=folder/filename
        temporary=target.with_suffix(target.suffix+'.tmp')
        temporary.write_text(value,encoding='utf-8')
        temporary.replace(target)
    return folder


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,default=POSITIVE)
    p.add_argument('--ledger',type=Path,default=LEDGER)
    p.add_argument('--output-dir',type=Path,
                   default=ROOT/'.audit/wp21_batch_review')
    a=p.parse_args()
    known,count=read_reviewed(a.ledger)
    report=build(reference(a.reference),known,count)
    path=write(report,a.output_dir)
    print('WP21_REVIEW_QUEUE_PASS: 17 unapproved candidate cases in four batches; '
          '0 new approved measures; outputs: '+str(path))


if __name__=='__main__':
    main()
