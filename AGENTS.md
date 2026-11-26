# AGENTS.md — Arbeitsanweisungen für Codex

## Mission

Entwickle eine generische, lokal ausführbare FIS Discovery Engine zur automatisierten Rekonstruktion und Visualisierung von Produktionsnetzen aus Parquet-Ereignisdaten. Lies zuerst `PROJECT.md`, `ARCHITECTURE.md`, `ROADMAP.md` und `data/README.md` vollständig. `START_PROMPT.md` definiert den ersten Auftrag.

## Arbeitsweise

- Beginne mit Schema- und Datenqualitätsanalyse, nicht mit einem fertigen Dashboard oder einem erratenen Schema.
- Prüfe die vorhandene Projektstruktur und Abhängigkeiten, bevor du Änderungen vornimmst. Bevorzuge eine kleine, testbare End-to-End-Lösung vor unnötiger Infrastruktur.
- Trenne beobachtete Tatsachen, Annahmen, fachliche Hypothesen und algorithmische Entscheidungen. Kennzeichne Unbekanntes. Erfinde keine echten Produktionsinformationen.
- Lege einen Implementierungsplan an; arbeite in nachvollziehbaren Phasen. Halte den aktuellen Projektstand in `docs/STATUS.md` und wesentliche Entscheidungen in `docs/DECISIONS.md` fest.
- Sprache: Code, Dateinamen und API-Felder Englisch. Dokumentation und Erläuterungen bevorzugt Deutsch. UI zunächst Englisch, sofern keine andere Vorgabe erfolgt.
- Verwende Python mit Type Hints, kleine testbare Funktionen, strukturierte Fehlermeldungen, konfigurierbare Regeln und pytest. Frontend bevorzugt React/TypeScript. Abhängigkeiten versionieren; keine unnötigen Bibliotheken.
- Nutze bestehende Dateien und Versionierung, überschreibe keine Nutzerdateien ohne Grund. Keine destruktiven Aktionen, Cloud-Deployments, Git-Pushes oder Datenübertragungen ohne ausdrückliche Freigabe.

## Vertrauliche Daten (verbindlich)

- `data/`, Rohdaten und daraus abgeleitete vertrauliche Ergebnisse sind nicht für Git oder unfreigegebene externe Dienste bestimmt. `.gitignore` beachten; zusätzlich vor Commit/Upload prüfen.
- Vor jeder Inspektion tatsächlicher FIS-Daten muss geklärt sein, ob deren Verarbeitung durch diesen KI-Agenten einschließlich Modellkontext/Toolausgaben freigegeben ist. Wenn nicht oder unklar: ausschließlich mit synthetischen Daten und freigegebenem Schema arbeiten. Nicht versuchen, Schutzmaßnahmen zu umgehen.
- Keine realen IDs, Event-Zeilen, Lesestellennamen, Routen oder vertraulichen Dateiinhalte in Modellantworten, Logs oder Dokumentation wiedergeben. Auch aggregierte Ergebnisse können vertraulich sein; nur freigegebene/minimierte Ausgaben in den KI-Kontext übernehmen.
- Keine AWS-Zugangsdaten anfordern, speichern oder ausgeben. Kein Netzwerkzugriff mit Produktionsdaten. Keine externen LLM-APIs als Teil der Engine. Die spätere Analysesoftware soll offline mit lokalen Dateien laufen können.
- Nutze synthetische Fixtures für Tests. Keine realen FIS-Daten in Test-Snapshots oder Beispielgrafiken.

## Fachliche Leitplanken

- Node = eindeutige Lesestelle; Edge = beobachtetes Aufeinanderfolgen zweier Lesestellen derselben Fahrzeuginstanz. Keine physische Kante behaupten.
- Fahrzeug- und Lesestellenidentitäten nicht anhand bloßer Namensähnlichkeit zusammenführen. Werk/Linie/Instanz berücksichtigen, soweit notwendig und belegt.
- Tagesdateien gemeinsam verarbeiten, nicht je Tag getrennt die Routen ableiten. Unklare Ereignisreihenfolgen, fehlende Lesungen und lange Zeitlücken explizit behandeln.
- Wiederholte Lesungen nicht pauschal entfernen. Unterschied zwischen exaktem/technischem Duplikat und echter Wiederholung dokumentieren.
- Seltene Kanten und Schleifen erhalten; nur die Anzeige filtern oder klassifizieren. Confidence nicht als Wahrscheinlichkeit physischer Korrektheit ausgeben.
- Topologie, Layout und zeitabhängigen Zustand getrennt modellieren. Rohdaten unverändert lassen. Keine Neuanordnung bei jeder KPI-Aktualisierung.
- MVP: 2D, kein 3D, kein Machine Learning oder LLM erforderlich, kein verpflichtender AWS-/Mendix-Zugriff.

## Qualität und Abschluss

- Tests für Tageswechsel, identische Lesestellennamen auf verschiedenen Linien, mehrere Fahrzeuge, Schleifen, Duplikate, uneindeutige Zeitstempel, Datenlücken und leere Eingaben erstellen.
- Jede Phase mit konkreten Ergebnissen, geänderten Dateien, ausgeführten Tests, bekannten Einschränkungen und nächsten Schritten abschließen. Nicht behaupten, Tests seien erfolgreich, wenn sie nicht ausgeführt wurden.
- Benchmarking mit tatsächlicher Hardware und klarer Datengröße durchführen; keine erfundenen Performance-Werte.
- `README.md` nach Implementierung um ausführbare Installations- und Startbefehle ergänzen.
