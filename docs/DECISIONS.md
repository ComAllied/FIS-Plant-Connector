# Entscheidungen

## DuckDB für das erste Profiling

DuckDB 1.4.4 liest lokal Parquet und aggregiert die Qualitätskennzahlen. Der Profiler prüft zunächst je Datei das physische Parquet-Schema und das für DuckDB sichtbare Spaltenschema. Danach zählt er Nullwerte sowie leere beziehungsweise nur aus ASCII-Whitespace bestehende Texte. Hive-Pfadpartitionen werden bei der Prüfung nicht als Spalten ergänzt. Die optionale Mapping-Prüfung vergleicht deklarierte Typen explizit mit den sichtbaren DuckDB-Typen. Dateieigene, ungemappte Typänderungen werden gemeldet. Für die dateiübergreifende Analyse werden ausschließlich geprüfte Spalten kombiniert.

Die CLI schreibt die Datenkennzahlen in eine lokale JSON-Datei. Fehler beim Lesen oder Profilieren belassen einen vorhandenen Bericht unverändert. Eingabedateien werden über einen Index statt über ihren Dateinamen referenziert. Die Reihenfolge ist die Sortierung der aufgelösten Pfade. Gemappte Zeitbereiche stammen direkt aus dem Quelltyp. Die fachliche Zeitnormalisierung wird mit dem Produktionsmapping vereinbart.

## Versioniertes Mapping mit explizitem Status

`config/mapping.example.yaml` zeigt das Versionsschema mit `schema_version: 1`. Jedes Feld deklariert eine geordnete Liste von Quellspalten und ihre DuckDB-Typen. So lassen sich Identitätskomponenten getrennt prüfen. Eine Case- oder Reader-Komponente ist ungültig, wenn sie null oder ein leerer beziehungsweise nur aus ASCII-Whitespace bestehender Text ist. Nichtendliche Zeitstempel werden separat in der Pflichtfeldqualität erfasst. Der Profiler zählt verschiedene Case- und Reader-Schlüssel jeweils über alle Einträge mit gültigen Komponenten des betreffenden Schlüssels.

Das beobachtete FIS-Schema liegt als lokaler Entwurf mit Status `candidate` vor. `schemaCompatible` bescheinigt die technische Spalten- und Typprüfung. Ob die Felder die fachlich richtigen Identitäten und Zeitpunkte beschreiben, bleibt bis zur Bestätigung offen. Die Sequenzdiagnose zählt vollständige, eindeutige Sequenzwerte pro Zeitgleichstand und bewertet keine fachliche Reihenfolge. Die Diagnose wiederholter Event-Schlüssel setzt eine gemappte Event-ID voraus. Die Eingabe bleibt unverändert.

## Regeln für die erste Graphversion

- Eine Kante basiert auf zwei benachbarten, verlässlich geordneten Ereignissen derselben bestätigten Fahrzeuginstanz. Zeitgleichstände und Ereignisse mit fehlender Lesestelle bleiben bei der Nachbarschaftsbildung sichtbar, damit keine künstlichen Übergänge über unsichere Ereignisse hinweg entstehen.
- Wenn eine bekannte Fahrzeuginstanz ein Ereignis ohne einordenbare Zeit enthält, muss die betroffene Folge vor dem Kantenexport als unsicher bewertet werden. Zeilen mit unbekannter Fahrzeuginstanz werden separat gezählt. Lesestellen mit gültiger Identität bleiben als Knoten erhalten.
- Bei einer bestätigten stabilen Event-ID wird Deduplizierung auf nachgewiesen redundante Ereignisse begrenzt. Konflikte mit derselben ID werden als Datenqualitätsfall erfasst. Lange Lücken werden für die spätere Bewertung gekennzeichnet.
- Der DFG beschreibt aufeinanderfolgende Beobachtungen an Lesestellen. Die physische Fördertopologie ist ein separates Validierungsziel. Layout und beobachteter Fahrzeugzustand werden separat vom DFG gespeichert.

## Wiederholbare Aktualisierung

Eine Aktualisierung berechnet den Graphen aus dem vollständigen aktuellen Importbestand. Dadurch können später eintreffende Lesungen auch ältere Nachbarschaften korrigieren. Die Dateien werden vor dem Scan inventarisiert und nach der Berechnung erneut geprüft. Der Export enthält einen Fingerabdruck der sortierten Datei-Hashes und des Mappings. Gleichlautende Eingabepfade werden aufgelöst und einmal gelesen. Bytegleiche Kopien unter unterschiedlichen Pfaden werden als solche gezählt. Die fachliche Deduplizierung setzt eine bestätigte Event-ID voraus.

Gleichzeitige Aktualisierungen für dasselbe Ausgabeziel werden gesperrt. DuckDB erhält pro Lauf ein eigenes System-Temp-Verzeichnis für mögliche Zwischendateien. Die Ausgabe wird erst nach einer erfolgreichen Berechnung atomar ersetzt. Die API liest die letzte gespeicherte Version, und der Browser erkennt neue Versionen anhand der Graph-ID. Ändern sich nur Gewichte oder Zähler, behält die Ansicht ihr Layout.

## Metriken und Layout

- Ausgehende Anteile verwenden die Anzahl gültiger Paare je Ausgangsknoten als Nenner. Aktive Tage zählen UTC-Tage des Quellereignisses. Zeitmaße ergeben sich aus der Differenz der beiden Passagezeiten.
- Varianten sind beobachtete, innerhalb des Eingabefensters eindeutig geordnete Lesestellenfolgen. Die Zusammenfassung gibt höchstens 20 Folgen aus. Fachlicher Prozessbeginn und Prozessende bleiben offen.
- ELK berechnet Gruppen und Kanten im Browser-Worker. Ab mehr als 220 Knoten oder 700 Kanten wird ein deterministisches Linienraster verwendet. Das Raster hält Karten disjunkt und kann höhere Kantenkreuzungen haben. Linien- und Gewichtsfilter ändern die Anzeige. Das exportierte Layout enthält den ganzen Graphen.
