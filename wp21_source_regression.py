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
    (57, 'sie kriegen jetzt von mir einen ordnungsruf dafür'): ('unassigned', None),
    (61, 'für das lachen können sie gleich'): ('conditional_warning', None),
    (65, 'das belege ich jetzt hiermit mit einem ordnungsruf'): ('named_hint', 'Pantisano'),
    (67, 'dass sie der kollegin gebel'): ('false_victim', 'Gebel'),
    (68, 'möchte ich der abgeordneten dr. paula piechotta'): ('named_hint','Piechotta'),
    (71, 'erteile ich ihnen, herr jünger'): ('named_hint','Jünger'),
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
            elif expect=='unassigned':
                if cls != 'possible_grant' or people:
                    raise AssertionError(f'Pronomen ohne Namen nicht sicher; 21/{session}: '
                                         f'{cls=} {names=}')
            elif expect=='conditional_warning':
                if cls != 'warning_or_conditional' or people:
                    raise AssertionError(f'Konditionale Drohung statt Erteilung 21/{session}: '
                                         f'{cls=} {names=}')
            elif expect=='retrospective_only':
                if people:
                    raise AssertionError(f'Historische Bestätigung nicht als zusätzliche Erteilung: '
                                         f'{session=} {names=}')
            results[f'21/{session:03d}: {fragment}'] = {
                'classification':cls,'people_as_unverified_parser_hints':names,
                'status':'checked_against_original_xml_not_effective_sanctions',
            }
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
