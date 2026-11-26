# Implementierungsplan und Abnahmekriterien

## Phase 0 — Umgebung und Datenschema

Prüfe Python, Node.js, Dateizugriff und installierbare Abhängigkeiten im freigegebenen Entwicklungsumfeld. Kläre zuerst die Datenfreigabe. Erstelle einen lokalen, parametrisierten Profiling-Befehl, der Parquet-Dateien, Schema, Pflichtfelder, Nullwerte und Qualitätsmerkmale untersucht. Falls echte Daten nicht freigegeben sind, synthetische Fixtures generieren und ein minimiertes freigegebenes Schema anfordern. Kein Rohdaten-Dump in den Modellkontext.

**Ergebnis:** Schema-Mapping-Entwurf, Qualitätsbericht (lokal), offene fachliche Fragen, konkretisierte Implementierungsplanung, dokumentierte Annahmen.

**Abnahme:** Quelle und Typ jedes Pflichtfelds nachvollziehbar; IDs und Zeitsemantik geklärt oder klar als ungeklärt markiert; keine echten Datensätze in Git oder KI-Ausgaben.

## Phase 1 — Discovery Engine

Python-Paket, DuckDB-gestützte Batch-Ingestion, kanonisches Event-Schema, Datenvalidierung, DFG, Knoten-/Kanten-Kennzahlen und JSON-Export implementieren. Minimaler CLI-Vertrag als Vorschlag:

```bash
python -m fis_twin.cli profile --input data --output artifacts/profile.json
python -m fis_twin.cli discover --input data --config config/mapping.yaml --output artifacts/graph.json
```

Befehle erst nach Implementierung als ausführbar dokumentieren. Eine synthetische Demo muss ohne vertrauliche Daten funktionieren.

**Abnahme:** Handberechnete Sollwerte aller Kernfixtures treffen zu; Ergebnisse nachvollziehbar und unabhängig von Dateireihenfolge; gültige isolierte Knoten bleiben erhalten; keine Kanten zwischen verschiedenen Cases; Tageswechsel korrekt; keine stillen Datenverluste.

## Phase 2 — Graphanalyse und Qualität

Ausgangsanteile, Anzahl unterschiedlicher Cases, Zeitquantile, aktive Tage, Varianten und Qualitätsflags ergänzen. Ungefilterten DFG und abgeleitete Ansichten getrennt speichern. Seltene Kanten hervorheben statt löschen. Schleifen und mögliche fehlende Lesungen untersuchen.

**Abnahme:** Übergangsanteile je Quellknoten mit gültigen ausgehenden Kanten summieren sich innerhalb numerischer Toleranz auf 1. Knoten ohne ausgehende Kanten haben keine künstlichen Anteile. Filter sind reproduzierbar und Rohgraph bleibt unverändert. Evidenz und Unsicherheit werden getrennt von tatsächlichen Beobachtungen benannt.

## Phase 3 — Lokale Visualisierung

FastAPI für Graphabfrage, React/TypeScript und ELK.js für 2D-Layout. Beginne mit einem kleinen synthetischen Netz und prüfe dann die Skalierung. Implementiere Zoom/Pan, Suche, Linienfilter, Detailpanel und Hervorhebung ein-/ausgehender Kanten. Knoten als kompakte Kacheln, Kanten gerichtet und nach Gewichten unterscheidbar. UI soll automatisch aus dem Graphen entstehen, ohne Drag-and-drop als Voraussetzung. Synthetische Daten deutlich kennzeichnen.

**Abnahme:** Startanleitung funktioniert; Graph wird nach Import ohne manuelle Positionierung sichtbar; Kanten verbinden korrekte Knoten, Gruppen und Schleifen werden verständlich dargestellt. Knoten sind auswählbar und überschneiden sich nicht in Testfällen; Layout unabhängig vom Zustand. Große Netze dürfen gruppiert/gefaltet werden. Beobachtete Performance und verbleibende Layoutprobleme dokumentieren.

## Phase 4 — Validierung und Performance

Benchmark mit synthetischen Daten bis etwa 2,5 Mio. Ereignissen und bei Freigabe mit echten Daten. Erfasse Hardware, Dateianzahl, Datenmenge, Anzahl Events/Knoten/Kanten, Laufzeit je Phase, Peak-RAM und Renderverhalten. Optional Referenznetz aus Value Stream Monitor fachlich abgleichen; zunächst Vergleichbarkeit der Lesestellen und Granularität prüfen. Edge Precision/Recall/F1 nur bei einer geeigneten, geprüften Referenz berechnen. Abweichungen können reale Routenänderungen oder Unterschiede im Referenzmodell sein. Zusätzlich zeitliche Stabilität per getrennten Beobachtungsfenstern und Abdeckung zurückgehaltener Fahrzeugtraces prüfen; keine zukünftigen Daten für Trainings-/Kalibrierentscheidungen nutzen. Ohne Referenz keine behauptete physische Topologiegenauigkeit.

**Abnahme:** Reproduzierbarer Benchmark, dokumentierte Abweichungen, vollständige Tests und nachvollziehbare Grenzen.

## Phase 5 — Historical Playback und Bestände

Zeitregler, Durchsatz je Zeitfenster, letzte Lesung je Fahrzeug und optional retrospektive Segmentbelegung ergänzen. Beobachtet, geschätzt und unbekannt im UI unterscheidbar machen. Keine Rohdatenflut im Browser; aggregierte Zeitfenster oder paginierte freigegebene Detailabfragen nutzen.

**Abnahme:** Synthetischer Zeitverlauf stimmt mit Sollwerten überein; offene Intervalle und fehlende Beobachtungen sind sichtbar; Live-Sicht verwendet keine zukünftigen Ereignisse; Topologie bleibt beim Zeitwechsel stabil.

## Phase 6 — Inkrementelle Importe / AWS / Integration

Erst nach erfolgreichem MVP: idempotente Tagesimporte, Late Events und Versionierung. Optional freigegebene AWS-Quelle und Schnittstellen zum Value Stream Studio / Monitor. Keine AWS-Ressourcen ohne expliziten Auftrag erstellen.

**Abnahme:** Bei gleichem finalen Eventbestand liefert inkrementelle Verarbeitung dieselben fachlichen Aggregate wie Batch-Rebuild; wiederholter Import erzeugt keine Doppelzählung; verspätete Events korrigieren betroffene Kanten; dokumentierter Export/API-Vertrag für spätere Integration.

## Kern-Testmatrix (synthetische Daten)

| Test | Erwartung |
|---|---|
| Ein Case A->B->C | 3 Nodes, 2 Edges, Gewicht jeweils 1 |
| Zwei Cases A->B, A->C | Keine Verbindung zwischen Cases; ausgehende Anteile je 0,5 |
| Gleiche Namen auf L1/L2 | Unterschiedliche Node-IDs |
| A 23:58 in Datei 1, B 00:04 in Datei 2 | Eine Kante A->B, Dauer 360 Sekunden |
| Ereignisse in Dateien unsortiert | Derselbe DFG wie sortierte Eingabe |
| A->B->A->C | Rückkante B->A bleibt erhalten |
| Eindeutige Event-ID doppelt | Nach belegter Deduplizierung keine doppelte Zählung |
| Echte Wiederholung A->A | Nicht pauschal entfernen |
| Gleichzeitige A/B ohne Sequenz | Keine willkürlich bestätigte A->B-Kante |
| A->B->C mit B mehrdeutig | Nicht künstlich A->C erzeugen |
| Einzelereignis D | Node D ohne Kanten |
| Fehlende Pflichtspalte | Verständliche Validierungsfehlermeldung |
| Leere Datei / leeres Verzeichnis | Dokumentiertes Verhalten, keine Phantomkanten |
| Seltene Nebenroute | Im Rohgraph erhalten |
| Sehr lange Lücke | Flag/konfigurierbare Regel, keine unbegründete physische Interpretation |
| Später eintreffendes B zwischen A und C | Inkrementell A->C korrigieren, A->B und B->C erzeugen |
| Gleicher Tagesimport zweimal | Idempotenz bei späterer inkrementeller Verarbeitung |

## Definition of Done für MVP

- Phasen 0–4 im vereinbarten Umfang umgesetzt.
- Lokale Installation und Start dokumentiert, synthetische Demo verfügbar.
- Tests ausgeführt; Ergebnisse, bekannte Fehler und Einschränkungen dokumentiert.
- Konfigurierbares Mapping statt werksspezifischer Hardcodierung.
- Automatisch generierter und visuell navigierbarer Graph samt maschinenlesbarem Export.
- Kein Anspruch auf physische Genauigkeit oder vollständige Live-Bestände ohne zusätzliche Validierung.
