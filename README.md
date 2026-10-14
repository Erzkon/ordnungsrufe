# Ordnungsruf-Counter — erster technischer Prototyp

Dieser Stand ist ein **Kandidaten-Extractor**, noch kein verlässlicher Ordnungsruf-Zähler.
Er findet Textstellen in XML-Plenarprotokollen, die auf Ordnungsrufe hindeuten.
Er erkennt **noch nicht** zuverlässig die betroffene Person, Mehrfachzählungen,
Rücknahmen oder Erwähnungen eines früheren Ordnungsrufs.

## Einrichtung

```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
```

Lade XML-Plenarprotokolle von https://www.bundestag.de/services/opendata
und speichere sie im Ordner `protokolle/`.

```bash
python parser.py protokolle --out kandidaten.csv
```

Die CSV enthält **Prüfkandidaten**, keine fertige Statistik. Prüfe die Treffer
gegen die Originalprotokolle. Offizielle Vergleichszahl für die 20. Wahlperiode:
135 Ordnungsrufe (Quelle: Bundestag, https://www.bundestag.de/dokumente/textarchiv/1949-09-20-ordnungsruf-1086652).

## Nächste Arbeitsschritte

1. Reale XML-Strukturen mehrerer Sitzungen prüfen und Extraktion daran anpassen.
2. Ordnungsmaßnahmen als Ereignisse statt Stichworttreffer modellieren.
3. Personen über IDs und Präsidiumsansprachen korrekt zuordnen.
4. Rücknahmen, Einsprüche, Erwähnungen und Duplikate gesondert behandeln.
5. Alle 214 Protokolle der 20. Wahlperiode validieren und Abweichungen dokumentieren.
6. Erst danach veröffentlichungsfähige Statistiken erstellen.
