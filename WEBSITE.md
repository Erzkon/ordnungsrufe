# GitHub-Pages-Website

Die erste Website-Version liegt unter `docs/` und benötigt **keinen Server, kein Docker, keine Datenbank**. Sie nutzt ausschließlich HTML, CSS, JavaScript und eine versionierte JSON-Datei.

## Aufbau

- `docs/index.html`, `docs/styles.css`, `docs/app.js`: Oberfläche mit Personen-/Fraktionsrankings, Suche, historischen Zugehörigkeiten und Quellenlinks.
- `docs/data/ordnungsrufe.json`: maschinenlesbare Momentaufnahme der **135 wirksamen Maßnahmen** der 20. Wahlperiode.
- `daten/wirksame_ordnungsrufe_20wp.csv`: nachvollziehbarer, geprüfter Ausgangsdatensatz aus dem Update-12-Kontrolllauf (nicht automatisch durch den Import-Workflow verändert).
- `daten/korrekturbericht_20wp.json`: Kontrollbericht für diesen Datensatz.
- `QUELLENABGLEICH.md`: Methodik und die verbleibende Differenz bei Beatrix von Storch.
- `export_webdaten.py`: deterministischer Export und Sicherheitsprüfungen gegen Daten-/Statusdrift.
- `.github/workflows/pages.yml`: prüft auf Pull Requests und veröffentlicht nach Merge nach `main` über GitHub Actions.

## GitHub Pages aktivieren

Nach dem Merge unter **Settings → Pages → Build and deployment → Source: GitHub Actions** auswählen. Sollte das bereits eingestellt sein, ist nichts weiter zu tun. Danach unter **Actions → Website pruefen und GitHub Pages veroeffentlichen** den Lauf prüfen. Die Website ist anschließend regulär unter **https://erzkon.github.io/ordnungsrufe/** erreichbar, sofern GitHub Pages für das Repository freigeschaltet ist.

## Daten nach einer neuen Prüfung aktualisieren

Nur wenn die Korrekturentscheidungen wieder gegen alle Quellen geprüft wurden, die neue wirksame CSV und ihren Kontrollbericht nach `daten/` übernehmen. Dann die JSON-Datei neu erzeugen:

```bash
python export_webdaten.py
python -m unittest discover -s tests -p 'test_web_export.py' -v
python export_webdaten.py --check
```

Ein Commit dieser Dateien löst die Veröffentlichung erneut aus. Die Website ist **keine Live-API** und derzeit nicht mit dem bisherigen manuellen `Bundestag Datenimport`-Workflow verbunden; das verhindert auch, dass ein ungeprüfter Import sofort die öffentliche Statistik ändert.

## Datenschutz und Unabhängigkeit

Die Website setzt keine Cookies, bindet keine Analysedienste ein und überträgt keine Suchanfragen an einen Server. Die Protokoll-Links führen zu amtlichen PDF-Dateien des Bundestages. Das Projekt ist unabhängig und nichtamtlich.
