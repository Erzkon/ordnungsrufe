"""Guard first/second WP21/040 paired grants without confirming legal effects."""
import unittest
from html import escape
from pathlib import Path

from lxml import etree
from parser import candidates,events,speaker_index

CHAIR='Vizepräsidentin Andrea Lindholz'
OTHER='Vizepräsident Omid Nouripour'

S_FIRST=('Herr Kollege, ich habe es gestern auch schon mal gesagt, '
         'und ich sage es Ihnen jetzt auch: Ich erteile Ihnen jetzt '
         'einen Ordnungsruf, weil Sie mit dem Finger auf Kollegen '
         'gezeigt haben; das ist unparlamentarisch.')
S_WARNING=('– Und wenn Sie lachen – und ich weiß, wer gelacht hat –, '
           'erteile ich Ihnen gleich fürs Lachen den nächsten Ordnungsruf.')
S_SECOND=('– Ich erteile Ihnen auch für den Widerspruch gerade einen '
          'zweiten Ordnungsruf; das kann ich.')
JANICH_INTERJECTION=(
    '(Beifall des Abg. Luigi Pantisano [Die Linke] – '
    'Steffen Janich [AfD]: Also fürs Lachen einen Ordnungsruf! Danke!)')
G_FIRST=('Herr Kollege Gottschalk, ich erteile Ihnen jetzt einen '
         'Ordnungsruf für die Verwendung des Wortes „pfui“.')
G_SECOND=('Denn das ist unparlamentarisches Verhalten. Und ich erteile '
          'Ihnen einen zweiten Ordnungsruf dafür, dass Sie vorhin eine '
          'Gleichsetzung mit dem Nationalsozialismus vorgenommen haben.')


def build(speeches):
    """Independent XML redner IDs plus inline presiding interjections."""
    rede=[]
    for ident,first,last,segments in speeches:
        parts=[f'<p klasse="redner"><redner id="{ident}"><name>'
               f'<vorname>{escape(first)}</vorname>'
               f'<nachname>{escape(last)}</nachname>'
               '</name></redner></p>']
        for who,spoken in segments:
            if who == 'comment':
                parts.append('<kommentar>'+escape(spoken)+'</kommentar>')
                continue
            if who == 'speaker_switch':
                parts.append('<p klasse="redner"><redner id="9999999">'
                             '<name><vorname>Andere</vorname>'
                             '<nachname>Person</nachname></name>'
                             '</redner></p>')
                parts.append('<p>'+escape(spoken)+'</p>')
                continue
            if who is not None:
                parts.append('<name>'+escape(who)+'</name>')
            parts.append('<p>'+escape(spoken)+'</p>')
        rede.append('<rede>\n'+'\n'.join(parts)+'\n</rede>')
    janich=('<vorsprann><redner id="11009991"><name>'
            '<vorname>Steffen</vorname><nachname>Janich</nachname>'
            '</name></redner></vorsprann>')
    xml=('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="40" '
         'sitzung-datum="15.10.2026">'+janich+'<sitzungsverlauf>'
         '<tagesordnungspunkt>\n'+'\n'.join(rede)+
         '\n</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
    root=etree.fromstring(xml.encode())
    index=speaker_index([root])
    return root,index


def analyze(speeches):
    root,index=build(speeches)
    path=Path('21040.xml')
    return list(events(path,root=root,index=index)),list(candidates(path,root=root))


class SeparateOriginalMeasuresTests(unittest.TestCase):
    def test_sichert_first_and_janich_second_are_distinct_recipients(self):
        result,hints=analyze([('11004892','Martin','Sichert',[
            (None,'Sie sollten sich schämen für Ihre Heuchelei!'),
            (CHAIR,S_FIRST),(CHAIR,S_WARNING),
            ('comment',JANICH_INTERJECTION),(CHAIR,S_SECOND),
            (None,'Wir brauchen eine klare Anwendung des Rechts.')
        ])])
        self.assertEqual([x['person'] for x in result],
                         ['Martin Sichert','Steffen Janich'])
        self.assertEqual(len({x['line'] for x in result}),2)
        self.assertTrue(all(x['status']=='review_required' for x in result))
        self.assertTrue(result[0]['zuordnungsmethode'].startswith(
            'erstes_erteilungswort_redner_sichert_xmlzeile_'))
        self.assertTrue(result[1]['zuordnungsmethode'].startswith(
            'zweitvergabe_zu_benanntem_zwischenruf_xmlzeile_'))
        self.assertFalse(any(x['text']==S_WARNING for x in result))
        self.assertEqual(sum(x['classification']=='possible_grant'
                             for x in hints),2)

    def test_gottschalk_first_named_then_second_is_one_new_hint(self):
        result,_=analyze([('11005753','Kay','Gottschalk',[
            (None,'Gegen diese Politik protestiere ich.'),
            (CHAIR,G_FIRST),(CHAIR,G_SECOND),
            (None,'Das nehme ich zur Kenntnis.')
        ])])
        self.assertEqual([x['person'] for x in result],
                         ['Kay Gottschalk','Kay Gottschalk'])
        self.assertEqual(len({x['line'] for x in result}),2)
        self.assertNotIn('zweiter_ordnungsruf_',result[0]['zuordnungsmethode'])
        self.assertTrue(result[1]['zuordnungsmethode'].startswith(
            'zweiter_ordnungsruf_vorheriger_erteilung_xmlzeile_'))
        self.assertEqual(result[1]['text'],G_SECOND)

    def test_two_grant_contexts_have_three_different_recipient_names(self):
        result,_=analyze([
            ('11004892','Martin','Sichert',[
                (CHAIR,S_FIRST),('comment',JANICH_INTERJECTION),
                (CHAIR,S_SECOND)]),
            ('11005753','Kay','Gottschalk',[(CHAIR,G_FIRST),(CHAIR,G_SECOND)])])
        self.assertEqual(len(result),4)
        self.assertEqual([x['person'] for x in sorted(result,key=lambda e:int(e['line']))],
                         ['Martin Sichert','Steffen Janich',
                          'Kay Gottschalk','Kay Gottschalk'])

    def test_second_without_first_does_not_infer_person(self):
        result,_=analyze([('11004892','Martin','Sichert',[(CHAIR,S_SECOND)])])
        self.assertEqual(result,[])

    def test_separate_rede_speaker_context_does_not_borrow_old_first(self):
        result,_=analyze([
            ('11004892','Martin','Sichert',[(CHAIR,S_FIRST)]),
            ('11005753','Kay','Gottschalk',[(CHAIR,S_SECOND)])])
        self.assertEqual(result,[])

    def test_two_different_chairs_do_not_make_a_pair(self):
        result,_=analyze([('11004892','Martin','Sichert',[
            (CHAIR,S_FIRST),(OTHER,S_SECOND)
        ])])
        self.assertEqual(result,[])

    def test_intervening_new_speech_marker_not_safely_same_addressee(self):
        result,_=analyze([('11004892','Martin','Sichert',[
            (CHAIR,S_FIRST),
            ('speaker_switch','Ich widerspreche dieser Sichtweise.'),
            (CHAIR,S_SECOND)
        ])])
        self.assertEqual(result,[])

    def test_conditional_next_sanction_is_not_second_granted_sanction(self):
        result,_=analyze([('11004892','Martin','Sichert',[
            (CHAIR,S_FIRST),(CHAIR,S_WARNING)
        ])])
        self.assertEqual(result,[])

    def test_retro_reference_to_second_not_a_new_issuing_event(self):
        result,_=analyze([('11004892','Martin','Sichert',[
            (CHAIR,'Der zweite Ordnungsruf ist schon erteilt worden.')
        ])])
        self.assertEqual(result,[])

    def test_no_pair_if_competing_third_issuing_statement_intervenes(self):
        result,_=analyze([('11004892','Martin','Sichert',[
            (CHAIR,S_FIRST),
            (CHAIR,'Ich erteile Ihnen einen weiteren Ordnungsruf.'),
            (CHAIR,S_SECOND)
        ])])
        self.assertEqual(result,[])

    def test_first_named_for_different_speaker_not_inherited(self):
        result,_=analyze([('11004892','Martin','Sichert',[
            (CHAIR,G_FIRST),(CHAIR,G_SECOND)
        ])])
        # Never assign Gottschalk's explicit first issuance to Sichert,
        # even though Sichert is the XML speech owner.
        self.assertFalse(any(x['person']=='Martin Sichert' for x in result))

    def test_repeated_phrase_not_second_without_explicit_ordinal(self):
        result,_=analyze([('11005753','Kay','Gottschalk',[
            (CHAIR,G_FIRST),
            (CHAIR,'Und dafür erteile ich Ihnen einen Ordnungsruf.')
        ])])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['person'],'Kay Gottschalk')

    def test_sichert_speech_block_without_named_janich_interjection_is_not_enough(self):
        result,_=analyze([('11004892','Martin','Sichert',[
            (CHAIR,S_FIRST),(CHAIR,S_WARNING),(CHAIR,S_SECOND)])])
        self.assertEqual(result,[])

    def test_applause_only_pantisano_does_not_steal_recipient(self):
        result,_=analyze([('11004892','Martin','Sichert',[
            (CHAIR,S_FIRST),
            ('comment','(Beifall des Abg. Luigi Pantisano [Die Linke])'),
            (CHAIR,S_SECOND)])])
        self.assertEqual(result,[])

    def test_janich_name_without_explicit_interjection_does_not_link_second(self):
        result,_=analyze([('11004892','Martin','Sichert',[
            (CHAIR,S_FIRST),
            ('comment','(Zuruf des Abg. Steffen Janich [AfD])'),
            (CHAIR,S_SECOND)])])
        self.assertEqual(result,[])

    def test_janich_interjection_not_same_as_explicit_first_for_sichert(self):
        result,_=analyze([('11004892','Martin','Sichert',[
            (CHAIR,S_FIRST),('comment',JANICH_INTERJECTION),(CHAIR,S_SECOND)])])
        self.assertEqual([x['person'] for x in sorted(result,key=lambda r:r['line'])],
                         ['Martin Sichert','Steffen Janich'])
        self.assertEqual(len({x['line'] for x in result}),2)


if __name__=='__main__':
    unittest.main()
