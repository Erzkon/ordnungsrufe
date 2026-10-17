"""Gottschalk future decision watch must stay cache-scoped and non-counting."""
import copy
import unittest

from wp21_gottschalk_folgebeobachter import inspect,markdown


def states():
    parents={
        'last_success_utc':'2026-10-17T09:00:00+00:00',
        'items':{
            '328225':{
                'id':'328225','active':True,
                'source':'https://dip.bundestag.de/vorgang/328225',
                'date':'2025-11-25',
                'title':'Erteilung von zwei Ordnungsrufen an den Abg Kay Gottschalk (AfD)',
            },
            '328000':{
                'id':'328000','active':True,
                'source':'https://dip.bundestag.de/vorgang/328000',
                'date':'2025-09-23',
                'title':'Erteilung eines Ordnungsrufes an Kay Gottschalk',
            },
        },
    }
    url='https://dip.bundestag.de/vorgang/328225'
    positions={
        'last_success_utc':'2026-10-17T09:05:00+00:00',
        'items':{
            '681046':{
                'id':'681046','parent_id':'328225','active':True,
                'source':url,'date':'2025-11-13','step':'Ordnungsruf',
                'official_plenary_session':40,
                'official_decision_tenors':[],
                'official_position_abstract_excerpt':'',
            },
            '681803':{
                'id':'681803','parent_id':'328225','active':True,
                'source':url,'date':'2025-11-25','step':'Abstimmung',
                'official_plenary_session':42,
                'official_decision_tenors':['Zurückweisung des Einspruchs'],
                'official_position_abstract_excerpt':
                    'Einspruch des Abg Kay Gottschalk (AfD) gegen die erste Ordnungsmaßnahme',
            },
        },
    }
    return parents,positions


class IncrementalGottschalkScoping(unittest.TestCase):
    def test_unchanged_cache_not_proof_of_no_appeal_elsewhere(self):
        a,b=states()
        r=inspect(a,b)
        self.assertEqual(r['status'],'no_additional_candidate_in_current_tracked_cache')
        self.assertFalse(r['manual_review_required'])
        self.assertEqual(r['two_original_calls_single_parent_documented'],2)
        self.assertTrue(r['absent_other_cache_candidates_is_not_appeal_absence_proof'])
        self.assertTrue(r['eventual_effectiveness_of_second_measure_unresolved'])
        self.assertEqual(r['automatically_confirmed_effective_sanctions'],0)
        self.assertEqual(r['public_counter_delta'],0)
        self.assertIn('kein',markdown(r).lower())

    def test_extra_vote_in_original_parent_creates_manual_review_not_count(self):
        a,b=states()
        b['items']['699999']={
            **b['items']['681803'],'id':'699999',
            'official_position_abstract_excerpt':
                'Einspruch des Kay Gottschalk gegen die zweite Ordnungsmaßnahme',
        }
        r=inspect(a,b)
        self.assertTrue(r['manual_review_required'])
        self.assertEqual(len(r['new_positions_in_same_parent']),1)
        self.assertEqual(r['public_counter_delta'],0)

    def test_new_foreign_parent_name_after_original_date_creates_manual_review(self):
        a,b=states()
        a['items']['339999']={
            'id':'339999','active':True,'date':'2026-10-01',
            'title':'Erteilung eines Ordnungsrufes an den Abgeordneten Kay Gottschalk',
            'source':'https://dip.bundestag.de/vorgang/339999',
        }
        r=inspect(a,b)
        self.assertTrue(r['manual_review_required'])
        self.assertEqual([x['parent_id'] for x in r['other_potential_gottschalk_parents']],
                         ['339999'])
        self.assertEqual(r['automatically_confirmed_effective_sanctions'],0)

    def test_abstract_only_ordnungsmaßnahme_and_objection_title_are_candidates(self):
        a,b=states()
        a['items']['339998']={
            'id':'339998','active':True,'date':'2026-09-01',
            'title':'Einspruch des Abgeordneten Kay Gottschalk',
            'abstract_excerpt':'Mögliche spätere Entscheidung zu einer Ordnungsmaßnahme',
            'source':'https://dip.bundestag.de/vorgang/339998',
        }
        r=inspect(a,b)
        self.assertTrue(r['manual_review_required'])
        self.assertEqual(r['other_potential_gottschalk_parents'][0]['parent_id'],
                         '339998')
        self.assertEqual(r['other_potential_gottschalk_parents'][0]['matching_fields'],
                         ['title','abstract'])
        self.assertEqual(r['public_counter_delta'],0)

    def test_unrelated_name_only_metadata_is_not_an_appeal_candidate(self):
        a,b=states()
        a['items']['339997']={
            'id':'339997','active':True,'date':'2026-09-01',
            'title':'Rede des Kay Gottschalk zum Haushalt',
            'source':'https://dip.bundestag.de/vorgang/339997',
        }
        self.assertFalse(inspect(a,b)['manual_review_required'])

    def test_older_unrelated_original_parent_is_not_second_2025_proceeding(self):
        a,b=states()
        self.assertFalse(inspect(a,b)['other_potential_gottschalk_parents'])

    def test_stale_or_inactive_official_parent_and_position_fails(self):
        a,b=states()
        b['last_success_utc']='2026-10-17T08:55:00+00:00'
        with self.assertRaisesRegex(ValueError,'älter'):
            inspect(a,b)
        a,b=states()
        b['items']['681803']['active']=False
        with self.assertRaisesRegex(ValueError,'inaktiv'):
            inspect(a,b)
        a,b=states()
        a['items']['328225']['active']=False
        with self.assertRaisesRegex(ValueError,'fehlt'):
            inspect(a,b)

    def test_first_vote_cannot_be_switched_to_second_vote_silently(self):
        a,b=states()
        b['items']['681803']['official_position_abstract_excerpt']=(
            'Einspruch des Abg Kay Gottschalk (AfD) gegen die zweite Ordnungsmaßnahme')
        with self.assertRaisesRegex(ValueError,'quellengleich'):
            inspect(a,b)

    def test_invalid_foreign_parent_url_not_confused_with_dip_source(self):
        a,b=states()
        a['items']['339999']={
            'id':'339999','active':True,'date':'2026-01-15',
            'title':'Ordnungsruf an Kay Gottschalk',
            'source':'https://malicious.example/vorgang/339999',
        }
        with self.assertRaisesRegex(ValueError,'amtliche Identität'):
            inspect(a,b)

    def test_report_cannot_publish_new_legal_confirmation(self):
        a,b=states()
        r=inspect(a,b)
        with self.assertRaises(ValueError):
            markdown({**r,'automatically_confirmed_effective_sanctions':1})
        with self.assertRaises(ValueError):
            markdown({**r,'absence_of_appeal_anywhere_not_established':False,
                      'eventual_effectiveness_of_second_measure_unresolved':False})


if __name__=='__main__':
    unittest.main()
