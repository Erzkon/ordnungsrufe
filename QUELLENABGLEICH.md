# Quellenabgleich · 20. Wahlperiode

**Datenstand: 14. Oktober 2026. Status: vorläufiger personenbezogener Abgleich.**

Die statische Website veröffentlicht **135 einzeln belegte wirksame personenbezogene Ordnungsrufe** aus der 20. Wahlperiode (2021–2025), zusammengestellt aus 214 Plenarprotokollen, einzeln geprüften Ereignissen und ergänzenden DIP-Belegen. Zwei nachträglich zurückgenommene Ordnungsrufe sind nicht enthalten. Die neue veröffentlichte Website nutzt den unveränderlichen Arbeits-Snapshot unter [`daten/wirksame_ordnungsrufe_20wp.csv`](daten/wirksame_ordnungsrufe_20wp.csv) und den zugehörigen [`Korrekturbericht`](daten/korrekturbericht_20wp.json).

## Abgleich mit veröffentlichten Angaben

| Zahl | Belegte Projektstatistik | Veröffentlichte Angabe |
|---|---:|---:|
| Wirksame Maßnahmen insgesamt | 135 | 135 |
| Stephan Brandner | 20 | 20 |
| Beatrix von Storch | **18** | **19** |

Der Bundestag nennt in seiner [historischen Darstellung](https://www.bundestag.de/dokumente/textarchiv/1949-09-20-ordnungsruf-1086652) die Gesamtzahl 135 sowie die personenbezogenen Zahlen 20 (Brandner) und 19 (von Storch). Das [Datenhandbuch, Kapitel 7.16](https://www.bundestag.de/resource/blob/196296/08d0a21670ca40e45ecfdb242d119d58/Kapitel_07_16_Ordnungsma__nahmen-data.pdf) weist zwei später zurückgenommene Maßnahmen gesondert aus.

Eine [RND-Veröffentlichung vom 22. März 2025](https://www.rnd.de/politik/mehr-ordnungsrufe-denn-je-im-bundestag-eine-fraktion-treibt-es-besonders-uebel-S7XBX3ONJJEL3E6NLP2NSKWOB4.html) nennt unter Berufung auf die Bundestagsverwaltung folgende Aufteilung: AfD 85, fraktionslos 13, SPD 11, Grüne 7, Linke 6, CDU/CSU 4, FDP 2 und BSW 8. Diese Angaben ergeben addiert **136** und widersprechen deshalb der gleichzeitig genannten Gesamtsumme von 135. Unsere 135 Einzelbelege zählen 84 AfD-Maßnahmen; die übrigen Gruppenzahlen sind deckungsgleich. Das beweist keinen amtlichen Zählfehler, dokumentiert aber einen offenen Widerspruch in veröffentlichten Zahlen.

## Noch offener DIP-Sonderfall

- Am **30. März 2023 (Sitzung 20/094)** wurde gegen Beatrix von Storch eine Ordnungsmaßnahme zunächst lediglich **vorbehalten**. Ein in derselben Sitzung unmittelbar erteilter Ordnungsruf betraf **Fabian Jacobi**. [Protokoll 20/094](https://dserver.bundestag.de/btp/20/20094.pdf).
- Am **31. März 2023 (Sitzung 20/095)** wurde gegen von Storch wegen der Äußerung vom Vortag ein **nachträglicher Ordnungsruf erteilt**. [Protokoll 20/095](https://dserver.bundestag.de/btp/20/20095.pdf#page=25).
- Die DIP-Daten enthalten zu den Sitzungen zwei entsprechende Vorgangskennungen ([298177](https://dip.bundestag.de/vorgang/298177) und [298160](https://dip.bundestag.de/vorgang/298160)). **Zwei DIP-Vorgänge belegen hier nicht zwei getrennte tatsächlich erteilte Ordnungsrufe.**

Die Website zählt deshalb aus diesem Zusammenhang nur die konkret nachgewiesene Vergabe. Die personenbezogene Differenz bleibt gekennzeichnet, bis sie sich anhand einer unabhängigen, belastbaren Quelle auflösen lässt. Es wird kein erfundener Ausgleichseintrag aufgenommen.

## Zählregeln

1. Zähleinheit ist eine **wirksame personenbezogene Maßnahme** (nicht die Anzahl der Texttreffer oder DIP-Metadatensätze). Ein gemeinsamer Vorgang mit mehreren Empfängern kann deshalb mehrere Personenmaßnahmen ergeben.
2. Maßgeblich ist die **historische Fraktions- oder Gruppenzugehörigkeit** zum Zeitpunkt der Vergabe. Im Fraktionsranking werden *Die Linke* und *Die Linke (Gruppe)* gemeinsam dargestellt; in der Tabelle werden sie unterschieden.
3. Einträge haben jeweils eine **PDF-Fundstelle in den amtlichen Plenarprotokollen**. Die Liste der Maßnahmen wird nicht automatisch auf amtliche Summen aufgefüllt.
4. Der Website-Datensatz ist derzeit ein **versionierter, lokal gegen den Korrekturbericht geprüfter Snapshot**, keine Live-Synchronisation mit dem Bundestag. Änderungen an Ausgangsdaten erfordern einen neu geprüften Export und einen neuen Commit.

Dieses Projekt ist **unabhängig und nicht vom Deutschen Bundestag betrieben**.
