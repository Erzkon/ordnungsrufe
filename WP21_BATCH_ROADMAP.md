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


## Zusätzlicher amtlicher Rechtsquellenabgleich am 21. Oktober 2026

Beim Abgleich der datierten Stichprobe sind zwei getrennte amtliche Verfahrensbelege explizit **nicht** als neue Ordnungsrufe aufgenommen worden:

- [Reichardt: Einspruch gegen ein Ordnungsgeld zurückgewiesen am 16.10.2026](https://www.bundestag.de/dokumente/textarchiv/2026/kw42-de-einspruch-ordnungsgeld-1225202). Das Ordnungsgeld wurde am **15.10.2026** verhängt. Es ist ein **anderer Maßnahmentyp** und kein Beleg für einen zweiten Ordnungsruf oder für den Rechtsstatus von Reichardts Ursprungsvorgang **21/065** aus März.
- [Sichert: Einspruch gegen Ordnungsruf aus 21/090 am 08.09.2026 zurückgewiesen](https://www.bundestag.de/dokumente/textarchiv/2026/kw37-de-einspruch-ordnungsruf-1210768). Dieser ursprünglich erteilte Ruf ist bereits in den **acht** bestätigten Einträgen enthalten; die Einspruchsentscheidung erzeugt **keine neue ursprüngliche Erteilung**.

Beide Original-Links sind als getrennte Verfahrensquellen im JSON-Bericht vermerkt. Die Review-Queue erhält **keinen** weiteren Kandidaten und ändert keine Statistik. Keine Aussage über andere, nicht untersuchte Rechtsfolgen wird daraus abgeleitet.


## Amtlicher Original-PDF-Abgleich: das erste Bündel ist in Arbeit

Die beiden zunächst priorisierten Mehrfachformulierungen wurden unabhängig
am tatsächlichen Original-PDF nachgeprüft und als **verschiedenartige
Beweisprobleme** klassifiziert:

- Frohnmaier 21/051, Seite 6144: [Original](https://dserver.bundestag.de/btp/21/21051.pdf#page=74).
  Zwei ausgesprochene Formulierungen sind durch eine weitere Äußerung des
  Adressaten unterbrochen. Deshalb ist offen, ob eine wiederholte Erteilung oder
  zwei eigenständige Maßnahmen gemeint waren; eine einzelne DIP-Position ist
  kein sicherer Zählbeweis.
- Reichardt 21/065, Seite 7785: [Original](https://dserver.bundestag.de/btp/21/21065.pdf#page=25).
  Die zweite Formulierung folgt innerhalb derselben zusammenhängenden
  Intervention der Sitzungsleitung. Eine Wiederholung der ersten Erteilung
  liegt nahe, bleibt jedoch eine Interpretation. Der amtliche
  [Einspruchsbeschluss vom 20.03.2026](https://www.bundestag.de/dokumente/textarchiv/2026/kw12-de-einspruch-ordnungsruf-1156828)
  behandelt einen Ordnungsruf.

Die genaue Abgrenzung und nächsten Nachweise stehen in
`WP21_BATCH_1_ORIGINALNOTIZEN.md`. Beide Fälle bleiben **nichtzählend**.

## Drei zusätzliche Original- und Abstimmungspaare geprüft (21.10.2026)

Hess (21/052), Przygodda (21/067) und Fahl (21/069) sind anhand der
**jeweiligen originalen Erteilungsseite**, der **parlamentarischen
Einspruchsabstimmung in späterer Sitzung** und eines unabhängigen
Bundestagsberichts als Einzelpersonen zuordenbar. Die konkreten
Original-PDF-Seiten stehen in `WP21_BATCH_1_APPEAL_VOTES.md`.

Das lesende Modul `wp21_three_decisions.py` verbindet diese Primärquellen
mit den bisherigen kuratierten XML-Ankern, dem datierten amtlichen
DIP-Positivsnapshot und den individuellen Einspruchsreferenzen.
Es exportiert `.audit/wp21_three_decisions/crosswalk.json` und
`crosswalk.md`, prüft Namens-/Sitzungs-/Quellenkonsistenz und blockiert
unbelegte Zusatzfreigaben. Die bestehende Bearbeitungsqueue enthält
die drei konkreten Original-/Abstimmungslinks ebenfalls gesondert.

**Abstimmungsentscheidung** und **endgültiger Stand sämtlicher möglicher
weiterer Rechtsfolgen** sind unterschiedliche Beweisfragen.
Auch bei diesen drei Fällen bleiben automatische Zähleränderungen **null**.
