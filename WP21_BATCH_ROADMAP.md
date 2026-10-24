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


## Zweites Fünferbündel: fünf weitere Originalerteilungen quellenkritisch überprüft

Im zweiten Bearbeitungsbündel sind nun auch **Reichinnek (21/053),
Baumann (21/057), von Zons (21/061), Pantisano (21/065) und Gebel
(21/067)** anhand der ursprünglichen PDF-Seiten nachgewiesen.
Die exakten Originalseiten und jeweiligen Kontexte stehen in
`WP21_BATCH_2_ORIGINALNOTIZEN.md` und in dem neuen nichtzählenden
`wp21_five_origins.py`-Bericht.

Damit sind in diesem Durchgang **acht bisher offene Fälle** auf
Original-PDF-Seiten erneut geprüft; bei drei davon liegt zusätzlich
ein Original-Protokollabgleich der parlamentarischen Zurückweisung vor.
Bei den fünf neuen Fällen ist der spätere individuelle
Einspruchs-/Aufhebungs-/Wirksamkeitsstatus **ausdrücklich ungeprüft**.
Es wurden weder weitere bestätigte Maßnahmen noch Veränderungen am
geschützten Acht-Fälle-Teilbestand erzeugt.


## Fünf spätere Rechtsfolgenfälle jetzt als präziser DIP-Abgleich (21.10.2026)

Die fünf bereits originalbelegten Fälle erhalten eigenständige amtliche
DIP-Vorgangs-IDs und eine **gezielte frische Live-Prüfung nur dieser fünf
Vorgänge und ihrer vollständigen Verfahrenspositionen**, ohne die gesamte
WP21-DIP-API ständig neu abzufragen. Das neue
`wp21_five_rechtsfolgen.py` vergleicht sie zusätzlich mit der begrenzten
Sammlung von **13 weiteren und vier zuvor separat geprüften
Einspruchszurückweisungen**. Nur ein exaktes Person- und Ursprungsdatum-
Paar ist zuordenbar; der Pantisano-Einspruch aus Juni **2025** darf
nicht zum Pantisano-Ordnungsruf aus März **2026** wechseln.

Ein Name als bloße Erwähnung in einem anderen Bundestagsbericht
(z. B. Kathrin Gebel in der Entscheidung über Przygodda oder über
Reichardts späteres Ordnungsgeld) ist **kein Beleg, dass gegen Gebel
ein Einspruch entschieden wurde**. Ein alter Baumann-Einspruch aus der
19. Wahlperiode ist ebenso keine Rechtsfolge aus 21/057.

**Negative Feststellung verboten:** Weder das Fehlen eines
Einspruchs in diesen 17 Berichten noch eine DIP-Positionenliste ohne
Abstimmung schließt weitere Einsprüche, Korrekturen, spätere
Rücknahmen oder Verfahrenshandlungen außerhalb dieses einzelnen
Originalvorgangs aus. Der Workflow archiviert
`later_effects.json` / `later_effects.md` gesondert unter
`.audit/wp21_five_later_offline/` und `.audit/wp21_five_later_live/`.
Vollständig abgefragte DIP-Positionen sind **Quellenmetadaten**,
nicht bestätigte rechtswirksame Maßnahmen.


## Weiterführender Quellenabgleich: alle 17 bekannten DIP-Ursprünge

Die bisherigen fünf einzeln verankerten, live abgefragten DIP-Ursprungsvorgänge
werden nun mit **12 weiteren bereits am 16. Oktober amtlich festgestellten
Original-DIP-Vorgangs-IDs** kombiniert. Der separate Python-Baustein
`wp21_all17_followups.py` prüft dafür die Daten des 15.10.-Teilsnapshots,
die amtlichen Person-/Sitzungsschlüssel, Original-XML-Fundstellen und
die exakte Zugehörigkeit aller 17 verschiedenen DIP-IDs.

Der neue GitHub-Workflow-Schritt ruft den vollständigen
**Positionssatz dieser zusätzlichen zwölf Ursprungsvorgänge** ab und
verwendet im selben Lauf das bereits erneuerte Fünfer-Quellenartefakt.
Nur wenn beide Gruppen vollständig, widerspruchsfrei und zeitnah
vorliegen, wird der Bericht `all_17_pinned_parents_refreshed` gesetzt.
Jede Position jenseits der ursprünglichen Erteilung ist ausschließlich
ein **Hinweis für individuelle Prüfung**. Die Zahl der zusätzlichen
Verfahrenspositionen belegt weder die Zahl der Einsprüche noch
die Zahl der endgültig wirksamen Ordnungsrufe.

**Ziel:** alle bekannten Fälle an einer Stelle priorisieren und
die eigentliche Quellen- und Rechtsfolgenrecherche bündeln, statt
immer wieder bekannte Metadaten einzeln aufzusuchen.

Die genaue Durchführung, Beweisgrenzen und Workflow-Artefakte sind
in `WP21_ALL17_DIP_REVIEW.md` dokumentiert. Für die produktive
wöchentliche Ausführung ist eine spätere ausdrückliche Merge-Freigabe nötig.


## Nächster Quellenbereich: DIP-Vorgänge außerhalb der 18 bekannten Eltern-IDs (24.10.2026)

Das read-only Modul `wp21_new_dip_candidates.py` gleicht die
**vollständig paginierten amtlichen DIP-Vorgänge eines ausgewiesenen
Aktualisierungsfensters** mit den 18 fest verankerten DIP-Eltern-IDs ab.
Es erzeugt getrennte Listen mit möglichen ursprünglichen
Erteilungs-Metadaten und sonstigen Einspruchs-, Ordnungsgeld- oder
Ordnungsruf-Bezügen.

Die Einstufung ist **nur ein Recherchefilter**. Nicht verankerte
DIP-IDs können insbesondere auch bekannte Maßnahmen der acht
bestätigten Beispiele oder der datierten 24er-Stichprobe enthalten.
Ein vorsichtiger Abgleich gegen Person und Ursprungsdatum weist auf
mögliche Überschneidungen hin, dedupliziert aber nicht rechtsverbindlich.

Ein wöchentlicher 45-Tage-Liveabgleich sowie ein monatlicher
Vollzeitraum-Abgleich am ersten Montag werden erst nach späterer
ausdrücklicher Merge-Freigabe auf `main` produktiv. Auf PRs
erfolgt lediglich die read-only-Liveprobe, die Daten landen
ausschließlich unter `.audit/`. Sämtliche bestätigten
Statistikdateien und individuellen Rechtsfolgen bleiben unverändert.

Methodik, Grenzen und lokale Tests: [WP21_DIP_DISCOVERY.md](WP21_DIP_DISCOVERY.md).
