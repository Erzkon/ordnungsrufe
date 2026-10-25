# WP21: Rechtsfolgenabgleich für Reichardt/Keuter (DIP 322921, 322922, 328596)

**Stand 24. Oktober 2026 · amtliche Metadaten, individuelle Quellenprüfung,
keine automatische Wirksamkeitsentscheidung.**

## Welche Fälle werden geprüft?

| Amtlicher DIP-Vorgang | Im DIP-Titel genannte Person | Tatsächlicher Originalwortlaut | Amtliche Originalpositionen |
|---|---|---|---|
| [322921](https://dip.bundestag.de/vorgang/322921) | Martin Reichardt | **Stefan Keuter** wird in 21/014, XML-Zeile 5705, ausdrücklich als Empfänger klargestellt; Titel-/Empfängerkonflikt | [672193](https://search.dip.bundestag.de/api/v1/vorgangsposition/672193) |
| [322922](https://dip.bundestag.de/vorgang/322922) | Martin Reichardt | 21/014, XML-Zeile 2311, ursprüngliche Erteilung im unmittelbaren Reichardt-Zwischenrufkontext | [672194](https://search.dip.bundestag.de/api/v1/vorgangsposition/672194) |
| [328596](https://dip.bundestag.de/vorgang/328596) | Stefan Keuter | 21/043, zwei ausdrücklich getrennte Erteilungsformulierungen in XML-Zeilen 2405 und 3495 | [681904](https://search.dip.bundestag.de/api/v1/vorgangsposition/681904), [682732](https://search.dip.bundestag.de/api/v1/vorgangsposition/682732) |

Die wörtlichen Quellen sind bereits in
[WP21_PRIORITY_ORIGINALS.md](WP21_PRIORITY_ORIGINALS.md) erläutert.
Ein DIP-Elternvorgang entspricht nicht zwingend einer einzigen
individuellen Erteilung; die vier amtlichen *Positions-IDs* sind auch
nicht automatisch vier rechtswirksame Maßnahmen.

## Neue unabhängige Überwachung

`wp21_priority_later_effects.py` ruft **alle** amtlich paginierten
Verfahrenspositionen der **drei exakt festgelegten DIP-Eltern-IDs**
erneut von der offiziellen API ab. Der Bericht verwirft Dubletten,
fremde oder fehlende Positionen, falsche Tage/Sitzungen und veränderte
amtliche Original-PDF-Fundstellen.

Zusätzliche Positionen innerhalb einer solchen Elternakte werden
getrennt mit Position, Verfahrensart, Datum, Plenarsitzung,
amtlichem Beschlusstenor und möglichen Rechtsfolge-Signalen
archiviert, **nicht** automatisch als akzeptierter oder
zurückgewiesener Einspruch bewertet. Insbesondere ist auch ein
Protokoll mit dem Wort „Abstimmung“ nicht schon die endgültige
Wirksamkeitsfreigabe einer individuellen Maßnahme.

Ein zweiter Abgleich verwendet die bereits vollständig paginierte
aktuelle DIP-Vorgangs-Discovery in
`.audit/wp21_dip_discovery/outside_pins.json`. Er sammelt
**nur** andere Elternvorgänge, deren Titel den vollständigen Namen
Martin Reichardt oder Stefan Keuter tragen. Für jeden Hinweis wird
zwischen einer getrennten Sanktion (Ordnungsgeld), einem
Rechtsfolgen-Schlüsselwort oder einer bloßen namensgleichen
Originalakte unterschieden.

**Wichtige Einschränkung:** Die Discovery ist selbst ein
schlüsselwortgefilterter Ausschnitt **außerhalb der bisherigen 18
verankerten Eltern-IDs** und wird nach DIP-Aktualisierungsdatum
begrenzt. Auch ein vollständiger Aktualisierungsfilter über die
gesamte Wahlperiode beweist keine Vollständigkeit über alle
anderen Verfahren, Gerichtsdokumente oder späteren Rechtsfolgen.
Eine andere Eltern-ID mit demselben Namen ist keine automatische
Zuordnung zum jetzt geprüften Original.

## Getrennte bereits bekannte Einspruchsquellen

Die amtlich quellengeprüften 13 zusätzlichen Einspruchsbelege und
vier weiteren Hochprioritäts-Beschlüsse werden nochmals gegen
**Ursprungsdatum und Person bzw. ursprüngliche Sitzung** geprüft.
Insbesondere die unabhängig dokumentierten
[Reichardt-Einsprüche zum 26. November 2025](https://www.bundestag.de/dokumente/textarchiv/2025/kw48-de-einspruch-ordnungsruf-2-1128096)
und [18. Dezember 2025](https://www.bundestag.de/dokumente/textarchiv/2025/kw51-de-einspruch-ordnungsruf-2-1134402)
betreffen andere Ursprungsmaßnahmen und dürfen nicht auf
Reichardt im Juni 2025 übertragen werden.

Das offiziell belegte
[Ordnungsgeld gegen Reichardt vom 15. Oktober 2026](https://www.bundestag.de/dokumente/textarchiv/2026/kw42-de-einspruch-ordnungsgeld-1225202)
ist **kein Ordnungsruf** und bleibt als ausdrückliche Negativkontrolle
ausgeschlossen.

## Historischer Ausgangsstand

Der erfolgreiche, vollständig paginierte
[Workflow 40115113903](https://github.com/Erzkon/ordnungsrufe/actions/runs/40115113903)
hat vom 25. März 2025 bis zum 24. Oktober 2026 rund **19.400 DIP-Vorgänge
auf 194 Seiten** überprüft. In der damaligen amtlichen
Elternpositionssicht enthielten alle drei jetzt priorisierten
Elternvorgänge ausschließlich ihre ursprünglichen vier
Quellpositionen und **keine zusätzliche Position innerhalb
dieser drei Elternvorgänge**.

Das ist eine **zeitlich begrenzte Quellenaussage**, nicht „kein
Einspruch eingelegt“ und nicht „Ruf endgültig wirksam“.
Sie wird durch die neue Live-Quellenprüfung aktualisiert.

## Ausführung und unveränderbare Schutzregeln

```bash
python -m unittest -v tests.test_wp21_priority_later_effects
python wp21_priority_later_effects.py \
  --original-scout .audit/wp21_priority_originals/original_contexts.json \
  --discovery .audit/wp21_dip_discovery/outside_pins.json \
  --output-dir .audit/wp21_priority_later_effects
```

Ausgaben sind ausschließlich
`.audit/wp21_priority_later_effects/priority_later_effects.json`
und `priority_later_effects.md`. Sie enthalten keine
automatisch bestätigten, aberkannten oder veröffentlichten
Ordnungsrufe. Fehlgeschlagene API-Abfragen dürfen nicht als
vollständige negative Suchergebnisse gespeichert werden.

Die geschützten CSV-/JSON-Dateien für WP20 und WP21 werden nach
dieser Prüfung wie bisher byteweise und per SHA256 verglichen.
**PR #10 wird ohne gesonderte Freigabe nicht gemergt.**

## Fachlich als Nächstes

- Externe und später veröffentlichte Einsprüche/Mitteilungen zu
  Reichardt Juni 2025 sowie Keuter Juni und November 2025
  einzeln quellenkritisch zuordnen.
- Falls echte Entscheidungspositionen auftauchen: Wortlaut,
  ursprüngliche **einzelne** Erteilung und Entscheidungstenor
  aus dem Originalprotokoll abgleichen.
- Erst nach vollständiger separater Einzelfall- und
  Rechtsfolgenprüfung über mögliche statistische Freigabe entscheiden.


## Ergebnis der ersten Live-Abgleiche vom 24.10.2026

Die [erste Echtzeitprüfung](https://github.com/Erzkon/ordnungsrufe/actions/runs/40127706929)
hat **alle drei offiziellen DIP-Elternakten** und ihre vollständigen
Positionenlisten frisch eingelesen: **322921: 1 Original/0 weitere
Positionen**, **322922: 1/0**, **328596: 2/0**.
Der Testlauf bestand **94 spezialisierte Python-Tests** und prüfte
die vier geschützten CSV-/JSON-Zählerdateien bytegleich.

Ein zusätzlich ausgeführter [historischer Live-Abgleich ab
25.03.2025](https://github.com/Erzkon/ordnungsrufe/actions/runs/40127919630)
hat die drei Eltern erneut exakt gleich vorgefunden und unter den
namentlich gefilterten, übrigen DIP-Elternakten **sieben** weitere
Metadatenquellen gefunden: **sechs** andere ursprüngliche
Reichardt-Ordnungsruf-Elternvorgänge (**323646, 325925, 328036,
328595, 329551, 334727**) sowie das getrennte **Ordnungsgeld
340550**. **Keiner dieser sieben Vorgänge ist ein individueller
Beleg für eine Einspruchsentscheidung zu 322921, 322922 oder 328596.**

Das ist ausdrücklich **keine abschließende Negativauskunft**:
Der Discovery-Filter berücksichtigt nur bestimmte DIP-Titel/
Abstract-Schlüsselwörter und ist auf Vorgänge außerhalb
der bisher kuratierten 18 Eltern-IDs eingeschränkt. Auch eine über
die ganze laufende Wahlperiode vollständig paginierte
Aktualisierungsabfrage ersetzt keine Prüfung anderer
parlamentarischer Verfahren oder gerichtlicher Unterlagen.

### Automatische Warnungen – nur bei künftig tatsächlich neuen Quellen

Der zusätzliche Bericht `priority_review_alerts.json` archiviert
*nichtzählende* manuelle Quellenhinweise. Eine Benachrichtigung
kommt nach einer später **separat genehmigten Merge-Freigabe** nur
im geplanten Lauf infrage, falls entweder eine neue amtliche
Verfahrensposition bei einer der drei Eltern-IDs erscheint oder
ein anderer namensgleicher DIP-Elternvorgang ausdrücklich ein
einspruchs-/rechtsfolgenbezogenes Stichwort im Titel trägt.

Namensgleiche ursprüngliche Erteilungsakten oder Ordnungsgelder
erzeugen **keinen solchen Einspruchs-Alarm**. Eine Prüfung erfolgt
über ein stabiles Prüfhash im vorhandenen GitHub-Issue; es wird
nicht bei jedem Lauf ein Duplikat eröffnet. Pull Requests erstellen
keine Issues und verändern keine bestätigten Zähler.

Auch ein leerer Quellenalarm bleibt im Schema als
`absence_of_hints_means_no_appeal=false` kodiert.


## Zweite Suchlinie ohne den Begriff Ordnungsruf (25.10.2026)

Die bisherige DIP-Ursprungsprüfung hatte eine lexikalische
**Blindstelle**: `relevant_item()` berücksichtigt nur Titel und
Kurzbeschreibungen mit „Ordnungsruf“, „Ordnungsgeld“ oder
„Ordnungsmaßnahme“. Separat veröffentlichte Rechtsmittelverfahren
ohne diese Wörter fielen deshalb durch das Raster.

Der bestehende vollständig paginierte DIP-Abruf wird nun ein
**zweites Mal ohne diesen Wortfilter** auf die Kombination aus
*vollständigem Namen* (**Martin Reichardt**, **Stefan Keuter**) und
einem **Rechtsfolgen-/Verfahrensbegriff** geprüft, u.a. Einspruch,
Beschwerde, Widerspruch, Rücknahme, Zurückweisung und Aufhebung.
Es erfolgt **kein zusätzlicher amtlicher API-Abruf**, sondern die
bereits vollständig heruntergeladenen DIP-Datensätze werden
quellenkritisch erneut ausgewertet.

Die daraus resultierenden, gesondert gezählten Quellenhinweise
liegen unter
`outside_pins.json → unfiltered_priority_procedure_parents`,
inklusive amtlicher Eltern-ID, unveränderter Quellen-URL,
Aktualisierungsdatum und Titel/Auszug. Im Quellenbericht
`priority_later_effects.json` werden sie **zusätzlich**, ohne die
ursprünglichen 18/43/37 Erteilungs-IDs oder frühere
Zähldaten zu verändern, als manuelle potenzielle
Rechtsfolgenhinweise ausgegeben.

**Grenzen:** Ein gleichlautender Personenname mit dem Wort
„Einspruch“ im selben DIP-Vorgang ist weder ein Beweis, dass die
hier untersuchte Erteilung angegriffen wurde, noch ein Beweis
über das Ergebnis. Fälle ohne ausgeschriebenen vollständigen Namen,
außerhalb des DIP, ohne Rechtsfolgenvokabular oder ohne Bezug zum
Aktualisierungsfenster bleiben in dieser Suche unentdeckt.
Leere Trefferlisten bedeuten ausdrücklich nicht Einspruchsfreiheit.

### Erstes echtes Zeitfenster

[Liveprüfung 40207457951](https://github.com/Erzkon/ordnungsrufe/actions/runs/40207457951):
**6.184 vollständig paginierte DIP-Datensätze auf 62 Seiten** im
45-Tage-Aktualisierungsfenster, **null** zusätzliche
vollnamige Verfahrensquellen ohne Ordnungsruf-Wort.
**101 spezialisierte Regressionstests bestanden.**
Der vollständige historische Gegenlauf wird gesondert berichtet.

### Zusätzlicher amtlicher Vergleichsfall außerhalb der Prioritätsakten

Der [Bundestagsbericht vom 20.03.2026](https://www.bundestag.de/dokumente/textarchiv/2026/kw12-de-einspruch-ordnungsruf-1156828)
und das
[amtliche Protokoll 21/066](https://www.bundestag.de/resource/blob/1155780/amtpr21066.pdf)
belegen eine Einspruchszurückweisung gegen einen **Reichardt-Ordnungsruf
vom 19.03.2026**. Dieser geprüfte weitere Fall ist
**nicht** identisch mit Reichardts ursprünglicher Erteilung vom
**26.06.2025**. Das zusätzliche amtliche Dokument ist im
Rechtsfolgenbericht als eigene unabhängige Negativkontrolle
hinterlegt und gehört **nicht** zu einer automatischen Erhöhung
der zwölf älteren Erteilungen oder zu den geschützten Zählern.

