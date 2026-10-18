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
