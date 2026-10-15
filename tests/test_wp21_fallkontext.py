"""Read-only audit-queue to official XML context selection contracts."""
import csv
import tempfile
import unittest
from pathlib import Path

from wp21_dip_kontrolle import reference
from wp21_fallkontext import targeted_gaps
from wp21_autopruefung import norm

HEADER=['typ','sitzung','person','dip_urspruengliche_erteilungen_stichprobe',
        'parser_person_sitzung_vorhanden']


def write(folder, rows):
    path=Path(folder)/'audit.csv'
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return path


def case(session,person,present='nein',dip='1'):
    return {'typ':'person_sitzung_ohne_einzelereignisabgleich',
            'sitzung':str(session),'person':person,
            'parser_person_sitzung_vorhanden':present,
            'dip_urspruengliche_erteilungen_stichprobe':dip}


class ReadOnlyContextQueueTests(unittest.TestCase):
    def test_only_unmatched_known_dip_person_sessions(self):
        ref=reference()
        x=ref['entries'][0]
        y=ref['entries'][1]
        with tempfile.TemporaryDirectory() as tmp:
            file=write(tmp,[case(x['session'],x['person']),
                            case(y['session'],y['person'],'ja'),
                            case(x['session'],'Unrelated','ja','')])
            self.assertEqual(targeted_gaps(file,ref),
                             {(x['session'],norm(x['person']))})

    def test_curated_scope_is_validated_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=write(tmp,[case(99,'Eine erfundene Person')])
            with self.assertRaisesRegex(ValueError,'Unbekannte'):
                targeted_gaps(path,reference())

    def test_duplicate_reference_is_rejected(self):
        ref=reference()
        x=ref['entries'][0]
        with tempfile.TemporaryDirectory() as tmp:
            path=write(tmp,[case(x['session'],x['person']),
                            case(x['session'],x['person'])])
            with self.assertRaisesRegex(ValueError,'doppelte'):
                targeted_gaps(path,ref)

    def test_no_unresolved_keys_means_no_context_download(self):
        ref=reference()
        x=ref['entries'][0]
        with tempfile.TemporaryDirectory() as tmp:
            path=write(tmp,[case(x['session'],x['person'],'ja')])
            self.assertEqual(targeted_gaps(path,ref),set())


if __name__=='__main__':
    unittest.main()
