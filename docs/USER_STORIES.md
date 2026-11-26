# User Stories und Abnahme

| ID | User Story | Prüfkriterien |
| --- | --- | --- |
| US01 | Als Datenanalyst möchte ich einen neuen Export lokal prüfen und seine Felder konfigurieren, damit ich weitere Werke anbinden kann. | Profiling zeigt Schema- und Qualitätsabweichungen. Unbekannte zusätzliche Spalten sind zulässig. Bei geändertem Pflichtfeld oder Typ bleibt der bisherige Graph abrufbar. |
| US02 | Als Produktionsplaner möchte ich aus mehreren Tagesdateien ein Netz der beobachteten Übergänge erhalten. | Sortierung über Dateigrenzen, isolierte Knoten, Linienkontext, Verzweigungen, Rückkanten und Wiederholungen sind durch Sollgraphen abgedeckt. |
| US03 | Als Produktionsplaner möchte ich erkennen, welche Aussagen die Daten tragen. | Mehrdeutige Zwischenereignisse unterbrechen die Kantenbildung. Event-ID-Konflikte, fehlende Felder und große Zeitlücken erscheinen in Qualitätskennzahlen. Ein vorläufiges Mapping ist im Export und in der Ansicht gekennzeichnet. |
| US04 | Als Analyst möchte ich Mengen, Anteile und Übergangszeiten vergleichen. | Häufigkeiten, Distinct-Case-Zahlen, UTC-Aktivtage, Zeitquantile und Ausgangsanteile stimmen mit synthetischen Sollwerten überein. |
| US05 | Als Anwender möchte ich das Netz ohne manuelle Platzierung durchsuchen und navigieren. | Die lokale Ansicht lädt und positioniert einen synthetischen Graphen automatisch. Suche, Linienfilter, Zoom, Verschieben und Knoten-/Kanteninspektion sind bedienbar. |
| US06 | Als Betreiber möchte ich weitere Parquet-Dateien hinzufügen und eine Analyse reproduzierbar aktualisieren. | Ein erneuter Lauf zählt den gleichen Bestand gleich. Neue Knoten und Kanten erscheinen automatisch. Eine nachgelieferte Passage korrigiert betroffene Kanten. Ein fehlgeschlagener Lauf erhält die letzte gültige Ausgabe. |
| US07 | Als Betreiber möchte ich Kapazität und fachliche Grenzen kennen. | Ein synthetischer Benchmark misst 2,5 Mio. Zeilen. Abnahmestand, offene Quellsemantik und Verfügbarkeit eines Referenznetzes sind dokumentiert. |

## Nachweise

| Story | Geprüft mit |
| --- | --- |
| US01 | `tests/test_profile.py` und Profiling der freigegebenen Stichprobe |
| US02–US04 | Handberechnete Sollwerte in `tests/test_discovery.py` |
| US05 | `frontend/tests/network.spec.ts` und Browser-Smoke-Test der vorläufigen Stichprobe |
| US06 | CLI-Tests für verspätete Ereignisse, neue Linien, wiederholten und beschädigten Import. Browsertest für den Wechsel der Graphversion bei gleichem Layout. |
| US07 | `tests/benchmark_discovery.py`, Vergleich zweier Beobachtungsfenster und dokumentierte Fachfragen in `STATUS.md`. Der physische Netzabgleich erfordert ein geeignetes Referenznetz. |
