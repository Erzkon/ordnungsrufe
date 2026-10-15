# Ordnungsruf-Counter

[**Zur Website: erzkon.github.io/ordnungsrufe**](https://erzkon.github.io/ordnungsrufe/)

Unabhängiges, nichtamtliches Transparenzprojekt zu personenbezogenen Ordnungsrufen im Deutschen Bundestag mit Originalprotokoll-Links.

## Datenstände

- **20. Wahlperiode (2021–2025):** 135 einzeln überprüfte wirksame personenbezogene Maßnahmen, 123 Vorgänge. Zwei zurückgenommene Maßnahmen ausgeschlossen. Die veröffentlichte personenbezogene Statistik zu Beatrix von Storch (19) weicht von unserer geprüften Einzelliste (18) ab. Siehe [QUELLENABGLEICH.md](QUELLENABGLEICH.md).
- **21. Wahlperiode (seit 2025):** Derzeit eine **unvollständige, ausdrücklich nicht repräsentative Anfangsauswahl von acht einzeln belegten Maßnahmen**. **Keine Gesamtzahl**. Details, Quellen, offener Reviewbedarf und täglicher Quellencheck in [WP21.md](WP21.md).

Die beiden Wahlperioden sind über die Buttons im oberen Seitenbereich getrennt auswählbar. Rankings und Tabellen beziehen sich jeweils nur auf die gewählte Wahlperiode.

## Publizieren und lokal testen

Die Website liegt in `docs/`. Der GitHub-Actions-Workflow `.github/workflows/pages.yml` prüft beide Datenexporte auf Integrität und veröffentlicht die Seite aus einem Actions-Artefakt auf GitHub Pages. Auf GitHub unter **Settings → Pages → GitHub Actions** aktivieren.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_web_export.py' -v
python -m unittest discover -s tests -p 'test_wp21.py' -v
python export_webdaten.py --check
python export_wp21.py --check
```

Der separate manuelle Importworkflow `import.yml` für die historische 20. Wahlperiode bleibt bestehen.

## Täglicher Prüfprozess für die 21. Wahlperiode

Der Seitenworkflow läuft täglich um 06:23 UTC und durchsucht die XML-Protokolle nach Ordnungsruf-Hinweisen. Die Ergebnisse sind als **Prüfhinweis-Artefakt** im Actions-Lauf abrufbar und dienen zur Vorbereitung einer manuellen Sichtung. Hinweise erhöhen die geprüfte Zahl **nicht automatisch**. Erst einzeln geprüfte neue Zeilen in `daten/wirksame_ordnungsrufe_21wp.csv` werden nach Export und Merge in die Website übernommen.

Die laufende Prüfung läuft unabhängig davon, ob neue Ordnungsrufe entdeckt werden; eine Veröffentlichung fehlerhafter oder ungeprüfter Treffer findet nicht statt. Weitere Details: [WP21.md](WP21.md).


## Automatisierung ohne laufende Handarbeit

Der tägliche GitHub-Actions-Lauf veröffentlicht bei erfolgreichem Abruf neben
`scan_21.json` einen maschinenlesbaren **Prüfhinweis-Feed** (`docs/data/hinweise_21.json`).
Die Website zeigt die bis zu 40 neuesten relevanten Textstellen mit Protokolllink,
**getrennt** von den bestätigten Zahlen. Der vollständige CSV-Export ist weiterhin
als Action-Artefakt verfügbar. Der letzte erfolgreiche Feed wird im Actions-Cache
aufbewahrt; bei einem vorübergehenden Quellenausfall bleibt er mit seinem alten
Zeitstempel sichtbar. Es ist kein manueller Commit für diese Aktualisierung nötig.

**Wichtig:** Automatischer Textfund bedeutet noch keine gültige Maßnahme. Eine
vollautomatische Übernahme in bestätigte Zähler wird erst nach unabhängiger
Validierung von Identität, tatsächlicher Vergabe, Dubletten und späteren Rücknahmen
freigegeben. Bis dahin gibt es keine ungeprüfte automatische Zählung.


## Automatische Vorprüfung und Qualitätsmessung

Die tägliche Pipeline erstellt zusätzlich eine maschinenunterstützte
**Personen-Prüfliste** (`wp21_autopruefung.csv`, GitHub-Actions-Artefakt)
und einen öffentlichen Prüfbericht (`docs/data/autopruefung_21.json`).
Ein echter Ordnungsruf wird dabei **nicht** automatisch veröffentlicht:
Personen- und Sitzungstreffer werden zunächst nur mit der bereits belegten
21.-WP-Referenzliste abgeglichen. Der Bericht zeigt auch fehlende Treffer und
mehrdeutige Zuordnungen. Details und Grenzen stehen in [WP21.md](WP21.md).

## Verbesserte Quellenkontrolle (noch ohne automatische Zahlenänderung)

Der tägliche Scanner lädt neben den neuesten Sitzungen turnusmäßig ein
Siebtel der älteren Bundestags-XML-Protokolle erneut, um spätere Korrekturen
an den Quellen nicht dauerhaft zu übersehen.

Die automatische **Personen-Vorprüfung** misst die Wiedererkennung
unterschiedlicher Personen pro Sitzung – ausdrücklich nicht die Trefferquote
einzelner Ordnungsrufe. Mehrfachvergaben bleiben gesondert ausgewiesen.
Eine zusätzliche **Rechtsfolgenprüfung** markiert Einsprüche, mögliche
Rücknahmen und Entscheidungen als zu prüfende Textstellen; sie entscheidet
keinen Rechtsstatus automatisch und löscht keine Maßnahmen.

In **GitHub → Actions** erhält jeder tägliche Lauf einen kompakten
Betriebsbericht über Quellenstand, Vorprüfung, Rechtsfolgensignale und
fehlende oder veraltete Daten. Die freigegebene Statistik wird dabei nicht
überschrieben. Die neuen Prüfungen sind auch in der GitHub-Testpipeline
mit synthetischen Positiv- und Negativfällen abgesichert.


## Quellenbasierte Erkennungsvalidierung (noch ohne automatisches Zählen)

Der CI-Lauf überprüft echte Textstellen aus dem Originalprotokoll **20/214**
gegen die vollständig belegten Einträge dieser Sitzung. Der Test umfasst
direkte Erteilung, Gruppenruf, spätere namentliche Bestätigung und eine
Erwähnung, die **keine** zusätzliche Maßnahme darstellt.
Er ist ein kleiner Regressionstest, keine repräsentative Erkennungsquote.

Eine separate, amtlich in DIP dokumentierte **positive Teilstichprobe** zur
21. Wahlperiode wird täglich gegen die ausgegebene Personen-Prüfliste
abgeglichen. Sie enthält zum Quellenstand 15.10.2026 ausgewählte
24 Person/Sitzung-Kombinationen und 25 ursprünglich berichtete Ordnungsrufe,
von denen die bestehende geprüfte Teilmenge acht umfasst. Die übrigen
17 sind **Prüflücken**, keine automatischen neuen Einträge und nicht
notwendigerweise noch wirksame Maßnahmen. Die positiven Kontrollen sind
bewusst *keine* vollständige amtliche Statistik.
Details und Grenzen: [WP21.md](WP21.md).


## Täglicher, automatischer DIP-API-Änderungsmonitor

Zusätzlich zu den PDF/XML-Protokollen prüft die Pipeline über die
[offizielle DIP-REST-Schnittstelle](https://dip.bundestag.de/%C3%BCber-dip/hilfe/api)
alle seit dem letzten erfolgreichen Abruf aktualisierten Vorgänge
der 21. Wahlperiode. Sie durchläuft die vollständige paginierte
DIP-Vorgangsliste, merkt sich bereits gefundene amtliche Vorgangs-IDs
und erkennt geänderte Metadatensätze mit Ordnungsruf-Bezug.
Der erste Lauf beginnt mit dem Zeitraum seit 25. März 2025; spätere
Abrufe überschneiden sich 30 Tage. Unvollständige Abfragen ersetzen
den letzten erfolgreichen Datenstand nicht.

- **Kein Setup nötig:** Der Bundestag stellt für öffentliche Abfragen
  einen API-Key bereit (laut Bundestag zunächst bis Mai 2027).
  Optional kann das Repo-Secret \`DIP_API_KEY\` diesen ersetzen.
- Status auf der Website: \`docs/data/dip_live_21.json\`, auf der
  21.-WP-Seite klar als **nicht vollständiger Metadatenmonitor**
  ausgezeichnet.
- Neue und veränderte Vorgangs-IDs: Actions-Artefakt
  \`wp21_dip_aenderungen.json\`; langfristiger Zustands-Cache.
- DIP-Metadaten allein werden **niemals** als bestätigte
  Ordnungsrufe gezählt. Sie ersetzen keine Prüfung tatsächlicher
  Vergaben, Rücknahmen und Einspruchsentscheidungen.
- Die echte DIP-Laufzeit/Endpunkt-Verfügbarkeit ist erst beim
  ersten GitHub-Actions-Lauf nach dem späteren Merge zu prüfen.


## Gebündeltes Automatisierungspaket im Entwicklungs-PR

Im offenen Entwicklungs-PR werden die aus der amtlichen Bundestags-DIP-API
ermittelten **Vorgänge UND zugehörigen Vorgangspositionen** über ihre
eindeutigen DIP-IDs verknüpft. Spätere Einspruchs-/Entscheidungstexte
werden als **Prüfsignale** gespeichert, nie direkt als wirksame
Aufhebung. Auf der Website erscheint eine begrenzte, nach
Prüfbedarf sortierte Quellenvorgangsliste mit Links zu DIP.
Der vollständige JSON-Datensatz steht in GitHub Actions
zum Abruf bereit. Die bestätigten Zahlen werden durch den
Workflow weder erweitert noch vermindert.

Der GitHub-Actions-Workflow überwacht alle Quellen auf fehlende
oder veraltete Daten und kann bei längerem Quellenausfall
automatisch **ein offenes GitHub-Issue** zur Störung anlegen.
Bei erfolgreichem neuem Quellenlauf schließt er es.
Voraussetzung ist, dass **Issues im Repository aktiviert**
sind; der auf \`main\` beschränkte Überwachungsjob
verwendet nur das benötigte \`issues:write\`-Recht.
Es ist keine manuelle tägliche Action-Ausführung geplant.

Alle Prüfpfade sind durch Offline-Tests abgesichert.
Ein gesonderter CI-Test bestätigt zusätzlich vor dem
Merge mit echten DIP-Antworten, dass die beiden
Endpunkte erreichbar sind und ein Verfahrensschritt
tatsächlich auf seinen Ursprungs-Vorgang verweist.
Die erste **vollständige** Aktualisierung aller
relevanten DIP-Daten und XML-Protokolle muss nach
dem gemeinsamen Merge noch im Betrieb kontrolliert werden.
Die genaue Methodik und Sicherheitsgrenzen stehen
in [WP21.md](WP21.md).


Für verzögert gemeldete DIP-Änderungen wird am **ersten Sonntag
jedes Monats ein vollständiger Neuabgleich seit Beginn der
21. Wahlperiode** ausgeführt. Die täglichen Abfragen nutzen
ansonsten 30 Tage Überlappung. Fehlende Altvorgänge werden
nicht aufgrund eines kurzen Änderungsfensters fälschlich gelöscht.
Die vollständige dreistufige DIP-Verarbeitung wird zusätzlich
mit einem isolierten End-to-End-Test überprüft.
