# Version 1.0 – überprüfte Readiness-Entscheidung

**Prüfdatum:** 17.10.2026  
**Geltungsbereich:** PR #4, Branch automation/wp21-audit-and-triage.  
**Urteil:** **BEDINGTES TECHNISCHES GO für eine begrenzte 1.0**; **kein GO für einen vollständigen aktuellen Ordnungsruf-Counter**.  
**Merge/Veröffentlichung:** ausdrücklich **NICHT genehmigt**; keine automatischen Zähleränderungen.

## Was tatsächlich geprüft wurde

| Abnahme | Nachweis | Ergebnis |
|---|---|---|
| Historisch kuratierte Zähler | Release-Gate, beide deterministischen CSV/JSON-Exporte | 20. WP: **135 Maßnahmen, 123 Ereignisse**; vier bestätigte Statistikdateien unverändert |
| Laufende Wahlperiode | JSON-Vertrag, sichtbarer Warnhinweis | 21. WP: **acht Einzelbelege**, ausdrücklich unvollständige Auswahl ohne Gesamtzahl |
| Parser und Quelleninvarianten | [Parser-Action 39066725728](https://github.com/Erzkon/ordnungsrufe/actions/runs/39066725728) | **695 pytest bestanden, 145 Subtests** |
| Release- und Website-Prüfungen | [Pages-Prüfung 39066729257](https://github.com/Erzkon/ordnungsrufe/actions/runs/39066729257) | Datenintegrität, Negativtests, nichtzählende Release-Akte grün |
| Tatsächlich gerenderte Website | [Browser-Action 39066729290](https://github.com/Erzkon/ordnungsrufe/actions/runs/39066729290) | **Zwei Durchläufe zu je neun Checks**, Chrome auf Desktop 1366 × 900 und Mobil 390 × 844 |
| Umgang mit fehlenden Quellen | Browserdurchlauf ohne Quellenstatus sowie zweiter Durchlauf mit erzeugtem simuliertem Ausfallbericht | Beide Fälle sichtbar und korrekt von bestätigten Ranglisten getrennt |
| Schutz bei manipuliertem Datensatz | Echter Browser mit absichtlich veränderter 21.-WP-JSON-Antwort | Beide Ranglisten verweigern die Anzeige, statt ungeprüfte Zahlen zu übernehmen |
| Main-Pages-Veröffentlichung | Workflow-Abhängigkeits- und Reihenfolgeprüfungen | Produktiver Browser-Smoke liegt **nach** Erzeugung des aktuellen Quellenstands und **vor** dem Pages-Artefakt; Fehlschlag blockiert neuen Deploy |
| Reproduzierbare Sichtkontrolle | Screenshots im GitHub-Actions-Artefakt v1-actual-browser-preview | Desktop- und Mobilansicht zusätzlich visuell geprüft; Artefakte 14 Tage abrufbar |

Das Browser-Artefakt ist eine Vorschau des **PR-Builds**, nicht der Beweis einer bereits live veröffentlichten oder nach Merge getesteten Seite. Der produktive Main-only-Pfad kann technisch erst mit einer dafür freigegebenen Veröffentlichung ausgeführt werden.

## Finaler CI-Abgleich (17.10.2026)

Die vollständige erneute Abfrage der GitHub-Actions-Ergebnisse für den
Basiscommit `1db9a359d40918219b4a8d54076e16c6700af109` ergab **acht erfolgreiche Workflow-Läufe**:
[Python-Parser](https://github.com/Erzkon/ordnungsrufe/actions/runs/39067138892),
[Website-Release-Gate](https://github.com/Erzkon/ordnungsrufe/actions/runs/39067141823),
[echter Chrome-Desktop-/Mobilbrowser](https://github.com/Erzkon/ordnungsrufe/actions/runs/39067141780)
sowie fünf weitere amtliche XML-/DIP-Einzelprüfungen. Die tatsächlich
beobachteten Zahlen waren **695 bestandene Python-Tests und 145 Subtests**
sowie **zweimal neun Browserchecks**. Die produktiven Deploy- und
Quellenwache-Jobs waren im PR erwartungsgemäß **übersprungen**; ihre
Funktionsfähigkeit auf `main` ist damit noch **nicht** nachgewiesen.

Die Logprüfung identifizierte kleinere, im folgenden Wartungsschritt
adressierte Python-Probleme (ungültige Escape-Sequenzen in einem
Prüfbericht und ein `unittest`-Test, der Hilfsdaten zurückgab).
**Die erneute CI-Prüfung des Wartungscommits ist vor der Merge-Entscheidung
verpflichtend.** GitHub meldete außerdem Node.js-20-Abkündigungen für
ältere Actions-Versionen. Im nachfolgenden Wartungscommit wurden deshalb
die zentrale Parser-CI, der Chrome-Smoke und das Pages-Release-Gate
gezielt auf die offiziellen Node.js-24-kompatiblen Versionen von
`checkout`, `setup-python`, `setup-node` und `upload-artifact`
umgestellt. **Eine erneute erfolgreiche CI-Prüfung dieses Commits bleibt
vor einer Merge-Entscheidung zwingend**. Andere, vor allem ausschließlich
auf `main` genutzte Actions sind nicht Gegenstand dieser Umstellung und
bleiben als **P2-Wartungsaufgabe** zu beobachten.

Im gesamten PR wurden **132 geänderte Dateien** gefunden, jedoch **keine**
der vier geschützten CSV-/JSON-Statistikdateien. Die große PR-Differenz
erfordert weiterhin einen bewussten abschließenden Merge-Review.

## Risiken nach Priorität

| Priorität | Risiko | Behandlung vor oder bei Freigabe |
|---|---|---|
| **P0 – Release-Sperre** | PR #4 wurde vom Eigentümer **nicht ausdrücklich zum Merge freigegeben** | Weiterhin offen lassen. Ein grüner technischer Check autorisiert keinen Merge. |
| **P0 – Aussagegrenze** | Vollständigkeit der 21. WP und endgültiger Rechtsfolgenstatus sind **nicht belegt** | Version 1.0 ausschließlich als historische 20.-WP-Auswertung **plus klar unvollständige 21.-WP-Vorschau** veröffentlichen. Keine automatische Zuordnung neuer Ordnungsrufe. |
| **P1 – Datenklarheit** | Amtlich **19** Ordnungsrufe für Beatrix von Storch, einzeln belegt **18**; die historische Differenz bleibt offen | Vor Veröffentlichung Hinweis im sichtbaren Bereich und in der Methodik belassen. Nicht durch Schätzung korrigieren. |
| **P1 – Produktiver Erstlauf** | GitHub-Pages-Umgebung, echte öffentliche URL und post-Merge-Deployment sind auf dem PR-Branch nicht abschließend validierbar | Nach expliziter Genehmigung: Main-Actions einschließlich Browser-Gate prüfen; tatsächliche öffentliche Startseite und beide Wahlperioden einmal kontrollieren. |
| **P1 – Reviewumfang** | PR #4 umfasst ungewöhnlich viele zusammengefasste Forschungs-, Workflow- und Website-Änderungen | Vor Merge GitHub-Datei-/Statusübersicht prüfen; nach Freigabe gegebenenfalls **Squash-Merge** statt hunderter Einzelcommits erwägen. Keine automatische Migration der bestätigten Zähler. |
| **P2 – Bedienbarkeit** | Automatischer Chrome-Test umfasst Desktop/Mobil und zentrale Interaktionen, aber **keine vollständige WCAG-/Screenreader-Abnahme** | Manuelle Tastatur-/Screenreader-Stichprobe vor öffentlicher Bewerbung; Fehler getrennt priorisieren. |
| **P2 – Externe Quellen** | Bundestag XML/DIP und GitHub Actions können ausfallen; Cache-Berichte können alt werden | Quellenstatus wird öffentlich als aktuell/veraltet/fehlend/ungültig markiert; fehlender/widersprüchlicher **Gesamtstatus blockiert neuen Deploy**. |
| **P2 – Spätere Erweiterungen** | v1-Release-Gate friert die aktuelle geprüfte Ausgangsauswahl ein; spätere genehmigte Zählerergänzungen sind ein eigener Review-Schritt | Für Version 1.1 unter eigener Quellen- und Exportprüfung bewusst aktualisieren, nicht aus automatischen Textfundstellen übernehmen. |

## Konkrete Entscheidung

**Technischer Stand: bedingtes GO** für eine erste, klar abgegrenzte und transparent vorläufige Version 1.0. Navigation, Ranglisten, Protokoll-Links, Filter, Teilmengenwarnung, Browser-Datenfehler, Mobilbreite und Produktions-Schutzkette sind getestet.

**Noch kein öffentliches Go:** Der verbleibende **Freigabevorbehalt** ist eine ausdrückliche Entscheidung des Nutzers, **genau diesen begrenzten Umfang** öffentlich zu stellen. Auch nach Zustimmung bleibt die Live-Prüfung nach dem ersten Main-Deployment verpflichtend.

**No-Go** für die Bezeichnungen „vollständiger Ordnungsruf-Counter der 21. Wahlperiode“, „rechtlich abschließend überprüfte Wirkung aller Maßnahmen“ oder automatische Übernahme von XML-/DIP-Prüfhinweisen in bestätigte Zähler.

## Nach einer später ausdrücklich genehmigten Zusammenführung

1. Hauptlauf des Pages-Workflows auf main kontrollieren: frischer Quellenstatus, CSV/JSON-Abnahme **und tatsächlicher Chrome-Smoke müssen erfolgreich sein**.
2. GitHub Pages bei Bedarf mit **Settings → Pages → GitHub Actions** konfigurieren; sicherstellen, dass das Deployment **erfolgreich** war.
3. Öffentlich unter https://erzkon.github.io/ordnungsrufe/ die Startansicht (135 / 123), die 21.-WP-Teilmenge (8), den sichtbaren Differenzhinweis und die Quelleinstiege prüfen.
4. Statusanzeigen für aktuelle und ausgefallene Quellen bewusst testen und auf eventuell eröffnete GitHub-Quellenwache-Issues achten.
5. Kein automatisches Nachzählen, keine automatischen Rechtsfolgeentscheidungen und keine verdeckte Statusänderung.

**Bis dahin bleibt PR #4 offen.** Dieser Bericht ist eine fachliche Freigabeempfehlung, kein Merge-Auftrag.
