from pathlib import Path
from tempfile import TemporaryDirectory
from parser import candidates

def test_candidate():
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'sample.xml'
        path.write_text('<dbtplenarprotokoll wahlperiode="20" sitzung-nr="1"><sitzungsverlauf><p>Ich erteile Ihnen einen Ordnungsruf.</p><p>Anderer Text.</p></sitzungsverlauf></dbtplenarprotokoll>', encoding='utf-8')
        rows = list(candidates(path))
        assert len(rows) == 1
        assert rows[0]['wahlperiode'] == '20'
        assert rows[0]['status'] == 'review_required'
