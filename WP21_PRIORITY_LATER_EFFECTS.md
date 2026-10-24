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
