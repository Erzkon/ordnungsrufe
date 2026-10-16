#!/usr/bin/env python3
"""Read-only audit dossier linking 3 official original XML grants to recipients.

Identity of each candidate is supported either by an explicit later chair
clarification (Janich/Keuter) or the DIP catalog (Brucker); it never changes
the separately reviewed effective-sanction ledgers or published counters.
"""
import argparse
import hashlib
import json
from pathlib import Path

from parser import events,iter_session_text,speaker_index
from wp21_amtliche_empfaenger import DIP_BRUCKER
from wp21_scan import HOST,fetch,safe_parse

EXPECTED={
    (26,3436):('Steffen Janich','namentliche_sitzungsleitungs_klarstellung_xmlzeile_3541',3541),
    (43,2405):('Stefan Keuter','zweitgenannte_erteilung_vorsitz_klaerung_xmlzeile_2418',2418),
    (43,3497):('Erhard Brucker','amtliche_dip_person_fundstelle_21_43_5015A',None),
}
PDF_PAGE={(26,3436):'2774D',
          (43,2405):'4997B',
          (43,3497):'5015A'}


def build(roots):
    if set(roots)!={26,43}:
        raise ValueError('Quellenprüfung 26/43 braucht exakt beide Originale')
    index=speaker_index(roots.values())
    proof=[]
    for session,root in sorted(roots.items()):
        if (root.get('wahlperiode')!='21'
                or int(root.get('sitzung-nr') or -1)!=session):
            raise ValueError('Ungültiges Protokoll oder andere Wahlperiode')
        paragraphs={
            int(el.sourceline):(el,txt) for el,txt in iter_session_text(root)
        }
        indexed={}
        for row in events(Path(f'21{session:03d}.xml'),index=index,root=root):
            indexed.setdefault(int(row['line']),[]).append(row)
        for (meeting,line),(name,method,retro_line) in EXPECTED.items():
            if meeting!=session:
                continue
            original=paragraphs.get(line)
            found=indexed.get(line,[])
            if (not original or len(found)!=1
                    or found[0]['person']!=name
                    or found[0]['zuordnungsmethode']!=method
                    or found[0]['status']!='review_required'
                    or found[0]['evidence_type']!='possible_grant'):
                raise ValueError(
                    f'Amtlicher Identitätsnachweis 21/{session:03d} '
                    f'Zeile {line} fehlt oder ist mehrdeutig')
            issue_text=original[1]
            supporting=None
            if retro_line is not None:
                retro=paragraphs.get(retro_line)
                if retro is None:
                    raise ValueError('Originale Vorsitz-Klarstellung fehlt')
                supporting={
                    'type':'namentliche_nachtraegliche_vorsitz_klarstellung',
                    'xml_line':retro_line,
                    'original_text':retro[1][:850],
                    'sha256':hashlib.sha256(retro[1].encode()).hexdigest(),
                }
            else:
                supporting={
                    'type':'amtliche_dip_person_originalstelle',
                    'source':DIP_BRUCKER,
                    'page':PDF_PAGE[(session,line)],
                    'caveat':'DIP-Name, keine namentliche XML-Rednerkennung am Ordnungsruf',
                }
            proof.append({
                'case_id':f'wp21-{session:03d}-xml{line}',
                'session':session,
                'xml_line':line,
                'person_review_reference':name,
                'person_id_in_parser':found[0]['person_id'],
                'identity_status':found[0]['identity_status'],
                'attribution_method':method,
                'grant_original_text':issue_text[:950],
                'grant_sha256':hashlib.sha256(issue_text.encode()).hexdigest(),
                'original_pdf':f'{HOST}/21{session:03d}.pdf',
                'original_xml':f'{HOST}/21{session:03d}.xml',
                'pdf_page_column':PDF_PAGE[(session,line)],
                'independent_recipient_evidence':supporting,
                'unverified_effective_sanction':True,
            })
    if (len(proof)!=3 or len({p['case_id'] for p in proof})!=3):
        raise ValueError('Nicht exakt 3 getrennte amtliche Belegstellen')
    return {
        'status':'separat_zu_pruefende_offizielle_personenbelege',
        'wahlperiode':21,
        'protocols_checked':2,
        'previously_anonymous_locations_linked':3,
        'official_chair_references':2,
        'official_dip_person_references':1,
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'warning':('Name und Original-XML-Stelle sind quellenkundlich '
                   'verbunden. Individuelle Rechtswirkung, Einspruch '
                   'und spätere Aufhebung sind weiterhin separat zu prüfen. '
                   'Die Statistikdateien werden nicht verändert.'),
        'cases':proof,
    }


def run(cache,output):
    roots={}
    for n in (26,43):
        data=fetch(n,Path(cache))
        if data is None:
            raise ValueError(f'Amtliches Original 21/{n:03d} nicht verfügbar')
        roots[n]=safe_parse(data,n)
    report=build(roots)
    out=Path(output)
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix(out.suffix+'.tmp')
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',
                   encoding='utf-8')
    tmp.replace(out)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,default=Path('.audit/targeted_xml'))
    parser.add_argument('--output',type=Path,default=Path('.audit/wp21_offizielle_empfaenger.json'))
    a=parser.parse_args()
    d=run(a.cache,a.output)
    print(f"{d['previously_anonymous_locations_linked']} personell "
          "quellenbelegte Prüfstellen aus zwei Originalprotokollen; "
          "0 automatisch bestätigte wirksame Maßnahmen.")


if __name__=='__main__':
    main()
