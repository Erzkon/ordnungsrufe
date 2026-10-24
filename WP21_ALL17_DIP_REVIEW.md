# WP21 – DIP-Metadaten für alle 17 bekannten offenen Originalfälle

**Arbeitsstand: 24. Oktober 2026.**

Die datierte amtliche DIP-Positivstichprobe vom **15.10.2026** enthält
24 Person-/Sitzungskombinationen und 25 ursprünglich berichtete
Ordnungsruf-Erteilungen. Acht sind im bestätigten, **unvollständigen**
WP21-Beispielbestand einzeln dokumentiert. Für die übrigen
**17 Person-/Sitzungskombinationen** sind amtliche individuelle
DIP-Original-Vorgangs-IDs und 21 kuratierte Original-XML-Fundstellen im
größeren 18er-Quellenpaket bekannt.

## Neue Abdeckung

Die bereits bestehende Prüfung von fünf ursprünglichen Fällen
(Reichinnek, Baumann, von Zons, Pantisano und Gebel) ruft jede
DIP-Elternakte samt all ihren paginierten Verfahrenspositionen ab.

Ein zweites, nun angebundenes Skript erfasst die **restlichen zwölf**
Ursprungsvorgänge anhand der amtlichen, zuvor fest verifizierten IDs.
Dazu zählen auch die ausgesprochen schwierigen Fälle Frohnmaier und
Reichardt mit mehreren gesprochenen Erteilungsformulierungen.
Für die vier bereits quellenkritisch gesondert dokumentierten
Einspruchsentscheidungen wird die Zuordnung beibehalten,
aber nicht als neue Sanktion interpretiert.

Erst wenn die zwölf neuen und fünf bestehenden, nach Personen,
Originalsitzung, Erteilungsdatum, Quelle und Elternvorgang
streng verknüpften Abfragen im **selben Workflow** erfolgreich sind,
wird der technische Status `all_17_pinned_parents_refreshed`
ausgegeben. Die Fünfer- und Zwölfer-Ergebnisse müssen maximal eine
Stunde auseinanderliegen; widersprüchliche oder fehlende DIP-Fundstellen
stoppen den Vorgang. Beide Rohberichte bleiben separat erhalten.

## Beweisgrenzen

- Die Zahl **17** bezieht sich nur auf diese eingefrorene Stichprobe
  und ist **kein gegenwärtiger Gesamtstand** aller Ordnungsrufe der WP21.
- Eine `Abstimmung`-Verfahrensposition belegt nicht alleine
  eine Zurückweisung oder die Wirksamkeit einer Maßnahme.
- Die vollständigen Verfahrenspositionen von **einem Original-DIP-Vorgang**
  schließen weitere gesonderte parlamentarische Vorgänge, Gerichtsverfahren
  oder spätere Rücknahmen **nicht** aus.
- **Null neue automatische Zählerfreigaben und null
  Änderungen an vier bestätigten CSV-/JSON-Statistikdateien.**
- Die bereits geprüften acht WP21-Beispiele bleiben ausdrücklich
  unvollständig. Die elf historischen Rechtsfolgen- und
  Datenschutzgrenzen aus den Fallakten werden beibehalten.

## Ausgaben

```bash
python wp21_all17_followups.py --offline
python wp21_all17_followups.py \
  --five-live-report .audit/wp21_five_later_live/later_effects.json
```

Ausschließlich `.audit/wp21_all17_offline/` und
`.audit/wp21_all17_live/` werden im PR-Workflow beschrieben.
Die Reports `all17.json` und `all17.md` werden getrennt archiviert.
Kein produktiver Datenexport wird dadurch verändert.

**Nächster Schritt:** Unter den neu sichtbaren positionsgebundenen
Rechtsfolgenhinweisen diejenigen mit unabhängig überprüfbarer
Abstimmungs-/Entscheidungsquelle priorisieren. Parallel weitere,
im datierten DIP-Snapshot noch **nicht enthaltene** Quellen suchen,
ohne deren Fund automatisch als Sanktion zu zählen.


## Weitere Quellenpositionen nur dann als „neu“ melden, wenn sie nicht bereits überprüft sind

Eine rein technische Änderung macht die Live-Abfrage noch nicht nützlich:
die 17 bekannten Original-DIP-Vorgänge umfassen bereits **vier einzeln
kuratierte Einspruchsabstimmungspositionen** zu Reichardt, Hess,
Przygodda und Fahl. Diese vier sind trotz zusätzlicher DIP-Metadaten
**keine neuen Fälle**.

Deshalb unterscheidet die erweiterte Auswertung nun zwischen
`already_curated_vote_metadata_positions` und
`new_uncurated_procedure_position_hints`.
Eine Abstimmungsposition gilt nur als *bereits kuratiert*, wenn
Person/Sitzung, amtliches Abstimmungsdatum und ausgewiesener
Beschlusstenor auf die schon unabhängig dokumentierte Zurückweisung
passen. Fehlt einer dieser Nachweise, landet die Position in der
**manuellen** Prüfqueue.

Nach später genehmigtem Merge verwendet der wöchentliche,
`main`-exklusive Issue-Melder diese **nicht kuratierten** Positionen
aller 17 Ursprungsvorgänge. Bei null neuen Hinweisen legt er
**kein neues Issue** an; identische unveränderte Hinweislisten
werden anhand eines stabilen Hashes dedupliziert.
Jeder neue Treffer bleibt eine manuelle Rechercheaufgabe,
niemals eine automatisch bestätigte Sanktion.

Das ist weiterhin nur ein **sicher begrenzter 17-Fälle-Monitor**:
ein völlig neuer WP21-DIP-Ursprungsvorgang außerhalb der bekannten
Stichprobe ist hiervon noch nicht abgedeckt.
