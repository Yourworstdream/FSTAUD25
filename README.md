# ⚙️ FST AUD 25 – Gemeinsam auf GitHub

Das Klassen-Repository der Automatisierungsklasse **FST AUD 25**. Hier lernen wir, mit Git und GitHub im Team zu arbeiten – und schreiben zusammen ein **Automatisierungs-Wiki**.

| | |
|---|---|
| 📘 **Anleitung** | https://yourworstdream.github.io/FSTAUD25/ |
| 📊 **Live-Fortschritt** | https://yourworstdream.github.io/FSTAUD25/fortschritt.html |
| 📝 **Anmelden** | [Anmelde-Issue öffnen](https://github.com/Yourworstdream/FSTAUD25/issues/new?template=anmeldung.yml) |
| 🆘 **Hilfe** | [Hilfe-Issue öffnen](https://github.com/Yourworstdream/FSTAUD25/issues/new?template=hilfe.yml) |

## Dein Weg in 7 Schritten

Jeder Schritt wird automatisch erkannt und erscheint etwa eine Minute später auf dem Live-Fortschritt.

| # | Schritt | Was du tust | Woran er erkannt wird |
|---|---------|-------------|------------------------|
| 1 | 📝 Angemeldet | GitHub-Konto erstellen, Anmelde-Formular abschicken | Issue mit Label `anmeldung` |
| 2 | 🤝 Im Team | Einladung per E-Mail annehmen | Du bist Collaborator |
| 3 | 🌿 Pull Request | Steckbrief `teilnehmer/<dein-login>.md` per PR vorschlagen | Eigener PR |
| 4 | ✅ Gemerged | Review bekommen, PR mergen | Eigener PR wurde gemerged |
| 5 | 👀 Review | PR einer anderen Person prüfen | Abgeschicktes Review |
| 6 | 💬 Diskussion | In einem Issue mitreden | Issue oder Kommentar |
| 7 | 🚀 Projekt | Seite fürs Automatisierungs-Wiki schreiben | Gemergter PR in `projekt/` |

## Aufbau

```
├── index.html                 Anleitung (GitHub Pages)
├── fortschritt.html           Live-Fortschritt aller 12 Plätze
├── assets/                    Design und JavaScript der Webseite
├── klasse.json                Klassenname, Anzahl Plätze, ausgeblendete Konten
├── teilnehmer/                Ein Steckbrief pro Person (Schritt 3)
├── projekt/                   Klassenprojekt: Automatisierungs-Wiki (Schritt 7)
├── CONTRIBUTING.md            Unsere Teamregeln
└── .github/
    ├── ISSUE_TEMPLATE/        Formulare: Anmeldung, Hilfe, Idee
    ├── scripts/fortschritt.js Berechnet den Fortschritt aus der GitHub-Aktivität
    └── workflows/             Aktualisiert und veröffentlicht die Webseite
```

## So funktioniert der Live-Fortschritt

Nach jeder Aktivität (Issue, Kommentar, Pull Request, Review, Push auf `main`) und zusätzlich alle 10 Minuten läuft die Action **Fortschritt & Webseite**. Sie liest die Aktivität im Repository über die GitHub-API, berechnet für jede Person die 7 Schritte, schreibt `fortschritt.json` und veröffentlicht alles auf GitHub Pages. `fortschritt.html` lädt diese Datei alle 20 Sekunden neu und zeigt neue Erfolge sofort an. Mit `fortschritt.html?demo` gibt es eine Vorschau mit Beispieldaten, mit `fortschritt.html?ich=<login>` wird die eigene Karte hervorgehoben.

Nebenbei begrüßt die Action neue Anmeldungen und schließt Anmelde-Issues automatisch, sobald die Einladung angenommen wurde.

## Einrichtung (einmalig, für @Yourworstdream)

1. **Pages einschalten:** Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
2. **Einmal starten:** Actions → *Fortschritt & Webseite* → **Run workflow**. Danach ist die Seite unter https://yourworstdream.github.io/FSTAUD25/ erreichbar.
3. **`main` schützen:** Settings → Rules → Rulesets → *New branch ruleset* → Target: *Include default branch* → **Restrict deletions**, **Require a pull request before merging** (1 Approval), **Block force pushes**.
4. **Aufräumen:** Settings → General → *Automatically delete head branches* anhaken.
5. **Einladen:** Für jedes Anmelde-Issue unter Settings → Collaborators → *Add people* den Benutzernamen eintragen.
