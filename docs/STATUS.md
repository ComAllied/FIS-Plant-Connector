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

## Umsetzung nach der Mapping-Abstimmung

| Abschnitt | Umsetzung und Abnahme |
| --- | --- |
| 1 · Batch-Discovery | Konsistent typisierte Parquet-Projektion und normalisierte Events. Zusammengesetzte IDs kollisionsfrei kodieren, Status zu ungültigen Zeilen erhalten, deduplizieren nur bei belegter Event-Identität. DuckDB gruppiert über alle Dateien nach Case und ordnet nach bestätigter Ereigniszeit. Der DFG umfasst auch isolierte Lesestellen, Schleifen, Selbstkanten und seltene Übergänge. JSON-Export deterministisch sortieren und mit Mapping- und Eingabeversion versehen. |
| 1 · Abnahmetests | Synthetische Sollgraphen aus der Roadmap prüfen, insbesondere 360 Sekunden über Mitternacht, keine Übergänge zwischen Cases, getrennte Linien, Wiederholungen, identische Zeitstempel, blockierte Zwischenereignisse und identisches Resultat bei anderer Dateireihenfolge. Eingangszeilen, gültige Events und ausgeschlossene Paare mit Gründen nachvollziehbar zählen. |
| 2 · Graphanalyse | Ausgangsanteile, Distinct-Case-Anzahl, Zeitquantile, aktive Tage und Hinweise auf große Lücken ergänzen. Ausgangsanteile pro Quelle prüfen. Filteransichten aus dem vollständigen Aggregat ableiten. |
| 3 · 2D-Frontend | Eine lokale FastAPI liefert den aggregierten Graphen. React und ELK.js visualisieren zunächst ein synthetisches Netz mit Liniengruppen, Schleifen und Querübergängen. Reproduzierbares Layout separat speichern. Suche, Filter, Detailansicht, Pan und Zoom im Browser prüfen. |
| 4 · Validierung | Laufzeit und Peak-RAM bis rund 2,5 Mio. synthetische Ereignisse messen. Getrennte Zeitfenster und zurückgehaltene Traces vergleichen. Abgleich mit dem Referenznetz bei bestätigter Lesestellengranularität. |
