#!/usr/bin/env python3
"""Dry-run the FULL WP21 DIP history and its linked procedural follow-ups.

This integration gate can only write to an isolated temporary directory.
It cannot publish, edit or even open the reviewed CSV or public counts.
Network errors fail the pre-merge check, not the protected website.
"""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from wp21_dip_monitor import PUBLIC_KEY, run as monitor
from wp21_dip_positionen import run as positions
from wp21_pruefqueue import run as queue


def execute(key=None):
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix='wp21-dip-audit-') as temp:
        root = Path(temp)
        states = root/'vorgaenge.json', root/'positionen.json'
        reports = root/'vorgangsreport.json', root/'positionreport.json', root/'queuereport.json'
        changes = root/'vorgangsaenderungen.json', root/'positionaenderungen.json'
        data = root/'prueffaelle.json'
        live_key = key or os.getenv('DIP_API_KEY') or PUBLIC_KEY
        first = monitor(states[0],reports[0],changes[0],key=live_key,now=now)
        second = positions(states[0],states[1],reports[1],changes[1],key=live_key,now=now)
        third = queue(states[0],states[1],reports[2],data)
        if (first['automatically_confirmed_sanctions'] != 0
                or second['automatically_confirmed_sanctions'] != 0
                or second['automatically_rescinded_sanctions'] != 0
                or third['automatically_confirmed_sanctions'] != 0
                or third['automatically_rescinded_sanctions'] != 0):
            raise ValueError('Gefährliche unerwartete Statistikübernahme')
        return {
            'schema':'wp21-dip-readonly-audit-v1',
            'checked_utc':now.isoformat(timespec='seconds'),
            'full_history_pages':first['api_pages'],
            'full_history_vorgaenge':first['changed_documents_scanned'],
            'source_related_vorgaenge':first['tracked_relevant_vorgaenge'],
            'positions_monitored_parents':second['monitored_parent_vorgaenge'],
            'positions_loaded':second['tracked_positions'],
            'legal_wording_positions':second['legal_wording_positions'],
            'linked_cases':third['linked_dip_vorgaenge'],
            'high_priority_cases':third['high_priority_cases'],
            'automatically_confirmed_sanctions':0,
            'automatically_rescinded_sanctions':0,
            'scope':'Isolierte echte DIP-API-Erstladung; keine XML-Vollabdeckung, '
                    'keine Ermittlung rechtswirksamer Maßnahmen.'
        }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('wp21_premerge_dryrun.json'))
    args=parser.parse_args()
    report=execute()
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',
                           encoding='utf-8')
    print('Vollständiger isolierter DIP-Erstlauf:',report)


if __name__=='__main__':
    main()
