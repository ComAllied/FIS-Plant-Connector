# Startauftrag für Codex

Den folgenden Abschnitt als erste Nachricht in Codex im entpackten Projektordner verwenden:

---

Lies `AGENTS.md`, `PROJECT.md`, `ARCHITECTURE.md`, `ROADMAP.md` und `data/README.md` vollständig. Diese Dateien enthalten den bisherigen Projektkontext aus ChatGPT.

Unser Ziel ist eine generische FIS Digital Twin Discovery Engine, die aus täglichen Parquet-Ereignisdaten automatisch einen gerichteten, gewichteten Produktionsgraphen generiert und ihn als interaktives 2D-Produktionsnetz visualisiert. Die technische Umsetzung soll auf den tatsächlichen Daten basieren, nicht auf einem erfundenen FIS-Schema.

Beginne mit Phase 0:

1. Prüfe den Workspace und die lokale Entwicklungsumgebung.
2. Kläre, ob die Verarbeitung echter FIS-Daten durch den KI-Agenten einschließlich seiner Toolausgaben ausdrücklich freigegeben ist. Falls nicht, arbeite zunächst ausschließlich mit synthetischen Daten und freigegebenem Schema. Gib niemals vertrauliche Rohdaten oder IDs in Chat-/Toolausgaben aus.
3. Implementiere einen kleinen lokalen Parquet-Profiler. Ermittle bei vorliegender Freigabe das tatsächliche Schema, die Semantik der verfügbaren Felder, Datenqualität und mögliche Probleme. Berichte nur freigegebene, minimierte Ergebnisse. Falls keine freigegebenen Dateien vorhanden sind, erstelle synthetische Fixtures und eine Anleitung zur lokalen Ausführung des Profilers.
4. Leite ein konfigurierbares Mapping auf das kanonische Event-Schema ab. Markiere alle noch ungeklärten fachlichen Annahmen, insbesondere Case-ID, Reader-ID, Zeitsemantik und Duplikate.
5. Erstelle einen konkreten Implementierungsplan für die Discovery Engine, ihre Tests und das Frontend. Halte Erkenntnisse in `docs/STATUS.md` und Entscheidungen in `docs/DECISIONS.md` fest, ohne vertrauliche Produktionsinformationen zu veröffentlichen.

Beende den ersten Arbeitsabschnitt mit den Ergebnissen des Profilings bzw. der synthetischen Vorbereitung, offenen fachlichen Fragen, den vorgeschlagenen nächsten Schritten und den ausgeführten Tests. Noch kein umfangreiches Frontend implementieren. Keine AWS-Zugänge, Cloud-Ressourcen oder externe Datenübertragung voraussetzen. Anschließend stimmen wir das Mapping ab und setzen den MVP phasenweise um.

---
