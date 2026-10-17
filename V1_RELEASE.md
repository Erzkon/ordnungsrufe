# Version 1.0 – begrenzter Veröffentlichungskandidat

**Status:** Diese Checkliste bereitet die technische Freigabe in PR #4 vor. Auch ein grüner CI-Lauf autorisiert keinen Merge. Der PR bleibt bis zu einer ausdrücklichen menschlichen Entscheidung offen.

## Veröffentlichung und Beweisgrenzen

| Bereich | Version 1.0 | Noch nicht abgeschlossen |
|---|---|---|
| 20. Wahlperiode | 135 einzeln geprüfte wirksame Maßnahmen, 123 Ereignisse, Primärquellen und historische Zugehörigkeiten | Von Storch: amtlich 19, einzeln überprüft 18 |
| 21. Wahlperiode | Acht individuell geprüfte Maßnahmen als ausdrücklich **nicht repräsentative Teilmenge** | Keine Gesamtzahl; viele Erteilungen, Einsprüche und Wirkungen offen |
| Automatische Prüfungen | Lesender XML-/DIP-Quellenmonitor mit separat gekennzeichneten Hinweisen | Keine Freigabe automatischer Zählerkorrekturen |

Die Wahlperioden werden getrennt dargestellt und dürfen nicht zu einer erfundenen aktuellen Gesamtzahl addiert werden.

## Technische Abnahmekriterien

- Vier geschützte Statistikdateien sind gegenüber main bytegleich; die Tests lesen sie nur.
- Die beiden veröffentlichten JSON-Dateien entsprechen exakt den bestehenden CSV-Exportfunktionen.
- Die Website zeigt Datenstände für beide Wahlperioden unmittelbar aus dem jeweiligen JSON-Snapshot statt aus festem HTML.
- Ein eigenständiger Browser-Vertrag kontrolliert Wahlperiode, Personenzahl, Ereignisse, offizielle Protokoll-Links, Teilmengenkennzeichnung und historische Personendifferenz, bevor ein Datensatz in die Ranglisten gelangt.
- Gesonderte automatische Hinweise dürfen die bestätigten Zähler nicht verändern.
- Negativtests prüfen beschädigte JSONs, gefälschte Belege, fehlende Warnungen und inkonsistente Daten.
- Website-PR-Läufe prüfen die Abnahme, veröffentlichen aber keine neuen Pages; ein PR wird nicht automatisch gemergt.

## Offline-Prüfung

    python -m pip install -r requirements.txt
    python export_webdaten.py --check
    python export_wp21.py --check
    node --check docs/verified_contract.js
    node --check docs/app.js
    node --test tests/frontend_contract.test.cjs
    python -m unittest -v tests.test_v1_release_gate
    python v1_release_gate.py --output .audit/v1_release.json --brief .audit/v1_release.md

GitHub Actions archiviert denselben begrenzten Release-Bericht inklusive SHA-256 der vier geprüften Statistikdateien. Der Status heißt ausdrücklich Release-Kandidat und **nicht** Genehmigung rechtlicher Wirksamkeit oder Freigabe zum Merge.

## Vor einer tatsächlichen öffentlichen Version 1.0

Erst die ausdrücklich bestätigte Entscheidung, eine **historische Auswertung der 20. Wahlperiode plus klar als unvollständig markierte Vorschau der 21. Wahlperiode** zu veröffentlichen, autorisiert den nächsten Schritt. Die ungelöste von-Storch-Differenz und die bestehenden 21.-WP-Quellenlücken müssen sichtbar bleiben. Eine Veröffentlichung aller jemals erteilten Ordnungsrufe ist damit nicht behauptet.
