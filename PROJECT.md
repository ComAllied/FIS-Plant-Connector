# Projektdefinition — FIS Digital Twin

## 1. Ausgangslage

FIS (Fahrzeugidentifikationssystem) erfasst Ereignisse, wenn eine Karosse mit einer bestimmten ID eine Lesestelle im Werk passiert. Jede Passage erzeugt einen Eintrag. Lesestellen sind identifizierbar und verfügen beispielsweise über einen Namen wie `M100`, einen Linien-Tag und möglicherweise eine Beschreibung. Gleichnamige Lesestellen können auf unterschiedlichen Linien liegen (z. B. M100 auf Linie 1 und Linie 2). Die tatsächliche Eindeutigkeit und der Gültigkeitsbereich aller IDs sind anhand des Schemas zu prüfen.

In AWS wird täglich eine Parquet-Datei mit den FIS-Tagesdaten abgelegt. Im betrachteten Zeitraum von ungefähr einem bis zwei Monaten sind laut Projektbeschreibung über 2,5 Millionen Ereignisse angefallen. Der genaue Zeitraum und die Verteilung sind noch unbekannt. Die Dateien werden zunächst lokal bereitgestellt. S3 ist die vorgesehene spätere Quelle, aber noch nicht verifiziert.

Im vorhandenen Value Stream Monitor werden Produktionsnetze bereits modelliert und visualisiert. Das Value Stream Studio ist als Editor/Plattform für dynamische Dashboards vorgesehen. Die neue Discovery Engine soll diese manuelle Modellierung perspektivisch ersetzen oder erheblich reduzieren, ohne zunächst eine technische Abhängigkeit von Mendix einzuführen.

## 2. Zielbild

Aus historischen FIS-Ereignissen soll eine generische, datengetriebene Discovery Engine ein gerichtetes, gewichtetes Produktionsnetz automatisch ableiten und ohne manuelles Platzieren oder Verbinden von Kacheln visualisieren. Das Ergebnis ist ein logischer Materialflusszwilling: Lesestellen als Knoten, beobachtete aufeinanderfolgende Passagen als Kanten, gruppiert nach Linien und gegebenenfalls Fertigungsbereichen. Es soll später für mehrere Werke nutzbar sein.

Drei getrennte Problemstellungen:

1. Topology Discovery: Welche Lesestellen existieren und welche Übergänge werden beobachtet?
2. Automatic Graph Layout: Wie lässt sich diese Struktur übersichtlich und reproduzierbar anordnen?
3. State Reconstruction: Welche historischen oder aktuellen Zustände lassen sich auf der Topologie aus Ereignissen berechnen?

## 3. Funktionale Anforderungen

| ID | Anforderung | Priorität |
|---|---|---|
| F01 | Mehrere Parquet-Dateien lokal lesen und Schema sowie Datenqualität untersuchen | MVP |
| F02 | Konfigurierbares Mapping der tatsächlichen Quellfelder auf ein kanonisches Event-Schema | MVP |
| F03 | Ereignisse nach Fahrzeugidentität und Zeit ordnen; Tagesgrenzen übergreifen | MVP |
| F04 | Gewichteten Directly-Follows Graph (DFG) generieren | MVP |
| F05 | Knoten und Kanten mit nachvollziehbaren Kennzahlen und Qualitätsmerkmalen ausgeben | MVP |
| F06 | Linienwechsel, Verzweigungen, Zusammenführungen und Schleifen erhalten | MVP |
| F07 | Automatische 2D-Anordnung inklusive Liniengruppen; kein manuelles Positionieren notwendig | MVP |
| F08 | Zoom, Pan, Suche, Detailansicht, Filter und Hervorhebung von Knoten/Routen | MVP |
| F09 | Maschinenlesbarer Export der Topologie und eines reproduzierbaren Layouts | MVP |
| F10 | Historische Durchsatz-KPIs, Übergangszeiten und Fahrzeugrouten | MVP/Erweiterung |
| F11 | Historisches Playback mit Zeitregler und beobachtetem Fahrzeugzustand | Erweiterung |
| F12 | Inkrementelle Tagesimporte, versionierte Topologien, Vergleich von Strukturänderungen | Erweiterung |
| F13 | Schätzung von Segmentbeständen und Engpassindikatoren mit Unsicherheitskennzeichnung | Erweiterung |
| F14 | AWS-Anbindung sowie Integration in Value Stream Studio / Monitor | Später |

## 4. Nichtfunktionale Anforderungen

- Reproduzierbar: identische Eingaben, Konfiguration und Version führen zu identischem logischem Graphen; Layout separat versionieren und deterministisch konfigurieren.
- Skalierbar: erste Zielgröße etwa 2,5 Mio. Ereignisse, ohne alle Rohdaten im Browser zu laden. Laufzeit und Speicherverbrauch messen, nicht vorab versprechen.
- Generisch: keine hartcodierten Lesestellennamen, Produktionslinien, Werke oder tatsächlichen Spaltennamen.
- Erklärbar: jede Kante muss auf beobachtete, nachvollziehbare Evidenz zurückgehen; Filter dürfen Rohbefunde nicht vernichten.
- Lokal ausführbar, keine KI zur Laufzeit erforderlich; keine externe Infrastruktur für MVP.
- Robust gegenüber fehlenden Daten, Mehrfachereignissen, Sonderrouten, Wiederholungen und Tagesgrenzen.
- Vertraulichkeit: Rohdaten bleiben außerhalb von Git und unfreigegebenen externen Systemen.

## 5. Abgrenzung und fachliche Grenzen

Aus einem zeitlich sortierten Event-Log folgt eine beobachtete Lesestellenfolge, nicht zwingend eine direkte physische Verbindung. Fehlende Lesungen können vermeintliche Abkürzungen erzeugen; gleiche Zeitstempel können die Reihenfolge unentscheidbar machen. Eine Lesestelle muss keine Maschine sein. Eine seltene Route kann fachlich korrekt sein, etwa Nacharbeit.

FIS erlaubt keine eindeutige Rekonstruktion von Hallengeometrie, Weglängen, Maschinenkapazitäten, Störungsursachen, Echtzeitpositionen zwischen Lesestellen oder unsichtbaren Stationen. Eine letzte Lesung ist keine GPS-Position. Übergangszeiten enthalten möglicherweise Warte-, Transport- und Bearbeitungszeit. Bestände und Engpässe sind nur unter nachvollziehbaren Voraussetzungen schätzbar. Keine automatische physische Simulation, kein 3D-Hallenmodell, keine KI/LLM-basierte Topologieerfindung im MVP.

## 6. Offene Fragen aus der realen Datenanalyse

- Wie heißen und typisieren sich die Spalten? Welche Metadaten sind tatsächlich enthalten?
- Welche Fahrzeug-ID identifiziert eine Karosse über mehrere Tage eindeutig? Ist sie über Werke/Produktionsdurchläufe wiederverwendbar?
- Gibt es eine native Lesestellen-ID? Ist M100 pro Linie, Werk oder global eindeutig?
- Ereigniszeit vs. Importzeit, Zeitzone, Sommerzeit, Auflösung und Sequenznummer?
- Enthalten Dateien Überlappungen, verspätete Events, Duplikate oder Korrekturen?
- Existieren eindeutige Start-/End-Lesestellen und fachliche Vorgaben zur Rework-Erkennung?
- Gibt es ein Referenznetz, eine Lesestellenliste oder einen Layout-Export zur Validierung?
- Dürfen die Daten und aggregierten Ergebnisse im gewählten Entwicklungsumfeld verarbeitet werden?

Fehlende Antworten nicht erfinden. Wo möglich mit sicheren Standardannahmen weiterarbeiten, diese dokumentieren und bei semantisch kritischen Entscheidungen eine fachliche Bestätigung einholen.
