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

## Discovery und Browseransicht starten

Für die lokale Ansicht sind Node.js ab 20.19 oder 22 ab 22.12 sowie die Python-Webabhängigkeiten erforderlich. Die folgenden Befehle laufen im Projektordner nach Aktivierung der Python-Umgebung.

```bash
python -m pip install -e '.[web,test]'
npm --prefix frontend ci
npm --prefix frontend run build
python -m fis_twin.cli discover --input artifacts/demo \
  --config config/mapping.example.yaml --output artifacts/graph.demo.json
python -m fis_twin.cli serve --graph artifacts/graph.demo.json
```

Die Demo-Dateien entstehen mit `demo-data` aus dem vorherigen Abschnitt. Die Ansicht läuft auf der lokalen Loopback-Adresse `http://127.0.0.1:3000`. Sie zeigt Lesestellen und gerichtete Übergänge mit automatischem Layout, Linienfilter, Suche, Zoom und Detailansicht. `Export layout` speichert Koordinaten und Kantenverläufe mit der zugehörigen Graphversion.

## Eigene Parquet-Dateien und neue Tagesexporte

1. Freigegebene Parquet-Dateien unter `data/` ablegen und mit `profile` prüfen. Eine Kopie von `config/mapping.example.yaml` als `config/local.mapping.yaml` speichern und Quellspalten, Typen und Identitätskomponenten eintragen.
2. Die Rollen von Case-ID, Reader-ID und Passagezeit fachlich bestätigen. Discovery erwartet für die Passagezeit einen Parquet-Zeitstempel mit Zeitzonenbezug. Naive Lokalzeiten vor der Verarbeitung mit der gültigen Quellzeitzone und Sommerzeitregel normalisieren. `event_id` und `sequence_id` nur eintragen, wenn ihre Semantik für Deduplizierung bzw. die Reihenfolge belegt ist.
3. Den Graphen erzeugen. Für ein abgestimmtes Mapping `status: confirmed` setzen. Für eine vorläufige Sicht `status: candidate` beibehalten und `--allow-candidate` angeben. Die vorläufige Sicht behandelt Zeitgleichstände konservativ und kennzeichnet ihren Status im Export und im Browser.

```bash
python -m fis_twin.cli discover --input data --config config/local.mapping.yaml \
  --output artifacts/graph.json
python -m fis_twin.cli serve --graph artifacts/graph.json
```

Für ein Update weitere Dateien in dasselbe Eingabeverzeichnis legen und den `discover`-Befehl erneut ausführen. Ein konsistenter, neu berechneter Graph ersetzt die vorige Ausgabe atomar. Dadurch können neue Lesestellen erscheinen und nachträgliche Lesungen bereits beobachtete Übergänge korrigieren. Die laufende Ansicht lädt neue Graphversionen selbst nach. Unbekannte Zusatzspalten werden toleriert. Abweichende gemappte Spalten und unlesbare Dateien werden gemeldet. Bei einem Fehler bleibt die letzte gültige Ausgabe verfügbar.

Der Export enthält beobachtete Nachbarschaften von Lesestellen. Ausgangsanteile beziehen sich auf die gültigen ausgehenden Übergänge des Beobachtungsfensters. Lange Übergänge bleiben erhalten und werden oberhalb von 24 Stunden gekennzeichnet. Mit `--long-gap-seconds` lässt sich der Grenzwert ändern. Das Layout ordnet größere Netze in einem Linienraster an, damit auch dort alle Lesestellen verfügbar bleiben.

## Abnahme und Projektstatus

```bash
python -m pytest -q
# Einmalig Chromium für Playwright bereitstellen
npm --prefix frontend exec -- playwright install chromium
npm --prefix frontend test
# Synthetischer Benchmark unter Linux
python tests/benchmark_discovery.py
```

Für ein installiertes Chromium kann `FIS_CHROMIUM_PATH` auf dessen Programmpfad gesetzt werden. Das Produktschema und das tatsächliche Netz benötigen weiterhin einen fachlichen Abgleich. Projektstand, Entscheidungen und Story-Abnahme stehen in [STATUS.md](docs/STATUS.md), [DECISIONS.md](docs/DECISIONS.md) und [USER_STORIES.md](docs/USER_STORIES.md).

## Datenschutz und Unternehmensfreigabe

FIS-Daten können vertrauliche Produktionsinformationen enthalten. Lokaler Dateizugriff durch einen KI-Coding-Agenten bedeutet nicht automatisch, dass der gesamte Verarbeitungsvorgang offline ist. Vor Nutzung Unternehmensfreigabe und Tool-/Datenrichtlinien prüfen. Keine echten Datensätze, IDs, Routen, Zugangsdaten oder unfreigegebenen Metadaten in Modellprompts, externe Dienste, Git oder Telemetrie übertragen. Eine lokale Ausführung der späteren Analyse-Software ohne LLM ist vorgesehen. Falls eine KI-gestützte Inspektion echter Daten nicht freigegeben ist, ausschließlich mit synthetischen Beispielen und einem freigegebenen, minimierten Schema entwickeln; echte Daten anschließend mit dem fertigen Programm intern verarbeiten. `.gitignore` ist nur eine zusätzliche Schutzmaßnahme, keine Zugriffskontrolle.
