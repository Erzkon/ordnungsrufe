"""Review-only episode attribution tests on accurately structured XML fragments."""
from html import escape
from pathlib import Path
import unittest
from lxml import etree

from parser import events,iter_session_text,speaker_index
from wp21_episoden import PAIRS,episode_recipient_hints,episode_summary

CHAIR49='Vizepräsident Omid Nouripour:'
CHAIR51='Vizepräsidentin Andrea Lindholz:'
CHAIR65='Präsidentin Julia Klöckner:'
FIRST49=('Vielen Dank. – Bevor wir die Debatte fortsetzen, möchte ich '
         'dem Abgeordneten Stephan Brandner von der AfD einen Ordnungsruf '
         'erteilen für den Zwischenruf „Heul doch!“. '
         'Das ist eine eindeutige Herabsetzung eines Kollegen')
LAST49=('– lustig ist daran überhaupt nichts –, und deshalb bekommen '
        'Sie einen Ordnungsruf.')
FIRST51=('Herr Kollege, warten Sie bitte einen Moment. '
         'Ich erteile einen Ordnungsruf für den Begriff „Lügen-Stegner“, '
         'den Sie, Herr Frohnmaier, gerade verwendet haben.')
LAST51=('– Ich erteile Ihnen dafür einen Ordnungsruf. '
        'Das ist ein persönlicher Angriff gegen Herrn Stegner gewesen.')
FIRST65='Ich erteile Ihnen jetzt einen Ordnungsruf.'
LAST65=('Jetzt ist gut. Ich mache hier nicht jeden Quatsch mit. Herr Reichardt, '
        'Sie können Ihre Performance gleich draußen machen. '
        'Ich habe Sie jetzt schon drei-, viermal ermahnt. '
        'Jetzt kriegen Sie einen Ordnungsruf von mir. '
        'Vielleicht wollten Sie genau den auch haben.')
COMMENTS={
    49:'(Lachen bei der AfD)',
    51:'(Markus Frohnmaier [AfD]: Das war eine Lüge, die er gerade geäußert hat!)',
    65:'(Beifall bei Abgeordneten der CDU/CSU, der SPD, des BÜNDNISSES 90/DIE GRÜNEN und der Linken)',
}
BEFORE65=(
    '(Martin Reichardt [AfD], an die CDU/CSU gewandt: '
    'Im Unterschied zu Ihrer Fraktion habe ich wenigstens Humor! '
    '– Gegenruf von der SPD: Ruhe jetzt!)'
)


def xml_fragment(session,changes=None,include_index=True):
    """Sparse real-source-number lines: exact XML paragraph and comment nodes."""
    pre={
        49:{3277:('name',CHAIR49),3278:('p',FIRST49),
            3279:('kommentar',COMMENTS[49]),3280:('p',LAST49)},
        51:{3978:('name',CHAIR51),3979:('p',FIRST51),
            3980:('kommentar',COMMENTS[51]),3981:('p',LAST51)},
        65:{2042:('kommentar',BEFORE65),2043:('name',CHAIR65),
            2044:('p',FIRST65),2045:('kommentar',COMMENTS[65]),
            2046:('p',LAST65)},
    }[session].copy()
    pre.update(changes or {})
    # Inject XML person records (Thomas Stephan is a trap: he must NOT
    # steal Stephan Brandner's grant merely for sharing "Stephan".)
    people=[
        ('11005585','Thomas','Stephan'),
        ('11004721','Markus','Frohnmaier'),
        ('11004859','Martin','Reichardt'),
    ] if include_index else []
    people_xml=''.join(
        f'<redner id="{ident}"><name><vorname>{first}</vorname>'
        f'<nachname>{last}</nachname></name></redner>'
        for ident,first,last in people
    )
    lines=[
        f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{session}">',
        f'<vorsprann>{people_xml}</vorsprann><sitzungsverlauf>',
        '<tagesordnungspunkt><rede>',
    ]
    for line,(tag,txt) in sorted(pre.items()):
        if line<=len(lines):
            raise ValueError('Overlapping fixture XML line')
        lines+=['']*(line-len(lines)-1)
        lines.append(f'<{tag}>{escape(txt)}</{tag}>')
    lines.append('</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
    return etree.fromstring('\n'.join(lines).encode())


def hints(root):
    idx=speaker_index([root])
    return episode_recipient_hints(list(iter_session_text(root)),idx,set())


def parsed(root,session):
    return list(events(Path(f'21{session:03d}.xml'),
                       root=root,index=speaker_index([root])))


class EpisodeSourceRegression(unittest.TestCase):
    def test_49_brandner_full_name_must_not_be_thomas_stephan(self):
        root=xml_fragment(49)
        items=parsed(root,49)
        self.assertEqual([(x['line'],x['person']) for x in items],
                         [(3278,'Stephan Brandner'),(3280,'Stephan Brandner')])
        self.assertNotIn('Thomas Stephan',[x['person'] for x in items])
        self.assertEqual(items[0]['person_id'],'')
        self.assertEqual(items[0]['identity_status'],
                         'named_official_source_reference')
        self.assertEqual(items[1]['zuordnungsmethode'],
                         'fortsetzung_benannter_erteilungsrede_xmlzeile_3278')
        self.assertTrue(all(x['status']=='review_required' for x in items))

    def test_49_without_index_still_exact_brandner_no_fabricated_id(self):
        rows=parsed(xml_fragment(49,include_index=False),49)
        self.assertEqual([x['person'] for x in rows],
                         ['Stephan Brandner','Stephan Brandner'])
        self.assertTrue(all(x['person_id']=='' for x in rows))

    def test_49_laughter_comment_absent_does_not_link_followup(self):
        root=xml_fragment(49,{3279:('kommentar','(Zuruf des Abg. Thomas Stephan)')})
        rows=parsed(root,49)
        self.assertEqual([(x['line'],x['person']) for x in rows],
                         [(3278,'Stephan Brandner')])

    def test_49_false_named_recipient_in_first_grant_is_not_accepted(self):
        root=xml_fragment(49,{
            3278:('p',FIRST49.replace('Stephan Brandner','Thomas Stephan'))})
        self.assertEqual(hints(root),[])

    def test_51_second_has_named_frohnmaier_interjection_not_victim(self):
        root=xml_fragment(51)
        items=parsed(root,51)
        self.assertEqual([(x['line'],x['person']) for x in items],
                         [(3979,'Markus Frohnmaier'),(3981,'Markus Frohnmaier')])
        self.assertTrue(items[1]['zuordnungsmethode'].startswith(
            'neuer_benannter_zwischenruf_xmlzeile_3980'))
        self.assertNotIn('Ralf Stegner',[x['person'] for x in items])
        self.assertTrue(all(x['status']=='review_required' for x in items))

    def test_51_foreign_interjector_must_not_be_assigned_frohnmaier(self):
        root=xml_fragment(51,{
            3980:('kommentar',COMMENTS[51].replace('Markus Frohnmaier','Steffen Janich'))})
        self.assertEqual(hints(root),[])

    def test_51_remove_original_fresh_offence_no_identity_link(self):
        root=xml_fragment(51,{
            3980:('kommentar','(Beifall bei der AfD)')})
        self.assertEqual(hints(root),[])

    def test_65_first_unnamed_chair_grant_verified_from_next_named_restatement(self):
        root=xml_fragment(65)
        events_=parsed(root,65)
        self.assertEqual([(r['line'],r['person']) for r in events_],
                         [(2046,'Martin Reichardt'),(2044,'Martin Reichardt')])
        self.assertTrue(events_[1]['zuordnungsmethode'].startswith(
            'gleiche_erteilungsepisode_spaetere_anrede_xmlzeile_2046'))
        self.assertNotEqual(events_[1]['person'],'Diana Herbstreuth')

    def test_65_without_named_interjection_never_borrow_next_name(self):
        root=xml_fragment(65,{
            2042:('kommentar','(Beifall bei der CDU/CSU)')})
        self.assertEqual(hints(root),[])

    def test_65_other_politician_in_earlier_comment_no_identity(self):
        root=xml_fragment(65,{
            2042:('kommentar',BEFORE65.replace('Martin Reichardt','Luigi Pantisano'))})
        self.assertEqual(hints(root),[])

    def test_wrong_presiding_chair_all_links_fail(self):
        for session in (49,51,65):
            first=PAIRS[session][0]
            prev_line=first-1
            if session==65:
                prev_line=2043
            root=xml_fragment(session,{
                prev_line:('name','Vizepräsident Bodo Ramelow:')})
            self.assertEqual(hints(root),[],session)

    def test_source_relation_not_legally_counted(self):
        assert episode_summary(49)['source_relation_hypothesis'] == (
            'same_issuance_continuation_possible')
        assert episode_summary(51)['source_relation_hypothesis'] == (
            'additional_issuance_requires_individual_legal_review')
        assert episode_summary(65)['source_relation_hypothesis'] == (
            'same_issuance_repetition_possible')
        self.assertTrue(all(
            not episode_summary(n)['individual_legal_event_count_verified']
            for n in (49,51,65)))
