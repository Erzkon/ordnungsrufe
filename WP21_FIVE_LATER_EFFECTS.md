# WP21: fünf nachgelagerte Rechtsfolgenprüfungen

**21. Oktober 2026.** Die folgenden offiziellen Vorgangs-IDs sind
bereits am 16.10.2026 in einem 18er-Bundestags-DIP-Referenzabgleich
individuell verankert worden. Jetzt wird jeder dieser **fünf** Vorgänge
mit allen zugehörigen DIP-Positionen frisch abgefragt. Eine vollständige
Vorgangsabfrage bedeutet **nicht**, dass außerhalb des Vorgangs keine
andere parlamentarische oder gerichtliche Entscheidung besteht.

| Ursprüngliche Erteilung | Amtlicher DIP-Vorgang | Individueller Einspruchsstatus |
|---|---|---|
| Heidi Reichinnek 21/053, 15.01.2026 | [330237](https://dip.bundestag.de/vorgang/330237) | Noch nicht unabhängig abschließend geklärt |
| Bernd Baumann 21/057, 30.01.2026 | [330700](https://dip.bundestag.de/vorgang/330700) | Noch nicht unabhängig abschließend geklärt |
| Ulrich von Zons 21/061, 04.03.2026 | [332078](https://dip.bundestag.de/vorgang/332078) | Noch nicht unabhängig abschließend geklärt |
| Luigi Pantisano 21/065, 19.03.2026 | [332778](https://dip.bundestag.de/vorgang/332778) | Noch nicht unabhängig abschließend geklärt |
| Kathrin Gebel 21/067, 25.03.2026 | [333090](https://dip.bundestag.de/vorgang/333090) | Noch nicht unabhängig abschließend geklärt |

### Bereits ausgeschlossene Verwechslungen

- [Luigi Pantisanos zurückgewiesener Einspruch vom 08.07.2025](https://www.bundestag.de/dokumente/textarchiv/2025/kw28-de-einspruch-ordnungsruf-1098806)
  bezieht sich auf einen Ordnungsruf vom 27.06.2025, **nicht** auf 21/065 vom März 2026.
- [Przygodda-Einspruch vom 26.03.2026](https://www.bundestag.de/dokumente/textarchiv/2026/kw13-de-einspruch-ordnungsruf-1158042)
  nennt Kathrin Gebel als Adressatin einer beleidigenden Äußerung, **nicht**
  als Einspruchsführerin gegen ihren eigenen Ordnungsruf.
- [Reichardts Ordnungsgeld-Entscheidung vom Oktober 2026](https://www.bundestag.de/dokumente/textarchiv/2026/kw42-de-einspruch-ordnungsgeld-1225202)
  erwähnt Gebel ebenfalls, betrifft aber ein **Ordnungsgeld gegenüber Reichardt**.
- Eine [alte Baumann-Einspruchsentscheidung aus Juli 2018](https://www.bundestag.de/webarchiv/textarchiv/2018/kw27-de-go-einspruch-563058)
  gehört zur **19. Wahlperiode**, nicht zu Baumanns Erteilung 21/057.

Das Modul `wp21_five_rechtsfolgen.py` klassifiziert die 13 zusätzlichen
und vier zuvor separat belegten amtlichen Zurückweisungsentscheidungen
ausschließlich nach exaktem ursprünglichem Empfänger- und Erteilungsdatum.
Für einen neuen exakten Treffer muss die individuelle Quelle geprüft
werden; das Programm verweigert automatische Entscheidungen.

Die **Live-Abfrage** prüft je Fall fünf bekannte amtliche
Original-DIP-Vorgänge und sämtliche über die DIP-API paginierten
Verfahrenspositionen. Zusätzliche „Abstimmung“-Positionen, auch wenn
ein Beschlusstenor enthalten ist, werden als **manueller Rechtsfolgenhinweis**
ausgegeben, niemals als automatisch bestätigt. Kein Treffer ist kein
Negativbeweis.

**Öffentliche Statistik:** unverändert, 8 einzeln verifizierte WP21-Beispiele,
ausdrücklich unvollständig. Neue automatische bestätigte Maßnahmen: **0**.
Die fünf Fälle bleiben bis zur umfassenden fachlichen Prüfung offen.
