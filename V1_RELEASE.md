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


## Produktionsbetrieb: veraltete und fehlende Quellen sichtbar kennzeichnen

Der tägliche Hauptlauf erzeugt **nach** XML- und DIP-Quellenabgleich unter
docs/data/quellenstatus_21.json einen maschinenlesbaren Quellenstand für
sieben Teilprüfungen: XML-Plenarprotokolle, Personen-Vorprüfung,
Einspruchshinweise, DIP-Vorgänge, DIP-Verfahrenspositionen, verknüpfte
DIP-Prüffälle und Vollständigkeitsprüfung. Ein eigener Browser-Vertrag
(docs/source_health.js) unterscheidet:

- alle sieben Quellen aktuell;
- nur einzelne Quellen fehlend, ungültig oder aus einem älteren Cache
  (entsprechende Namen sichtbar, **keine automatische Zähleränderung**);
- insgesamt zu alter oder fehlender Betriebsbericht; der Browser zeigt
  die automatische Datenaktualisierung dann nicht als erfolgreich an.

Die Website-Kennzahlen der bestätigten CSV-/JSON-Auswahl sind davon
**unabhängig**. Ein veralteter Suchtreffer darf nicht als bestätigte
oder rechtlich wirksame Maßnahme erscheinen.

Der produktive Hauptlauf führt **unmittelbar vor dem Erzeugen des
GitHub-Pages-Artefakts** den V1-Check ein zweites Mal aus. Diesmal
mit --require-source-health. Er verlangt einen neuen, in sich
widerspruchsfreien Statusbericht für alle sieben Quellen sowie
unveränderte bestätigte CSV/JSON-Werte. Ein ungültiger oder fehlender
Bericht stoppt das Deployment; ein korrekt ausgewiesener
Quellenausfall dagegen bleibt sichtbar und führt nicht zu erfundenen
Nullzahlen. Die Betriebslaufakte wird als eigenes
GitHub-Actions-Artefakt archiviert.

Weitere Offline-Abnahmetests:

    node --check docs/source_health.js
    node --test tests/source_health.test.cjs
    python -m unittest tests.test_wp21_workflow -v

Diese zusätzlichen Schritte ändern weder bestätigte Zähler noch
den Status des offenen Pull Requests.
