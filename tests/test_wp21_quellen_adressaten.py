"""Original utterance -> exact redner-ID -> chair recipient hints, never counts."""
import unittest
from html import escape
from pathlib import Path
from lxml import etree

from parser import events,speaker_index,classify

CHAIR='Vizepräsidentin Andrea Lindholz'
OTHER='Vizepräsidentin Josephine Ortleb'
GRANT_14=('– Herr Kollege, dann muss ich Ihnen leider einen Ordnungsruf '
          'erteilen dafür, dass Sie die Rednerin als „Schwätzer“ '
          'bezeichnet haben.')
GRANT_37=('Herr Kollege, ich erteile Ihnen hiermit einen Ordnungsruf '
          'für die Verwendung „braunes Gelaber“.')
GRANT_39=('Frau Kollegin, kommen Sie jetzt bitte zu Ihrer Frage. '
          '– Im Übrigen erteile ich Ihnen einen Ordnungsruf dafür, '
          'dass Sie den Kollegen der Lüge bezichtigen, und zwar direkt '
          'und persönlich.')
COMMENT_14='(Martin Reichardt [AfD]: Schwätzer!)'


def fixture(session,who,remarks,grant,comment=None,
            chair=CHAIR,other_speaker=None,same_rede=False):
    first,last=who.split(' ',1)
    main=('<rede>\n<p klasse="redner"><redner id="11005554">'
          '<name><vorname>'+escape(first)+'</vorname>'
          '<nachname>'+escape(last)+'</nachname></name>'
          '</redner></p>\n'+
          '\n'.join('<p>'+escape(t)+'</p>' for t in remarks)+'\n')
    if same_rede:
        main+='<name>'+escape(chair)+'</name>\n'
        if comment is not None:
            main+='<kommentar>'+escape(comment)+'</kommentar>\n'
        main+='<p>'+escape(grant)+'</p>\n</rede>'
    else:
        main+='</rede>\n'
        if other_speaker:
            a,b=other_speaker.split(' ',1)
            main+=('<rede>\n<p klasse="redner"><redner id="11005555">'
                   '<name><vorname>'+escape(a)+'</vorname>'
                   '<nachname>'+escape(b)+'</nachname></name>'
                   '</redner></p><p>Ich halte das für falsch.</p></rede>\n')
        main+='<rede>\n<name>'+escape(chair)+'</name>\n'
        if comment is not None:
            main+='<kommentar>'+escape(comment)+'</kommentar>\n'
        main+='<p>'+escape(grant)+'</p>\n</rede>'
    root=etree.fromstring((
        f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{session}">'
        '<sitzungsverlauf><tagesordnungspunkt>\n'+main+
        '\n</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>'
    ).encode())
    return list(events(Path(f'21{session:03d}.xml'),
                       root=root,index=speaker_index([root])))


class OriginalSourceRecipientSafeguards(unittest.TestCase):
    def test_14_named_reichardt_interjection_is_review_hint(self):
        found=fixture(14,'Martin Reichardt',[
            'Sie unterstützen diese Menschen als nützliche Trottel.',
            'Sie sollen mehr miteinander sprechen.',
        ],GRANT_14,COMMENT_14)
        self.assertEqual([x['person'] for x in found],['Martin Reichardt'])
        self.assertTrue(found[0]['zuordnungsmethode'].startswith(
            'namenszwischenruf_schwaetzer_xmlzeile_'))
        self.assertEqual(found[0]['status'],'review_required')

    def test_14_quoted_offence_without_personal_xml_comment_not_enough(self):
        found=fixture(14,'Martin Reichardt',[
            'Nützliche Trottel, das ist Ihre Politik.',
        ],GRANT_14)
        self.assertEqual(found,[])

    def test_14_different_named_interjector_not_borrowed_from_reichardt(self):
        found=fixture(14,'Martin Reichardt',[
            'Nützliche Trottel, das ist Ihre Politik.'
        ],GRANT_14,'(Steffen Janich [AfD]: Schwätzer!)')
        self.assertEqual(found,[])

    def test_14_no_original_reichardt_speech_no_link(self):
        found=fixture(14,'Steffen Janich',[
            'Ich unterstütze diese Vorgehensweise nicht.'
        ],GRANT_14,COMMENT_14)
        self.assertEqual(found,[])

    def test_14_wrong_chair_no_link(self):
        self.assertEqual(fixture(14,'Martin Reichardt',[
            'Eine kurze Erwiderung.'
        ],GRANT_14,COMMENT_14,chair=OTHER),[])

    def test_37_prior_actual_original_words_with_xml_speaker_id(self):
        found=fixture(37,'Ates Gürpinar',[
            'Migration, um weiterhin gut Geld zu verdienen und '
            'braunes Zeug zu labern.',
            'Schönen Tag.'
        ],GRANT_37)
        self.assertEqual([x['person'] for x in found],['Ates Gürpinar'])
        self.assertTrue(found[0]['zuordnungsmethode'].startswith(
            'wortgleiche_rede_und_anrede_xmlzeile_'))
        self.assertEqual(found[0]['status'],'review_required')

    def test_37_last_speaker_not_author_of_offence_fails(self):
        found=fixture(37,'Steffen Janich',[
            'Migration, um weiterhin gut Geld zu verdienen und '
            'braunes Zeug zu labern.'
        ],GRANT_37)
        self.assertEqual(found,[])

    def test_37_no_original_offence_is_not_direct_speaker_evidence(self):
        found=fixture(37,'Ates Gürpinar',[
            'Wir sollten miteinander friedlich diskutieren.'
        ],GRANT_37)
        self.assertEqual(found,[])

    def test_37_new_other_speaker_turn_destroys_unique_reference(self):
        found=fixture(37,'Ates Gürpinar',[
            'Migration, um weiterhin gut Geld zu verdienen und '
            'braunes Zeug zu labern.'
        ],GRANT_37,other_speaker='Steffen Janich')
        self.assertEqual(found,[])

    def test_39_direct_question_original_lie_allegation_xml_id(self):
        found=fixture(39,'Anna Rathert',[
            'Ich habe erlebt, wie Sie Lügen über uns auskippen, '
            'wenn offizielle Gäste zu Gast sind.',
            'Aber was Sie sagen, sind ausgedachte Vorwürfe.'
        ],GRANT_39)
        self.assertEqual([x['person'] for x in found],['Anna Rathert'])
        self.assertTrue(found[0]['zuordnungsmethode'].startswith(
            'wortgleiche_rede_und_anrede_xmlzeile_'))
        self.assertEqual(found[0]['status'],'review_required')

    def test_39_chair_criticism_not_from_target_person_rejected(self):
        found=fixture(39,'Ates Gürpinar',[
            'Ich habe erlebt, wie Sie Lügen über uns auskippen.'
        ],GRANT_39)
        self.assertEqual(found,[])

    def test_39_question_without_verbatim_offence_not_enough(self):
        found=fixture(39,'Anna Rathert',[
            'Ich möchte noch eine Zwischenfrage stellen.'
        ],GRANT_39)
        self.assertEqual(found,[])

    def test_different_session_with_same_phrases_not_automatically_linked(self):
        found=fixture(38,'Ates Gürpinar',[
            'Migration, um weiterhin gut Geld zu verdienen und '
            'braunes Zeug zu labern.'
        ],GRANT_37)
        self.assertEqual(found,[])

    def test_named_original_spoken_in_same_rede_as_chair_not_safe(self):
        found=fixture(39,'Anna Rathert',[
            'Ich habe erlebt, wie Sie Lügen über uns auskippen.'
        ],GRANT_39,same_rede=True)
        self.assertEqual(found,[])

    def test_hypothetical_rebuke_never_a_grant(self):
        statement=('Frau Kollegin, wenn Sie den Kollegen der Lüge '
                   'bezichtigen würden, könnte ich Ihnen '
                   'einen Ordnungsruf erteilen.')
        self.assertNotEqual(classify(statement),'possible_grant')


if __name__=='__main__':
    unittest.main()
