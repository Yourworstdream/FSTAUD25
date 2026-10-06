// Tests für fortschritt.js mit nachgebauter GitHub-API. Ausführen mit:
//   node --test .github/scripts/fortschritt.test.js

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const berechnen = require('./fortschritt.js');

const OWNER = 'Lehrkraft';
const U = (login) => ({ __typename: 'User', login, avatarUrl: `https://avatars.example/${login}` });
const BOT = { __typename: 'Bot', login: 'github-actions', avatarUrl: 'https://avatars.example/bot' };

function issue(nummer, autor, titel, { labels = [], kommentare = [], body = '', state = 'OPEN' } = {}) {
  return {
    number: nummer, title: titel, url: `https://github.com/o/r/issues/${nummer}`, createdAt: `2026-10-01T08:${String(nummer).padStart(2, '0')}:00Z`,
    state, body, author: U(autor), labels: { nodes: labels.map((name) => ({ name })) },
    comments: { nodes: kommentare.map(([wer, zeit]) => ({ author: wer === 'bot' ? BOT : U(wer), createdAt: zeit, url: `https://github.com/o/r/issues/${nummer}#c` })) },
  };
}

function pr(nummer, autor, { gemerged = null, dateien = [], reviews = [], fork = false } = {}) {
  return {
    number: nummer, title: `PR ${nummer}`, url: `https://github.com/o/r/pull/${nummer}`, createdAt: `2026-10-01T09:${String(nummer).padStart(2, '0')}:00Z`,
    mergedAt: gemerged, isCrossRepository: fork, author: U(autor), commits: { totalCount: 1 },
    files: { nodes: dateien.map((p) => ({ path: p })) },
    reviews: { nodes: reviews.map(([wer, state, zeit]) => ({ author: U(wer), state, submittedAt: zeit, url: `https://github.com/o/r/pull/${nummer}#r` })) },
    comments: { nodes: [] },
  };
}

// Führt das Skript in einem leeren Ordner aus und gibt Ergebnis und API-Aufrufe zurück.
async function ausfuehren({ issues = [], pulls = [], mitglieder = [OWNER], steckbriefe = {}, context = {}, pages = true }) {
  const ordner = fs.mkdtempSync(path.join(os.tmpdir(), 'fortschritt-'));
  fs.writeFileSync(path.join(ordner, 'klasse.json'), JSON.stringify({ klasse: 'Testklasse', plaetze: 12, ignorieren: [] }));
  fs.mkdirSync(path.join(ordner, 'teilnehmer'));
  fs.writeFileSync(path.join(ordner, 'teilnehmer', 'README.md'), '# Steckbriefe');
  for (const [datei, inhalt] of Object.entries(steckbriefe)) fs.writeFileSync(path.join(ordner, 'teilnehmer', datei), inhalt);

  const aufrufe = [];
  const ausgaben = {};
  const seiten = (liste, cursor) => {
    const start = cursor ? Number(cursor) : 0;
    const weiter = start + 2 < liste.length;
    return { nodes: liste.slice(start, start + 2), pageInfo: { hasNextPage: weiter, endCursor: weiter ? String(start + 2) : null } };
  };
  const github = {
    graphql: async (abfrage, v) => (abfrage.includes('pullRequests')
      ? { repository: { pullRequests: seiten(pulls, v.cursor) } }
      : { repository: { issues: seiten(issues, v.cursor) } }),
    paginate: async (fn, parameter) => (await fn(parameter)).data,
    rest: {
      repos: {
        getPages: async () => {
          if (pages) return { data: { build_type: 'workflow' } };
          throw Object.assign(new Error('Not Found'), { status: 404 });
        },
        listCollaborators: async () => ({ data: mitglieder.map((login) => ({ login, avatar_url: `https://avatars.example/${login}?v=4` })) }),
      },
      issues: {
        listLabelsForRepo: async () => ({ data: [] }),
        createLabel: async (p) => aufrufe.push(['label', p.name]),
        updateLabel: async (p) => aufrufe.push(['labelFarbe', p.name]),
        addLabels: async (p) => aufrufe.push(['addLabels', p.issue_number]),
        createComment: async (p) => aufrufe.push(['kommentar', p.issue_number, p.body]),
        update: async (p) => aufrufe.push(['update', p.issue_number, p.state]),
      },
    },
  };
  const summary = { addHeading() { return this; }, addTable() { return this; }, addLink() { return this; }, write: async () => {} };
  const core = { setOutput: (k, v) => { ausgaben[k] = v; }, info() {}, warning() {}, summary };
  const ctx = { repo: { owner: OWNER, repo: 'r' }, eventName: 'schedule', payload: {}, ...context };

  const vorher = process.cwd();
  process.chdir(ordner);
  try {
    await berechnen({ github, context: ctx, core });
    const daten = JSON.parse(fs.readFileSync('fortschritt.json', 'utf8'));
    const person = (login) => daten.teilnehmer.find((t) => t.login === login);
    return { daten, person, aufrufe, ausgaben };
  } finally {
    process.chdir(vorher);
    fs.rmSync(ordner, { recursive: true, force: true });
  }
}

test('erkennt alle sieben Schritte', async () => {
  const { person, daten } = await ausfuehren({
    mitglieder: [OWNER, 'lena'],
    issues: [
      issue(1, 'lena', 'Anmeldung: Lena K.', { labels: ['anmeldung'], body: '### Name (Vorname)\n\nLena Kowalski' }),
      issue(2, OWNER, 'Thema 03', { labels: ['thema'], kommentare: [['lena', '2026-10-01T10:00:00Z'], ['bot', '2026-10-01T10:01:00Z']] }),
    ],
    pulls: [
      pr(10, 'lena', { gemerged: '2026-10-01T11:00:00Z', dateien: ['teilnehmer/lena.md'] }),
      pr(11, 'jonas', { reviews: [['lena', 'APPROVED', '2026-10-01T12:00:00Z']] }),
      pr(12, 'lena', { gemerged: '2026-10-01T13:00:00Z', dateien: ['projekt/themen/03-sensoren.md'] }),
    ],
    steckbriefe: { 'lena.md': '# Lena K.\n\n- Das will ich lernen: Git' },
  });
  const lena = person('lena');
  assert.deepStrictEqual(Object.keys(lena.erledigt).sort(), ['anmeldung', 'diskussion', 'merge', 'pr', 'projekt', 'review', 'team']);
  assert.strictEqual(lena.name, 'Lena K.', 'Name aus dem Steckbrief geht vor');
  assert.strictEqual(lena.zahlen.reviews, 1);
  assert.ok(!daten.teilnehmer.some((t) => t.login === 'github-actions'), 'Bots tauchen nicht auf');
  assert.ok(daten.aktivitaet.length > 0 && daten.aktivitaet[0].zeit >= daten.aktivitaet[1].zeit, 'neueste Aktivität zuerst');
});

test('zählt nur, was wirklich zählt', async () => {
  const { person, daten } = await ausfuehren({
    issues: [
      issue(1, 'tim', 'Anmeldung: Tim B.', { labels: ['anmeldung'], kommentare: [['tim', '2026-10-01T10:00:00Z']] }),
    ],
    pulls: [
      pr(10, 'tim'),
      pr(11, 'paul', { reviews: [['paul', 'COMMENTED', '2026-10-01T11:00:00Z']] }),
      pr(12, 'fremd', { fork: true }),
    ],
    mitglieder: [OWNER, 'paul'],
  });
  const tim = person('tim');
  assert.ok(!tim.erledigt.diskussion, 'Kommentar im eigenen Anmelde-Issue ist keine Diskussion');
  assert.ok(tim.erledigt.team, 'Branch im selben Repository heißt: im Team');
  const paul = person('paul');
  assert.ok(!paul.erledigt.review, 'Review im eigenen PR zählt nicht als Review');
  assert.ok(paul.erledigt.diskussion, 'Antwort im eigenen PR zählt als Diskussion');
  assert.ok(!daten.teilnehmer.some((t) => t.login === 'fremd'), 'Fremde ohne Anmeldung bleiben draußen');
});

test('ordnet einen falsch benannten Steckbrief der Person zu, die ihn gemerged hat', async () => {
  const { person, daten } = await ausfuehren({
    pulls: [pr(10, 'mara-w', { gemerged: '2026-10-01T11:00:00Z', dateien: ['teilnehmer/Mara.md'] })],
    steckbriefe: { 'Mara.md': '# Mara W.' },
  });
  assert.strictEqual(person('mara-w').name, 'Mara W.');
  assert.ok(!daten.teilnehmer.some((t) => t.login === 'Mara'));
});

test('begrüßt neue Anmeldungen und setzt das Label', async () => {
  const neu = issue(5, 'aylin', 'Anmeldung: Aylin S.');
  const { aufrufe } = await ausfuehren({
    issues: [neu],
    context: { eventName: 'issues', payload: { action: 'opened', issue: { number: 5, title: neu.title, user: { login: 'aylin' }, labels: [] } } },
  });
  assert.ok(aufrufe.some(([art, nr]) => art === 'addLabels' && nr === 5));
  const gruss = aufrufe.find(([art, nr]) => art === 'kommentar' && nr === 5);
  assert.match(gruss[2], /angenommen/);
});

test('„angenommen“ ohne Einladung bekommt einen Hinweis, mit Einladung wird geschlossen', async () => {
  const anmeldung = issue(6, 'deniz', 'Anmeldung: Deniz A.', { labels: ['anmeldung'] });
  const ereignis = {
    eventName: 'issue_comment',
    payload: { action: 'created', comment: { user: { login: 'deniz' } }, issue: { number: 6, title: anmeldung.title, state: 'open', user: { login: 'deniz' }, labels: [{ name: 'anmeldung' }] } },
  };

  const ohne = await ausfuehren({ issues: [anmeldung], context: ereignis });
  assert.ok(ohne.aufrufe.some(([art, nr, text]) => art === 'kommentar' && nr === 6 && /noch nicht angenommen/.test(text)));
  assert.ok(!ohne.aufrufe.some(([art]) => art === 'update'));

  const mit = await ausfuehren({ issues: [anmeldung], context: ereignis, mitglieder: [OWNER, 'deniz'] });
  assert.ok(mit.aufrufe.some(([art, nr, state]) => art === 'update' && nr === 6 && state === 'closed'));
  assert.ok(mit.person('deniz').erledigt.team);
});

test('veröffentlicht nur, wenn GitHub Pages eingeschaltet ist', async () => {
  assert.strictEqual((await ausfuehren({ pages: true })).ausgaben.pages, 'true');
  assert.strictEqual((await ausfuehren({ pages: false })).ausgaben.pages, 'false');
});
