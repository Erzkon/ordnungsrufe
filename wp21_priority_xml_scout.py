#!/usr/bin/env python3
"""Read-only official spoken-XML review of Reichardt/Keuter WP21 grants.

DIP parent/position IDs are *source pointers*, not independently effective
sanctions. This first-stage evidence inventory deliberately does not decide
whether similarly named parents prove distinct grants, or any final legal
effect. The original stenographic paragraphs must be reviewed explicitly.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from parser import classify, iter_session_text
from wp21_scan import fetch, safe_parse
from wp21_new_dip_candidates import AUDIT_ROOT

EXPECTED={
    14:{'date':'26.06.2025','person':'Martin Reichardt',
        'positions':(
            ('322922','672194','https://dserver.bundestag.de/btp/21/21014.pdf#P.1133'),
            ('322921','672193','https://dserver.bundestag.de/btp/21/21014.pdf#P.1221'),
        )},
    43:{'date':'26.11.2025','person':'Stefan Keuter',
        'positions':(
            ('328596','681904','https://dserver.bundestag.de/btp/21/21043.pdf#P.4996'),
            ('328596','682732','https://dserver.bundestag.de/btp/21/21043.pdf#P.5015'),
        )},
}
GRANT=re.compile(r'\bordnungsruf(?:e|es|en)?\b|\bzur\s+Ordnung\s+(?:gerufen|rufen)\b',re.I)
NAMES={14:re.compile(r'\bReichardt\b',re.I),
       43:re.compile(r'\bKeuter\b',re.I)}
ROOT=Path(__file__).resolve().parent


def inspect_session(root,session):
    """Preserve all spoken name/Ordnungsruf mentions, not fabricated issuance."""
    target=EXPECTED[session]
    if (root.get('wahlperiode')!='21' or
            root.get('sitzung-nr')!=str(session) or
            root.get('sitzung-datum')!=target['date']):
        raise ValueError('Amtlicher Ursprung/Tag stimmt nicht zum DIP-Protokoll')
    rows=[(int(p.sourceline),text) for p,text in iter_session_text(root)]
    if len(rows)<30 or len(rows)>80000:
        raise ValueError('Originaler Plenar-Sitzungstext unvollständig')
    found=[]
    for idx,(line,text) in enumerate(rows):
        if not GRANT.search(text):
            continue
        # A name may be in a preceding chair paragraph, while the explicit
        # sanction follows in the next <p>. Keep context as evidence only.
        context=rows[max(0,idx-5):min(len(rows),idx+6)]
        related=any(NAMES[session].search(t) for _,t in context)
        found.append({
            'session':session,'xml_line':line,
            'source_xml':f'https://dserver.bundestag.de/btp/21/21{session:03d}.xml',
            'paragraph_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'text':text[:1800],
            'candidate_classification':classify(text),
            'person_mentioned_within_five_spoken_paragraphs':related,
            'context':[
                {'line':n,'text':t[:1300]} for n,t in context
            ] if related else [],
            'individual_original_grant_verified':False,
            'legally_effective_sanction_verified':False,
        })
    if not found or len(found)>150:
        raise ValueError('Keine/zu viele Ordnungsruf-Wortlaute im Originalprotokoll')
    return {
        'session':session,'original_day':target['date'],
        'name':target['person'],
        'spoken_paragraphs_checked':len(rows),
        'raw_ordnungsruf_mention_paragraphs':len(found),
        'person_context_candidates':sum(x['person_mentioned_within_five_spoken_paragraphs']
                                        for x in found),
        'candidate_paragraphs':found,
        'all_dip_parent_position_refs':[
            {'official_parent_id':p,'official_position_id':ident,
             'official_pdf_page':pdf,'source_position':
                 'https://search.dip.bundestag.de/api/v1/vorgangsposition/'+ident}
            for p,ident,pdf in target['positions']],
        'source_is_full_original_spoken_xml':True,
        'position_to_specific_spoken_paragraph_conclusively_verified':False,
        'automatically_confirmed_new_sanctions':0,
    }


def audit(roots):
    if not isinstance(roots,dict) or set(roots)!=set(EXPECTED):
        raise ValueError('Beide originalen plenaren Quellen benötigt')
    reports=[inspect_session(roots[i],i) for i in sorted(EXPECTED)]
    return {
        'schema':'wp21-reichardt-keuter-official-xml-scout-v1',
        'status':'original_spoken_paragraphs_for_individual_manual_review',
        'sessions':reports,
        'official_positions_expected':4,
        'confirmed_independent_new_grants':0,
        'automatically_confirmed_effective_sanctions':0,
        'protected_statistics_changed':False,
        'warning':('Ein DIP-Vorgang, eine amtliche DIP-Verfahrensposition '
                   'oder eine nahe stehende Namensnennung ist kein Beweis '
                   'einer individuellen eigenständigen Erteilung. '
                   'Die wörtliche Erteilung muss gesondert am amtlichen '
                   'Originalabsatz und ihrer Person untersucht werden; '
                   'spätere Einsprüche/Aufhebungen bleiben ebenfalls offen.'),
    }


def render(report):
    if (report.get('schema')!='wp21-reichardt-keuter-official-xml-scout-v1'
            or report['confirmed_independent_new_grants']!=0
            or report['automatically_confirmed_effective_sanctions']!=0
            or report['protected_statistics_changed']):
        raise ValueError('Automatische Sanktionfreigabe verboten')
    lines=['# 21/014 Reichardt · 21/043 Keuter: Original-XML-Quellensichtung','',
           '**Nur Recherchekontexte; noch keine individuell bestätigte, '
           'rechtswirksame neue Maßnahme.**','']
    for entry in report['sessions']:
        lines.extend([
            '## 21/'+f"{entry['session']:03d}"+' – '+entry['name'],'',
            'Originaltag: '+entry['original_day']+' · gesprochene Absätze: '+
            str(entry['spoken_paragraphs_checked']),
            'Wortlaut-Fundstellen: '+str(entry['raw_ordnungsruf_mention_paragraphs'])+
            ' · mit Namenskontext: '+str(entry['person_context_candidates']),''])
        for ref in entry['all_dip_parent_position_refs']:
            lines.append('- [DIP-Position '+ref['official_position_id']+']('+
                         ref['source_position']+') · [PDF-Seite]('+
                         ref['official_pdf_page']+') · Elternvorgang '+
                         ref['official_parent_id'])
        lines.append('')
        for p in entry['candidate_paragraphs']:
            if not p['person_mentioned_within_five_spoken_paragraphs']:
                continue
            lines.append('### XML-Zeile '+str(p['xml_line'])+
                         ' – '+p['candidate_classification'])
            lines.append(p['text'].replace('\n',' ')[:900])
            lines.append('')
            for context in p['context']:
                lines.append('- '+str(context['line'])+': '+
                             context['text'].replace('\n',' ')[:320])
            lines.append('')
    lines.extend([report['warning'],'','**Geschützte Zähler unverändert.**',''])
    return '\n'.join(lines)


def save(report,output_dir):
    folder=Path(output_dir).resolve()
    base=AUDIT_ROOT.resolve()
    if folder==base or base not in folder.parents or folder.is_symlink():
        raise ValueError('Originalquellen nur im isolierten .audit-Unterordner')
    folder.mkdir(parents=True,exist_ok=True)
    for name,content in (
        ('original_contexts.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n'),
        ('original_contexts.md',render(report))):
        temp=folder/(name+'.tmp')
        temp.write_text(content,encoding='utf-8')
        temp.replace(folder/name)


def run(*, cache_dir=None, output_dir=AUDIT_ROOT/'wp21_priority_originals'):
    cache=Path(cache_dir or AUDIT_ROOT/'wp21_priority_xml_cache')
    roots={}
    for session in sorted(EXPECTED):
        data=fetch(session,cache)
        if data is None:
            raise ValueError(f'Amtliches Original XML 21/{session:03d} nicht veröffentlicht')
        roots[session]=safe_parse(data,session)
    result=audit(roots)
    save(result,output_dir)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir',type=Path,
                        default=AUDIT_ROOT/'wp21_priority_xml_cache')
    parser.add_argument('--output-dir',type=Path,
                        default=AUDIT_ROOT/'wp21_priority_originals')
    args=parser.parse_args()
    report=run(cache_dir=args.cache_dir,output_dir=args.output_dir)
    for entry in report['sessions']:
        print('21/'+f"{entry['session']:03d}"+':',
              entry['raw_ordnungsruf_mention_paragraphs'],
              'Wortlaut-Treffer, davon',
              entry['person_context_candidates'],'personengebundene Kontexte.')
    print('Keine automatische Erteilungs- oder Zählerfreigabe.')


if __name__=='__main__':
    main()
