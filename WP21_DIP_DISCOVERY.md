# WP21: neuer DIP-Entdeckungsabgleich außerhalb der 18 verankerten Vorgänge

**Stand: 24. Oktober 2026 · Audit-Only · keinerlei automatische Zählung.**

## Zweck und Abgrenzung

Die bisherige 17-Fälle-Matrix überprüft vollständige Verfahrenspositionen
von **17 exakt bekannten Eltern-DIP-Vorgängen** aus einer datierten Stichprobe.
Sie findet keinen völlig anderen DIP-Elternvorgang. Das neue
`wp21_new_dip_candidates.py` verwendet deshalb die bestehende
offizielle, vollständig paginierende DIP-Vorgangssuche und gruppiert
Treffer **außerhalb der 18 bereits amtlich individuell verankerten
DIP-Eltern-IDs**.

**Außerhalb dieser 18 IDs heißt ausdrücklich nicht:**
ein neuer, ungeprüfter, rechtswirksamer oder bisher ungezählter
Ordnungsruf. Es gibt weitere Personen in der bisherigen amtlichen
24er-Teilstichprobe und acht bereits geprüfte Beispiele. Ein nicht
bekannter Elternvorgang kann daher eine Dublette, einen bekannten Fall,
einen Einspruch oder ein völlig anderes parlamentarisches Verfahren
betreffen.

## Drei disjunkte Kategorien

1. **Bereits verankerte ID**: bekannter Elternvorgang aus den 18 festen
   DIP-IDs, ohne erneutes Erzeugen eines neuen Falles.
2. **Mögliche ursprüngliche Erteilung**: eine nicht verankerte DIP-ID,
   deren Vorgangstitel ausdrücklich eine Erteilung beziehungsweise einen
   Ordnungsruf an/gegen eine Person beschreibt. Ein Rechtsfolgen- oder
   Ordnungsgeldbegriff im Titel blockiert diese Einordnung.
3. **Sonstige relevante Verfahrensmetadaten**: beispielsweise Einsprüche,
   Ordnungsgelder und unbestimmte Erwähnungen. Diese werden als getrennte
   Nachprüfhinweise archiviert, nicht als ursprüngliche Erteilung.

Eine mögliche Zuordnung zur datierten 24er-Positivstichprobe wird lediglich
als **unsicherer Namens- und Datumshinweis** dokumentiert. Keine
Personen-/Sitzungs- oder Maßnahmenfreigabe erfolgt automatisch.

## Lauf und Beweisgrenzen

```bash
python -m unittest -v tests.test_wp21_new_dip_candidates
python wp21_new_dip_candidates.py --days 45
python wp21_new_dip_candidates.py --full-term
```

- **Wöchentlich** nach genehmigtem Merge: jüngste 45 Tage anhand des
  amtlichen **Aktualisierungsdatums** (mit überlappenden Zeitfenstern).
- **Am ersten Montag jedes Monats**: vollständiger Aktualisierungsfilter
  ab 25. März 2025 für Rückmeldungen und rückwirkende Änderungen.
- **Im PR**: ein kleinerer Live-Lauf über 45 Tage, getrennt von den
  bestehenden 17 elterngebundenen Live-Prüfungen.
- **Manuell auslösbar**: GitHub-Actions-Option
  `full_term_discovery`, ohne Änderungen an bestätigten Dateien.
- **Fehlertoleranz**: Unvollständige API-Paginierung, fremde Wahlperiode,
  doppelte Vorgangs-IDs oder verändertes Quellenschema brechen den
  Bericht ab. Alte Artefakte werden nicht in einen neuen, angeblich
  vollständigen Bericht umetikettiert.

Selbst ein vollständiger Aktualisierungsfilter über die laufende
Wahlperiode ist **keine vollständige Ordnungsrufinventur**:
Die Suchheuristik liest nur Titel/Abstract der DIP-Vorgänge, nicht alle
Plenartextstellen, separate Gerichtsverfahren oder alle späteren
Aufhebungen. XML-/DIP-Kombinationen und individuelle Quellenprüfung
sind weiterhin notwendig.

## Dateien und Sicherheitsgrenzen

Im isolierten Workflow-Artefakt werden ausschließlich

- `.audit/wp21_dip_discovery/outside_pins.json`
- `.audit/wp21_dip_discovery/outside_pins.md`

geschrieben. Kein öffentlicher JSON-Export, keine neue bestätigte
Maßnahmenzeile, kein Review-Issue auf PRs und kein Merge.
Die bisherige SHA256-Prüfung aller vier bestätigten CSV-/JSON-Dateien
bleibt nach dem Live-Lauf zwingend aktiv.

## Nächstes Fachpaket

Die tatsächlich gefundenen nicht verankerten DIP-IDs nach jeweils
individueller Originalperson, ursprünglicher Sitzung, PDF-/XML-Seite
und separater Rechtsfolgensuche sortieren. Nur quellenkritisch
abgeschlossene Einzelfälle können in einem **gesondert freigegebenen
Statistik-PR** zur Zählung vorgeschlagen werden.


## Erster amtlicher Originalpositions-Abgleich (24.10.2026)

Der erste echte 45-Tage-Lauf (seit 9. September 2026 nach
**DIP-Aktualisierungsdatum**) hat 6.201 Dokumente auf 63 vollständigen
API-Seiten abgefragt und vier möglich ursprüngliche
Erteilungs-Elternvorgänge **außerhalb der 18 schon fest verankerten IDs**
gefunden.

Anschließend wurden **alle amtlichen Verfahrenspositionen dieser vier
Elternvorgänge** erneut live abgefragt, jeweils mit amtlicher
Originalposition, Sitzungsnummer und Original-PDF-Seite. Ergebnis:
**4 von 4** lassen sich der bereits datierten Positivstichprobe und
zugleich der bestätigten Acht-Fälle-Vorschau zuordnen.
**Null daraus neu freizugebende Maßnahmen.**

| DIP-Eltern-ID | Person / ursprüngliche Sitzung | Amtliche Ursprungsposition | Beobachtung |
|---|---|---|---|
| [339748](https://dip.bundestag.de/vorgang/339748) | Robin Wagener, 21/097 | [700670](https://search.dip.bundestag.de/api/v1/vorgangsposition/700670) | Bereits bekannt |
| [340146](https://dip.bundestag.de/vorgang/340146) | Roland Theis, 21/099 | [701389](https://search.dip.bundestag.de/api/v1/vorgangsposition/701389) | Bereits bekannt |
| [337160](https://dip.bundestag.de/vorgang/337160) | Martin Sichert, 21/090 | [696896](https://search.dip.bundestag.de/api/v1/vorgangsposition/696896) | Ursprünglich 10.07.2026, später separate Abstimmungsposition |
| [338942](https://dip.bundestag.de/vorgang/338942) | Jürgen Koegel, 21/092 | [699250](https://search.dip.bundestag.de/api/v1/vorgangsposition/699250) | Bereits bekannt |

Die DIP-Elternakte von **Sichert** zeigt als `datum` den **08.09.2026**,
weil sie zusätzlich eine spätere Plenar-Abstimmungsposition
[699168](https://search.dip.bundestag.de/api/v1/vorgangsposition/699168)
enthält. Der individuell entscheidende ursprüngliche
Ordnungsruf-Quellenschritt ist dagegen **21/090 vom 10.07.2026**.
Ein Vergleich nur auf Eltern-Datum würde diesen bekannten Fall irrtümlich
als neu ausweisen. Deshalb verwendet der verfeinerte Crosswalk die
eindeutige amtliche Originalpositions-ID, ursprüngliche Sitzung,
Datum und Titelperson statt des veränderlichen Eltern-Anzeigedatums.

**Unverändert offen:** Ein vollständiger Zeitfenster-Abgleich der
DIP-Metadaten oder eine gefundene Originalposition beweist nicht,
dass sämtliche früheren Fälle oder späteren Aufhebungen bekannt sind.
Neue Hinweise müssen weiterhin mit Quellen und Rechtsfolgen einzeln
abgeglichen werden. Die bisherige Acht-Fälle-Auswahl bleibt
ausdrücklich unvollständig.


## Erstmaliger Vollzeitraum-Liveabgleich (24.10.2026)

[Quellenlauf 40115113903](https://github.com/Erzkon/ordnungsrufe/actions/runs/40115113903)
hat **19.400 DIP-Vorgänge auf 194 vollständig paginierten Seiten**
mit dem amtlichen 21.-WP-Aktualisierungsfilter seit **25.03.2025**
geprüft. **43** Titel deuten außerhalb der 18 fest verankerten
Eltern-IDs auf ursprüngliche Ordnungsruf-Erteilungen. Für alle 43
wurden zusätzlich ihre konkreten amtlichen DIP-Verfahrenspositionen
vollständig je Elternvorgang abgefragt.

- **Sechs** Elternvorgänge sind anhand ihrer ursprünglichen
  Protokollposition in der **bereits bekannten datierten
  24er-Positivstichprobe** und in der bestätigten Acht-Fälle-Vorschau
  wiedergefunden; kein neuer Fall allein wegen anderer DIP-ID.
- **37 weitere DIP-Elternvorgänge** liegen außerhalb dieser datierten
  Stichprobe, mit originaler Erteilungsfundstelle jeweils **2025**.
  Viele überschneiden sich mit älteren separaten Forschungsakten des
  Projekts; es sind keine 37 neu bestätigten Sanktionen.
- Bei **36 von 37** ist eine ursprüngliche DIP-Erteilungsposition
  vorhanden; beim Vorgang **328596 (Keuter, 21/043)** gibt es
  **zwei** amtliche Erteilungspositionen. Der Wortlaut „zwei
  Ordnungsrufe“ in anderen DIP-Titeln ist ebenfalls **kein
  automatischer Beleg zweier selbständiger wirksamer Sanktionen**.
- **Zehn** der 37 Elternvorgänge enthalten insgesamt **elf
  zusätzliche Verfahrenspositionen**. Das sind Metadaten für spätere
  Entscheidungen/Verfahrensschritte, keine automatischen
  Einspruchszurückweisungs- oder Wirksamkeitsfeststellungen.

Die neu ergänzte, ausschließlich unter `.audit/` archivierte
`review_queue.json` / `review_queue.md` stellt solche nicht
durch die datierte Stichprobe bereits zugeordneten DIP-Vorgänge in
**Fünfer-Arbeitsbündeln** bereit: Für diese erste Vollzeitraum-Stichprobe
sind das **37 manuelle Elternvorgangs-Aufgaben in acht Bündeln**,
darunter elf mit besonderem Quellenklärungsbedarf (mehrere
Originalpositionen oder zusätzliche Verfahrensschritte).

Die Queue nimmt nichts in bestätigte CSVs oder öffentliche Statistiken
auf, erzeugt kein Pull-Request-Merge und entscheidet keine Rechtsfolge.
Ein wirklich belastbarer Zählerzuwachs erfordert die Prüfung der
konkreten einzelnen Erteilung, ihrer Unabhängigkeit und all ihrer
späteren möglichen Rechtsfolgen. DIP-Titel allein genügen nicht.

