# Lokales Datenverzeichnis

Hier können nach Prüfung der Unternehmensfreigabe täglich erzeugte Parquet-Dateien abgelegt werden. Zum Einstieg etwa drei aufeinanderfolgende Tage verwenden; tatsächliche Dateinamen sind beliebig, sofern der Import sie unterstützt.

Keine Dateien enthalten. Keine vertraulichen Dateinamen, Rohdaten oder abgeleiteten Produktionsdaten in Git übernehmen. Die `.gitignore` schützt nur vor gewöhnlichem versehentlichem Staging, nicht vor Zugriff durch Tools oder bereits versionierten Dateien.

Falls die Daten nicht für einen KI-Agenten freigegeben sind, echte Dateien außerhalb seines Workspaces aufbewahren. Mit synthetischen Fixtures und einem freigegebenen, minimierten Schema entwickeln; die später erstellte Analysesoftware intern ohne KI ausführen. Pseudonymisierung muss konsistent über alle Tage erfolgen, damit Fahrzeugketten erhalten bleiben. Auch pseudonymisierte Topologien und Zeitmuster können vertraulich sein.
