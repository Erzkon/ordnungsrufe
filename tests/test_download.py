from io import BytesIO
from pathlib import Path

import download_protokolle as downloader


def fixture_xml(session):
    return (f'<dbtplenarprotokoll wahlperiode="20" sitzung-nr="{session}" '
            f'sitzung-datum="01.01.2022"><sitzungsverlauf><p>'
            + ('Dies ist Testtext. ' * 8) + '</p>'
            '</sitzungsverlauf></dbtplenarprotokoll>').encode()


def test_accept_realistic_minimal_xml():
    assert downloader.check_xml(fixture_xml(1), 1) == '01.01.2022'


def test_reject_wrong_session():
    try:
        downloader.check_xml(fixture_xml(1), 2)
    except ValueError as exc:
        assert 'Sitzungsnummer' in str(exc)
    else:
        assert False, 'Falsche Sitzungsnummer wurde akzeptiert'


def test_download_report_records_failed_documents(tmp_path, monkeypatch):
    def fake_urlopen(req, timeout):
        if req.full_url.endswith('20001.xml'):
            return BytesIO(fixture_xml(1))
        raise ConnectionError('Keine Verbindung')

    monkeypatch.setattr(downloader, 'urlopen', fake_urlopen)
    monkeypatch.setattr(downloader.time, 'sleep', lambda x: None)
    folder = tmp_path / 'protokolle'
    report_file = tmp_path / 'report.json'
    report = downloader.download_all(folder, report_file, start=1, end=2, workers=2)
    assert report['erfolgreich'] == 1
    assert report['fehlgeschlagen'] == 1
    assert not report['vollstaendig']
    assert (folder / '20001.xml').exists()
    assert not (folder / '20002.xml').exists()
    assert report_file.exists()
