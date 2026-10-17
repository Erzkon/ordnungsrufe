"""Source-linked *review hypotheses* for 21/077, 21/090 and 21/094.

A later chair's named retrospective statement cannot itself be a new sanction.
Use real XML-paragraph-shaped synthetic fixtures to enforce boundaries,
uniqueness and same-chair evidence independently of the DIP-positive sample.
"""
import unittest
from pathlib import Path
from html import escape
from lxml import etree

from parser import candidates, events, speaker_index


def fixture(rows, people=(), session=94):
    names=''.join(
        f'<redner id="{1000+i}"><name><vorname>{escape(first)}</vorname>'
        f'<nachname>{escape(last)}</nachname>'
        f'<fraktion>Test</fraktion></name></redner>'
        for i,(first,last) in enumerate(people))
    speeches=[]
    for chair,utterances in rows:
        if chair == 'speaker':
            marker='<p klasse="redner">Andere Abgeordnete</p>'
        elif chair.startswith('speaker:'):
            full=chair.partition(':')[2]
            who=[(i,first,last) for i,(first,last) in enumerate(people)
                 if first+' '+last==full]
            if len(who)!=1:
                raise ValueError('Unique fixture speaker is required')
            ix,first,last=who[0]
            marker=(f'<p klasse="redner"><redner id="{1000+ix}">'
                    f'<name><vorname>{escape(first)}</vorname>'
                    f'<nachname>{escape(last)}</nachname></name>'
                    f'</redner></p>')
        else:
            marker=f'<name>{escape(chair)}</name>'
        children='\n'.join(f'<p>{escape(utterance)}</p>' for utterance in utterances)
        speeches.append(f'<rede>\n{marker}\n{children}\n</rede>')
    xml=(f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{session}" '
         f'sitzung-datum="11.09.2026">\n<vorspann>{names}</vorspann>'
         '<sitzungsverlauf><tagesordnungspunkt>\n'
         +'\n'.join(speeches)+
         '</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
    return etree.fromstring(xml.encode())


CHAIR='Vizepräsidentin Andrea Lindholz'
SECOND='Vizepräsidentin Josephine Ortleb'
CHAIR90='Präsidentin Julia Klöckner'
REICHARDT_GRANT='Und für dieses Persönliche bekommen Sie jetzt von mir einen Ordnungsruf.'
REICHARDT_RECAP=('Und fürs Protokoll darf ich noch kurz mitteilen, dass der '
                 'Ordnungsruf von mir vorhin an Herrn Reichardt gegangen ist.')
KOEKTUERK_FIRST='So, bitte schön, dann haben Sie jetzt Ihren Ordnungsruf, und dann ist es jetzt auch gut.'
KOEKTUERK_SECOND='Dafür gibt es den nächsten Ordnungsruf.'
KOEKTUERK_RECAP='Und fürs Protokoll bitte ich zu vermerken, dass zwei Ordnungsrufe an Frau Köktürk gegangen sind.'
SICHERT_GRANT=('Das sind keine Lügner. Das sind keine Abgeordneten, '
               'die eine Mitschuld am Tod von Menschen tragen oder nicht '
               'gewissenhaft abstimmen. Deshalb erteile ich Ihnen hierfür '
               'einen Ordnungsruf.')


def parse(rows,people,session):
    root=fixture(rows,people,session)
    path=Path(f'21{session:03d}.xml')
    idx=speaker_index([root])
    hints=list(candidates(path,root=root))
    found=list(events(path,index=idx,root=root))
    return hints,found


class CrossParagraphReviewLinks(unittest.TestCase):
    def test_reichardt_later_exact_named_confirmation_links_one_original_grant(self):
        hits,found=parse([
            (CHAIR,['Wir bezichtigen uns hier nicht der Lüge.',
                    REICHARDT_GRANT,
                    'Die Debatte wird fortgesetzt.',
                    REICHARDT_RECAP])],
            [('Martin','Reichardt')],77)
        self.assertEqual([x['person'] for x in found],['Martin Reichardt'])
        self.assertEqual(found[0]['text'],REICHARDT_GRANT)
        self.assertTrue(found[0]['zuordnungsmethode'].startswith(
                        'namensbestaetigung_xmlzeile_'))
        self.assertEqual(found[0]['status'],'review_required')
        self.assertNotEqual(int(found[0]['line']),
                            int(found[0]['zuordnungsmethode'].split('_')[-1]))
        self.assertEqual(sum(h['classification']=='possible_grant' for h in hits),1)

    def test_koektuerk_two_independent_grants_are_linked_but_not_confirmed(self):
        hits,found=parse([
            (CHAIR,[KOEKTUERK_FIRST,
                    'Sonst drohe ich Ihnen einen weiteren Ordnungsruf an.',
                    KOEKTUERK_SECOND,
                    KOEKTUERK_RECAP,
                    'Die Abgeordnete Köktürk hat heute zwei Ordnungsrufe von mir erhalten.'])],
            [('Cansin','Köktürk')],94)
        self.assertEqual([x['person'] for x in found],
                         ['Cansin Köktürk','Cansin Köktürk'])
        self.assertEqual(len(set(row['line'] for row in found)),2)
        self.assertTrue(all(x['status']=='review_required' for x in found))
        self.assertEqual(sum(h['classification']=='possible_grant' for h in hits),2)
        self.assertNotIn(KOEKTUERK_RECAP,[x['text'] for x in found])

    def test_sichert_same_presiding_turn_and_named_address(self):
        _,found=parse([
            (CHAIR90,['Herr Sichert, Sie haben die Kollegen persönlich angegriffen.',
                      'Ein zweiter Punkt. Herr Sichert, Sie haben ihnen '
                      'eine Mitschuld am Tod von Personen vorgeworfen.',
                      'Es gehört in einer Demokratie dazu, anderes Abstimmen zu akzeptieren.',
                      SICHERT_GRANT])],
            [('Martin','Sichert')],90)
        self.assertEqual([x['person'] for x in found],['Martin Sichert'])
        self.assertTrue(found[0]['zuordnungsmethode'].startswith(
                        'vorherige_direkte_anrede_xmlzeile_'))
        self.assertEqual(found[0]['text'],SICHERT_GRANT)

    def test_named_recap_other_chair_never_attributes_grant(self):
        _,found=parse([
            (CHAIR,[REICHARDT_GRANT]),
            (SECOND,[REICHARDT_RECAP])],
            [('Martin','Reichardt')],77)
        self.assertEqual(found,[])

    def test_two_grants_cannot_be_arbitrarily_attributed_by_single_confirmation(self):
        _,found=parse([
            (CHAIR,[REICHARDT_GRANT,REICHARDT_GRANT,REICHARDT_RECAP])],
            [('Martin','Reichardt')],77)
        self.assertEqual(found,[])

    def test_one_grant_cannot_satisfy_two_measures_confirmation(self):
        _,found=parse([
            (CHAIR,[KOEKTUERK_FIRST,KOEKTUERK_RECAP])],
            [('Cansin','Köktürk')],94)
        self.assertEqual(found,[])

    def test_named_recaps_do_not_resolve_unknown_or_ambiguous_xml_identity(self):
        _,found=parse([(CHAIR,[REICHARDT_GRANT,REICHARDT_RECAP])],[],77)
        self.assertEqual(found,[])

    def test_recap_before_grant_is_never_backlinked(self):
        _,found=parse([(CHAIR,[REICHARDT_RECAP,REICHARDT_GRANT])],
                      [('Martin','Reichardt')],77)
        self.assertEqual(found,[])

    def test_direct_address_by_another_chair_does_not_resolve_pronoun(self):
        _,found=parse([
            (CHAIR90,['Herr Sichert, Sie wurden angegriffen.']),
            (SECOND,[SICHERT_GRANT])],
            [('Martin','Sichert')],90)
        self.assertEqual(found,[])

    def test_direct_address_interrupted_by_another_speaker_is_not_safe(self):
        _,found=parse([
            (CHAIR90,['Herr Sichert, Sie haben es gesagt.']),
            ('speaker',['Die Abgeordnete ruft dazwischen.']),
            (CHAIR90,[SICHERT_GRANT])],
            [('Martin','Sichert')],90)
        self.assertEqual(found,[])

    def test_multiple_direct_addressees_in_previous_paragraph_stay_unassigned(self):
        _,found=parse([
            (CHAIR90,['Herr Sichert, Sie haben gesprochen. Herr Brandner, '
                      'Sie haben ebenfalls gesprochen.',SICHERT_GRANT])],
            [('Martin','Sichert'),('Stephan','Brandner')],90)
        self.assertEqual(found,[])

    def test_only_hypothetical_grant_after_direct_address_not_linked(self):
        _,found=parse([
            (CHAIR90,['Herr Sichert, Sie müssen vorsichtiger sein.',
                      'Wenn Sie noch einmal stören, erteile ich Ihnen einen Ordnungsruf.'])],
            [('Martin','Sichert')],90)
        self.assertEqual(found,[])

    def test_unrelated_surname_in_text_is_not_identity_evidence(self):
        _,found=parse([
            (CHAIR90,['Für die Debatte hat Herr Sichert einen Antrag gestellt.',
                      SICHERT_GRANT])],
            [('Martin','Sichert')],90)
        self.assertEqual(found,[])

    def test_named_grant_is_not_duplicated_by_retrospective_reference(self):
        _,found=parse([
            (CHAIR,['Herr Reichardt, ich erteile Ihnen einen Ordnungsruf.',
                    REICHARDT_RECAP])],
            [('Martin','Reichardt')],77)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['person'],'Martin Reichardt')
        self.assertNotIn('namensbestaetigung',found[0]['zuordnungsmethode'])

    def test_two_reichardts_prior_full_name_uniquely_disambiguates_recipient(self):
        _,found=parse([
            (CHAIR,['Der erste Redner in dieser Debatte ist Martin Reichardt.',
                    'Herr Reichardt, Sie haben das Wort.',
                    REICHARDT_GRANT,
                    'Der nächste Redner ist Truels Reichardt.',
                    REICHARDT_RECAP])],
            [('Martin','Reichardt'),('Truels','Reichardt')],77)
        self.assertEqual([row['person'] for row in found],['Martin Reichardt'])
        self.assertTrue(found[0]['zuordnungsmethode'].startswith('namensbestaetigung'))

    def test_two_reichardts_both_introduced_before_grant_are_ambiguous(self):
        _,found=parse([
            (CHAIR,['Der Abgeordnete Martin Reichardt spricht.',
                    'Danach spricht der Abgeordnete Truels Reichardt.',
                    REICHARDT_GRANT,REICHARDT_RECAP])],
            [('Martin','Reichardt'),('Truels','Reichardt')],77)
        self.assertEqual(found,[])

    def test_two_reichardts_without_prior_full_name_do_not_choose_one(self):
        _,found=parse([
            (CHAIR,['Herr Reichardt, Sie haben das Wort.',
                    REICHARDT_GRANT,REICHARDT_RECAP])],
            [('Martin','Reichardt'),('Truels','Reichardt')],77)
        self.assertEqual(found,[])


    def test_baumann_immediately_previous_named_chair_address(self):
        _,found=parse([
            (CHAIR,['– Ich leite die Sitzung, Herr Baumann, '
                    'so wie ich die Sitzung leiten möchte. '
                    'Und Sie werden mir nicht vorschreiben, wie ich sie leite.',
                    '– Sie können sich gerne aufregen, Herr Baumann.',
                    'Sie kriegen jetzt von mir einen Ordnungsruf dafür, '
                    'dass Sie meine Sitzungsleitung kritisiert haben.'])],
            [('Bernd','Baumann')],57)
        self.assertEqual([x['person'] for x in found],['Bernd Baumann'])
        self.assertTrue(found[0]['zuordnungsmethode'].startswith(
            'vorsitz_direkte_anrede_xmlzeile_'))

    def test_von_zons_prior_chair_vocative_and_explicit_issuing_verb(self):
        _,found=parse([
            ('Vizepräsident Bodo Ramelow',['Herr von Zons.']),
            ('speaker:Ulrich von Zons',[
                '– und die werden Ihnen das bei den nächsten Wahlen zeigen.',
                'Vielen Dank.']),
            ('Vizepräsident Bodo Ramelow',[
                'Sehr geehrter Herr Abgeordneter, für die Bezeichnung '
                'von Frau Brosius-Gersdorf als Linksextremistin '
                'erteile ich Ihnen einen Ordnungsruf.'])],
            [('Ulrich','von Zons'),('Frauke','Brosius-Gersdorf')],61)
        self.assertEqual([x['person'] for x in found],['Ulrich von Zons'])

    def test_bessin_presiding_address_with_reason_spanning_paragraphs(self):
        _,found=parse([
            ('Vizepräsident Bodo Ramelow',[
                'Sehr geehrte Frau Abgeordnete Bessin, für die Formulierung, '
                'dass Sie eine ganze Jugendorganisation, in der es einen '
                'inakzeptablen Vorfall gegeben hat,',
                'der aber zur Aufklärung gebracht worden ist, pauschal '
                'als sozialistische Pornoorganisation bezeichnet haben,',
                'dafür erteile ich Ihnen einen Ordnungsruf.'])],
            [('Birgit','Bessin')],93)
        self.assertEqual([x['person'] for x in found],['Birgit Bessin'])

    def test_eddis_requires_full_original_interruption_and_one_intro(self):
        _,found=parse([
            (SECOND,['Für die Fraktion Die Linke hat jetzt das Wort '
                     'der Abgeordnete Mirze Edis.']),
            ('speaker:Mirze Edis',[
                'Nein. Meine Mutter hat mir verboten, mit Faschisten zu reden.']),
            (SECOND,['Herr Kollege, ich bitte Sie um etwas Mäßigung. '
                     'Dafür muss ich Ihnen einen Ordnungsruf erteilen: '
                     'für die Bezeichnung „Faschisten“ gegenüber der AfD-Fraktion.'])],
            [('Mirze','Edis')],71)
        self.assertEqual([x['person'] for x in found],['Mirze Edis'])
        self.assertTrue(found[0]['zuordnungsmethode'].startswith(
            'vorsitz_redeeinleitung_und_wortlaut_xmlzeile_'))

    def test_quoted_interruption_not_enough_without_unique_intro(self):
        _,found=parse([
            (SECOND,[
                'Nein. Meine Mutter hat mir verboten, mit Faschisten zu reden.',
                'Dafür muss ich Ihnen einen Ordnungsruf erteilen: '
                'für die Bezeichnung „Faschisten“ gegenüber der AfD-Fraktion.'])],
            [('Mirze','Edis')],71)
        self.assertEqual(found,[])

    def test_sanctioned_person_not_insulted_victim(self):
        _,found=parse([
            (CHAIR,[
                'Frau Kollegin, dafür, dass Sie der Kollegin Gebel '
                '„pathologischen Männerhass“ vorgeworfen haben, '
                'erhalten Sie jetzt von mir einen Ordnungsruf.'])],
            [('Kathrin','Gebel'),('Kerstin','Przygodda')],67)
        self.assertEqual(found,[])

    def test_named_mp_in_report_is_not_a_direct_chair_vocative(self):
        _,found=parse([
            (CHAIR,[
                'In der Sitzung sagte der Abgeordnete Martin Hess, '
                'die Kollegin sei inkompetent.',
                'Herr Kollege, dafür, dass Sie der Kollegin Inkompetenz '
                'vorgeworfen haben, erteile ich Ihnen hiermit '
                'einen Ordnungsruf.'])],
            [('Martin','Hess')],52)
        self.assertEqual(found,[])

    def test_direct_vocative_wrong_presiding_person_cannot_link(self):
        _,found=parse([
            (CHAIR,['Sie können sich gerne aufregen, Herr Baumann.']),
            (SECOND,['Sie kriegen jetzt von mir einen Ordnungsruf.'])],
            [('Bernd','Baumann')],57)
        self.assertEqual(found,[])

    def test_prior_chair_name_only_without_direct_address_cannot_link(self):
        _,found=parse([
            (CHAIR,['Für die AfD-Fraktion hat jetzt Herr Baumann das Wort.',
                    'Sie kriegen jetzt von mir einen Ordnungsruf.'])],
            [('Bernd','Baumann')],57)
        self.assertEqual(found,[])

    def test_two_vocatives_in_prior_paragraph_cannot_assume_recipient(self):
        _,found=parse([
            (CHAIR,['Herr Baumann, Sie sind jetzt dran; Herr Hess, '
                    'Sie auch.',
                    'Sie kriegen jetzt von mir einen Ordnungsruf.'])],
            [('Bernd','Baumann'),('Martin','Hess')],57)
        self.assertEqual(found,[])

    def test_21067_gebel_is_real_second_sanction_not_earlier_victim(self):
        _,found=parse([
            (CHAIR,['Die nächste Rednerin in dieser Debatte ist Kathrin Gebel '
                    'für die Fraktion Die Linke.']),
            ('speaker:Kathrin Gebel',[
                '– doch, wirklich –: In der Befragung der Bundesregierung '
                'gerade eben gibt der Kanzler hier rassistischen Dreck von sich',
                'und missbraucht allen Ernstes dieses Thema.']),
            (CHAIR,['Frau Kollegin, für die Bemerkung, der Kanzler würde '
                    'rassistischen Dreck von sich geben – was wirklich '
                    'unglaublich ist –, bekommen Sie jetzt von mir einen Ordnungsruf.'])],
            [('Kathrin','Gebel'),('Kerstin','Przygodda')],67)
        self.assertEqual([x['person'] for x in found],['Kathrin Gebel'])
        self.assertEqual(found[0]['status'],'review_required')
        self.assertTrue(found[0]['zuordnungsmethode'].startswith(
            'vorsitz_redeeinleitung_und_wortlaut_xmlzeile_'))

    def test_21067_reported_wuerde_without_actual_grant_stays_non_sanction(self):
        from parser import classify
        self.assertNotEqual(
            classify('Wenn der Kanzler rassistischen Dreck von sich geben '
                     'würde, müsste ich Ihnen dafür einen Ordnungsruf erteilen.'),
            'possible_grant')

    def test_21067_offence_without_previous_speaker_quote_not_linked(self):
        _,found=parse([
            (CHAIR,[
                'Die nächste Rednerin in dieser Debatte ist Kathrin Gebel '
                'für die Fraktion Die Linke.',
                'Die betroffene Person fordert besondere Schutzmaßnahmen.',
                'Frau Kollegin, für die Bemerkung, der Kanzler würde '
                'rassistischen Dreck von sich geben – was wirklich '
                'unglaublich ist –, bekommen Sie jetzt von mir einen Ordnungsruf.'])],
            [('Kathrin','Gebel')],67)
        self.assertEqual(found,[])


    def test_21067_quote_by_other_xml_speaker_cannot_attribute_to_gebel(self):
        _,found=parse([
            (CHAIR,['Die nächste Rednerin in dieser Debatte ist Kathrin Gebel '
                    'für die Fraktion Die Linke.']),
            ('speaker:Kerstin Przygodda',[
                'Der Kanzler gibt rassistischen Dreck von sich.']),
            (CHAIR,['Frau Kollegin, für die Bemerkung, der Kanzler würde '
                    'rassistischen Dreck von sich geben – was wirklich '
                    'unglaublich ist –, bekommen Sie jetzt von mir einen Ordnungsruf.'])],
            [('Kathrin','Gebel'),('Kerstin','Przygodda')],67)
        self.assertEqual(found,[])


    def test_21061_intervening_speech_of_other_mp_does_not_link(self):
        _,found=parse([
            ('Vizepräsident Bodo Ramelow',['Herr von Zons.']),
            ('speaker:Other Person',['Ich halte diesen Vorschlag für falsch.']),
            ('Vizepräsident Bodo Ramelow',[
                'Sehr geehrter Herr Abgeordneter, '
                'für diese persönliche Bezeichnung erteile ich Ihnen '
                'einen Ordnungsruf.'])],
            [('Ulrich','von Zons'),('Other','Person')],61)
        self.assertEqual(found,[])



if __name__=='__main__':
    unittest.main()
