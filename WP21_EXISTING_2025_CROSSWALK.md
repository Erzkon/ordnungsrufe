# WP21 – 2025er DIP-Entdeckungen gegen vorhandene Quellenakten abgleichen

**Arbeitsstand: 24.10.2026 · ausschließlich nichtzählende Quellenarbeit.**

## Ausgangslage

Der erste vollständig paginierte DIP-Aktualisierungsfilter ab dem
25.03.2025 brachte 19.400 Datensätze und 43 mögliche
Ursprungsvorgänge außerhalb der bereits fest verankerten 18
DIP-Eltern-IDs hervor. Sechs dieser 43 sind der datierten
24er-Positivstichprobe schon quellengebunden zuzuordnen; die übrigen
**37 sind Elternvorgangs-Prüfaufträge, keine bestätigten wirksamen
Ordnungsrufe.**

Diese 37 enthalten **zehn** bereits ausführlich individuell
dokumentierte DIP-Elternakten aus dem älteren 2025er Dossier.
Die neue `wp21_existing_2025_crosswalk.py`-Auswertung verknüpft diese
exakt nach **amtlicher Eltern-ID, Ursprungsdatum, Originalplenum,
vollständigem Namen und Positionen**. Sie verwendet
`wp21_2025_dip_einzelakten.CASES`, die sieben unabhängigen
Original-XML-Anker und die 13 kuratierten Einspruchseinträge aus
`wp21_weitere_einspruchsberichte.py`.

Die restlichen **27 Elternakten** sind *nicht Bestandteil dieses
Zehnerdossiers*. Es wäre jedoch falsch zu behaupten, sie seien
automatisch 27 bislang überhaupt nicht recherchierte Vorgänge:
andere bereits bestehende Projektdateien können Teilquellen enthalten.

## Historisches Zehnerdossier – bekannte Arbeit wiederverwenden

| DIP-ID | Ursprüngliche Person/Sitzung | Originalmaßnahme laut individueller Akte | Getrennte Einspruchszurückweisungen |
|---|---|---:|---:|
| [322353](https://dip.bundestag.de/vorgang/322353) | Stephan Brandner, 21/010 | 1 | 1 |
| [322377](https://dip.bundestag.de/vorgang/322377) | Stephan Brandner, 21/011 | 1 | 1 |
| [322932](https://dip.bundestag.de/vorgang/322932) | Luigi Pantisano, 21/015 | 1 | 1 |
| [326010](https://dip.bundestag.de/vorgang/326010) | Mirze Edis, 21/025 | 1 | 1 |
| [328225](https://dip.bundestag.de/vorgang/328225) | Kay Gottschalk, 21/040 | 2 | 1 |
| [328523](https://dip.bundestag.de/vorgang/328523) | Martin Sichert, 21/040 | 1 | 1 |
| [328224](https://dip.bundestag.de/vorgang/328224) | Steffen Janich, 21/040 | 2 | 2 |
| [328595](https://dip.bundestag.de/vorgang/328595) | Martin Reichardt, 21/043 | 1 | 1 |
| [329445](https://dip.bundestag.de/vorgang/329445) | Stephan Brandner, 21/049 | 1 | 1 |
| [329551](https://dip.bundestag.de/vorgang/329551) | Martin Reichardt, 21/050 | 1 | 1 |
| **Summe** | **10 amtliche Elternakten** | **12 ursprünglich berichtete Erteilungen** | **11 individuell belegte Einspruchszurückweisungen** |

**Diese Summen sind keine bestätigte Gesamtzahl rechtswirksamer
Ordnungsrufe.** Die Anzahl amtlicher Erteilungs-*Positionen* ist auch
nicht zwangsläufig die Anzahl einzelner gesprochener Erteilungen.

Bei **Janich** sind die zwei Einspruchszurückweisungen einzeln
belegt, aber die wortgenaue Original-XML-Stelle der *ersten*
Erteilung bleibt noch ungeklärt. Die zwischenzeitliche bedingte
Androhung darf nicht in eine Erteilung umgedeutet werden.

Bei **Gottschalk** sind zwei ursprüngliche Erteilungen in 21/040
nachvollzogen; der belegte Einspruch aus 21/042 betrifft nur die
*erste*. Das Ausbleiben einer zweiten Abstimmung in der untersuchten
DIP-Elternakte sagt nichts Abschließendes über andere Rechtswege
oder den finalen Status des zweiten Rufs aus.

## Weitere Originalquellen sicher priorisieren

DIP [328596](https://dip.bundestag.de/vorgang/328596) (**Stefan
Keuter, 21/043**) enthält zwei amtliche Original-Verfahrenspositionen.
Das rechtfertigt eine gezielte manuelle Abgrenzung dieser einzelnen
Ordnungsruf-Erteilungen, aber **keine automatische Freigabe von zwei
wirksamen Maßnahmen**.

Die beiden Elternvorgänge [322921](https://dip.bundestag.de/vorgang/322921)
und [322922](https://dip.bundestag.de/vorgang/322922)
beziehen sich beide auf **Martin Reichardt, 21/014 vom 26.06.2025**
und können eine gemeinsame Person-/Sitzungs-/Datum-/Titelidentität
haben. Der Crosswalk kennzeichnet deshalb eine potenzielle
**elternübergreifende Quellenkontext-Kollision**. Beide Eltern-IDs
bleiben für die Einzelbelegprüfung erhalten. Weder werden sie
automatisch zu einer Maßnahme zusammengefasst noch automatisch
als zwei wirksame Maßnahmen addiert.

Weitere Prioritätskriterien: Mehrdeutige Originalpositionen,
weitere amtliche Verfahrensschritte, bereits vorhandene gesonderte
Quellenakten und noch ausstehende Einspruchs-/Rücknahmeentscheidungen.

## Technischer Vertrag

```bash
python -m unittest -v tests.test_wp21_existing_2025_crosswalk
python wp21_existing_2025_crosswalk.py \
  --discovery .audit/wp21_dip_discovery/outside_pins.json \
  --review-queue .audit/wp21_dip_discovery/review_queue.json \
  --output-dir .audit/wp21_dip_discovery/existing_2025_dossiers
```

Ausschließlich `.audit/wp21_dip_discovery/existing_2025_dossiers/`
enthält die zwei neuen Artefakte
`dossier_overlap.json` und `dossier_overlap.md`. Ohne vollständig
abgerufene DIP-Originalpositionen, kohärente Eltern-IDs, validierte
Einspruchsbelege und übereinstimmende Review-Queue wird der Abgleich
abgebrochen.

**Keine Änderung der vier geschützten CSV-/JSON-Zähler, keine
automatische Publikation bestätigter Maßnahmen, kein PR-Merge.**

### Nächster fachlicher Schritt

Die verbleibenden 27 Elternakten gegen sämtliche vorhandenen
Personen-/Sitzungsfallakten auf Quellenbasis zusammenführen,
Prioritätsfälle mit Original-XML-Wortlaut abgleichen und danach
separat Einspruchsfolgen prüfen. Erst tatsächlich abgeschlossene
Einzelakten können mit ausdrücklicher Freigabe in einen
eigenen Statistik-PR übernommen werden.
