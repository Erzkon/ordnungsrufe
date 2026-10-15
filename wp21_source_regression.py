#!/usr/bin/env python3
"""Conservative regression checks against actual official WP21 XML paragraphs.

Only examines transcript snippets already downloaded by wp21_fallkontext.
Fails if the sample's source wording changes: never silently accepts a new
negative/positive ground truth. Proposals remain unverified and never count.
"""
import argparse
from pathlib import Path

from parser import candidates, events, iter_session_text, speaker_index
from wp21_scan import safe_parse

SOURCE_FRAGMENTS = {
    # 21/040 has TWO distinct first/second pairs involving two MPs,
    # not one three-grant series: Sichert 8715+8719, Gottschalk 8990+8992.
    (40, 'ich erteile ihnen jetzt einen ordnungsruf, weil sie mit dem finger'):
        ('linked_hint','Sichert'),
    (40, 'ich erteile ihnen auch für den widerspruch gerade einen zweiten ordnungsruf'):
        ('linked_hint','Sichert'),
    (40, 'herr kollege gottschalk, ich erteile ihnen jetzt einen ordnungsruf'):
        ('named_hint','Gottschalk'),
    (40, 'und ich erteile ihnen einen zweiten ordnungsruf dafür'):
        ('linked_hint','Gottschalk'),
    (40, 'wenn sie lachen – und ich weiß, wer gelacht hat'):
        ('conditional_warning',None),
    # Three remaining independent DIP-positive references, with exact XML
    # recipients supported by named speech blocks / formal introductions.
    (52, 'herr kollege, dafür, dass sie der kollegin inkompetenz'):
        ('linked_hint','Hess'),
    (65, 'jetzt ist gut. ich mache hier nicht jeden quatsch mit. herr reichardt'):
        ('full_identity','Martin Reichardt'),
    (67, 'frau kollegin, dafür, dass sie der kollegin gebel'):
        ('linked_hint','Przygodda'),
    (57, 'sie kriegen jetzt von mir einen ordnungsruf dafür'): ('linked_hint','Baumann'),
    (61, 'für die bezeichnung von frau brosius-gersdorf'): ('linked_hint','Zons'),
    (71, 'dafür muss ich ihnen einen ordnungsruf erteilen'): ('linked_hint','Edis'),
    (93, 'dafür erteile ich ihnen einen ordnungsruf'): ('linked_hint','Bessin'),
    (27, 'nach durchsicht des protokolls muss ich feststellen'): ('named_hint','Koch'),
    (69, 'werden sie auch dafür einen ordnungsruf bekommen'): ('conditional_warning',None),
    # Separately validate previously unrecognised direct recipients and
    # strict negative/hypothetical language in the real official transcripts.
    (15, 'ich erteile einen ordnungsruf an herrn lamely'): ('named_hint','Lamely'),
    (22, 'wer dreimal einen ordnungsruf erhält'): ('conditional_warning', None),
    (23, 'ich erteile hier noch einen nachträglichen ordnungsruf'): ('named_hint','Hilse'),
    (25, 'dann bekommt man ja einen ordnungsruf'): ('conditional_warning', None),
    (43, 'herrn frohnmaier erteile ich einen ordnungsruf'): ('named_hint','Frohnmaier'),
    (43, 'ich müsste ihnen theoretisch einen ordnungsruf erteilen'): ('conditional_warning', None),
    (50, 'ich erteile dem bundestagsabgeordneten martin reichardt einen ordnungsruf'): ('named_hint','Reichardt'),
    (74, 'muss ich ihnen dafür jetzt einen ordnungsruf erteilen'): ('conditional_warning', None),
    (75, 'da ich es nicht zuordnen kann, kann ich keinen ordnungsruf erteilen'): ('conditional_warning', None),
    (82, 'ob sie dafür auch schon einen ordnungsruf'): ('conditional_warning', None),
    (52, 'kollegin inkompetenz'): ('false_victim', None),
    (53, 'möchte ich der abgeordneten reichinnek'): ('named_hint', 'Reichinnek'),
    (61, 'für das lachen können sie gleich'): ('conditional_warning', None),
    (65, 'das belege ich jetzt hiermit mit einem ordnungsruf'): ('named_hint', 'Pantisano'),
    # Deliberate independently surfaced *conflict*: 21/067 names Gebel
    # as the offended colleague. Only a separate actual issuing clause can
    # prove a grant to her; this paragraph must never propose her.
    (67, 'dass sie der kollegin gebel'): ('false_victim', 'Gebel'),
    (67, 'für die bemerkung, der kanzler würde rassistischen dreck'):
        ('linked_hint','Gebel'),
    (68, 'möchte ich der abgeordneten dr. paula piechotta'): ('named_hint','Piechotta'),
    (71, 'erteile ich ihnen, herr jünger'): ('named_hint','Jünger'),
    (77, 'und für dieses persönliche bekommen sie jetzt von mir einen ordnungsruf'): ('linked_hint','Reichardt'),
    (77, 'der ordnungsruf von mir vorhin an herrn reichardt gegangen ist'): ('retrospective_only',None),
    (90, 'deshalb erteile ich ihnen hierfür einen ordnungsruf'): ('linked_hint','Sichert'),
    (94, 'so, bitte schön, dann haben sie jetzt ihren ordnungsruf'): ('linked_hint','Köktürk'),
    (94, 'dafür gibt es den nächsten ordnungsruf'): ('linked_hint','Köktürk'),
    (94, 'zwei ordnungsrufe an frau köktürk gegangen'): ('retrospective_only',None),
    (94, 'die abgeordnete köktürk hat heute zwei ordnungsrufe'): ('retrospective_only',None),
}


def run(folder):
    sessions={n for n,_ in SOURCE_FRAGMENTS}
    roots={}
    for n in sorted(sessions):
        path=Path(folder)/f'21{n:03d}.xml'
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'Nicht heruntergeladenes Original-XML: {path}')
        roots[n]=safe_parse(path.read_bytes(),n)
    index=speaker_index(roots.values())
    results={}
    for session,root in roots.items():
        path=Path(folder)/f'21{session:03d}.xml'
        paragraphs=list(iter_session_text(root))
        hints={int(row['line']):row for row in candidates(path,root=root)}
        people_by_line={}
        for row in events(path,index=index,root=root):
            people_by_line.setdefault(int(row['line']),[]).append(row)
        for (n,fragment),(expect,person) in SOURCE_FRAGMENTS.items():
            if n!=session:
                continue
            relevant=[(node,text) for node,text in paragraphs
                      if fragment in text.casefold()]
            if len(relevant)!=1:
                raise ValueError(f'Originalformulierung 21/{n:03d} nicht einzigartig: {fragment!r} '
                                 f'({len(relevant)} Treffer). Keine irreführenden Prüfclaims.')
            node,original=relevant[0]
            line=int(node.sourceline)
            people=people_by_line.get(line,[])
            cls=hints.get(line,{}).get('classification')
            names=[who['person'] for who in people]
            if expect=='false_victim':
                # 21/052 has noun "Inkompetenz" in the offended-colleague
                # slot, 21/067 has a real politician there ("Gebel").
                forbidden=(person or 'Inkompetenz').casefold()
                if any(forbidden in name.casefold() for name in names):
                    raise AssertionError(f'Falsche Person statt Empfänger in 21/{session}: {names}')
                if cls != 'possible_grant':
                    raise AssertionError(f'Erteilungstext in 21/{session} nicht erkannt')
            elif expect=='named_hint':
                if cls != 'possible_grant' or not any(
                        name.casefold().endswith(person.casefold()) for name in names):
                    raise AssertionError(f'Explizite Person als Prüfhinweis fehlt 21/{session}: '
                                         f'{cls=} {names=}')
            elif expect=='full_identity':
                if (cls != 'possible_grant' or len(people)!=1
                        or people[0]['person']!=person
                        or people[0]['identity_status']!='matched_xml_person'
                        or not people[0]['zuordnungsmethode'].startswith(
                            'vollname_vorsitz_einleitung_xmlzeile_')
                        or people[0]['status']!='review_required'):
                    raise AssertionError(f'Nicht eindeutig mit formaler '
                                         f'Original-XML-Einleitung verknüpft '
                                         f'21/{session}: {cls=} {people=}')
            elif expect=='unassigned':
                if cls != 'possible_grant' or people:
                    raise AssertionError(f'Pronomen ohne Namen nicht sicher; 21/{session}: '
                                         f'{cls=} {names=}')
            elif expect=='conditional_warning':
                if cls != 'warning_or_conditional' or people:
                    raise AssertionError(f'Konditionale Drohung statt Erteilung 21/{session}: '
                                         f'{cls=} {names=}')
            elif expect=='linked_hint':
                if (cls != 'possible_grant' or len(people)!=1
                        or not names[0].casefold().endswith(person.casefold())
                        or people[0]['status']!='review_required'
                        or not people[0]['zuordnungsmethode'].startswith(
                          ('namensbestaetigung_xmlzeile_',
                           'vorherige_direkte_anrede_xmlzeile_',
                           'vorsitz_direkte_anrede_xmlzeile_',
                           'vorsitz_redeeinleitung_und_wortlaut_xmlzeile_',
                           'redeblock_sprecher_xmlzeile_',
                           'vorherige_rede_und_einleitung_xmlzeile_',
                           'erstes_ordnungsrufpaar_zweiter_xmlzeile_',
                           'zweites_ordnungsrufpaar_erster_xmlzeile_',
                           'zweiter_ordnungsruf_vorheriger_erteilung_xmlzeile_'))):
                    raise AssertionError(f'Beleggebundener Personen-Prüfhinweis '
                                         f'21/{session} fehlt oder uneindeutig: '
                                         f'{cls=} {names=} {people=}')
            elif expect=='retrospective_only':
                if people:
                    raise AssertionError(f'Historische Bestätigung nicht als zusätzliche Erteilung: '
                                         f'{session=} {names=}')
            results[f'21/{session:03d}: {fragment}'] = {
                'classification':cls,'people_as_unverified_parser_hints':names,
                'status':'checked_against_original_xml_not_effective_sanctions',
            }
    # The conditional laughter threat at line 8717 is not a third
    # sanction. Similarly, 8990 is already a named first grant; 8992 adds
    # only a source-linked review identity to the separate second grant.
    if 40 in roots:
        path=Path(folder)/'21040.xml'
        rows=list(events(path,index=index,root=roots[40]))
        pairs={
            8715:'Martin Sichert',8719:'Martin Sichert',
            8990:'Kay Gottschalk',8992:'Kay Gottschalk',
        }
        for line,who in pairs.items():
            seen=[row for row in rows if int(row['line'])==line]
            if (len(seen)!=1 or seen[0]['person']!=who
                    or seen[0]['status']!='review_required'):
                raise AssertionError(
                    f'Unabhängige 21/040-Erteilungsstellen nicht korrekt '
                    f'getrennt: Zeile {line}, erwartet {who}, gefunden {seen}')
        if any(int(row['line'])==8717 for row in rows):
            raise AssertionError('21/040 bedingte Lachandrohung als Erteilung erfasst')
    if len(results)!=len(SOURCE_FRAGMENTS):
        raise AssertionError('Unvollständige reale XML-Testabdeckung')
    print(f'{len(results)} Original-XML-Paragraf-Regressionskontrollen OK; '
          '0 automatisch bestätigte oder aufgehobene Maßnahmen.')
    return results


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--folder',type=Path,default=Path('.audit/targeted_xml'))
    a=ap.parse_args()
    run(a.folder)


if __name__=='__main__':
    main()
