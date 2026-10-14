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
