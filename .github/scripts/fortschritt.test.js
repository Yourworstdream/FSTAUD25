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

function pr(nummer, autor, { gemerged = null, dateien = [], reviews = [], fork = false, state = gemerged ? 'MERGED' : 'OPEN' } = {}) {
  return {
    number: nummer, title: `PR ${nummer}`, url: `https://github.com/o/r/pull/${nummer}`, createdAt: `2026-10-01T09:${String(nummer).padStart(2, '0')}:00Z`,
    state, mergedAt: gemerged, isCrossRepository: fork, author: U(autor), commits: { totalCount: 1 },
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
        listCollaborators: async () => {
          if (!mitglieder) throw Object.assign(new Error('Forbidden'), { status: 403 }); // null: Liste nicht lesbar
          return { data: mitglieder.map((login) => ({ login, avatar_url: `https://avatars.example/${login}?v=4` })) };
        },
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

test('begrüßt offene Anmeldungen bei jedem Lauf und setzt das Label', async () => {
  // Der Lauf zum Ereignis „opened“ kann verdrängt worden sein – ein späterer Lauf holt die Begrüßung nach.
  const neu = issue(5, 'aylin', 'Anmeldung: Aylin S.');
  const { aufrufe } = await ausfuehren({ issues: [neu], context: { eventName: 'schedule' } });
  assert.ok(aufrufe.some(([art, nr]) => art === 'addLabels' && nr === 5));
  const gruss = aufrufe.filter(([art, nr]) => art === 'kommentar' && nr === 5);
  assert.strictEqual(gruss.length, 1);
  assert.match(gruss[0][2], /danke für deine Anmeldung/);
  assert.match(gruss[0][2], /angenommen/);
});

test('begrüßt nicht doppelt und lässt vorhandene Labels in Ruhe', async () => {
  const begruesst = issue(5, 'aylin', 'Anmeldung: Aylin S.', { labels: ['anmeldung'], kommentare: [['bot', '2026-10-01T09:00:00Z']] });
  const { aufrufe } = await ausfuehren({ issues: [begruesst], context: { eventName: 'push' } });
  assert.ok(!aufrufe.some(([art]) => art === 'kommentar' || art === 'addLabels' || art === 'update'));
});

test('„angenommen“ ohne Einladung bekommt einen Hinweis, mit Einladung wird geschlossen', async () => {
  const anmeldung = issue(6, 'deniz', 'Anmeldung: Deniz A.', {
    labels: ['anmeldung'],
    kommentare: [['bot', '2026-10-01T09:00:00Z'], ['deniz', '2026-10-01T09:10:00Z']],
  });

  const ohne = await ausfuehren({ issues: [anmeldung] });
  const hinweise = ohne.aufrufe.filter(([art, nr, text]) => art === 'kommentar' && nr === 6 && /noch nicht angenommen/.test(text));
  assert.strictEqual(hinweise.length, 1);
  assert.ok(!ohne.aufrufe.some(([art]) => art === 'update'));

  // Bot hat schon geantwortet: kein zweiter Hinweis
  const beantwortet = issue(6, 'deniz', anmeldung.title, {
    labels: ['anmeldung'],
    kommentare: [['bot', '2026-10-01T09:00:00Z'], ['deniz', '2026-10-01T09:10:00Z'], ['bot', '2026-10-01T09:11:00Z']],
  });
  assert.ok(!(await ausfuehren({ issues: [beantwortet] })).aufrufe.some(([art]) => art === 'kommentar'));

  // Mitgliederliste nicht lesbar: lieber schweigen
  assert.ok(!(await ausfuehren({ issues: [anmeldung], mitglieder: null })).aufrufe.some(([art]) => art === 'kommentar'));

  const mit = await ausfuehren({ issues: [anmeldung], mitglieder: [OWNER, 'deniz'] });
  assert.ok(mit.aufrufe.some(([art, nr, text]) => art === 'kommentar' && nr === 6 && /hat die Einladung angenommen/.test(text)));
  assert.ok(mit.aufrufe.some(([art, nr, state]) => art === 'update' && nr === 6 && state === 'closed'));
  assert.ok(mit.person('deniz').erledigt.team);
});

test('schließt Anmeldungen von Personen, die schon im Team sind, ohne Begrüßung', async () => {
  const { aufrufe } = await ausfuehren({ issues: [issue(7, 'ole', 'Anmeldung: Ole')], mitglieder: [OWNER, 'ole'] });
  const texte = aufrufe.filter(([art]) => art === 'kommentar').map(([, , text]) => text);
  assert.strictEqual(texte.length, 1);
  assert.match(texte[0], /du bist schon im Team/);
  assert.ok(aufrufe.some(([art, nr, state]) => art === 'update' && nr === 7 && state === 'closed'));
});

test('offen: zeigt, wer auf was wartet, die längste Wartezeit zuerst', async () => {
  const { daten } = await ausfuehren({
    mitglieder: [OWNER, 'lena', 'jonas', 'mia', 'ben'],
    issues: [
      issue(1, 'tim', 'Anmeldung: Tim B.', { labels: ['anmeldung'], kommentare: [['bot', '2026-10-01T08:30:00Z']] }),
      issue(2, 'fremd', 'Hilfe beim Klonen', { labels: ['Hilfe'] }),
      issue(3, 'lena', 'Erledigt', { labels: ['hilfe'], state: 'CLOSED' }),
      issue(4, 'lena', 'Anmeldung: Lena K.', { labels: ['anmeldung'], state: 'CLOSED' }),
    ],
    pulls: [
      pr(10, 'lena'),
      pr(11, 'jonas', { reviews: [['lena', 'APPROVED', '2026-10-01T12:00:00Z'], ['lena', 'COMMENTED', '2026-10-01T12:30:00Z']] }),
      pr(12, 'mia', { reviews: [['lena', 'APPROVED', '2026-10-01T10:00:00Z'], ['jonas', 'CHANGES_REQUESTED', '2026-10-01T11:00:00Z']] }),
      pr(13, 'ben', { reviews: [['lena', 'CHANGES_REQUESTED', '2026-10-01T10:00:00Z'], ['lena', 'APPROVED', '2026-10-01T13:00:00Z']] }),
      pr(14, 'ben', { reviews: [['ben', 'APPROVED', '2026-10-01T10:00:00Z'], ['lena', 'PENDING', null], ['jonas', 'DISMISSED', '2026-10-01T10:30:00Z']] }),
      pr(15, 'lena', { gemerged: '2026-10-01T14:00:00Z' }),
      pr(16, 'lena', { state: 'CLOSED' }),
      pr(17, 'fremd', { fork: true }),
    ],
  });
  const kurz = daten.offen.map((e) => [e.typ, e.login, e.seit]);
  assert.deepStrictEqual(kurz, [
    ['einladung', 'tim', '2026-10-01T08:01:00Z'],
    ['hilfe', 'fremd', '2026-10-01T08:02:00Z'],
    ['review', 'lena', '2026-10-01T09:10:00Z'],
    ['review', 'ben', '2026-10-01T09:14:00Z'],
    ['aendern', 'mia', '2026-10-01T11:00:00Z'],
    ['merge', 'jonas', '2026-10-01T12:00:00Z'],
    ['merge', 'ben', '2026-10-01T13:00:00Z'],
  ]);
  assert.deepStrictEqual(daten.offen[0], {
    typ: 'einladung', login: 'tim', name: 'Tim B.', text: 'wartet auf die Einladung',
    url: 'https://github.com/o/r/issues/1', seit: '2026-10-01T08:01:00Z',
  });
  const text = (typ, login) => daten.offen.find((e) => e.typ === typ && e.login === login).text;
  assert.strictEqual(text('aendern', 'mia'), 'soll Pull Request #12 überarbeiten');
  assert.strictEqual(text('merge', 'jonas'), 'kann Pull Request #11 mergen');
  assert.strictEqual(text('review', 'lena'), 'wartet auf ein Review für Pull Request #10');
  assert.strictEqual(text('hilfe', 'fremd'), 'braucht Hilfe (Issue #2)');
  assert.strictEqual(daten.offen.find((e) => e.typ === 'merge' && e.login === 'jonas').url, 'https://github.com/o/r/pull/11');
});

test('offen: ohne lesbare Mitgliederliste keine Einladungs-Einträge, PRs ohne state gelten nach mergedAt', async () => {
  const ohneState = { ...pr(10, 'tim'), state: undefined };
  const gemergedOhneState = { ...pr(11, 'tim', { gemerged: '2026-10-01T12:00:00Z' }), state: undefined };
  const { daten } = await ausfuehren({
    mitglieder: null,
    issues: [issue(1, 'tim', 'Anmeldung: Tim B.', { labels: ['anmeldung'] })],
    pulls: [ohneState, gemergedOhneState],
  });
  assert.deepStrictEqual(daten.offen.map((e) => [e.typ, e.login]), [['review', 'tim']]);
});

test('veröffentlicht nur, wenn GitHub Pages eingeschaltet ist', async () => {
  assert.strictEqual((await ausfuehren({ pages: true })).ausgaben.pages, 'true');
  assert.strictEqual((await ausfuehren({ pages: false })).ausgaben.pages, 'false');
});
