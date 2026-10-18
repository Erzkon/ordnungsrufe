# Accessibility-Audit · Ordnungsruf-Counter

**Stand 18.10.2026 · Änderungen nur über reviewten Pull Request.**

Die Website führt jetzt zusätzlich zum echten Desktop-/Mobil-Chrome-Smoke einen automatisierten [axe-core](https://github.com/dequelabs/axe-core)-Audit durch. Der Audit testet **vier reale Zustände**: 20. und 21. Wahlperiode jeweils auf Desktop (1366 × 900) und Mobil (390 × 844).

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
