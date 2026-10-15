"""Evidence-bounded original-XML speaker chains for WP21 052 / 065 / 067.

These are identity suggestions requiring independent grant/legal review.
The original XML granting paragraph remains the event location, not the
later mention or an extra inferred sanction.
"""
import unittest
from html import escape
from pathlib import Path

from lxml import etree
from parser import events,speaker_index

CHAIR='Vizepräsidentin Andrea Lindholz'
OTHER='Vizepräsidentin Josephine Ortleb'
JULIA='Präsidentin Julia Klöckner'

HESS_GRANT=('Herr Kollege, dafür, dass Sie der Kollegin Inkompetenz und '
            'noch mehr vorgeworfen haben, erteile ich Ihnen hiermit '
            'einen Ordnungsruf. Denn es war ein persönlicher Angriff '
            'direkt auf die Kollegin.')
PRZ_GRANT=('Frau Kollegin, dafür, dass Sie der Kollegin Gebel '
           '„pathologischen Männerhass“ vorgeworfen haben, erhalten '
           'Sie jetzt von mir einen Ordnungsruf.')
PRZ_INTRO=('Die nächste Rednerin in dieser Debatte ist für die '
           'AfD-Fraktion Kerstin Przygodda.')
REI_INTRO=('Nun hat für die AfD der Abgeordnete Herr Martin Reichardt '
           'das Wort. Bitte.')
REI_GRANT=('Jetzt ist gut. Ich mache hier nicht jeden Quatsch mit. '
           'Herr Reichardt, Sie können Ihre Performance gleich '
           'draußen machen. Ich habe Sie jetzt schon drei-, viermal '
           'ermahnt. Jetzt kriegen Sie einen Ordnungsruf von mir. '
           'Vielleicht wollten Sie genau den auch haben.')


def paragraph(text):
    return '<p>'+escape(text)+'</p>'


def chair_block(name,*texts):
    return '<rede><name>'+escape(name)+'</name>'+''.join(map(paragraph,texts))+'</rede>'


def speaker_block(ident,first,last,*texts,interjection=None):
    redner=(f'<p klasse="redner"><redner id="{ident}"><name>'
            f'<vorname>{escape(first)}</vorname>'
            f'<nachname>{escape(last)}</nachname></name></redner></p>')
    body=redner+''.join(map(paragraph,texts))
    if interjection is not None:
        name,text=interjection
        body+='<name>'+escape(name)+'</name>'+paragraph(text)
    return '<rede>'+body+'</rede>'


def xml_events(blocks,other_people=(),session=52):
    # Index speakers appear in original <redner> elements: never infer a
    # real MP's full name solely from an unstructured quoted surname.
    known=''.join(
        f'<redner id="{ident}"><name><vorname>{escape(first)}</vorname>'
        f'<nachname>{escape(last)}</nachname></name></redner>'
        for ident,first,last in other_people)
    root=etree.fromstring((
        f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{session}" '
        f'sitzung-datum="15.10.2026"><vorsprann>{known}</vorsprann>'
        '<sitzungsverlauf><tagesordnungspunkt>'
        +''.join(blocks)+
        '</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>'
    ).encode())
    return list(events(Path(f'21{session:03d}.xml'),
                       index=speaker_index([root]),root=root))


class RemainingIdentityEvidenceTests(unittest.TestCase):
    def test_hess_same_xml_rede_chair_interjection(self):
        rows=xml_events([
            speaker_block('11004749','Martin','Hess',
                          'Das ist hanebüchener Unsinn!',
                          'Sie unterstützen doch die Antifa.',
                          interjection=(CHAIR,HESS_GRANT))
        ],session=52)
        self.assertEqual([x['person'] for x in rows],['Martin Hess'])
        self.assertEqual(rows[0]['identity_status'],'matched_xml_person')
        self.assertTrue(rows[0]['zuordnungsmethode'].startswith(
            'redeblock_sprecher_xmlzeile_'))
        self.assertEqual(rows[0]['text'],HESS_GRANT)
        self.assertEqual(rows[0]['status'],'review_required')

    def test_hess_without_original_speaker_id_stays_unassigned(self):
        rows=xml_events([chair_block(CHAIR,
                        'Die betroffene Kollegin ist verletzt.',HESS_GRANT)],
                        other_people=[('11004749','Martin','Hess')],session=52)
        self.assertEqual(rows,[])

    def test_hess_no_disguised_hypothetical_grant(self):
        from parser import classify
        self.assertNotEqual(classify(
            'Wenn jemand der Kollegin Inkompetenz vorwerfen würde, '
            'könnte ich Ihnen einen Ordnungsruf erteilen.'),'possible_grant')

    def test_przygodda_previous_exact_xml_speaker_and_chair_intro(self):
        rows=xml_events([
            chair_block(CHAIR,PRZ_INTRO),
            speaker_block('11005547','Kerstin','Przygodda',
                          'An Ihren Händen klebt Blut.',
                          'Vielen Dank.'),
            chair_block(CHAIR,PRZ_GRANT)
        ],other_people=[('11200000','Kathrin','Gebel')],session=67)
        self.assertEqual([x['person'] for x in rows],['Kerstin Przygodda'])
        self.assertTrue(rows[0]['zuordnungsmethode'].startswith(
            'vorherige_rede_und_einleitung_xmlzeile_'))
        self.assertNotIn('Gebel',[x['person'] for x in rows])
        self.assertEqual(rows[0]['text'],PRZ_GRANT)

    def test_przygodda_intro_of_different_mp_rejected(self):
        rows=xml_events([
            chair_block(CHAIR,PRZ_INTRO),
            speaker_block('11200000','Kathrin','Gebel',
                          'Ich habe nichts zu diesem Vorwurf gesagt.'),
            chair_block(CHAIR,PRZ_GRANT)
        ],other_people=[('11005547','Kerstin','Przygodda')],session=67)
        self.assertEqual(rows,[])

    def test_przygodda_intro_of_other_chair_rejected(self):
        rows=xml_events([
            chair_block(OTHER,PRZ_INTRO),
            speaker_block('11005547','Kerstin','Przygodda',
                          'Vielen Dank.'),
            chair_block(CHAIR,PRZ_GRANT)
        ],session=67)
        self.assertEqual(rows,[])

    def test_przygodda_chair_interrupts_speaker_before_grant_rejected(self):
        rows=xml_events([
            chair_block(CHAIR,PRZ_INTRO),
            speaker_block('11005547','Kerstin','Przygodda',
                          'Vielen Dank.'),
            chair_block(CHAIR,
                        'Als nächstes kommen wir zum nächsten Thema.',
                        PRZ_GRANT)
        ],session=67)
        self.assertEqual(rows,[])

    def test_reichardt_existing_surname_hint_refined_without_duplication(self):
        rows=xml_events([
            chair_block(JULIA,REI_INTRO),
            speaker_block('11001111','Diana','Herbstreuth',
                          'Sehr geehrte Frau Präsidentin!'),
            chair_block(JULIA,'Ich erteile Ihnen jetzt einen Ordnungsruf.',
                        REI_GRANT)
        ],other_people=[('11006501','Martin','Reichardt'),
                        ('11006502','Truels','Reichardt')],session=65)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['person'],'Martin Reichardt')
        self.assertEqual(rows[0]['text'],REI_GRANT)
        self.assertTrue(rows[0]['zuordnungsmethode'].startswith(
            'vollname_vorsitz_einleitung_xmlzeile_'))

    def test_reichardt_two_competing_formal_intros_stay_ambiguous(self):
        rows=xml_events([
            chair_block(JULIA,REI_INTRO,
                        'Nun hat für die AfD der Abgeordnete Herr '
                        'Truels Reichardt das Wort. Bitte.',
                        REI_GRANT)
        ],other_people=[('11006501','Martin','Reichardt'),
                        ('11006502','Truels','Reichardt')],session=65)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['person'],'Reichardt')
        self.assertNotEqual(rows[0]['identity_status'],'matched_xml_person')

    def test_reichardt_another_chair_intro_stays_ambiguous(self):
        rows=xml_events([
            chair_block(OTHER,REI_INTRO),
            chair_block(JULIA,REI_GRANT)
        ],other_people=[('11006501','Martin','Reichardt'),
                        ('11006502','Truels','Reichardt')],session=65)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['person'],'Reichardt')

    def test_reichardt_no_chair_intro_stays_ambiguous(self):
        rows=xml_events([
            chair_block(JULIA,'Martin Reichardt war bereits Redner.',
                        REI_GRANT)
        ],other_people=[('11006501','Martin','Reichardt'),
                        ('11006502','Truels','Reichardt')],session=65)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['person'],'Reichardt')


if __name__=='__main__':
    unittest.main()
