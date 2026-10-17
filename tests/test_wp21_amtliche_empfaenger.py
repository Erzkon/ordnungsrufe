"""Exact-location official Bundestag chair/DIP recipient evidence tests.

Critical guard: Steffen Janich 21/026 is NOT the enclosing speaker
Tobias Ebenberger. 21/043 "zweiter Ordnungsruf" in the retro statement
means the chair's second immediate grant (to Keuter), not the later
explicitly second Keuter sanction. DIP assigns 3497 to Erhard Brucker.
"""
from html import escape
from pathlib import Path
import unittest

from lxml import etree
from parser import events,speaker_index

from wp21_amtliche_empfaenger import (
    official_source_recipient_links, DIP_BRUCKER,
)

CHAIR26='Vizepräsidentin Andrea Lindholz:'
CHAIR43='Vizepräsident Omid Nouripour:'
JANICH_RETRO=('Fürs Protokoll: Der Ordnungsruf ging an Herrn Steffen Janich '
              'wegen der Kommentierung der Sitzungsleitung.')
KEUTER_RETRO=('Vielen Dank. – Für das Protokoll noch mal präzisiert: '
              'Der zweite Ordnungsruf, den ich erteilt habe, ging an '
              'den Abgeordneten Keuter, weil Kritik am Vorsitz '
              'durchaus erlaubt ist, allerdings im Ältestenrat.')
KEUTER_COMMENT=('(Stefan Keuter [AfD]: Kurzintervention! – '
                'Beatrix von Storch [AfD]: Kurzintervention!)')
DIP_COMMENT=('(Lachen bei Abgeordneten der AfD)')
BRUCKER_GRANT=('– Auch Ihnen erteile ich einen Ordnungsruf; '
               'Namen rufe ich gleich aus.')
KEUTER_GRANT=('– Auch Sie kriegen einen Ordnungsruf, weil Sie anscheinend '
              'nicht verstanden haben, dass diese Debatte in den '
              'Ältestenrat gehört. Herzlichen Dank dafür!')


def p(t):
    return '<p>'+escape(t)+'</p>'


def name(t):
    return '<name>'+escape(t)+'</name>'


def comment(t):
    return '<kommentar>'+escape(t)+'</kommentar>'


def make_xml(session,positions,identities=True):
    # Empty lines are intentional: they reproduce the exact source-line
    # invariants of the independently checked original XML transcript.
    people=(('11001011','Steffen','Janich'),
            ('11001012','Stefan','Keuter'),
            ('11001013','Erhard','Brucker'),
            ('11001014','Tobias','Ebenberger'),
            ('11001015','Martin','Reichardt'))
    catalog=''.join(
        '<redner id="'+ident+'"><name><vorname>'+first+
        '</vorname><nachname>'+last+'</nachname></name></redner>'
        for ident,first,last in (people if identities else ())
    )
    lines=[f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{session}">'
           f'<vorsprann>{catalog}</vorsprann><sitzungsverlauf>'
           '<tagesordnungspunkt><rede>']
    for line,markup in sorted(positions):
        if line<=len(lines):
            raise ValueError('Invalid fixture line ordering')
        lines.extend(['']*(line-len(lines)-1))
        lines.append(markup)
    lines.append('</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
    root=etree.fromstring(('\n'.join(lines)).encode())
    return root


def case26(changes=None,identities=True):
    rows={
        3433:p('Gut. Vielen lieben Dank.'),
        3434:comment('(Lachen bei Abgeordneten der SPD – Zuruf von der AfD)'),
        3435:name(CHAIR26),
        3436:p('Herr Kollege, dafür erteile ich Ihnen einen Ordnungsruf.'),
        3540:name(CHAIR26),
        3541:p(JANICH_RETRO)
    }
    rows.update(changes or {})
    return make_xml(26,list(rows.items()),identities)


def case43(changes=None,identities=True):
    rows={
        2395:name(CHAIR43),
        2396:p('Ich erteile Ihnen hiermit einen Ordnungsruf, Herr Reichardt.'),
        2404:comment(KEUTER_COMMENT),
        2405:p(KEUTER_GRANT),
        2418:p(KEUTER_RETRO),
        3493:p('– Herrn Frohnmaier erteile ich einen Ordnungsruf.'),
        3494:comment('(Lachen des Abg. Stefan Keuter [AfD])'),
        3495:p('– Ihnen erteile ich jetzt den zweiten Ordnungsruf, Herr Keuter.'),
        3496:comment(DIP_COMMENT),
        3497:p(BRUCKER_GRANT)
    }
    rows.update(changes or {})
    return make_xml(43,list(rows.items()),identities)


def check(root,excluded=()):
    from parser import iter_session_text
    return official_source_recipient_links(
        list(iter_session_text(root)),speaker_index([root]),set(excluded))


class OfficialRecipientEvidenceTests(unittest.TestCase):
    def test_26_chair_later_says_janich_not_ebenberger(self):
        result=check(case26())
        self.assertEqual([(el.sourceline,person['person'])
                          for el,person in result],
                         [(3436,'Steffen Janich')])
        self.assertTrue(result[0][1]['zuordnungsmethode'].startswith(
            'namentliche_sitzungsleitungs_klarstellung_xmlzeile_3541'))
        self.assertNotEqual(result[0][1]['person'],'Tobias Ebenberger')
        self.assertNotEqual(result[0][1]['identity_status'],'confirmed_effective')
        self.assertEqual(result[0][1]['person_id'],'11001011')

    def test_26_official_confirmation_even_without_xml_speech_id(self):
        result=check(case26(identities=False))
        self.assertEqual(len(result),1)
        self.assertEqual(result[0][1]['person'],'Steffen Janich')
        self.assertEqual(result[0][1]['person_id'],'')
        self.assertEqual(result[0][1]['identity_status'],
                         'named_official_source_reference')

    def test_26_no_retro_no_guessed_ebenberger(self):
        result=check(case26({3541:p('Wir kommen zum nächsten Tagesordnungspunkt.')}))
        self.assertEqual(result,[])

    def test_26_retro_other_recipient_is_not_silently_accepted(self):
        result=check(case26({3541:p(JANICH_RETRO.replace('Steffen Janich',
                                                        'Tobias Ebenberger'))}))
        self.assertEqual(result,[])

    def test_26_retro_wrong_chair_rejected(self):
        result=check(case26({3540:name(CHAIR43)}))
        self.assertEqual(result,[])

    def test_26_anonymous_comment_not_own_speaker_id(self):
        result=check(case26({3434:comment('(Zuruf von der SPD)')}))
        self.assertEqual(result,[])

    def test_43_two_original_source_recipients_with_distinct_basis(self):
        result=check(case43())
        self.assertEqual([(el.sourceline,person['person'])
                          for el,person in result],
                         [(2405,'Stefan Keuter'),(3497,'Erhard Brucker')])
        self.assertTrue(result[0][1]['zuordnungsmethode'].startswith(
            'zweitgenannte_erteilung_vorsitz_klaerung_xmlzeile_2418'))
        self.assertEqual(result[1][1]['zuordnungsmethode'],
                         'amtliche_dip_person_fundstelle_21_43_5015A')
        self.assertTrue(DIP_BRUCKER.startswith('https://dip.bundestag.de/'))

    def test_43_retro_not_second_sanction_to_reichardt(self):
        result=check(case43())
        self.assertFalse(any(x['person']=='Martin Reichardt' for _,x in result))
        self.assertFalse(any(x['person']=='Stefan Keuter'
                             for e,x in result if e.sourceline==3497))

    def test_43_without_keuter_retrospective_only_brucker(self):
        result=check(case43({2418:p('Wir setzen die Debatte fort.')}))
        self.assertEqual([x['person'] for _,x in result],['Erhard Brucker'])

    def test_43_wrong_retrospective_recipient_fails_closed(self):
        result=check(case43({2418:p(KEUTER_RETRO.replace('Keuter','Reichardt'))}))
        self.assertEqual([x['person'] for _,x in result],['Erhard Brucker'])

    def test_43_no_matching_personal_comment_keuter_unassigned(self):
        result=check(case43({2404:comment('(Lachen bei Abgeordneten der AfD)')}))
        self.assertEqual([x['person'] for _,x in result],['Erhard Brucker'])

    def test_43_brucker_no_named_person_in_official_xml(self):
        result=check(case43(identities=False))
        self.assertEqual([x['person'] for _,x in result],
                         ['Stefan Keuter','Erhard Brucker'])
        self.assertTrue(all(x['person_id']=='' for _,x in result))
        self.assertTrue(all(x['identity_status']=='named_official_source_reference'
                            for _,x in result))

    def test_43_brucker_missing_separate_context_rejected(self):
        result=check(case43({3495:p('Wir machen jetzt weiter.')}))
        self.assertEqual([x['person'] for _,x in result],['Stefan Keuter'])

    def test_43_brucker_unidentified_laugh_not_later_named_person(self):
        result=check(case43({3496:comment('(Zuruf des Abg. Stefan Keuter)')}))
        self.assertEqual([x['person'] for _,x in result],['Stefan Keuter'])

    def test_43_late_brucker_grant_cannot_be_credited_to_keuter(self):
        result=check(case43())
        people={el.sourceline:x['person'] for el,x in result}
        self.assertEqual(people.get(3497),'Erhard Brucker')

    def test_guard_already_assigned_lines_no_duplicate_proposals(self):
        self.assertEqual(check(case43(),excluded=[2405,3497]),[])
        self.assertEqual(check(case26(),excluded=[3436]),[])

    def test_wrong_election_period_no_attribution(self):
        r=case43()
        r.set('wahlperiode','20')
        self.assertEqual(check(r),[])

    def test_independent_source_dossier_preserves_three_review_only_events(self):
        from wp21_offizielle_empfaenger_akte import build
        report=build({26:case26(),43:case43()})
        self.assertEqual(report['protocols_checked'],2)
        self.assertEqual(report['previously_anonymous_locations_linked'],3)
        self.assertEqual(report['official_chair_references'],2)
        self.assertEqual(report['official_dip_person_references'],1)
        self.assertEqual(report['automatically_confirmed_effective_sanctions'],0)
        self.assertEqual(report['automatically_rescinded_sanctions'],0)
        self.assertEqual([(x['session'],x['xml_line'],x['person_review_reference'])
                          for x in report['cases']],
                         [(26,3436,'Steffen Janich'),
                          (43,2405,'Stefan Keuter'),
                          (43,3497,'Erhard Brucker')])
        self.assertEqual([x['independent_recipient_evidence']['type']
                          for x in report['cases']],
                         ['namentliche_nachtraegliche_vorsitz_klarstellung',
                          'namentliche_nachtraegliche_vorsitz_klarstellung',
                          'amtliche_dip_person_originalstelle'])
        self.assertTrue(all(len(x['grant_sha256'])==64 for x in report['cases']))
        self.assertTrue(all(x['unverified_effective_sanction']
                            for x in report['cases']))

    def test_dossier_rejects_later_retro_person_mismatch(self):
        from wp21_offizielle_empfaenger_akte import build
        with self.assertRaisesRegex(ValueError,'Identitätsnachweis'):
            build({26:case26({
                3541:p(JANICH_RETRO.replace('Steffen Janich','Tobias Ebenberger'))}),
                   43:case43()})

    def test_dossier_rejects_missing_official_source_document(self):
        from wp21_offizielle_empfaenger_akte import build
        with self.assertRaisesRegex(ValueError,'exakt beide'):
            build({43:case43()})

    def test_dossier_rejects_source_original_wahlperiode_change(self):
        from wp21_offizielle_empfaenger_akte import build
        wrong=case26()
        wrong.set('wahlperiode','20')
        with self.assertRaisesRegex(ValueError,'andere Wahlperiode'):
            build({26:wrong,43:case43()})


if __name__=='__main__':
    unittest.main()
