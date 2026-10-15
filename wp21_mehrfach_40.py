#!/usr/bin/env python3
"""Read-only source dossier: distinct recipients and appeal decisions in WP21/040.

A significant pitfall: a chair may address a named interjector inside a
DIFFERENT MP's <rede>. In XML 8719, Janich objects to a warning about
laughter; the chair does not sanction Sichert a second time. Distinguish
each grant at its original XML line, with appeal sources kept separately.
No effective sanction total is derived or published.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from parser import classify,events,iter_session_text,speaker_index
from wp21_anonyme_quellen import paragraph_record
from wp21_scan import HOST,fetch,safe_parse

OFFICIAL_LINES={
    8715:('Martin Sichert','mit dem Finger auf Kollegen gezeigt',False),
    8719:('Steffen Janich','für den Widerspruch gerade',True),
    8990:('Kay Gottschalk','für die Verwendung des Wortes',False),
    8992:('Kay Gottschalk','Gleichsetzung mit dem Nationalsozialismus',True),
}
WARNING_LINE=8717
INTERJECTION_LINE=8718
APPEAL_SOURCE='https://www.bundestag.de/dokumente/textarchiv/2025/kw48-de-einspruch-ordnungsruf-1127758'
APPEAL_DECISIONS=(
    ('Martin Sichert', 'finger_pointing_first', 8715),
    ('Steffen Janich', 'first_grant_source_location_needs_review', None),
    ('Steffen Janich', 'second_grant_after_named_interjection', 8719),
    ('Kay Gottschalk', 'pfui_first', 8990),
)


def inspect(root,expected=OFFICIAL_LINES,warning_line=WARNING_LINE,
            interjection_line=INTERJECTION_LINE):
    if root.get('wahlperiode')!='21' or root.get('sitzung-nr') not in ('40','040'):
        raise ValueError('Fremdes oder beschädigtes Originalprotokoll')
    if (len(expected)!=4
            or len(set(expected))!=4
            or len({person for person,_,_ in expected.values()})!=3):
        raise ValueError('Vier getrennte Formulierungen für drei Personen erforderlich')
    paragraphs=list(iter_session_text(root))
    byline={int(node.sourceline):(node,text) for node,text in paragraphs}
    if len(byline)!=len(paragraphs):
        raise ValueError('Original-XML-Quellzeilen nicht eindeutig')
    index=speaker_index([root])
    rows={}
    for item in events(Path('21040.xml'),root=root,index=index):
        rows.setdefault(int(item['line']),[]).append(item)
    warning=byline.get(warning_line)
    if (not warning or classify(warning[1])!='warning_or_conditional'
            or rows.get(warning_line)
            or not re.search(r'\bwenn\s+Sie\s+lachen\b',warning[1],re.I)):
        raise ValueError('Warnung fürs Lachen fälschlich als Ordnungsruf behandelt')
    comment=next((x for x in root.iter('kommentar')
                  if x.sourceline==interjection_line),None)
    if (comment is None or comment.getparent() is None
            or comment.getparent().tag!='rede'
            or not re.search(
                r'[–—]\s*Steffen\s+Janich\s*\[AfD\]:\s*'
                r'Also\s+fürs\s+Lachen\s+einen\s+Ordnungsruf!\s*Danke!',
                ' '.join(''.join(comment.itertext()).split()),re.I)):
        raise ValueError('Benannter Janich-Zwischenruf nicht belegbar')
    out=[]
    for line,(person,reason,is_second) in sorted(expected.items()):
        item=byline.get(line)
        if item is None:
            raise ValueError(f'Amtliche Erteilungsstelle 21/040 Zeile {line} fehlt')
        node,txt=item
        if (classify(txt)!='possible_grant'
                or reason.casefold() not in txt.casefold()
                or bool(re.search(r'\beinen\s+zweiten\s+Ordnungsruf\b',
                                  txt,re.I))!=is_second):
            raise ValueError(f'Original-XML-Prüfwortlaut geändert: Zeile {line}')
        hints=rows.get(line,[])
        if (len(hints)!=1 or hints[0]['person']!=person
                or not hints[0]['person_id']
                or hints[0]['identity_status']!='matched_xml_person'
                or hints[0]['status']!='review_required'
                or hints[0]['issuer_evidence']!='chair_marker'):
            raise ValueError(f'Fehlende eindeutige Personen-Quellenverknüpfung: Zeile {line}')
        method=hints[0]['zuordnungsmethode']
        if line==8719:
            if (not method.startswith(
                    f'zweitvergabe_zu_benanntem_zwischenruf_xmlzeile_{interjection_line}')
                    or comment.getparent() is not node.getparent()
                    or warning[0].getparent() is not node.getparent()):
                raise ValueError('Janich-Zweiterteilung nicht durch seinen Zwischenruf belegt')
        if line==8715 and not method.startswith('erstes_erteilungswort_redner_sichert_'):
            raise ValueError('Sichert hat keine nachgewiesene zweite Erteilung in dieser Stelle')
        if line==8992 and not method.startswith('zweiter_ordnungsruf_vorheriger_erteilung_'):
            raise ValueError('Gottschalk-Zweiterteilung nicht aus Erst- und Zweitwortlaut belegt')
        out.append({
            'xml_line':line,
            'recipient_review_hint':person,
            'xml_person_id':hints[0]['person_id'],
            'original_grant':paragraph_record(node,txt),
            'source_text_sha256':hashlib.sha256(txt.encode('utf-8')).hexdigest(),
            'attribution_method':method,
            'explicit_second_issuing_wording':is_second,
            'effectiveness_independently_verified':False,
        })
    if len({x['xml_person_id'] for x in out})!=3:
        raise ValueError('Unvereinbare Redneridentität in Erst-/Zweiterteilungsgruppe')
    by_person={key:[r['xml_line'] for r in out
                    if r['recipient_review_hint']==key]
               for key in ('Martin Sichert','Steffen Janich','Kay Gottschalk')}
    if by_person!={'Martin Sichert':[8715], 'Steffen Janich':[8719],
                   'Kay Gottschalk':[8990,8992]}:
        raise ValueError('Originalfundstellen nach Personen verwechselt')
    return {
        'status':'unverified_source_linked_grant_passages_with_appeal_context',
        'wahlperiode':21, 'sitzung':40,
        'original_pdf':f'{HOST}/21040.pdf',
        'original_xml':f'{HOST}/21040.xml',
        'source_grant_passages_located':4,
        'different_recipient_review_hints':3,
        'located_source_lines_by_person':by_person,
        'conditional_warning_not_granted':warning_line,
        'janich_named_interjection_xml_line':interjection_line,
        'source_passages':out,
        'official_appeals':{
            'decision_date':'2025-11-25',
            'source':APPEAL_SOURCE,
            'appeals_rejected':4,
            'individual_appeals':[
                {'person':name,'scope':scope,'linked_original_xml_line':line,
                 'outcome':'einspruch_zurueckgewiesen'}
                for name,scope,line in APPEAL_DECISIONS],
            'warning':('Die offiziell bestätigten vier Einspruchsentscheidungen '
                       'sind nicht vier automatische neu bestätigte wirksame '
                       'Ordnungsrufe. Der ursprüngliche erste Janich-Ordnungsruf '
                       'ist in diesen vier XML-Fundstellen nicht lokalisiert; '
                       'Gottschalks zweiter Ordnungsruf ist nicht als eigener '
                       'Einspruch in diesem Beschluss belegt.'),
        },
        'automatically_confirmed_effective_sanctions':0,
        'automatically_rescinded_sanctions':0,
        'warning':('Weder Sprecherkontext noch ein Einspruchsbeschluss ersetzt '
                   'einen vollständigen Einzelereignis-/Rechtsfolgenabgleich. '
                   'Keine Ausgabe verändert veröffentlichte Zähler.'),
    }


def run(cache,output):
    data=fetch(40,Path(cache))
    if data is None:
        raise ValueError('Amtliches Original-XML 21/040 nicht verfügbar')
    report=inspect(safe_parse(data,40))
    out=Path(output)
    out.parent.mkdir(parents=True,exist_ok=True)
    temp=out.with_suffix(out.suffix+'.tmp')
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',
                    encoding='utf-8')
    temp.replace(out)
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache',type=Path,default=Path('.audit/targeted_xml'))
    ap.add_argument('--output',type=Path,default=Path('.audit/wp21_040_pairs.json'))
    a=ap.parse_args()
    report=run(a.cache,a.output)
    print(f"WP21/040: {report['source_grant_passages_located']} "
          f"Original-Erteilungsstellen, "
          f"{report['different_recipient_review_hints']} "
          f"namentlich belegte Personen, "
          f"{report['official_appeals']['appeals_rejected']} "
          "separate amtliche Einspruchsentscheidungen; "
          "0 automatisch bestätigte wirksame Maßnahmen.")


if __name__=='__main__':
    main()
