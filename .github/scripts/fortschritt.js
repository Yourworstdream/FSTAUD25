// Berechnet den Fortschritt aller Klassenmitglieder aus der Aktivität im Repository
// und schreibt ihn nach fortschritt.json – diese Datei zeigt fortschritt.html live an.
// Außerdem: Labels anlegen, Anmelde-Issues begrüßen und nach angenommener Einladung schließen.
// Aufgerufen vom Workflow .github/workflows/fortschritt.yml über actions/github-script.

const fs = require('fs');
const path = require('path');

// Die IDs müssen zu assets/common.js passen.
const SCHRITTE = [
  { id: 'anmeldung', titel: 'Angemeldet', beschreibung: 'Anmelde-Issue erstellt' },
  { id: 'team', titel: 'Im Team', beschreibung: 'Einladung ins Repository angenommen' },
  { id: 'pr', titel: 'Pull Request', beschreibung: 'Ersten Pull Request geöffnet' },
  { id: 'merge', titel: 'Gemerged', beschreibung: 'Ein eigener Pull Request wurde übernommen' },
  { id: 'review', titel: 'Review', beschreibung: 'Pull Request einer anderen Person geprüft' },
  { id: 'diskussion', titel: 'Diskussion', beschreibung: 'Issue erstellt oder kommentiert' },
  { id: 'projekt', titel: 'Wiki-Seite', beschreibung: 'Beitrag im Ordner projekt/ gemerged' },
];

const LABELS = [
  { name: 'anmeldung', color: '6366f1', description: 'Anmeldung für das Klassen-Repository' },
  { name: 'hilfe', color: 'd93f0b', description: 'Jemand braucht Unterstützung' },
  { name: 'projekt', color: '8b5cf6', description: 'Aufgabe oder Idee fürs Klassenprojekt' },
  { name: 'thema', color: '0ea5e9', description: 'Thema im Automatisierungs-Wiki' },
];

const GUELTIGER_LOGIN = /^[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38}$/i;
const MAX_AKTIVITAET = 40;

// Eine GraphQL-Abfrage pro 50 Pull Requests statt hunderter REST-Aufrufe.
const PR_ABFRAGE = `query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequests(first: 50, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title url createdAt mergedAt isCrossRepository
        author { __typename login avatarUrl(size: 96) }
        commits { totalCount }
        files(first: 100) { nodes { path } }
        reviews(first: 50) { nodes { author { __typename login avatarUrl(size: 96) } state submittedAt url } }
        comments(first: 100) { nodes { author { __typename login avatarUrl(size: 96) } createdAt url } }
      }
    }
  }
}`;

const ISSUE_ABFRAGE = `query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    issues(first: 50, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title url createdAt state body
        author { __typename login avatarUrl(size: 96) }
        labels(first: 20) { nodes { name } }
        comments(first: 100) { nodes { author { __typename login avatarUrl(size: 96) } createdAt url } }
      }
    }
  }
}`;

module.exports = async ({ github, context, core }) => {
  const { owner, repo } = context.repo;
  const klasse = JSON.parse(fs.readFileSync('klasse.json', 'utf8'));
  const ignoriert = new Set((klasse.ignorieren || []).map((login) => login.toLowerCase()));
  const seitenUrl = `https://${owner.toLowerCase()}.github.io/${repo}/`;
  const hinweise = [];

  await labelsAnlegen(github, owner, repo, core);
  core.setOutput('pages', (await pagesAktiv(github, owner, repo, core)) ? 'true' : 'false');

  const [pulls, issues, mitglieder] = await Promise.all([
    alleSeiten(github, PR_ABFRAGE, { owner, repo }, 'pullRequests'),
    alleSeiten(github, ISSUE_ABFRAGE, { owner, repo }, 'issues'),
    mitgliederLaden(github, owner, repo, core),
  ]);

  // ---------- Personen sammeln ----------

  const personen = new Map(); // login (klein) -> Person
  const kader = new Set(); // wer zur Klasse gehört: angemeldet, Mitglied oder mit Steckbrief
  const aktivitaet = [];

  const holen = (autor) => {
    const login = autor && autor.login;
    if (!login || login === 'ghost' || login.endsWith('[bot]')) return null;
    if (autor.__typename && autor.__typename !== 'User') return null;
    const schluessel = login.toLowerCase();
    if (ignoriert.has(schluessel)) return null;
    if (!personen.has(schluessel)) {
      personen.set(schluessel, {
        login,
        name: null,
        avatar: `https://github.com/${login}.png?size=96`,
        emoji: null,
        ziel: null,
        erledigt: {},
        zahlen: { prs: 0, gemerged: 0, reviews: 0, kommentare: 0, issues: 0, commits: 0 },
        letzteAktivitaet: null,
        reviewtePRs: new Set(),
        profil: false,
      });
    }
    const person = personen.get(schluessel);
    if (autor.avatarUrl) person.avatar = autor.avatarUrl;
    return person;
  };

  // Frühester Zeitpunkt zählt. `true` heißt: erledigt, Zeitpunkt unbekannt.
  const erreicht = (person, schritt, zeit) => {
    const bisher = person.erledigt[schritt];
    if (zeit) {
      if (!bisher || bisher === true || zeit < bisher) person.erledigt[schritt] = zeit;
    } else if (!bisher) {
      person.erledigt[schritt] = true;
    }
  };

  const melden = (person, zeit, typ, text, url) => {
    if (!zeit) return;
    aktivitaet.push({ zeit, login: person.login, typ, text, url });
    if (!person.letzteAktivitaet || zeit > person.letzteAktivitaet) person.letzteAktivitaet = zeit;
  };

  const kommentareZaehlen = (liste, nummer) => {
    for (const kommentar of liste) {
      const person = holen(kommentar.author);
      if (!person) continue;
      person.zahlen.kommentare += 1;
      erreicht(person, 'diskussion', kommentar.createdAt);
      melden(person, kommentar.createdAt, 'kommentar', `hat in #${nummer} kommentiert`, kommentar.url);
    }
  };

  // ---------- Issues ----------

  const anmeldungen = [];
  for (const issue of issues) {
    const person = holen(issue.author);
    if (person) {
      if (istAnmeldung(issue)) {
        kader.add(person.login.toLowerCase());
        anmeldungen.push({ issue, person });
        erreicht(person, 'anmeldung', issue.createdAt);
        person.name = person.name || nameAusAnmeldung(issue);
        melden(person, issue.createdAt, 'anmeldung', 'hat sich angemeldet', issue.url);
      } else {
        person.zahlen.issues += 1;
        erreicht(person, 'diskussion', issue.createdAt);
        melden(person, issue.createdAt, 'issue', `hat Issue #${issue.number} erstellt`, issue.url);
      }
    }
    kommentareZaehlen(issue.comments.nodes, issue.number);
  }

  // ---------- Pull Requests ----------

  const profilAutor = new Map(); // teilnehmer/<datei>.md -> Login der Person, die sie per PR hinzugefügt hat
  for (const pr of pulls) {
    const autor = holen(pr.author);
    const dateien = pr.files.nodes.map((datei) => datei.path);

    if (autor) {
      autor.zahlen.prs += 1;
      autor.zahlen.commits += pr.commits.totalCount;
      erreicht(autor, 'pr', pr.createdAt);
      // Ein Branch im selben Repository geht nur mit Schreibrechten, also als Collaborator.
      if (!pr.isCrossRepository) erreicht(autor, 'team', pr.createdAt);
      melden(autor, pr.createdAt, 'pr', `hat Pull Request #${pr.number} geöffnet`, pr.url);

      if (pr.mergedAt) {
        autor.zahlen.gemerged += 1;
        erreicht(autor, 'merge', pr.mergedAt);
        const projekt = dateien.some((datei) => datei.startsWith('projekt/'));
        if (projekt) erreicht(autor, 'projekt', pr.mergedAt);
        melden(autor, pr.mergedAt, projekt ? 'projekt' : 'merge', `hat Pull Request #${pr.number} gemerged`, pr.url);
        for (const datei of dateien) {
          const schluessel = datei.toLowerCase();
          if (/^teilnehmer\/[^/]+\.md$/.test(schluessel) && !profilAutor.has(schluessel)) profilAutor.set(schluessel, autor.login);
        }
      }
    }

    for (const review of pr.reviews.nodes) {
      const person = holen(review.author);
      if (!person || !review.submittedAt) continue; // noch nicht abgeschickte Reviews ignorieren
      if (autor && person === autor) {
        // Antwort im eigenen PR zählt als Diskussion, nicht als Review
        person.zahlen.kommentare += 1;
        erreicht(person, 'diskussion', review.submittedAt);
        continue;
      }
      person.reviewtePRs.add(pr.number);
      erreicht(person, 'review', review.submittedAt);
      melden(person, review.submittedAt, 'review', reviewText(review.state, pr.number), review.url);
    }

    kommentareZaehlen(pr.comments.nodes, pr.number);
  }

  // ---------- Steckbriefe in teilnehmer/ ----------

  const ordner = 'teilnehmer';
  if (fs.existsSync(ordner)) {
    for (const datei of fs.readdirSync(ordner)) {
      if (!/\.md$/i.test(datei) || /^(readme|vorlage)\.md$/i.test(datei)) continue;
      const login = profilAutor.get(`${ordner}/${datei}`.toLowerCase()) || datei.replace(/\.md$/i, '');
      if (!GUELTIGER_LOGIN.test(login)) continue;
      const person = holen({ login });
      if (!person) continue;
      kader.add(person.login.toLowerCase());
      person.profil = true;
      const profil = profilLesen(fs.readFileSync(path.join(ordner, datei), 'utf8'));
      if (profil.name) person.name = profil.name;
      if (profil.emoji) person.emoji = profil.emoji;
      if (profil.ziel) person.ziel = profil.ziel;
    }
  }

  // ---------- Mitglieder (Collaborators) ----------

  const mitgliedLogins = new Set();
  for (const mitglied of mitglieder || []) {
    const person = holen({ login: mitglied.login, avatarUrl: mitglied.avatar_url && `${mitglied.avatar_url}&s=96` });
    mitgliedLogins.add(mitglied.login.toLowerCase());
    if (!person) continue;
    kader.add(person.login.toLowerCase());
    erreicht(person, 'team');
  }

  // Wer im Team ist oder einen Steckbrief hat, ist offensichtlich angemeldet.
  for (const person of personen.values()) {
    if (!person.erledigt.anmeldung && (person.erledigt.team || person.profil)) {
      person.erledigt.anmeldung = person.erledigt.team || true;
    }
    person.zahlen.reviews = person.reviewtePRs.size;
  }

  // ---------- Anmelde-Issues betreuen ----------

  await anmeldungenBetreuen({ github, context, core, owner, repo, seitenUrl, anmeldungen, mitglieder, mitgliedLogins });

  // ---------- Ergebnis schreiben ----------

  const teilnehmer = [...kader]
    .map((schluessel) => personen.get(schluessel))
    .filter(Boolean)
    .map((p) => ({
      login: p.login,
      name: p.name || p.login,
      avatar: p.avatar,
      emoji: p.emoji,
      ziel: p.ziel,
      erledigt: Object.fromEntries(SCHRITTE.filter((s) => p.erledigt[s.id]).map((s) => [s.id, p.erledigt[s.id]])),
      zahlen: p.zahlen,
      letzteAktivitaet: p.letzteAktivitaet,
    }))
    .sort((a, b) => a.name.localeCompare(b.name, 'de'));

  const feed = aktivitaet
    .filter((eintrag) => kader.has(eintrag.login.toLowerCase()))
    .sort((a, b) => (a.zeit < b.zeit ? 1 : a.zeit > b.zeit ? -1 : 0))
    .slice(0, MAX_AKTIVITAET);

  const daten = {
    klasse: klasse.klasse || repo,
    repository: `${owner}/${repo}`,
    plaetze: Number(klasse.plaetze) || 12,
    aktualisiert: new Date().toISOString(),
    schritte: SCHRITTE,
    teilnehmer,
    aktivitaet: feed,
    hinweise,
  };
  fs.writeFileSync('fortschritt.json', `${JSON.stringify(daten, null, 2)}\n`);

  core.info(`${teilnehmer.length} Teilnehmende, ${pulls.length} Pull Requests, ${issues.length} Issues ausgewertet.`);
  await core.summary
    .addHeading(`Fortschritt ${daten.klasse}`)
    .addTable([
      [{ data: 'Name', header: true }, { data: 'Login', header: true }, { data: 'Schritte', header: true },
        ...SCHRITTE.map((s) => ({ data: s.titel, header: true }))],
      ...teilnehmer.map((t) => [t.name, `@${t.login}`, `${Object.keys(t.erledigt).length}/${SCHRITTE.length}`,
        ...SCHRITTE.map((s) => (t.erledigt[s.id] ? 'x' : ''))]),
    ])
    .addLink('Klassenliste öffnen', `${seitenUrl}fortschritt.html`)
    .write();
};

// ---------- Hilfsfunktionen ----------

async function alleSeiten(github, abfrage, variablen, feld) {
  const ergebnis = [];
  let cursor = null;
  do {
    const antwort = await github.graphql(abfrage, { ...variablen, cursor });
    const verbindung = antwort.repository[feld];
    ergebnis.push(...verbindung.nodes);
    cursor = verbindung.pageInfo.hasNextPage ? verbindung.pageInfo.endCursor : null;
  } while (cursor);
  return ergebnis;
}

async function mitgliederLaden(github, owner, repo, core) {
  try {
    return await github.paginate(github.rest.repos.listCollaborators, { owner, repo, per_page: 100 });
  } catch (fehler) {
    core.warning(`Mitgliederliste nicht lesbar: ${fehler.message}`);
    return null;
  }
}

// Veröffentlichen klappt nur, wenn Pages eingeschaltet ist und aus GitHub Actions baut.
async function pagesAktiv(github, owner, repo, core) {
  try {
    const { data } = await github.rest.repos.getPages({ owner, repo });
    if (data.build_type === 'workflow') return true;
    core.warning('GitHub Pages veröffentlicht direkt aus einem Branch. Für den Live-Fortschritt unter Settings → Pages als Source „GitHub Actions“ wählen.');
    return false;
  } catch (fehler) {
    if (fehler.status !== 404) return true; // unklar – dann einfach versuchen
    core.warning('GitHub Pages ist noch nicht eingeschaltet: Settings → Pages → Source „GitHub Actions“ wählen und diesen Workflow erneut starten.');
    return false;
  }
}

async function labelsAnlegen(github, owner, repo, core) {
  try {
    const vorhanden = await github.paginate(github.rest.issues.listLabelsForRepo, { owner, repo, per_page: 100 });
    const namen = new Map(vorhanden.map((label) => [label.name.toLowerCase(), label]));
    for (const label of LABELS) {
      const alt = namen.get(label.name);
      if (!alt) await github.rest.issues.createLabel({ owner, repo, ...label });
      // Beim Anlegen eines Issues automatisch erzeugte Labels sind grau und ohne Beschreibung.
      else if (alt.color === 'ededed' && !alt.description) {
        await github.rest.issues.updateLabel({ owner, repo, name: alt.name, color: label.color, description: label.description });
      }
    }
  } catch (fehler) {
    core.warning(`Labels konnten nicht angelegt werden: ${fehler.message}`);
  }
}

async function anmeldungenBetreuen({ github, context, core, owner, repo, seitenUrl, anmeldungen, mitglieder, mitgliedLogins }) {
  const istMitglied = (login) => mitgliedLogins.has(login.toLowerCase());
  const erledigt = new Set();

  try {
    // Neue Anmeldung: Label setzen und die nächsten Schritte erklären
    if (context.eventName === 'issues' && context.payload.action === 'opened') {
      const issue = context.payload.issue;
      const login = issue.user && issue.user.login;
      const hatLabel = (issue.labels || []).some((label) => label.name.toLowerCase() === 'anmeldung');
      if (login && istAnmeldung({ title: issue.title, labels: { nodes: issue.labels || [] } })) {
        if (!hatLabel) await github.rest.issues.addLabels({ owner, repo, issue_number: issue.number, labels: ['anmeldung'] });
        if (mitglieder && istMitglied(login)) {
          await schliessen(github, owner, repo, issue.number, `Hallo @${login}, du bist schon im Team. Weiter geht es mit [Schritt 3 der Anleitung](${seitenUrl}#schritt-3).`);
          erledigt.add(issue.number);
        } else {
          await github.rest.issues.createComment({
            owner, repo, issue_number: issue.number,
            body: [
              `Hallo @${login}, danke für deine Anmeldung.`,
              '',
              'So geht es weiter:',
              `1. @${owner} lädt dich als Collaborator in dieses Repository ein. Du bekommst dazu eine E-Mail von GitHub.`,
              `2. Nimm die Einladung an: https://github.com/${owner}/${repo}/invitations`,
              `3. Danach geht es mit [Schritt 3 der Anleitung](${seitenUrl}#schritt-3) weiter.`,
              '',
              `Dieses Issue wird automatisch geschlossen, sobald du die Einladung angenommen hast.`,
            ].join('\n'),
          });
        }
      }
    }

    // Einladung angenommen: offene Anmelde-Issues schließen
    if (mitglieder) {
      for (const { issue, person } of anmeldungen) {
        if (issue.state !== 'OPEN' || erledigt.has(issue.number) || !istMitglied(person.login)) continue;
        await schliessen(github, owner, repo, issue.number, `@${person.login} hat die Einladung angenommen und ist jetzt im Team. Weiter geht es mit [Schritt 3 der Anleitung](${seitenUrl}#schritt-3).`);
      }
    }
  } catch (fehler) {
    core.warning(`Anmelde-Issues konnten nicht bearbeitet werden: ${fehler.message}`);
  }
}

async function schliessen(github, owner, repo, nummer, text) {
  await github.rest.issues.createComment({ owner, repo, issue_number: nummer, body: text });
  await github.rest.issues.update({ owner, repo, issue_number: nummer, state: 'closed', state_reason: 'completed' });
}

function istAnmeldung(issue) {
  const labels = (issue.labels && issue.labels.nodes) || [];
  return labels.some((label) => label.name.toLowerCase() === 'anmeldung') || /^\s*anmeldung\b/i.test(issue.title || '');
}

function nameAusAnmeldung(issue) {
  // Das Issue-Formular erzeugt "### Name (…)\n\nMax M."
  const ausFormular = (issue.body || '').match(/###\s*Name[^\n]*\n+\s*([^\n]+)/i);
  const roh = ausFormular ? ausFormular[1] : (issue.title || '').replace(/^\s*anmeldung\s*[:\-–]?\s*/i, '');
  const name = bereinigen(roh);
  if (!name || /^_?no response_?$/i.test(name)) return null;
  return kuerzen(name, 40);
}

function profilLesen(text) {
  const zeile = (muster) => {
    const treffer = text.match(muster);
    return treffer ? bereinigen(treffer[1]) : null;
  };
  const name = zeile(/^#[ \t]+(.+)$/m);
  const emoji = zeile(/emoji[ \t*:]*(.+)$/im);
  const ziel = zeile(/lernen[ \t*:]*(.+)$/im);
  return {
    name: name ? kuerzen(name, 40) : null,
    emoji: emoji ? erstesZeichen(emoji) : null,
    ziel: ziel ? kuerzen(ziel, 90) : null,
  };
}

function bereinigen(text) {
  return String(text).replace(/[*_`<>#]/g, '').replace(/\s+/g, ' ').trim();
}

function kuerzen(text, laenge = 60) {
  const zeichen = Array.from(String(text));
  return zeichen.length > laenge ? `${zeichen.slice(0, laenge - 1).join('')}…` : String(text);
}

function erstesZeichen(text) {
  const segmente = new Intl.Segmenter('de', { granularity: 'grapheme' }).segment(text);
  const erstes = segmente[Symbol.iterator]().next().value;
  return erstes ? erstes.segment : null;
}

function reviewText(zustand, nummer) {
  switch (zustand) {
    case 'APPROVED': return `hat Pull Request #${nummer} freigegeben`;
    case 'CHANGES_REQUESTED': return `hat bei Pull Request #${nummer} Änderungen angefragt`;
    default: return `hat Pull Request #${nummer} geprüft`;
  }
}
