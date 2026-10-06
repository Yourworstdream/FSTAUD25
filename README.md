# FST AUD 25

Das gemeinsame GitHub-Repository der Automatisierungsklasse FST AUD 25. Hier üben wir, mit Git und GitHub im Team zu arbeiten, und schreiben zusammen ein kleines Wiki zur Automatisierungstechnik.

- Anleitung: https://yourworstdream.github.io/FSTAUD25/
- Klassenliste: https://yourworstdream.github.io/FSTAUD25/fortschritt.html
- Hilfe: https://yourworstdream.github.io/FSTAUD25/hilfe.html
- Anmelden: [Anmelde-Formular öffnen](https://github.com/Yourworstdream/FSTAUD25/issues/new?template=anmeldung.yml)
- Lebenslauf-Generator: [lebenslauf/](lebenslauf/) – Lebenslauf erstellen und als Word, LibreOffice oder Webseite exportieren

## Die sieben Schritte

| Nr. | Schritt | Wird erkannt an |
|-----|---------|-----------------|
| 1 | Konto erstellen und anmelden | Issue mit dem Label `anmeldung` |
| 2 | Einladung annehmen | Du bist Collaborator |
| 3 | Steckbrief vorschlagen | Eigener Pull Request |
| 4 | Review abwarten und mergen | Eigener Pull Request wurde gemerged |
| 5 | Einen Pull Request prüfen | Abgeschicktes Review bei jemand anderem |
| 6 | In einem Issue mitreden | Eigenes Issue oder Kommentar |
| 7 | Eine Wiki-Seite schreiben | Gemergter Pull Request im Ordner `projekt/` |

## Aufbau

```
index.html          Anleitung
fortschritt.html    Klassenliste mit dem Stand aller 12 Plätze
hilfe.html          Häufige Probleme, Begriffe, Regeln
assets/             CSS und JavaScript der Seiten
klasse.json         Klassenname, Anzahl Plätze, ausgeblendete Konten
teilnehmer/         Ein Steckbrief pro Person (Schritt 3)
projekt/            Das Wiki (Schritt 7)
lebenslauf/         Lebenslauf-Generator (Python): Export als Word, ODT und interaktive Webseite
.github/            Formulare, Actions, Skript und Tests für die Klassenliste
```

## Wie die Klassenliste funktioniert

Nach jeder Aktivität im Repository (Issue, Kommentar, Pull Request, Review, Push auf `main`) und zusätzlich regelmäßig nach Zeitplan läuft die Action *Fortschritt & Webseite*. Sie liest die Aktivität über die GitHub-API, berechnet für jede Person die sieben Schritte, schreibt `fortschritt.json` und veröffentlicht die Seiten auf GitHub Pages. `fortschritt.html` lädt die Datei alle 20 Sekunden neu. Geplante Läufe führt GitHub bei wenig Betrieb oft nur alle paar Stunden aus; das betrifft vor allem das Häkchen „Einladung“, weil GitHub für eine angenommene Einladung kein Ereignis an Actions schickt. Deshalb schreibt man nach dem Annehmen „angenommen“ in sein Anmelde-Issue: Der Kommentar startet die Action sofort, sie schließt das Issue und setzt das Häkchen.

Außerdem beantwortet die Action neue Anmeldungen mit den nächsten Schritten und schließt das Anmelde-Issue, sobald die Einladung angenommen wurde.

`fortschritt.html?demo` zeigt die Liste mit Testdaten, `fortschritt.html?ich=<login>` hebt die eigene Zeile hervor.

Das Skript hat Tests: `node --test .github/scripts/fortschritt.test.js`. Sie laufen automatisch, wenn ein Pull Request etwas in `.github/scripts/` ändert.

## Einrichtung (einmalig, für @Yourworstdream)

1. Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
2. Actions → *Fortschritt & Webseite* → **Run workflow**. Danach ist die Seite unter https://yourworstdream.github.io/FSTAUD25/ erreichbar.
3. Settings → Rules → Rulesets → *New branch ruleset*, Target: *Include default branch*, dann **Restrict deletions**, **Require a pull request before merging** (1 Approval) und **Block force pushes** anhaken.
4. Settings → General → *Automatically delete head branches* anhaken.
5. Für jede neue Anmeldung unter Settings → Collaborators → *Add people* den Benutzernamen eintragen.
