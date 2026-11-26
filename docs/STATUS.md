# Projektstand

## Phase 0 – Schema und Datenqualität

- Die Starterdokumentation liegt im Projektverzeichnis einschließlich `data/README.md`. Die Entwicklungsumgebung wurde mit Python 3.12, DuckDB 1.4.4, Node.js 24 und npm 11 geprüft.
- `python -m fis_twin.cli profile` profiliert lokale Parquet-Dateien. Es prüft die Spalten und Typen jeder Datei, zählt fehlende Werte und ermittelt mit kompatiblem Mapping dateiübergreifende Qualitätskennzahlen. `demo-data` erzeugt zwei synthetische Tagesdateien.
- Die freigegebene Stichprobe wurde aggregiert profiliert. Das vorläufige Quellmapping steht in `config/local.fis.candidate.yaml`. Schema, Kennzahlen und quellspezifische Hypothesen liegen lokal in `artifacts/profile.fis.json` und `artifacts/quality.fis.md`. Diese Pfade sind in Git ignoriert.
- Die synthetischen Tests decken Dateireihenfolge, Mehrdateiimport, Null- und Leerwerte, Schemaabweichungen, leere und beschädigte Inputs, Zeitgleichstände und wiederholte Event-Schlüssel ab.
- Die Neuinstallation nach README, die synthetische Demo, der Profillauf über die freigegebene Stichprobe und `python -m pytest -q` wurden geprüft. Alle acht Tests bestanden.

## Offene Fragen zum Quellsystem

1. Welche ID oder Kombination beschreibt eine Fahrzeuginstanz über Tagesgrenzen und mögliche Wiederverwendung hinweg? Wie erklären sich abweichende alternative Kennungen innerhalb derselben Kandidatengruppe?
2. Beschreiben Werk, Linie und Gerät eine Lesestelle dauerhaft eindeutig? Wofür steht eine fehlende Linie und ist ein Lesestellenstamm mit stabiler ID verfügbar?
3. Welche Zeit ist fachlich die Passagezeit? Wie entsteht die Abweichung zwischen nativer Zeit und Quelltext? Welche Uhr- und Zeitzonenregeln gelten bei Normal- und Sommerzeit?
4. Was bedeutet die Sequenz bei identischem Zeitstempel? Welche Statuswerte stehen für zählbare Passagen, und woran sind erneut exportierte Ereignisse oder Korrekturen erkennbar?

## Implementierung und Abnahme

| Abschnitt | Ergebnis |
| --- | --- |
| 1 · Batch-Discovery | Konfigurierbare Projektion und gerichteter Graph über alle Dateien. Isolierte Lesestellen, Schleifen und Wiederholungen bleiben erhalten. Ein Kandidaten-Mapping ist explizit zu aktivieren. Paare mit unsicherer Reihenfolge, fehlender Lesestelle oder widersprüchlicher Event-ID sind nachvollziehbar ausgeschlossen. |
| 2 · Graphanalyse | Gewichte, Case-Zahlen, Ausgangsanteile, UTC-Aktivtage, Zeitquantile, lange Lücken und beobachtete Varianten werden aggregiert. Graph und Layout besitzen separate Exporte. |
| 3 · 2D-Frontend | Lokale FastAPI und React-Oberfläche. Automatisches ELK-Layout für überschaubare Graphen, Linienraster für größere Graphen. Such- und Filteransichten, Zoom und Kanteninspektion greifen auf den vollständigen Graphen zu. |
| 4 · Validierung | Synthetische Sollgraphen und Browserabläufe geprüft. Die freigegebene Stichprobe wurde lokal als vorläufiger Graph ausgewertet und in getrennten Beobachtungsfenstern verglichen. Referenzvalidierung steht aus. |
| Aktualisierung | Derselbe Batch-Befehl importiert einen veränderten Dateibestand. Die Synthesetests prüfen Kantenkorrektur bei nachgeliefertem Event, neue Linien, identische Wiederholung sowie den Erhalt des letzten Graphen bei fehlerhaftem Export. |

## Benchmark

`python tests/benchmark_discovery.py` generiert fünf synthetische Dateien mit 2.500.000 Ereignissen, prüft die erwartete Anzahl an Paaren und misst Discovery inklusive CLI-Start und JSON-Ausgabe. Der gemessene Lauf verwendete Linux, drei sichtbare CPUs auf AMD EPYC 9V74 und ein Containerlimit von 8 GiB RAM.

| Parquet-Volumen | Knoten | Kanten | Paare | Generierung | Discovery | Peak-RSS Discovery |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 27,6 MB | 96 | 480 | 2.450.000 | 1,76 s | 13,09 s | 2,26 GiB |

Verteilung, Anzahl und Länge der Cases und Größe des resultierenden Graphen beeinflussen die Laufzeit. Die Kennzahlen gelten für den synthetischen Lauf. Für die freigegebene Stichprobe stehen Kennzahlen und Mapping-Fragen im lokalen Qualitätsbericht. Der Abgleich mit einem geprüften Netz aus dem Quellsystem steht aus.

## Ausgeführte Prüfungen

- 14 Python-Tests für Profiling, Sollgraphen und Dateiaktualisierung.
- 5 Chromium-Tests für automatische Positionierung, Linienfilter, Detailansicht, Suche, Verschieben, Zoom, Layout-Export und Aktualisierung der Browseransicht. Das Linienraster wurde mit 227 synthetischen Lesestellen geprüft.
- Lokaler Browser-Smoke-Test des vorläufigen FIS-Graphen mit Abgleich der dargestellten Knotenzahl und Kantenanzahl gegen den Export.
