# WP21 – vier quellenbasierte Arbeitsbündel

**Stand: 21. Oktober 2026.** Die bestätigte öffentlich sichtbare WP21-Teilauswahl bleibt bei **8 einzeln geprüften Ordnungsrufen** und ist **ausdrücklich unvollständig**.

## Sofort nutzbare Arbeitsliste

Die kuratierte amtliche DIP-Positivstichprobe vom **15. Oktober 2026** enthält 24 Person-/Sitzungskombinationen und 25 gemeldete **ursprüngliche** Erteilungen. 8 davon sind in der bisherigen bestätigten Teilmenge einzeln dokumentiert. Die verbleibenden **17 Person-/Sitzungskombinationen** sind offene Review-Aufgaben, **keine automatisch neuen oder wirksamen Ordnungsrufe**.

Das Programm `wp21_batch_review.py` führt die vorhandenen Quellenbelege zusammen, statt dieselben Fälle wiederholt von Grund auf zu untersuchen:

- vier Bearbeitungsbündel mit 5, 5, 5 und 2 Fällen;
- zu jedem Fall die bereits kuratierte amtliche Original-XML-Fundstelle und ein PDF-Link;
- getrennte Kennzeichnung von mehrfach gesprochenen Erteilungsformulierungen und individuell kuratierten Einspruchsentscheidungen;
- eine konkrete nächste manuelle Prüfhandlung und eine feste, nachvollziehbare Priorisierung.

Die zwei besonders erklärungsbedürftigen Mehrfachformulierungen zu **Frohnmaier (21/051)** und **Reichardt (21/065)** kommen zuerst. Der bereits doppelt belegte Köktürk-Fall wird nicht nochmals als offener Kandidat behandelt. Die vollständige 18er-Quellenakte umfasst 21 XML-Formulierungen aus 14 Protokollen; **kein** Parserfund allein ist eine Rechtsfolgenentscheidung.

## Ausführung ohne Internetrecherche

```bash
python wp21_batch_review.py --output-dir .audit/wp21_batch_review
```

Es entstehen nur drei gesonderte Prüfarbeitsprodukte: `review_queue.json`, `review_queue.md` und `review_queue.csv`. Sie werden ausschließlich unter `.audit/` gespeichert und im dazugehörigen GitHub-Actions-Workflow separat archiviert. Der Workflow kann ohne manuellen Dauerbetrieb wöchentlich, bei passenden PRs oder auf Anforderung laufen.

## Sicherheitsgrenzen und weitere Roadmap

1. Quelle ist eine **datierte und ausdrücklich unvollständige** amtliche Referenzauswahl; die wöchentliche Wiederholung macht sie **nicht** zu aktuellen vollständigen DIP-Daten.
2. Jede Änderung an Grundreferenz, 18er-Quellenbelegen, vier Einspruchsentscheidungen oder acht bestätigten Teilmengenmaßnahmen stoppt die bisher eingefrorene Arbeitsliste, bis eine eigene fachliche Neubewertung erfolgt.
3. In keinem Fall werden bestätigte CSV-/JSON-Zähler verändert. **Automatische neue Maßnahmen und automatische Aufhebungen: jeweils null.**
4. Nächstes großes Paket: zeitaktuelle DIP-/XML-Kandidaten aus dem bereits laufenden Quellenmonitor zusätzlich zur eingefrorenen Basis aufnehmen, mit klarer Herkunfts- und Aktualitätskennzeichnung; weiter ohne automatisches Zählen.
5. Danach die vier Bearbeitungsbündel mit unabhängigen Original- und Rechtsfolgenbelegen abarbeiten. Bereits geprüfte Fälle müssen in einem separaten, ausdrücklich freigegebenen Statistik-PR landen.

Die unabhängigen offenen Akten **von Storch, Janich, Gottschalk und Mixl** bleiben daneben in `OFFENE_EINZELFAELLE.md` dokumentiert. Diese Arbeitsliste löst sie nicht automatisch auf.
