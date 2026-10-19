# Accessibility-Audit · Ordnungsruf-Counter

**Stand 18.10.2026 · Änderungen nur über reviewten Pull Request.**

Die Website führt jetzt zusätzlich zum echten Desktop-/Mobil-Chrome-Smoke einen automatisierten [axe-core](https://github.com/dequelabs/axe-core)-Audit durch. Der Audit testet **acht reale Zustände**: 20. und 21. Wahlperiode jeweils mit 1366, 640, 390 und 320 CSS-Pixeln Breite. Die kleineren Breiten bilden Reflow-Anforderungen bei größerer Darstellung näherungsweise ab, stellen aber keine tatsächlichen 200- oder 400-Prozent-Zoomtests dar.

## Reproduzierbar

Auf einem Rechner mit Node.js 22 und Google Chrome/Chromium:

```bash
npm install --no-save --no-package-lock --ignore-scripts puppeteer-core@24.20.0 axe-core@4.14.0
AXE_ENFORCE=1 node tests/accessibility_audit.cjs
```

Der Test startet ausschließlich einen lokalen HTTP-Server mit dem verifizierten statischen Website-Build. Er verändert keine Quellendaten. Der normale PR-Workflow prüft einmal ohne und einmal mit einem generierten Quellenstatus; die separate Axe-Prüfung nutzt die reguläre statische Vorschau. Der produktive Main-Workflow testet vor der Freigabe der Pages-Artefakte ebenfalls mit `AXE_ENFORCE=1`.

**Ein Verstoß einer der aktivierten Regeln macht den Workflow rot.** Aktivierte Rule-Tags: WCAG 2.0 A/AA, WCAG 2.1 A/AA, WCAG 2.2 AA und axe-Best-Practices. Die JSON-Datei `.audit/browser_smoke/accessibility/axe_report.json` und die menschenlesbare `summary.md` werden in den GitHub-Actions-Artefakten archiviert.

## Nachvollziehbare Ausgangsbefunde

Die erste Messung des PR #9 zeigte **zwei** betroffene Regeltypen in vier gerenderten Zuständen: `color-contrast` und `label-content-name-mismatch`. Die Prüfung identifizierte zu blasse Sekundärtexte sowie explizite `aria-label`-Werte, die sichtbare Ranglisten-, Marken- und Quellennamen überdeckten.

Die daraufhin vorgenommenen Verbesserungen:
- Dunklere sekundäre Text- und Akzentfarben zur Erfüllung der gemessenen WCAG-Kontrastschwellen.
- Die sichtbaren Ranglisten-/Quellenbezeichnungen bleiben Bestandteil des zugänglichen Namens; reine Zusatzinformationen stehen als Screenreader-Text bereit.
- Einheitliche Prüfung gegen Regressionen vor dem produktiven Website-Upload.

## Aussagegrenzen

Automatische Regelprüfungen **ersetzen keine umfassende WCAG-Konformitätsprüfung**, keinen echten NVDA-, VoiceOver- oder TalkBack-Test und keine manuelle Prüfung von Vergrößerung, Kontrastmodi, Zeitverhalten, Tastatur-Fokusfolgen und Sinnverständlichkeit. `incomplete`-Ergebnisse von axe werden im JSON dokumentiert und müssen bei manueller Abnahme einzeln beurteilt werden.

Die Website bleibt ein unabhängiges nichtamtliches Projekt. Ihre historischen Zähler (20. WP: 135 Maßnahmen, 123 Ereignisse) und die ausdrücklich unvollständige 21.-WP-Auswahl von acht Maßnahmen werden **durch den Accessibility-Audit nie verändert**.

## Derzeit noch manuell zu prüfen

Der erfolgreiche axe-Prüflauf vom 18.10.2026 (PR #9) meldete **null bestätigte automatische Verstöße** in vier Ansichten. Unter `incomplete` verblieben jedoch insbesondere auf Mobilgeräten einzelne Kontrastbewertungen: dynamischer Hero-Text, dekorative Pfeilsymbole und Zellen der horizontal scrollbaren Tabelle. Solche `incomplete`-Regeln sind **keine bestandenen Prüfungen**, sondern gezielt in Browser, Zoom- und Screenreader-Umgebungen nachzuprüfen. Der außerdem aufgetretene unklare ARIA-Kontext für die DIP-Fallregion wurde durch eine explizite benannte `role="region"`-Kennzeichnung präzisiert.

Eine manuelle NVDA-/VoiceOver-Stichprobe muss noch folgen, bevor eine umfassende Konformitätsaussage zulässig wäre.

## Zusätzliche Reflow-, Tastatur- und Bewegungsprüfungen (18.10.2026)

- Die verbindliche Axe-Prüfung untersucht beide Wahlperioden jetzt auch bei **640 und 320 CSS-Pixeln** auf document-weiten Überlauf. Die separat horizontal scrollbare Quellentabelle bleibt absichtlich innerhalb ihres fokussierbaren Bereichs verschiebbar.
- Bei 320 CSS-Pixeln wird `prefers-reduced-motion: reduce` simuliert und geprüft, ob glattes Scrollen und Buttonanimationen deaktiviert sind. Das ist eine Computed-Style-Prüfung im Chrome, kein Screenreader-Test.
- Der funktionale Chrome-Smoke überprüft außerdem, dass mit **Enter** auf „Weitere Einträge anzeigen“ die nächste Seite erscheint, der Fokus am Button bleibt und die historische Gesamtzahl unverändert ist.

**Grenze:** Geräteemulation und CSS-Reflow-Checks ersetzen weder optisches Vergrößern bei 200/400 % auf mehreren echten Browsern noch Screenreader- und Hochkontrasttests. Unklare Axe-Ergebnisse bleiben dokumentiert.

## Ergänzte praktische Prüfung vor dem nächsten Merge

Der Browser-Smoke prüft zusätzlich eine **320-CSS-Pixel-Ansicht** mit Screenshot, die tastaturgesteuerte Paginierung („Weitere Einträge anzeigen“) sowie im Chromium **emulierte erzwungene Farben**. Im CSS sind markierte Perioden und Ranglistenbalken in diesem Modus nicht nur durch Farbfüllung erkennbar. Auf Smartphones wurden besonders kleine Beschriftungen angehoben; Formularnamen stammen weiterhin von sichtbaren `label`-Elementen.

Die konkreten manuellen Aufgaben stehen in [ACCESSIBILITY_MANUAL_CHECKLIST.md](ACCESSIBILITY_MANUAL_CHECKLIST.md). Diese Checkliste ist **noch nicht als bestanden** markiert. Eine Emulation von `forced-colors` ist keine echte Windows-High-Contrast-Systemprüfung.

## Fail-Closed-Positivkontrolle für Regelverstöße

Der PR-Workflow setzt in einer **temporären Kopie der Website** absichtlich einen sichtbaren, aber unbeschrifteten Button ein. Er startet den unveränderten Axe-Audit mit `AXE_ENFORCE=1` und verlangt **beides**: einen Nicht-Null-Exitcode **und** den konkreten WCAG-Regeltreffer `button-name`. Ein roter Prozess wegen eines anderen Fehlers genügt ausdrücklich **nicht**. Das Original wird nicht verändert, die künstliche Seite wird niemals deployt. Im Archiv bleibt eine Diagnose zur Kontrolle.

Damit wird der entscheidende Fehlerschutz des neuen Release-Gates selbst auf seine Wirksamkeit getestet.

## Erweiterte Browser-Semantikprüfung

Zusätzlich zu den acht Axe-Prüfungen wird über das Chrome DevTools Protocol die tatsächlich berechnete Accessibility-Struktur kontrolliert: `main`-Landmarke, `aria-pressed` der beiden Wahlperioden-Buttons, Status-Region mit der Unvollständigkeitswarnung, Suchfeld, Auswahlfeld, Protokolllink samt Person/Sitzung, Ranking-Schaltfläche und fokussierbare Tabellenregion. Ein nicht zuordenbares, ignoriertes oder unerwartet benanntes Element macht die CI rot. **Das misst den Chromium-Zugänglichkeitsbaum und weder tatsächliche Sprachausgabe noch Bedienbarkeit mit NVDA oder VoiceOver.**

## Zustandswechsel zusätzlich geprüft (18.10.2026)

Die Axe-Prüfung untersucht auf **1366 und 390 CSS-Pixeln** zusätzlich für beide Wahlperioden den **dynamischen leeren Suchzustand**: tatsächliche Tastatureingabe, Fokus im Suchfeld, sichtbare Leermeldung und unveränderte geprüfte Gesamtzahl. Danach wird die gerenderte Oberfläche erneut mit denselben WCAG-A/AA- und Best-Practice-Regeln bewertet. Unabhängig davon läuft die komplette Acht-Ansichten-Prüfung in der PR-CI zusätzlich mit einem **temporär generierten Quellenstatusbericht**; reale GitHub-Pages-Daten werden dabei nicht überschrieben und nichts veröffentlicht. Jeder gemeldete Verstoß stoppt den PR-Workflow.

## Leerer Suchzustand – zusätzliche gemessene Korrektur

Die erste Interaktionsmessung im dynamischen Leerzustand identifizierte für „Keine passenden Maßnahmen“ auf Weiß ein tatsächliches Kontrastverhältnis von **4,02:1**. Die Statusmeldung verwendet jetzt `#53616b` statt `#70818d`; der neue Interaktions-Axe-Test überwacht diesen Zustand in beiden Wahlperioden auf Desktop und Mobil verbindlich.

## Nachweisbarkeit der Negativkontrolle

Eine frühe Fassung des erweiterten dynamischen Audits brach bei einem absichtlich fehlerhaften Button vor dem JSON-Export ab. Nun werden Verstöße aus **Standardansichten und dynamischen Leerzuständen zuerst gemeinsam als `violationsTotal` protokolliert** und erst danach mit `AXE_ENFORCE=1` als Blocker ausgewertet. Die Negativkontrolle muss so den konkreten Treffer `button-name` aus dem geschriebenen Bericht nachweisen können, statt lediglich einen fehlgeschlagenen Prozess zu beobachten.

## Fokus nach der letzten Paginierungsseite

Bei Tastaturbedienung bleibt der Fokus beim Knopf „Weitere Einträge anzeigen“, solange weitere Seiten vorhanden sind. Wird die **letzte** Seite geladen, verschwindet der Knopf. In diesem Fall setzt die Website den Fokus ausdrücklich auf die erste neu erschienene Tabellenzeile, statt den Fokus stillschweigend auf den Seitenanfang zu verlieren. Ein echter Chrome-Test bedient nun **alle** 135 historischen Einträge mit Enter und kontrolliert die Fokusübernahme beim letzten Schritt; sichtbare Fokuskonturen sind auch für erzwungene Farben vorgesehen.

## Live-Zustände der automatischen Quellenüberwachung

Der Browser-Smoke simuliert jetzt **fünf getrennte Monitorzustände**, ohne Quelldaten oder bestätigte Zählerdateien zu ändern: sieben aktuelle Quellen, ein fehlender DIP-Positionsbericht, ein um 72 Stunden veralteter Bericht, ein ungültiger Zustandswert und ein unzulässig zukünftiger Zeitstempel. Der Browser muss jeweils den passenden lesbaren, per `role=status` angekündigten Quellenhinweis zeigen und die WP21-Anzeige weiterhin ausdrücklich als **acht belegte Teilmengenfälle** kennzeichnen. Für die gestörten und ungültigen Anzeigen wird zusätzlich eine Axe-Prüfung auf der tatsächlich gerenderten Warnoberfläche ausgeführt. Die Fälle sollen regressionssicher verhindern, dass ein fehlerhafter Quellenmonitor als aktuelle Vollständigkeit oder als Bestätigung von Ordnungsrufen erscheint.

## Zugänglicher Fehlerzustand bei ungültigen veröffentlichten Datensätzen

Werden bestätigte CSV-/JSON-Exporte versehentlich inkonsistent oder unvollständig ausgeliefert, bricht die Anzeige bereits heute **fail-closed** ab. Ein ergänztes `role=alert` informiert jetzt auch Nutzer assistiver Technik ausdrücklich, dass **keine ungeprüften Zahlen angezeigt werden**. Der Browser-Smoke manipuliert die unvollständige WP21-Kennzeichnung nur im Netzwerktransport, erwartet die unberührte Anzeige `—` statt einer Zahl, kontrolliert den sichtbaren Alarm und führt zusätzlich eine Axe-Prüfung dieses Fehlerzustands durch. Die Testmanipulation ist temporär und wird nicht veröffentlicht.

## Zusätzliche veröffentlichte Datenfehler abgesichert

Neben einer versehentlich fehlenden Teilmengenmarkierung für WP21 simuliert der PR-Browser-Test jetzt drei weitere **ausschließlich abgefangene HTTP-Antworten**: fehlende Offenlegung der amtlichen Personendifferenz in WP20, ein unzulässiger nichtamtlicher Protokolllink und ein Widerspruch zwischen Anzahl und Einzelnachweisen der WP21. In jedem Fall wird die Veröffentlichungsdatenprüfung abgebrochen, `role=alert` angezeigt und weder eine geprüfte Zahl noch ein vermeintlich offizieller Quellenlink ausgegeben. Keine der originalen vier geschützten Dateien wird verändert.

## Schutz vor falscher Null bei fehlerhaftem Datenladen

Beide bestätigten Datensätze müssen vollständig validiert sein, **bevor** Such-, Filter-, Perioden- und Paginierungssteuerungen freigeschaltet werden. Bei einem Lade-/Prüfungsfehler werden auch bereits zuvor validierte Teildaten verworfen, alle dynamischen Kennzahlen zeigen einen Gedankenstrich statt `0`, alte Vergleichshinweise werden ausgeblendet und die Datensatz-Fehlermeldung erscheint als `role=alert`. Die echten Browser-Fehlerfälle prüfen nun zusätzlich, dass auch absichtlich ausgelöste Suchereignisse **keinen falschen Nullstand** anzeigen können.

Bei „Weitere Einträge anzeigen“ ergänzt die Website nur die **neuen** Tabellenzeilen, statt alle bestehenden DOM-Zeilen neu zu erzeugen. Damit bleibt der virtuelle Lesekontext in bereits angezeigten Tabellenzeilen stabil. Der reale Chrome-Test vergleicht die Elementidentität vor und nach Paginierung; die letzte Seite behält weiterhin die bereits geprüfte Fokusübernahme zur ersten neuen Zeile.

## Langsame Verbindung und HTTP-Ausfall (zusätzliche Browserfälle)

Die neuen Browserprüfungen halten einen der zwei bestätigten Datensätze absichtlich im Netzwerk zurück und kontrollieren, dass **vor erfolgreicher gemeinsamer Prüfung** keine öffentliche Kennzahl gesetzt und keine aktive Such- oder Periodensteuerung freigeschaltet wird. Nach Freigabe des zweiten Datensatzes sind die 135 historisch geprüften Einträge wieder bedienbar. Ein unabhängiger Test simuliert außerdem einen echten HTTP-503-Fehler beim Laden des WP20-Datensatzes: Die Website zeigt dann eine zugängliche Fehlermeldung, aber weder eine irreführende Null noch amtlich aussehende Quellenlinks. Alle Eingriffe erfolgen ausschließlich in isolierten Browseranfragen; produktive Dateien bleiben unverändert.
