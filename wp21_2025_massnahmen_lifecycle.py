#!/usr/bin/env python3
"""Person- and ordinal-specific WP21/2025 initial grants and objections.

Sources: ten independently verified official DIP parents and the original
21/040 + 21/042 plenary XML transcripts. This is a read-only review ledger:
a rejected objection is NOT a newly issued grant or a determination about
every possible future legal outcome. A missing vote in one parent is not
proof that no other procedure exists.
"""
import argparse
import json
import re
from pathlib import Path

from wp21_autopruefung import norm
from wp21_2025_dip_einzelakten import CASES, official_plenary_url


# Each source location is verified independently in wp21_40_mehrfach_akte.py.
ORIGINAL_40={
    ('Martin Sichert',1):('Sichert_original_issuance',8715),
    ('Steffen Janich',2):('Janich_second_original_issuance_words',8719),
    ('Kay Gottschalk',1):('Gottschalk_first_original_issuance',8990),
    ('Kay Gottschalk',2):('Gottschalk_second_original_issuance',8992),
}
VOTES_42={
    ('Martin Sichert',1):('Sichert_objection_vote',1507),
    ('Steffen Janich',1):('Janich_first_objection_vote',1513),
    ('Steffen Janich',2):('Janich_second_objection_vote',1517),
    ('Kay Gottschalk',1):('Gottschalk_objection_vote',1521),
}


def text_anchor(source,index,expected_line):
    if not isinstance(source,dict):
        raise ValueError('XML-Quellenabsatz fehlt')
    ref=source.get(index)
    if (not isinstance(ref,dict)
            or ref.get('original_xml_line')!=expected_line
            or not re.fullmatch(r'[0-9a-f]{64}',str(ref.get('paragraph_sha256','')))
            or ref.get('legal_measure_count_confirmed_by_this_paragraph') is not False):
        raise ValueError('XML-Fundstelle/Hash für getrennten Ordnungsruf nicht belegbar')
    return {'line':expected_line,'sha256':ref['paragraph_sha256']}


def validate_40_42(xml):
    if (not isinstance(xml,dict)
            or xml.get('schema')!='wp21-40-42-source-episode-audit-v1'
            or xml.get('distinct_original_issued_measures_from_independent_sources')!=5
            or xml.get('distinct_rejected_appeals_in_42')!=4
            or xml.get('gottschalk_original_issued_measures')!=2
            or xml.get('gottschalk_appeals_decided_in_42')!=1
            or xml.get('janich_appeals_distinguish_first_and_second') is not True
            or xml.get('four_separate_vote_rejection_wordings_checked')!=4
            or xml.get('automatically_confirmed_effective_sanctions')!=0
            or xml.get('protected_public_counters_changed') is not False
            or xml.get('original_protocol')!='https://dserver.bundestag.de/btp/21/21040.xml'
            or xml.get('appeal_protocol')!='https://dserver.bundestag.de/btp/21/21042.xml'):
        raise ValueError('Zwei Original-Plenarprotokolle nicht unabhängig verifiziert')
    originals={key:text_anchor(xml.get('source_issuance_paragraphs'),*value)
               for key,value in ORIGINAL_40.items()}
    votes={key:text_anchor(xml.get('source_appeal_paragraphs'),*value)
           for key,value in VOTES_42.items()}
    return originals,votes


def validate_seven_other_source_lines(report):
    """Recheck independently sourced seven 2025 issuer line identities.

    The seven-source JSON is emitted only after parsing each official
    original XML document, matching the strict issuer phrase, and hashing
    that exact original paragraph. No replacement by a same-name mention.
    """
    from wp21_2025_sieben_originalzeilen import LOCATIONS,DAYS
    if (not isinstance(report,dict)
            or report.get('schema')!='wp21-2025-seven-verified-original-xml-loci-v1'
            or report.get('individually_sourced_original_xml_lines')!=7
            or report.get('known_other_21_040_lines_validated_separately')!=4
            or report.get('first_janich_original_xml_line_is_still_unlocated') is not True
            or report.get('automatically_confirmed_effective_sanctions')!=0
            or report.get('automatically_rescinded_sanctions')!=0
            or report.get('public_counter_delta')!=0):
        raise ValueError('Amtliche sieben Original-XML-Fundstellen unvollständig')
    records=report.get('cases')
    if not isinstance(records,list) or len(records)!=7:
        raise ValueError('Genau sieben unzensierte individuelle Erteilungsquellen')
    index={}
    for row in records:
        if not isinstance(row,dict):
            raise ValueError('Ungültiger amtlicher XML-Einzelfall')
        session=row.get('session')
        person=row.get('person')
        if type(session)!=int or not isinstance(person,str):
            raise ValueError('Amtliche Ursprungsidentität fehlt')
        key=(session,norm(person))
        if key not in LOCATIONS or key in index:
            raise ValueError('XML-Zeile fremder oder doppelter Ursprungsmaßnahme')
        expected_line=LOCATIONS[key][0]
        expected_xml=f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml'
        expected_pdf=f'https://dserver.bundestag.de/btp/21/21{session:03d}.pdf'
        if (row.get('original_date')!=DAYS[session]
                or row.get('original_xml_line')!=expected_line
                or row.get('original_xml_source')!=expected_xml
                or row.get('original_pdf_source')!=expected_pdf
                or not re.fullmatch(r'[0-9a-f]{64}',str(row.get('paragraph_sha256','')))
                or row.get('legally_effective_individual_sanction_confirmed') is not False
                or row.get('automatic_public_counter_delta')!=0):
            raise ValueError('Amtlicher Quellenabsatz/Zeitpunkt/Status widersprüchlich')
        index[key]={'line':expected_line,'sha256':row['paragraph_sha256']}
    if set(index)!=set(LOCATIONS):
        raise ValueError('Sieben individuell identifizierte Quellabsätze fehlen')
    return index


def review(official,xml,seven_other_origins=None):
    originals,xml_votes=validate_40_42(xml)
    extra_sources=(validate_seven_other_source_lines(seven_other_origins)
                   if seven_other_origins is not None else {})
    if (not isinstance(official,dict)
            or official.get('schema')!='wp21-2025-ten-cases-original-votes-review-v1'
            or official.get('case_count')!=10
            or official.get('official_parent_ids')!=10
            or official.get('source_original_grant_positions')!=10
            or official.get('original_issuance_events_review_only')!=12
            or official.get('separate_rejected_objections')!=11
            or official.get('official_position_records')!=21
            or official.get('automatically_confirmed_effective_measures')!=0
            or official.get('automatically_rescinded_measures')!=0
            or official.get('public_statistics_modified') is not False):
        raise ValueError('Zehn amtliche DIP-Original-/Einspruchsfälle nicht verifiziert')
    source_index={
        (d,norm(person)):(person,parent,sitting,decision_sitting,grants,votes)
        for d,person,parent,sitting,decision_sitting,grants,votes in CASES}
    cases=official.get('cases')
    if not isinstance(cases,list) or len(cases)!=10:
        raise ValueError('Genau zehn quellengebundene DIP-Einzelfälle erforderlich')
    used_keys=set()
    used_vote_ids=set()
    result=[]
    for case in cases:
        if not isinstance(case,dict):
            raise ValueError('DIP-Falldatensatz beschädigt')
        key=(case.get('original_date'),norm(case.get('person','')))
        if key not in source_index or key in used_keys:
            raise ValueError('Unbekannter/doppelter Person/Tag-Fall')
        used_keys.add(key)
        person,parent,sitting,decision_sitting,number,objection_count=source_index[key]
        if (case.get('person')!=person or case.get('original_sitting')!=sitting
                or case.get('decision_sitting')!=decision_sitting
                or case.get('official_dip_parent_id')!=parent
                or case.get('official_dip_parent')!='https://dip.bundestag.de/vorgang/'+parent
                or case.get('independently_sourced_original_issuance_count_review_only')!=number
                or case.get('independently_sourced_rejected_objection_count')!=objection_count
                or case.get('legal_effect_of_individual_measures_not_inferred') is not True):
            raise ValueError('Person/Sitzung/Originalzahl passt nicht zum DIP-Quellenfall')
        grant=case.get('original_dip_position')
        if (not isinstance(grant,dict)
                or not re.fullmatch(r'[1-9]\d{0,11}',str(grant.get('id','')))
                or not official_plenary_url(grant.get('plenary_pdf'),sitting)
                or grant.get('plenary_xml')!=f'https://dserver.bundestag.de/btp/21/21{sitting:03d}.xml'):
            raise ValueError('Amtlicher DIP-Erteilungsquellanker fehlt')
        positions=case.get('decision_dip_positions')
        if not isinstance(positions,list) or len(positions)!=objection_count:
            raise ValueError('Individuelle Einspruchspositionen unvollständig')
        mapped={}
        for vote in positions:
            if (not isinstance(vote,dict)
                    or not re.fullmatch(r'[1-9]\d{0,11}',str(vote.get('id','')))
                    or vote['id'] in used_vote_ids
                    or vote.get('decision_tenor')!='Zurückweisung des Einspruchs'
                    or not official_plenary_url(vote.get('plenary_pdf'),decision_sitting)):
                raise ValueError('Einzelner Einspruch oder amtlicher Beschlusstenor unklar')
            used_vote_ids.add(vote['id'])
            abstract=vote.get('abstract_excerpt')
            if not isinstance(abstract,str):
                raise ValueError('Einspruchsabstract ist kein Text')
            if number==2 and person in ('Kay Gottschalk','Steffen Janich'):
                if person=='Kay Gottschalk':
                    ordinal=1 if 'gegen die erste Ordnungsmaßnahme' in abstract else None
                else:
                    matched=re.search(r'\bgegen\s+die\s+([12])\.\s+Ordnungsmaßnahme\b',abstract,re.I)
                    ordinal=int(matched.group(1)) if matched else None
                if ordinal is None or ordinal in mapped:
                    raise ValueError('Erster/zweiter Einspruch nicht quellengebunden unterscheidbar')
            else:
                ordinal=1
                if ordinal in mapped:
                    raise ValueError('Einspruch mehrmals derselben Erteilung zugeordnet')
            mapped[ordinal]=vote
        if len(mapped)!=objection_count:
            raise ValueError('Einspruchspositionsanzahl nicht identisch zu gebundenen Maßnahmennummern')
        for ordinal in range(1,number+1):
            original_xml=(originals.get((person,ordinal)) if sitting==40
                          else extra_sources.get((sitting,norm(person)))
                          if ordinal==1 else None)
            decided=mapped.get(ordinal)
            decision_xml=xml_votes.get((person,ordinal)) if decided and sitting==40 else None
            if sitting==40 and person=='Steffen Janich' and ordinal==1:
                # The first issuance is explicitly referenced by the second
                # and by the later appeal, but its exact original XML line
                # has not yet been independently pinpointed.
                if original_xml is not None or decision_xml is None:
                    raise ValueError('Janich erster Ruf: ungesicherte XML-Erteilungszeile')
            elif sitting==40 and (original_xml is None or
                                  (decided is not None and decision_xml is None)):
                raise ValueError('Eine ursprüngliche/entschiedene Quellenzeile fehlt')
            if sitting==40 and person=='Kay Gottschalk' and ordinal==2 and decided:
                raise ValueError('Gottschalks zweiter Ruf fälschlich als Einspruch behandelt')
            result.append({
                'measure_id':f'21/{sitting:03d}:{norm(person)}:{ordinal}',
                'original_date':key[0],
                'person':person,'original_sitting':sitting,
                'ordinal_within_official_parent':ordinal,
                'official_parent_id':parent,
                'official_parent_url':'https://dip.bundestag.de/vorgang/'+parent,
                'original_grant_dip_position_id':grant['id'],
                'original_official_pdf':grant['plenary_pdf'],
                'original_official_xml':grant['plenary_xml'],
                'specific_original_issuance_xml_source':original_xml,
                'first_janich_xml_original_line_still_unlocated':(
                    sitting==40 and person=='Steffen Janich' and ordinal==1),
                'objection_vote_dip_position_id':decided['id'] if decided else None,
                'objection_vote_original_pdf':decided['plenary_pdf'] if decided else None,
                'objection_vote_xml_line':decision_xml,
                'objection_rejection_in_examined_parent':decided is not None,
                'missing_vote_means_no_appeal_anywhere':False,
                'review_status':(
                    'separate_rejected_objection_documented'
                    if decided else
                    'no_separate_vote_in_examined_parent_other_proceedings_unknown'),
                'individual_legally_effective_sanction_confirmed_here':False,
                'automatic_public_counter_delta':0,
            })
    if len(used_keys)!=10 or len(result)!=12 or len(used_vote_ids)!=11:
        raise ValueError('Zwölf Einzelerteilungen und elf eindeutige Beschlüsse fehlen')
    undecided=[x for x in result if x['objection_vote_dip_position_id'] is None]
    if (len(undecided)!=1 or undecided[0]['person']!='Kay Gottschalk'
            or undecided[0]['original_sitting']!=40
            or undecided[0]['ordinal_within_official_parent']!=2):
        raise ValueError('Ungesicherter Einspruchsstand falsch zugeordnet')
    if len({x['measure_id'] for x in result})!=12:
        raise ValueError('Einzelmaßnahme mehrfach in Prüfliste enthalten')
    if sum(bool(x['specific_original_issuance_xml_source']) for x in result)!=(4+len(extra_sources)):
        raise ValueError('Nicht alle separat bestätigten Original-XML-Erteilungszeilen zugeordnet')
    result.sort(key=lambda x:(x['original_date'],x['original_sitting'],
                              norm(x['person']),x['ordinal_within_official_parent']))
    return {
        'schema':'wp21-2025-person-ordinal-lifecycle-review-v1',
        'source_status':'source_bound_initial_grants_and_separate_objection_outcomes',
        'official_dip_original_parents':10,
        'initially_issued_individual_grants_review_only':12,
        'separately_rejected_objections':11,
        'no_vote_in_examined_parent':1,
        'identified_original_xml_issuance_lines':4+len(extra_sources),
        'still_unlocated_original_xml_issuance_lines':8-len(extra_sources),
        'seven_independently_source_bound_2025_originals':len(extra_sources),
        'source_line_completeness_scope':(
            '11_of_12_with_first_janich_line_unlocated'
            if len(extra_sources)==7 else
            'four_21_040_lines_only_others_not_checked_in_this_invocation'),
        'Gottschalk_second_grant_status_not_exhaustively_established':True,
        'automatically_confirmed_legally_effective_measures':0,
        'automatically_rescinded_measures':0,
        'public_counter_delta':0,
        'warning':('Beschlüsse über Einsprüche sind keine weiteren '
                   'Ordnungsrufe. Ein in diesem Vorgang fehlender '
                   'Einspruchsentscheid kann außerhalb des geprüften '
                   'Vorgangs vorliegen. '
                   + ('Eine genaue Erteilungszeile fehlt noch bei Janichs '
                      'erstem Ruf. Die elf anderen individuellen '
                      'Originalzeilen sind überprüft.'
                      if len(extra_sources)==7 else
                      'Eine genaue Erteilungszeile fehlt bei Janichs '
                      'erstem Ruf und sieben anderen ungeprüften '
                      '2025-Fällen.') +
                   ' Keine automatische Rechtsfreigabe.'),
        'measures':result,
    }


def markdown(report):
    if (report.get('schema')!='wp21-2025-person-ordinal-lifecycle-review-v1'
            or report.get('initially_issued_individual_grants_review_only')!=12
            or report.get('separately_rejected_objections')!=11
            or report.get('no_vote_in_examined_parent')!=1
            or report.get('public_counter_delta')!=0):
        raise ValueError('Einzelmaßnahmen-Prüfmatrix mit möglichem Zählerleck')
    lines=['# Zwölf einzelne Originalmaßnahmen – getrennte Einsprüche (21. WP, 2025)',
           '',
           '**12 ursprünglich erteilte Rufe in 10 amtlichen DIP-Elternvorgängen; '
           '11 person-/maßnahmenscharf zugeordnete zurückgewiesene Einsprüche.**',
           'Dies ist eine **nichtzählende** Quellenprüfmatrix, keine neue '
           'Zahl rechtswirksamer Maßnahmen.',
           '',
           '| Ursprung | Einzelmaßnahme | XML-Quellenzeile | Gesonderter Einspruch |',
           '| --- | --- | --- | --- |']
    for item in report['measures']:
        locus=(f"21/040 L{item['specific_original_issuance_xml_source']['line']}"
               if item['specific_original_issuance_xml_source'] else
               '**Noch nicht exakt ermittelt**')
        vote=('Zurückweisung dokumentiert'
              if item['objection_rejection_in_examined_parent'] else
              '**Keine Entscheidungsposition im geprüften Vorgang**')
        lines.append(
            f"| 21/{item['original_sitting']:03d} · {item['original_date']} | "
            f"{item['person']} – Nr. {item['ordinal_within_official_parent']} "
            f"([DIP]({item['official_parent_url']})) | {locus} | {vote} |")
    lines.extend(['','## Beweisgrenzen','',
        f"- Individuell geprüfte Erteilungszeilen: "
        f"{report['identified_original_xml_issuance_lines']} von 12.",
        '- Der erste Ruf bei Steffen Janich besitzt noch keinen eigenen'
        '  durchgängig eindeutig lokalisierten Original-XML-Zeilenanker.',
        '- Gottschalks zweiter Ruf besitzt ein ausdrücklich belegtes',
        '  Erteilungswort, aber keinen zweiten Zurückweisungsbeschluss',
        '  **innerhalb seines geprüften DIP-Elternvorgangs**.',
        '- Das schließt andere oder später bekannt gewordene',
        '  Rechtsmittel und Entscheidungen **nicht** aus.',
        '- Die JSON-Fallakte enthält je Maßnahme die DIP-Position,',
        '  die konkrete amtliche Original-PDF-Seite und soweit',
        '  verifiziert die Original-XML-Zeile plus SHA256.',
        '- **Automatische Freigaben / Rücknahmen / Änderungen der',
        '  geschützten Statistik: null.**',''])
    return '\n'.join(lines)


def run(dip_report,plenary_report,output,brief,seven_original_report=None):
    official=json.loads(Path(dip_report).read_text(encoding='utf-8'))
    xml=json.loads(Path(plenary_report).read_text(encoding='utf-8'))
    extra=(json.loads(Path(seven_original_report).read_text(encoding='utf-8'))
           if seven_original_report is not None else None)
    report=review(official,xml,extra)
    prose=markdown(report)
    for path,body in ((Path(output),json.dumps(report,indent=2,ensure_ascii=False)+'\n'),
                      (Path(brief),prose)):
        path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(body,encoding='utf-8')
        temp.replace(path)
    print('WP21_2025_LIFECYCLE_OK 12 original grants, 11 bound rejected '
          'objections, Gottschalk second without a vote in its one parent, '
          '0 automatic legal counts')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dip-report',type=Path,required=True)
    p.add_argument('--plenary-report',type=Path,required=True)
    p.add_argument('--seven-original-report',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--brief',type=Path,required=True)
    args=p.parse_args()
    run(args.dip_report,args.plenary_report,args.output,args.brief,
        args.seven_original_report)
