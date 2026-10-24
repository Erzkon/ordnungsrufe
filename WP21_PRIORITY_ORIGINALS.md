# WP21/014 und WP21/043: Reichardt und Keuter – Original-XML-Arbeitsakte

**Stand: 24.10.2026 | Nur amtliche Quellenprüfung, keine automatische Zählung.**

## Ausgangsbelege aus vollständiger DIP-Verfahrenspositionsabfrage

| Ursprung | DIP-Elternvorgang | DIP-Verfahrensposition | Amtliche Ursprungsfundstelle |
|---|---|---|---|
| Reichardt, 26.06.2025, 21/014 | [322922](https://dip.bundestag.de/vorgang/322922) | [672194](https://search.dip.bundestag.de/api/v1/vorgangsposition/672194) | [Plenar-PDF S. 1133](https://dserver.bundestag.de/btp/21/21014.pdf#P.1133) |
| Reichardt, 26.06.2025, 21/014 | [322921](https://dip.bundestag.de/vorgang/322921) | [672193](https://search.dip.bundestag.de/api/v1/vorgangsposition/672193) | [Plenar-PDF S. 1221](https://dserver.bundestag.de/btp/21/21014.pdf#P.1221) |
| Keuter, 26.11.2025, 21/043 | [328596](https://dip.bundestag.de/vorgang/328596) | [681904](https://search.dip.bundestag.de/api/v1/vorgangsposition/681904) | [Plenar-PDF S. 4996](https://dserver.bundestag.de/btp/21/21043.pdf#P.4996) |
| Keuter, 26.11.2025, 21/043 | [328596](https://dip.bundestag.de/vorgang/328596) | [682732](https://search.dip.bundestag.de/api/v1/vorgangsposition/682732) | [Plenar-PDF S. 5015](https://dserver.bundestag.de/btp/21/21043.pdf#P.5015) |

Die Reichardt-Positionen gehören **zwei eigenständigen DIP-Elternvorgängen**
an; die Keuter-Positionen dagegen **einem einzigen Elternvorgang**.
Keines dieser Merkmale erlaubt allein eine Zahl unabhängiger
rechtswirksamer Maßnahmen.

## Automatisierte erste Original-XML-Sichtung

`wp21_priority_xml_scout.py` ruft die amtlichen XML-Originale
[21/014](https://dserver.bundestag.de/btp/21/21014.xml) und
[21/043](https://dserver.bundestag.de/btp/21/21043.xml) ab und
überprüft ihre Sitzung und Tagesidentität mit der unabhängig
erhobenen DIP-Stichprobe.

Sie extrahiert **echte gesprochene Absätze** aus
`<sitzungsverlauf>`, nicht Tagesordnung, Anhang oder beliebige
Erwähnungen im XML. Jede Ordnungsruf-Fundstelle erhält eine
XML-Zeilennummer, den SHA256 des tatsächlichen Absatzes,
Quellenlink und vorläufige Klassifikation. Die jeweils fünf vorherigen
und nachfolgenden gesprochenen Absätze werden nur dann als
Überprüfungskontext mitgespeichert, wenn sich dort der relevante
Name Reichardt oder Keuter befindet.

Die Ausgaben sind die **nichtzählenden** GitHub-Actions-Artefakte
`.audit/wp21_priority_originals/original_contexts.json` und
`original_contexts.md`. Die Aufzeichnung wird nie in
`daten/wirksame_ordnungsrufe_21wp.csv` oder öffentliche JSONs
übernommen.

```bash
python -m unittest -v tests.test_wp21_priority_xml_scout
python wp21_priority_xml_scout.py \
  --output-dir .audit/wp21_priority_originals
```

## Voraussetzungen einer wirklichen Original-Erteilungskontrolle

Für jede der vier amtlichen Positionsquellen ist anschließend
individuell zu prüfen:

- Welche **genaue** aktuelle Erteilungsformulierung steht im amtlichen
  Originalabsatz – und welcher **namentlich eindeutig identifizierten**
  Person wird sie zugeschrieben?
- Ist es eine tatsächliche Erteilung, statt einer bedingten Androhung,
  einem historischen Hinweis oder einer späteren Einspruchsentscheidung?
- Liegen zwei Erteilungen auf **verschiedenen Originalabsätzen** vor,
  oder liegen zwei DIP-Datensätze für denselben Vorgang/Wortlaut vor?
- Stimmen Sitzung, Datum und erforderlichenfalls die PDF-Seite mit
  der amtlichen Verfahrensposition überein?
- Sind spätere Einsprüche, Rücknahmen, Plenarentscheidungen und andere
  Rechtsfolgen unabhängig überprüft?

Eine zutreffende Erteilungsstelle ist **notwendig**, aber für die
Bestätigung einer endgültig rechtswirksamen Maßnahme allein
**nicht hinreichend**. Eine fehlende Rechtsfolgenposition im jeweiligen
DIP-Elternvorgang ist kein abschließender Negativbeweis.

## Sicherheitsvorgaben

Das Modul lässt vor der originalen Quellenprüfung keine neue bestätigte
Maßnahme zu. Auch nach positivem Absatzfund bleiben
`confirmed_independent_new_grants=0`,
`automatically_confirmed_effective_sanctions=0` und
`protected_statistics_changed=false`. Die tatsächlichen
Erteilungsstellen werden in separaten Fallakten überprüft; rechtliche
Wirksamkeit und statistische Freigabe bleiben einem ausdrücklich
kontrollierten Prozess vorbehalten.

## Ergebnis der erstmaligen gesonderten Original-XML-Prüfung (24.10.2026)

Der amtliche Live-Scan der vollständigen Sitzungs-XMLs hat die folgenden
**einzeln am gesprochenen Originalwortlaut und der unveränderten XML-Zeile**
verorteten Angaben geliefert. Die unabhängige Kontrolle erfolgt im
neuen Modul `wp21_priority_xml_verify.py`, das elf genaue
Original-/Negativtexte prüft.

| Sitzung | Original-XML-Zeile | Aussage und fachliche Grenze |
|---|---:|---|
| 21/014 | **2311** | Aktuelle Erteilung durch die Vorsitzende nach dem Zwischenruf „Schwätzer“; [PDF-Seite 1133](https://dserver.bundestag.de/btp/21/21014.pdf#P.1133) ordnet den Zwischenruf Reichardt zu |
| 21/014 | **5693** | Vorsitzende benennt den Ordnungsruf, erklärt aber ausdrücklich, den Rufer noch nicht sicher zu kennen; keine vorgezogene Personenfreigabe |
| 21/014 | **5705** | Spätere ausdrückliche Klarstellung: **Empfänger Keuter**. Dadurch gerät die Zuordnung des auf [PDF 1221](https://dserver.bundestag.de/btp/21/21014.pdf#P.1221) verweisenden DIP-Titels **322921 (Reichardt)** in Konflikt mit dem Originalprotokoll |
| 21/014 | **5779** | Nur Androhung eines weiteren späteren Ordnungsrufs; nicht zählen |
| 21/043 | **2393** | Bloß theoretischer Ordnungsruf, der an dieser Stelle gerade **nicht** erteilt wird |
| 21/043 | **2396** | Tatsächliche Erteilungsformulierung an **Reichardt** (anderer Quellenfall) |
| 21/043 | **2405** | Aktuelle Erteilungsformulierung an Keuter; das nachfolgende Protokoll identifiziert den Empfänger ausdrücklich |
| 21/043 | **2418** | Nachträgliche ausdrückliche Klarstellung, dass die zweite in dieser Sequenz ausgesprochene Maßnahme an **Keuter** ging; das ist **nicht** bereits Keuters späterer zweiter Ordnungsruf |
| 21/043 | **3495** | **Weitere aktuelle Erteilungsformulierung an Keuter**, ausdrücklich als dessen zweiter Ordnungsruf bezeichnet; [PDF-Seite 5015](https://dserver.bundestag.de/btp/21/21043.pdf#P.5015) |
| 21/043 | **3493/3497** | Andere bzw. zunächst unbenannte Empfänger; keine weiteren Keuter-Erteilungen daraus ableiten |

**Neue Quellenkorrektur:** Der [DIP-Elternvorgang 322921](https://dip.bundestag.de/vorgang/322921)
zeigt Metadaten mit dem Namen Reichardt, aber im amtlichen
[Original-PDF auf Seite 1222](https://dserver.bundestag.de/btp/21/21014.pdf#P.1222)
wird der zugehörige Ordnungsruf ausdrücklich **Keuter** zugeordnet.
Es wäre falsch, aus 322921 und 322922 zwei zweifelsfrei bestätigte
**Reichardt**-Ordnungsrufe zu machen. Der Rechercheauftrag für 322921
bleibt als **manuell zu klärender DIP-/Originalpersonen-Konflikt** offen.

Die DIP-Position 681904 zu Keuter verweist auf die
[vorherige PDF-Seite 4996](https://dserver.bundestag.de/btp/21/21043.pdf#P.4996),
während die konkrete erste ausgesprochene Keuter-Erteilung in derselben
fortlaufenden Debatte auf
[Seite 4997](https://dserver.bundestag.de/btp/21/21043.pdf#P.4997)
steht. Der im Protokoll ebenfalls genannte Reichardt-Ordnungsruf und
der nur theoretisch angedrohte Ruf sind nicht mit dieser Keuter-Erteilung
zu verwechseln.

**Wichtig:** Die drei ausdrücklich abgegrenzten Originalformulierungen
(eine Reichardt 21/014, zwei Keuter 21/043) sind **Quellenbefunde**, keine
neuen statistisch freigegebenen rechtswirksamen Sanktionen. Rechtsfolgen
und mögliche spätere Aufhebungen müssen getrennt geprüft werden.

