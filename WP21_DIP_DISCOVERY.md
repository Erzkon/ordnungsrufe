# WP21: neuer DIP-Entdeckungsabgleich außerhalb der 18 verankerten Vorgänge

**Stand: 24. Oktober 2026 · Audit-Only · keinerlei automatische Zählung.**

## Zweck und Abgrenzung

Die bisherige 17-Fälle-Matrix überprüft vollständige Verfahrenspositionen
von **17 exakt bekannten Eltern-DIP-Vorgängen** aus einer datierten Stichprobe.
Sie findet keinen völlig anderen DIP-Elternvorgang. Das neue
`wp21_new_dip_candidates.py` verwendet deshalb die bestehende
offizielle, vollständig paginierende DIP-Vorgangssuche und gruppiert
Treffer **außerhalb der 18 bereits amtlich individuell verankerten
DIP-Eltern-IDs**.

**Außerhalb dieser 18 IDs heißt ausdrücklich nicht:**
ein neuer, ungeprüfter, rechtswirksamer oder bisher ungezählter
Ordnungsruf. Es gibt weitere Personen in der bisherigen amtlichen
24er-Teilstichprobe und acht bereits geprüfte Beispiele. Ein nicht
bekannter Elternvorgang kann daher eine Dublette, einen bekannten Fall,
einen Einspruch oder ein völlig anderes parlamentarisches Verfahren
betreffen.

## Drei disjunkte Kategorien

1. **Bereits verankerte ID**: bekannter Elternvorgang aus den 18 festen
   DIP-IDs, ohne erneutes Erzeugen eines neuen Falles.
2. **Mögliche ursprüngliche Erteilung**: eine nicht verankerte DIP-ID,
   deren Vorgangstitel ausdrücklich eine Erteilung beziehungsweise einen
   Ordnungsruf an/gegen eine Person beschreibt. Ein Rechtsfolgen- oder
   Ordnungsgeldbegriff im Titel blockiert diese Einordnung.
3. **Sonstige relevante Verfahrensmetadaten**: beispielsweise Einsprüche,
   Ordnungsgelder und unbestimmte Erwähnungen. Diese werden als getrennte
   Nachprüfhinweise archiviert, nicht als ursprüngliche Erteilung.

Eine mögliche Zuordnung zur datierten 24er-Positivstichprobe wird lediglich
als **unsicherer Namens- und Datumshinweis** dokumentiert. Keine
Personen-/Sitzungs- oder Maßnahmenfreigabe erfolgt automatisch.

## Lauf und Beweisgrenzen

```bash
python -m unittest -v tests.test_wp21_new_dip_candidates
python wp21_new_dip_candidates.py --days 45
python wp21_new_dip_candidates.py --full-term
```

- **Wöchentlich** nach genehmigtem Merge: jüngste 45 Tage anhand des
  amtlichen **Aktualisierungsdatums** (mit überlappenden Zeitfenstern).
- **Am ersten Montag jedes Monats**: vollständiger Aktualisierungsfilter
  ab 25. März 2025 für Rückmeldungen und rückwirkende Änderungen.
- **Im PR**: ein kleinerer Live-Lauf über 45 Tage, getrennt von den
  bestehenden 17 elterngebundenen Live-Prüfungen.
- **Manuell auslösbar**: GitHub-Actions-Option
  `full_term_discovery`, ohne Änderungen an bestätigten Dateien.
- **Fehlertoleranz**: Unvollständige API-Paginierung, fremde Wahlperiode,
  doppelte Vorgangs-IDs oder verändertes Quellenschema brechen den
  Bericht ab. Alte Artefakte werden nicht in einen neuen, angeblich
  vollständigen Bericht umetikettiert.

Selbst ein vollständiger Aktualisierungsfilter über die laufende
Wahlperiode ist **keine vollständige Ordnungsrufinventur**:
Die Suchheuristik liest nur Titel/Abstract der DIP-Vorgänge, nicht alle
Plenartextstellen, separate Gerichtsverfahren oder alle späteren
Aufhebungen. XML-/DIP-Kombinationen und individuelle Quellenprüfung
sind weiterhin notwendig.

## Dateien und Sicherheitsgrenzen

Im isolierten Workflow-Artefakt werden ausschließlich

- `.audit/wp21_dip_discovery/outside_pins.json`
- `.audit/wp21_dip_discovery/outside_pins.md`

geschrieben. Kein öffentlicher JSON-Export, keine neue bestätigte
Maßnahmenzeile, kein Review-Issue auf PRs und kein Merge.
Die bisherige SHA256-Prüfung aller vier bestätigten CSV-/JSON-Dateien
bleibt nach dem Live-Lauf zwingend aktiv.

## Nächstes Fachpaket

Die tatsächlich gefundenen nicht verankerten DIP-IDs nach jeweils
individueller Originalperson, ursprünglicher Sitzung, PDF-/XML-Seite
und separater Rechtsfolgensuche sortieren. Nur quellenkritisch
abgeschlossene Einzelfälle können in einem **gesondert freigegebenen
Statistik-PR** zur Zählung vorgeschlagen werden.
