# Manuelle Barrierefreiheitsprüfung – offene Abnahme

**Status: NOCH NICHT DURCHGEFÜHRT.** Diese Prüfliste ist eine Vorlage, kein Nachweis einer erfüllten WCAG-Konformität. Beobachtungen dürfen erst nach tatsächlich ausgeführten Tests eingetragen werden. Screenshots und axe-Ergebnisse allein sind nicht ausreichend.

## 1. Tastatur mit Windows und Chrome/Firefox

- Ohne Maus die Seite aufrufen, `Tab` und `Shift+Tab` nutzen. Der erste Fokus soll den sichtbaren Sprunglink „Zum Inhalt springen“ erreichen; `Enter` muss den Fokus auf den Inhaltsbereich setzen.
- Wahlperiode über beide Buttons mit `Enter` und `Space` wechseln. Die Auswahl muss visuell und über den Zugänglichkeitsbaum als `aria-pressed` nachvollziehbar sein.
- Ranglistenfilter über `Enter` auslösen: Suchfeld bzw. Zugehörigkeitsauswahl soll fokussiert sein. Leere Ergebnisliste, Reset und „Weitere Einträge anzeigen“ prüfen.
- Tabelle bei 320 CSS-Pixeln (z. B. ungefährer Reflow-Fall bei hohem Zoom) per Tastatur horizontal verschieben, ohne horizontales Scrollen der gesamten Seite. Prüfung bei tatsächlichem Browserzoom mit 200 % und 400 % wiederholen.

## 2. NVDA + Chrome/Firefox (echter Screenreader)

- Überschriftenstruktur und Landmarken auflisten. Protokolllinks müssen mit sichtbarem Namen sowie zugehöriger Person/Sitzung erkennbar sein.
- Den Wechsel von 20. zu 21. Wahlperiode durchführen. Die Statusansage muss ausdrücklich „unvollständige Auswahl, keine Gesamtzahl“ enthalten. Es darf keine vollständige WP21-Statistik suggeriert werden.
- Die dynamischen Ranglisten und die Ergebniszahl nach Filterwechsel prüfen. Keine unbeabsichtigten mehrfachen oder sehr langen Ansagen.
- Aktuellen und fehlenden Quellenstatus der WP21 getrennt testen. Fehlende Aktualität darf nicht als Erfolg vorgelesen werden.

## 3. iOS VoiceOver + Safari (echtes Mobilgerät)

- Mit Wischgesten zwischen Navigation, Periodenwahl, Quellenstatus, Rankings und Tabelle wechseln.
- Tabellenüberschriften sollen Datenzellen sinnvoll beschreiben; horizontale Scrollregion und echte Protokolllinks erreichbar sein.
- Bei der 21. Wahlperiode soll die Einschränkung der Datenbasis ebenso verständlich sein wie visuell.

## 4. Windows-Kontrastdesign / Zoom / geringe Bewegung

- Echtes Windows-Kontrastdesign einschalten und prüfen, dass aktive Perioden, Fokuskonturen, Balken und Quellenlinks weiterhin erkennbar sind. Die CI verwendet nur eine Chromium-Emulation.
- Mit 200 % und 400 % Zoom im Browser die Seite bedienen, Textvergrößerung und mobile Höhe beachten. Kein verdeckter Fokus, keine abgeschnittenen Aktionen.
- `prefers-reduced-motion` systemseitig aktivieren und prüfen, dass Animationen/Scrollbewegungen nicht erzwungen werden.

## 5. Noch unentschiedene Axe-Befunde

Die aktuellen Axe-Berichte listen im Feld `incomplete` einzelne Kontrastkonstellationen (vor allem über horizontal scrollbaren Tabellen, dynamischen Inhalten und dekorativen Elementen). Jede **sichtbare** Textstelle muss manuell auf genügend Kontrast geprüft werden. `aria-hidden` markiert dekorative Elemente, ersetzt bei sichtbaren Informationen aber keine Kontrastprüfung.

## Ergebnisprotokoll (erst nach Prüfung ausfüllen)

| Gerät / Browser / Hilfstechnik | Datum | Prüfschritt | Beobachtung | Bestanden? | Link zum Nachweis |
|---|---|---|---|---|---|
| Noch nicht geprüft | – | – | – | Offen | – |

**Keine der Prüfungen erlaubt Änderungen an den bestätigten vier Statistikdateien oder automatische Aussagen über offene Ordnungsruf-Rechtsfolgen.**


## Neue automatisierte Vorprüfungsartefakte

In `v1-actual-browser-preview-<run_id>` finden sich `keyboard_focus_evidence.json` (Tastatur-Fokusstationen) und `accessibility/manual_review_queue.md` (unentschiedene Axe-Befunde). Beides sind nur Hinweise für eine **weiterhin nicht durchgeführte** manuelle NVDA-/VoiceOver-/Zoom-Prüfung. Versionen von Browser, Betriebssystem und Hilfstechniken sind bei der echten Abnahme einzutragen.
