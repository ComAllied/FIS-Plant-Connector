# FIS Digital Twin — Codex Starter Package

Projektübergabe aus der bisherigen ChatGPT-Konzeption. Ziel: aus täglichen FIS-Parquet-Dateien automatisch ein logisches Produktionsnetz rekonstruieren, analysieren und als interaktiven Materialflusszwilling visualisieren.

## Start in VS Code / WSL

1. ZIP in einen neuen lokalen Projektordner entpacken (unter WSL vorzugsweise im Linux-Dateisystem).
2. Nur zur Verarbeitung freigegebene oder ausreichend pseudonymisierte Parquet-Dateien nach `data/` kopieren. Für den ersten Lauf genügen etwa drei aufeinanderfolgende Tage; später den gesamten verfügbaren Zeitraum einbeziehen.
3. Den Projektordner in VS Code öffnen und Codex im selben Workspace starten. Alternativ die Codex-CLI im Projektordner verwenden, falls installiert.
4. Den Inhalt von `START_PROMPT.md` als erste Nachricht an Codex senden. `AGENTS.md` enthält die projektweiten Entwicklungsregeln.
5. Zuerst Datenprofil, Schema-Mapping und Implementierungsplan prüfen. Danach den MVP umsetzen und testen lassen.

## Dokumente

| Datei | Zweck |
|---|---|
| `AGENTS.md` | Dauerhafte Arbeitsanweisungen für Codex |
| `PROJECT.md` | Fachlicher Kontext, Zielsetzung, Anforderungen und Abgrenzung |
| `ARCHITECTURE.md` | Technische Architektur, Datenmodell, Algorithmen und Visualisierung |
| `ROADMAP.md` | Implementierungsphasen, Tests und Abnahmekriterien |
| `START_PROMPT.md` | Kopierfertiger Startauftrag |
| `data/README.md` | Hinweise zur Datenbereitstellung |

## Lokalen Parquet-Profiler starten

Installation mit Python ab 3.11 im Projektordner.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest
```

Synthetische Tagesdateien erzeugen und mit dem Beispiel-Mapping untersuchen.

```bash
python -m fis_twin.cli demo-data --output artifacts/demo
python -m fis_twin.cli profile --input artifacts/demo \
  --config config/mapping.example.yaml --output artifacts/profile.demo.json
```

Für ein freigegebenes eigenes Verzeichnis zuerst das Schema ohne Mapping erfassen.

```bash
python -m fis_twin.cli profile --input data --output artifacts/profile.json
```

`--input` akzeptiert einzelne Parquet-Dateien und Verzeichnisse, auch mehrfach. Verzeichnisse werden rekursiv durchsucht. Die `fileIndex`-Werte folgen der Sortierung der aufgelösten Dateipfade. Der Bericht enthält Parquet-Speichertypen und DuckDB-Spaltentypen, Zeilen-, Null- und bei Textspalten Leerwertzahlen sowie Typ- und Spaltenabweichungen. Zeitbereiche und weitere Qualitätskennzahlen werden bei einem kompatiblen `--config` über alle Dateien gemeinsam ermittelt. `tiedGroupsWithCompleteUniqueSequence` misst technische Eindeutigkeit innerhalb von Zeitgleichständen. Die fachliche Verlässlichkeit der Sequenz ist separat zu klären.

Fehlende oder typabweichende Mapping-Spalten stehen pro Datei in `mappingIssues`. Der Profiler schreibt den Schemabericht mit `schemaCompatible: false` und `quality: null`. Ein Verzeichnis ohne Parquet-Dateien oder eine unlesbare Datei führt zu einem Fehler. Eine gültige Parquet-Datei mit null Zeilen bleibt im Bericht. Die Demo erzeugt zwei Dateien pro Zielverzeichnis. Für einen erneuten Lauf kann dasselbe Demo-Verzeichnis direkt profiliert werden.

## Status und Entscheidungen

Phase 0 enthält den Profiler, ein synthetisches Mapping und Tests. Das Produktionsmapping wird fachlich abgestimmt, bevor daraus bestätigte Übergänge abgeleitet werden. Fortschritt und Implementierungsplan stehen in [docs/STATUS.md](docs/STATUS.md) und [docs/DECISIONS.md](docs/DECISIONS.md).

## Datenschutz und Unternehmensfreigabe

FIS-Daten können vertrauliche Produktionsinformationen enthalten. Lokaler Dateizugriff durch einen KI-Coding-Agenten bedeutet nicht automatisch, dass der gesamte Verarbeitungsvorgang offline ist. Vor Nutzung Unternehmensfreigabe und Tool-/Datenrichtlinien prüfen. Keine echten Datensätze, IDs, Routen, Zugangsdaten oder unfreigegebenen Metadaten in Modellprompts, externe Dienste, Git oder Telemetrie übertragen. Eine lokale Ausführung der späteren Analyse-Software ohne LLM ist vorgesehen. Falls eine KI-gestützte Inspektion echter Daten nicht freigegeben ist, ausschließlich mit synthetischen Beispielen und einem freigegebenen, minimierten Schema entwickeln; echte Daten anschließend mit dem fertigen Programm intern verarbeiten. `.gitignore` ist nur eine zusätzliche Schutzmaßnahme, keine Zugriffskontrolle.
