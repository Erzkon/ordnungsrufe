"""Independently sourced appeal decisions, separate from verified counters.

Curated official Bundestag reports below describe rejection of objections
against one identified original grant. They DO NOT create a new sanction
entry, do not infer all later legal consequences, and do not assert any
unlisted politician lacks a possible appeal. The automatic DIP/position
monitors remain responsible for detecting later procedural changes.
"""
import re
from datetime import date
from wp21_autopruefung import norm

EVIDENCE = (
    {
        'session':52, 'person':'Martin Hess',
        'decision_date':'2026-01-15',
        'outcome':'einspruch_zurueckgewiesen',
        'source':'https://www.bundestag.de/dokumente/textarchiv/2026/'
                 'kw03-de-einspruch-ordnungsruf-1136742',
    },
    {
        'session':65, 'person':'Martin Reichardt',
        'decision_date':'2026-03-20',
        'outcome':'einspruch_zurueckgewiesen',
        'source':'https://www.bundestag.de/dokumente/textarchiv/2026/'
                 'kw12-de-einspruch-ordnungsruf-1156828',
    },
    {
        'session':67, 'person':'Kerstin Przygodda',
        'decision_date':'2026-03-26',
        'outcome':'einspruch_zurueckgewiesen',
        'source':'https://www.bundestag.de/dokumente/textarchiv/2026/'
                 'kw13-de-einspruch-ordnungsruf-1158042',
    },
    {
        'session':69, 'person':'Fabian Fahl',
        'decision_date':'2026-04-15',
        'outcome':'einspruch_zurueckgewiesen',
        'source':'https://www.bundestag.de/dokumente/textarchiv/2026/'
                 'kw16-de-einspruch-ordnungsruf-1165404',
    },
)
SOURCE_PATTERN = re.compile(
    r'https://www\.bundestag\.de/dokumente/textarchiv/2026/'
    r'kw\d{2}-de-einspruch-ordnungsruf-\d{5,9}\Z')


def validated_index(items=EVIDENCE):
    """Fail closed on malformed keys, duplicates and untrusted source URLs."""
    if not 0 < len(items) <= 60:
        raise ValueError('Einspruchsquellen fehlen oder unplausibel viele')
    result={}
    sources=set()
    for row in items:
        if not isinstance(row,dict) or set(row)!={
                'session','person','decision_date','outcome','source'}:
            raise ValueError('Einspruchseintrag unerwartetes Schema')
        session=row['session']
        if type(session)!=int or not 1<=session<=450:
            raise ValueError('Einspruchseintrag Sitzung ungültig')
        person=row['person']
        if not isinstance(person,str) or not re.fullmatch(
                r'[A-ZÄÖÜ][A-Za-zÄÖÜäöüß -]{3,95}',person):
            raise ValueError('Einspruchseintrag Name ungültig')
        try:
            decision=date.fromisoformat(row['decision_date'])
        except (TypeError,ValueError) as exc:
            raise ValueError('Einspruchseintrag Datum ungültig') from exc
        if not date(2025,1,1)<=decision<=date(2026,10,15):
            raise ValueError('Einspruchsentscheidung außerhalb der Quellengrenze')
        if row['outcome']!='einspruch_zurueckgewiesen':
            raise ValueError('Ungeprüfter Rechtsausgang nicht erlaubt')
        if not isinstance(row['source'],str) or not SOURCE_PATTERN.fullmatch(row['source']):
            raise ValueError('Nichtamtliche oder unplausible Quellenadresse')
        key=(session,norm(person))
        if key in result or row['source'] in sources:
            raise ValueError('Einspruchsdokument doppelt erfasst')
        sources.add(row['source'])
        result[key]=dict(row)
    return result


def find(session,person,items=EVIDENCE):
    return validated_index(items).get((int(session),norm(person)))
