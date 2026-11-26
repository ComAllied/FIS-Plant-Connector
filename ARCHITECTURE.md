# Technische Architektur und Methodik

## 1. Architekturvorschlag

```text
Daily Parquet files (local; later AWS)
        |
        v
Ingestion / Schema Mapping / Quality Report
        |
        v
Normalized Event Log (DuckDB / Parquet)
        |
        v
Directly-Follows Graph + Transition Analytics
        |
        v
Topology Model (versioned) -----> Layout Model (ELK.js)
        |                                  |
        +------------> FastAPI ------------+
                           |
                    React visualization
                           |
           Later: Playback / incremental state / VSS
```

Python + DuckDB für analytische SQL-Verarbeitung über Parquet; PyArrow optional für Schema- und Dateifunktionen. NetworkX optional für Graphanalysen auf aggregiertem Graphen. PM4Py optional für unabhängigen DFG-Vergleich und weiterführendes Process Mining, nicht zwingend für MVP. FastAPI für lokale API, React/TypeScript für UI, React Flow oder ein eigenes SVG-Rendering für Interaktionen; ELK.js für hierarchisches Layout. Bibliotheksversionen anhand der tatsächlich verfügbaren Umgebung wählen und sperren. Keine Datenbankserver oder Cloud-Dienste voraussetzen.

### Vorgeschlagene Zielstruktur (noch nicht implementiert)

```text
fis-digital-twin/
  data/                       # local raw files, ignored
  artifacts/                  # local generated data, ignored
  config/                     # non-sensitive mapping and thresholds
  src/fis_twin/
    ingestion/
    preprocessing/
    discovery/
    analytics/
    storage/
    api/
    cli.py
  frontend/
  tests/                      # synthetic fixtures only
  docs/
  pyproject.toml
  AGENTS.md
  PROJECT.md
  ARCHITECTURE.md
  ROADMAP.md
  README.md
```

## 2. Kanonisches Datenmodell

Die Feldnamen sind ein Zielmodell, nicht die tatsächlichen FIS-Spalten.

| Feld | Typ / Zweck |
|---|---|
| `case_id` | String, konsistente Fahrzeuginstanz im betrachteten Prozess |
| `reader_id` | String, stabile eindeutige Lesestellenidentität |
| `event_time` | Zeitzonenbewusster Zeitstempel bzw. eindeutig normalisierte Zeit |
| `event_id` | Optionaler stabiler Event-Schlüssel zur Deduplizierung |
| `sequence_id` | Optionaler fachlich zuverlässiger Tie-Breaker bei gleichen Zeiten |
| `plant_id`, `line_id`, `area_id` | Optionale Gruppierung / Identitätskontext |
| `reader_name`, `description` | Optionale Darstellungsmetadaten |
| `source_file`, `source_row` | Optionale lokale Provenienz; nicht in öffentliche Exporte übernehmen |

IDs als Strings behandeln (führende Nullen erhalten). Falls keine native reader_id eindeutig ist, einen validierten zusammengesetzten Schlüssel nutzen, z. B. Werk + Linie + Lesestellenname; Komponenten kollisionsfrei kodieren. Keine Zusammenführung rein aufgrund gleicher Anzeigenamen. Case-ID nur bei fachlich bestätigter Gültigkeit aus Fahrzeug-ID ableiten, ggf. Werk/Produktionsinstanz berücksichtigen. Keine willkürliche Sessionisierung allein durch Mitternacht.

## 3. Ingestion und Qualität

Parquet-Metadaten vor vollständigem Scan untersuchen. Mehrere Dateien mit möglicher Schemaentwicklung lesen; fehlende Pflichtspalten oder nicht kompatible Typen melden. Keine unkontrollierte Typumwandlung. Rohdaten unverändert lassen.

Qualitätsreport (lokale Ausgabedatei, nur freigegebene Ergebnisse an den KI-Agenten): Event-Anzahl pro Datei und Tag, Zeitbereich, Nullwerte, Kardinalitäten, ID-Kollisionen, Schema-Drift, ungültige Zeiten, exakte Duplikate, Wiederholungen, Zeitgleichheit, Metadatenkonflikte, sehr lange Übergänge, Randzensierung und Dateilücken. Profiling-Ausgaben so minimieren, dass keine unnötigen Rohdaten offengelegt werden.

Zeitzone und Semantik von event_time vor Normalisierung klären. Bei Gleichstand nur einen fachlich belegten Sequenzschlüssel nutzen. Ein stabiler Dateiname oder eine Zeilennummer kann Reproduzierbarkeit verbessern, beweist aber keine tatsächliche Reihenfolge. Ohne zuverlässige Reihenfolge die betroffenen Übergänge als mehrdeutig markieren bzw. aus dem bestätigten DFG ausschließen; nicht einfach einen beliebigen Nachfolger wählen.

Duplikate: nur bei nachweislich identischen Events (z. B. stabile Event-ID) deduplizieren. Gleiche Leserpassagen können echte Wiederholungen sein. Eine konfigurierbare zeitbasierte Entprellung erst nach Validierung aktivieren und Rohdaten/Filterstatistik erhalten.

## 4. Directly-Follows Graph (DFG)

### Definition

Für jede Fahrzeuginstanz c: zeitlich geordnete Ereignisfolge `T_c = [(r1,t1), ..., (rn,tn)]`. Jede hinreichend eindeutig geordnete benachbarte Passage liefert eine beobachtete Transition `(ri,ri+1)` mit `delta_t = ti+1 - ti`.

Knotenmenge V = alle gültigen, eindeutigen Lesestellen. Kantenmenge E = beobachtete geordnete Lesestellenpaare; auch Selbstkanten bei echten Wiederholungen zulässig. Gewicht `w(u,v)` = Anzahl beobachteter Übergänge. Empirischer Ausgangsanteil `p(v|u) = w(u,v)/sum_x w(u,x)` über beobachtete gültige ausgehende Transitionen, nicht die unbedingte physische Routingwahrscheinlichkeit. Die Metrik hängt von Zeitraum, Datenqualität und Filtern ab. Anzahl unterschiedlicher Fahrzeuge, aktive Produktionstage, Median und Quantile der Übergangszeit separat berechnen. Definition und Bezugszeitraum je Kennzahl dokumentieren.

### Beispiel (synthetisch)

```text
A: M100/L1 -> M110/L1 -> M200/L3
B: M100/L2 -> M110/L2 -> M200/L3
C: M100/L1 -> M110/L1 -> M200/L3
```

Ergibt fünf Knoten und vier Kanten; Gewichte 2,2 auf L1 und 1,1 auf L2. M200/L3 ist eine Zusammenführung. Gleichnamige Leser bleiben getrennt. Das Ergebnis muss nicht physisch gezeichnet oder manuell verbunden werden.

### SQL-Skizze (DuckDB)

Nur für bereits normalisierte, geordnete Ereignisse. `order_key` ist ein deterministischer, fachlich belegter Tie-Breaker bzw. kanonischer Ordnungsindex; `order_is_reliable` kennzeichnet Events, deren Position für die angrenzenden Transitionen hinreichend eindeutig ist. Nicht vor dem Window filtern: sonst würde man künstlich über unsichere Ereignisse hinweg verbinden. Fehlende oder ungültige Events können trotzdem nicht vollständig rekonstruierbar sein.

```sql
WITH ordered AS (
  SELECT case_id, reader_id AS source, event_time AS t0,
         order_is_reliable AS source_reliable,
         LEAD(reader_id) OVER w AS target,
         LEAD(event_time) OVER w AS t1,
         LEAD(order_is_reliable) OVER w AS target_reliable
  FROM normalized_events
  WINDOW w AS (PARTITION BY case_id ORDER BY event_time, order_key)
), transitions AS (
  SELECT *, epoch(t1 - t0) AS duration_seconds
  FROM ordered
  WHERE target IS NOT NULL AND source IS NOT NULL
    AND source_reliable AND target_reliable AND t1 >= t0
)
SELECT source, target,
       count(*) AS transition_count,
       count(DISTINCT case_id) AS distinct_case_count,
       median(duration_seconds) AS median_seconds,
       quantile_cont(duration_seconds, 0.9) AS p90_seconds
FROM transitions
GROUP BY source, target;
```

Ergänzend Transition-Evidenz, ausgeschlossene Paare und deren Gründe, Qualitätsmerkmale und Knoten unabhängig aggregieren. Bei Sessiongrenzen keine Kanten über getrennte Produktionsinstanzen hinweg erzeugen. SQL ist eine Implementierungsskizze, noch nicht auf echten Daten ausgeführt.

### Verfeinerung

- Roh-DFG unverändert erhalten. Sichtbare Haupt-, Neben-, Rework- und unsichere Routen sind Ansichts-/Analyseklassen. Schwellwerte konfigurierbar machen.
- Hinweise auf Leselücken: seltene Skip-Kante A->C parallel zu A->B->C, ähnliche Zeitverteilung, Häufung in einzelnen Zeiträumen. Nur Hypothese, kein automatischer Beweis.
- Evidenzscore optional aus Häufigkeit, unabhängigen Fahrzeugen, Wiederkehr über mehrere Tage und Qualitätsflags. Komponenten und Normalisierung veröffentlichen; keine kalibrierte Wahrscheinlichkeit behaupten. Seltene echte Routen nicht durch einen Score vernichten.
- Stark zusammenhängende Komponenten, Rückkanten, Split/Merge und häufige Varianten untersuchen. Schleifen dürfen nicht gelöscht werden, nur damit ein Layout funktioniert.
- DFG kann bei Verzweigungen nicht sämtliche zulässigen kompletten Routen oder langfristigen Abhängigkeiten ausdrücken. Für konkrete Fahrzeugpfade und Varianten die ursprünglichen Traces auswerten. Heuristics Miner / Inductive Miner können später verglichen werden, sind aber kein Ersatz für die Nachvollziehbarkeit der Rohtransitionen.

## 5. Automatisches Layout

2D-Layout als Default: horizontale Hauptflussrichtung (links nach rechts), Produktionslinien als Gruppen/Swimlanes, orthogonale Kantenführung. ELK Layered (Sugiyama-Familie) als Startpunkt. Ziele: wenige Kreuzungen, keine überlappenden Kacheln, nachvollziehbare Gruppen, sichtbare Verzweigungen und Rückkanten. Compound-Graph- und lane-Constraints prototypisch prüfen; ELK garantiert keine fachlich idealen Swimlanes für jede zyklische Topologie. Gegebenenfalls ein zweistufiges Layout (Liniengruppen und interne Knoten) erproben, ohne die Graphstruktur zu verändern. Bei sehr großen Graphen hierarchischer Zoom, Gruppenaggregation und Filter statt vollständiger Darstellung aller Elemente.

Layouts separat als Artefakt speichern (`topology_id`, Layout-Version, Engine-Version, Optionen, node coordinates, edge routing). Stabile Eingabereihenfolge und ggf. Seed verwenden. Keine automatischen Layoutwechsel bei Zustandsupdates. Bei Topologieänderungen möglichst vorhandene Positionen erhalten und neue Knoten ergänzen; konkrete Unterstützung evaluieren. Keine x/y-Koordinate als tatsächliche Hallenposition interpretieren. 3D nur später bei belegtem Nutzen und verfügbaren Geometriedaten.

## 6. Graph- und API-Vertrag (Entwurf)

```json
{
  "schemaVersion": "1.0",
  "topologyId": "synthetic-example",
  "nodes": [
    {"id": "reader-1", "label": "M100", "lineId": "L1", "eventCount": 3},
    {"id": "reader-2", "label": "M110", "lineId": "L1", "eventCount": 2}
  ],
  "edges": [
    {"id": "edge-1", "source": "reader-1", "target": "reader-2",
     "transitionCount": 2, "distinctCaseCount": 2,
     "outgoingShare": 1.0, "medianDurationSeconds": 120,
     "qualityFlags": []}
  ]
}
```

Felder und Werte rein synthetisch. IDs deterministisch und kollisionsfrei generieren; Kanten referenzieren existierende Knoten. Lauf-/Zeitraum-Metadaten, Mapping-/Filterversion, Qualitätsreport und Input-Fingerprint als separate Manifestfelder vorsehen. Keine Rohdaten in Standard-Graph-Responses.

| Endpoint (Vorschlag) | Aufgabe |
|---|---|
| GET /api/health | Betriebsstatus |
| GET /api/topologies | Verfügbare Graphversionen |
| GET /api/topologies/{id} | Aggregierter Graph |
| GET /api/topologies/{id}/quality | Qualitätsreport (intern, freigegeben) |
| GET /api/topologies/{id}/layout | Gespeichertes Layout, falls vorhanden |
| GET /api/topologies/{id}/nodes/{nodeId} | Knoten-Details |
| GET /api/topologies/{id}/edges/{edgeId} | Übergangsdetails |
| GET /api/state?at=... | Historischer Zustand, später |

Lokale API standardmäßig an Loopback binden, keine ungeschützte Veröffentlichung. CORS auf lokale UI beschränken. Rohdaten-Endpoints sind nicht für MVP vorgesehen.

## 7. Zustandsrekonstruktion und KPIs (Erweiterung)

Durchsatz als Anzahl Lesungen bzw. unterschiedliche Fahrzeuginstanzen je Zeitfenster definieren (nicht verwechseln). Übergangszeit ist die Differenz benachbarter Lesungen, keine reine Maschinenzykluszeit. Historisches Playback: für jeden Zeitpunkt die letzte beobachtete Lesestelle sowie Alter der Beobachtung darstellen. Bei vollständig beobachteten Übergängen kann offline retrospektiv ein Fahrzeug dem Intervall `[t_source, t_target)` zugeordnet werden. Diese Zuordnung nutzt zukünftige Informationen und ist für Live-Zustände nicht direkt verfügbar. Im Live-Betrieb nach einer Verzweigung ist das Ziel bis zur nächsten Lesung unbekannt, sofern keine zusätzliche Routinginformation vorliegt. Fehlende Lesungen und offene Intervalle als unbekannt bzw. zensiert markieren; keine exakte Position oder vollständigen Bestände behaupten. Anfangsbestände vor Beobachtungsbeginn separat berücksichtigen.

Engpassindikatoren: erhöhte Übergangszeiten, Durchsatzveränderungen oder geschätzte Bestandszunahmen, relativ zu geeigneten Zeit-/Produktionsregimen. Keine kausale Störungsdiagnose ohne Zusatzdaten. Historische und Online-Auswertung getrennt evaluieren, keine Nutzung zukünftiger Daten für Live-Prognosen.

## 8. Inkrementelle Verarbeitung (später)

Erst Batch-Referenz implementieren. Inkrementell persistierte Event-Identität, letzter verlässlicher Zustand je Case und Dateimanifest nutzen; über Mitternacht hinweg verbinden. Verspätete oder korrigierte Ereignisse können bereits gezählte Kanten ändern: betroffene Fahrzeugtraces bzw. Zeitpartitionen neu berechnen und Aggregate idempotent korrigieren. Reprocessing und Batch-Vergleich testen. Keine naive Addition von Tagesgraphen. Topologie-Änderungen von reinen Gewichts-/Zustandsänderungen unterscheiden, Versionspolitik definieren.

## 9. Methodische Referenzen (zur weiteren Vertiefung)

- Process Mining: Event Logs, Directly-Follows Graphs, Automated Process Discovery; optional Vergleich mit Heuristics/Inductive Miner.
- Graph Drawing: Sugiyama Layered Graph Drawing, Compound Graphs, orthogonales Edge Routing.
- Offizielle Einstiegspunkte: https://pm4py.fit.fraunhofer.de/ ; https://duckdb.org/docs/ ; https://eclipse.dev/elk/ ; https://github.com/kieler/elkjs

Die Architektur ist ein begründeter Vorschlag, kein bereits empirisch validiertes Ergebnis. Exakte Publikationsangaben für eine spätere wissenschaftliche Arbeit separat verifizieren.
