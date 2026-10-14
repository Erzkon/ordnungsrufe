from pathlib import Path
from tempfile import TemporaryDirectory
from parser import candidates, events


def test_candidate():
    with TemporaryDirectory() as folder:
        path = Path(folder) / 'sample.xml'
        path.write_text('''<dbtplenarprotokoll wahlperiode="20" sitzung-nr="1">
        <sitzungsverlauf><p>Ich erteile Ihnen einen Ordnungsruf.</p><p>Anderer Text.</p>
        </sitzungsverlauf></dbtplenarprotokoll>''', encoding='utf-8')
        rows = list(candidates(path))
        assert len(rows) == 1
        assert rows[0]['status'] == 'review_required'


def test_group_not_double_counted():
    with TemporaryDirectory() as folder:
        path = Path(folder) / 'sample.xml'
        path.write_text('''<dbtplenarprotokoll wahlperiode="20" sitzung-nr="2">
        <sitzungsverlauf><p>So, ich erteile jetzt allen Abgeordneten einen Ordnungsruf.</p>
        <p>Ich halte fest, dass die Abgeordneten Alpha, Beta und Gamma
        einen Ordnungsruf erhalten haben.</p>
        <p>Ein zweiter Ordnungsruf hätte Konsequenzen.</p></sitzungsverlauf>
        </dbtplenarprotokoll>''', encoding='utf-8')
        assert [e['person'] for e in events(path)] == ['Alpha', 'Beta', 'Gamma']


def test_single_person_direct_address():
    with TemporaryDirectory() as folder:
        path = Path(folder) / 'sample.xml'
        path.write_text('''<dbtplenarprotokoll wahlperiode="20" sitzung-nr="3">
        <vorspann><redner id="101"><name><vorname>Alex</vorname><nachname>Muster</nachname>
        <fraktion>Partei</fraktion></name></redner></vorspann>
        <sitzungsverlauf><p>Herr Muster, dafür bekommen Sie einen Ordnungsruf.</p>
        </sitzungsverlauf></dbtplenarprotokoll>''', encoding='utf-8')
        rows = list(events(path))
        assert len(rows) == 1
        assert rows[0]['person'] == 'Alex Muster'
        assert rows[0]['person_id'] == '101'
