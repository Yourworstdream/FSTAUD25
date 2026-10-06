/* Klassenliste: lädt fortschritt.json alle 20 Sekunden neu.
   Die Datei berechnet die Action .github/workflows/fortschritt.yml nach jeder Aktivität im Repository. */
(() => {
  'use strict';
  const { SCHRITTE, escape, relativeZeit, uhrzeit, anzahlErledigt } = FST;

  const params = new URLSearchParams(location.search);
  const DEMO = params.has('demo');
  const ICH = (params.get('ich') || '').toLowerCase();
  const INTERVALL = DEMO ? 5000 : 20000;
  const VERALTET_NACH = 45 * 60 * 1000;
  const HAKEN = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  const $ = (id) => document.getElementById(id);
  let daten = null;
  let zustand = 'laden'; // laden | ok | leer | fehler
  let signatur = '';
  let bekannteSchritte = null; // "login|schritt" – um Neues kurz zu markieren
  let bekannterVerlauf = null;

  const key = (t) => String(t.login).toLowerCase();
  const initialen = (name) => String(name).split(/[\s._-]+/).filter(Boolean).slice(0, 2).map((w) => Array.from(w)[0].toUpperCase()).join('');

  function teilnehmer() {
    return ((daten && daten.teilnehmer) || [])
      .filter((t) => t && t.login)
      .map((t) => ({ ...t, name: t.name || t.login, erledigt: t.erledigt || {} }))
      .sort((a, b) => a.name.localeCompare(b.name, 'de'));
  }

  function personHtml(t) {
    const bild = typeof t.avatar === 'string' && t.avatar.startsWith('https://')
      ? `<img src="${escape(t.avatar)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
      : `<span class="ini" aria-hidden="true">${escape(initialen(t.name))}</span>`;
    return `<span class="person">${bild}<span>${escape(t.name)}<small>@${escape(t.login)}</small></span></span>`;
  }

  // ---------- Anzeige ----------

  function render() {
    const liste = teilnehmer();
    const plaetze = Math.max(Number(daten && daten.plaetze) || 12, liste.length);
    const erledigtJetzt = new Set(liste.flatMap((t) => SCHRITTE.filter((s) => t.erledigt[s.id]).map((s) => `${key(t)}|${s.id}`)));
    const neu = (id) => bekannteSchritte !== null && !bekannteSchritte.has(id);

    const kopf = `<thead><tr><th scope="col">Name</th>${SCHRITTE.map((s) =>
      `<th scope="col" title="${s.nr}: ${escape(s.text)}">${s.nr}<span class="wort">${escape(s.kurz)}</span></th>`).join('')}<th scope="col" class="stand">Stand</th></tr></thead>`;

    const zeilen = liste.map((t) => {
      const zellen = SCHRITTE.map((s) => {
        const id = `${key(t)}|${s.id}`;
        return t.erledigt[s.id]
          ? `<td class="ja${neu(id) ? ' neu' : ''}" title="${escape(s.text)}">${HAKEN}<span class="visuell-versteckt">erledigt</span></td>`
          : '<td class="nein"><span class="visuell-versteckt">offen</span></td>';
      }).join('');
      return `<tr${key(t) === ICH ? ' class="ich"' : ''}><th scope="row">${personHtml(t)}</th>${zellen}<td class="stand">${anzahlErledigt(t)}/7</td></tr>`;
    });
    for (let i = liste.length; i < plaetze; i++) {
      zeilen.push(`<tr class="frei"><th scope="row">frei</th>${'<td></td>'.repeat(SCHRITTE.length)}<td class="stand"></td></tr>`);
    }
    const summen = SCHRITTE.map((s) => `<td>${liste.filter((t) => t.erledigt[s.id]).length}</td>`).join('');
    const fuss = `<tfoot><tr><th scope="row">erledigt</th>${summen}<td class="stand"></td></tr></tfoot>`;
    $('liste').innerHTML = `${kopf}<tbody>${zeilen.join('')}</tbody>${fuss}`;

    const schritte = liste.reduce((summe, t) => summe + anzahlErledigt(t), 0);
    const prozent = Math.round((schritte / (plaetze * SCHRITTE.length)) * 100);
    $('zusammenfassung').textContent = `${liste.length} von ${plaetze} angemeldet · ${prozent} % aller Schritte erledigt`;

    renderVerlauf(liste);
    bekannteSchritte = erledigtJetzt;
  }

  function renderVerlauf(liste) {
    const namen = new Map(liste.map((t) => [key(t), t.name]));
    const eintraege = ((daten && daten.aktivitaet) || []).slice(0, 10);
    const id = (a) => `${a.zeit}|${a.login}|${a.text}`;
    if (!eintraege.length) {
      $('verlauf').innerHTML = '<li class="leise">Noch nichts passiert.</li>';
    } else {
      $('verlauf').innerHTML = eintraege.map((a) => {
        const text = `${escape(namen.get(String(a.login).toLowerCase()) || a.login)} ${escape(a.text)}`;
        const url = typeof a.url === 'string' && a.url.startsWith('https://github.com/') ? a.url : null;
        const neu = bekannterVerlauf !== null && !bekannterVerlauf.has(id(a));
        return `<li${neu ? ' class="neu"' : ''}><time datetime="${escape(a.zeit)}">${escape(uhrzeit(a.zeit))}</time>${url ? `<a href="${escape(url)}">${text}</a>` : text}</li>`;
      }).join('');
    }
    bekannterVerlauf = new Set(eintraege.map(id));
  }

  function legende() {
    $('legende').innerHTML = `${SCHRITTE.map((s) => `${s.nr} = ${escape(s.text)}`).join(' · ')}. Wie das geht, steht in der <a href="./">Anleitung</a>.`;
  }

  function hinweisZeigen() {
    let html = '';
    if (DEMO) {
      html = 'Das sind Testdaten, die sich alle paar Sekunden ändern. <a href="fortschritt.html">Echte Daten ansehen</a>';
    } else if (zustand === 'leer') {
      html = 'Noch keine Daten. Die Liste füllt sich, sobald sich die ersten Leute angemeldet haben.';
    } else if (zustand === 'fehler' && !daten) {
      html = location.protocol === 'file:'
        ? 'Diese Seite funktioniert nur online über GitHub Pages. <a href="fortschritt.html?demo">Beispiel ansehen</a>'
        : 'Die Daten konnten gerade nicht geladen werden. Die Seite versucht es gleich noch mal.';
    } else if (daten && daten.aktualisiert && Date.now() - new Date(daten.aktualisiert).getTime() > VERALTET_NACH) {
      html = `Stand von ${escape(uhrzeit(daten.aktualisiert))} Uhr. Normalerweise wird die Liste spätestens alle 10 Minuten aktualisiert.`;
    }
    $('hinweis').innerHTML = html;
    $('hinweis').hidden = !html;
  }

  function statusZeigen() {
    const el = $('status');
    el.classList.remove('aktuell', 'alt', 'weg');
    if (DEMO) {
      el.textContent = 'Testdaten';
      el.classList.add('aktuell');
    } else if (zustand === 'fehler') {
      el.textContent = 'keine Verbindung';
      el.classList.add('weg');
    } else if (zustand === 'leer') {
      el.textContent = 'noch keine Daten';
    } else if (daten && daten.aktualisiert) {
      const alt = Date.now() - new Date(daten.aktualisiert).getTime() > VERALTET_NACH;
      el.textContent = `aktualisiert ${relativeZeit(daten.aktualisiert)}`;
      el.classList.add(alt ? 'alt' : 'aktuell');
    }
  }

  // ---------- Daten holen ----------

  async function aktualisieren() {
    try {
      const neu = DEMO ? demo().weiter() : await FST.fortschrittLaden();
      if (neu) {
        zustand = 'ok';
        daten = neu;
        const neueSignatur = JSON.stringify([neu.teilnehmer, neu.aktivitaet, neu.plaetze]);
        if (neueSignatur !== signatur) {
          signatur = neueSignatur;
          render();
        }
      } else {
        zustand = 'leer';
        daten = null;
        signatur = '';
        render();
      }
    } catch (fehler) {
      console.warn('Daten nicht geladen:', fehler);
      zustand = 'fehler';
      if (!daten) render();
    }
    hinweisZeigen();
    statusZeigen();
  }

  function planen() {
    setTimeout(() => aktualisieren().then(planen), INTERVALL);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') aktualisieren();
  });

  // ---------- Vollbild für Beamer oder Smartboard ----------

  const vollbildKnopf = $('vollbild');
  function vollbildSetzen(an) {
    document.documentElement.classList.toggle('vollbild', an);
    vollbildKnopf.textContent = an ? 'Vollbild beenden' : 'Vollbild';
  }
  vollbildKnopf.addEventListener('click', async () => {
    const an = !document.documentElement.classList.contains('vollbild');
    vollbildSetzen(an);
    try {
      if (an && !document.fullscreenElement) await document.documentElement.requestFullscreen();
      if (!an && document.fullscreenElement) await document.exitFullscreen();
    } catch { /* ohne echtes Vollbild geht es trotzdem */ }
  });
  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement) vollbildSetzen(false);
  });

  // ---------- Testdaten (?demo) ----------

  let demoDaten = null;
  function demo() {
    if (demoDaten) return demoDaten;
    const namen = ['Lena K.', 'Jonas M.', 'Aylin S.', 'Tim B.', 'Mara W.', 'Niklas H.', 'Sophie R.', 'Deniz A.', 'Paul F.', 'Emma L.', 'Luca T.', 'Mia G.'];
    const texte = {
      anmeldung: () => 'hat sich angemeldet',
      team: () => 'hat die Einladung angenommen',
      pr: (nr) => `hat Pull Request #${nr} geöffnet`,
      merge: (nr) => `hat Pull Request #${nr} gemerged`,
      review: (nr) => `hat Pull Request #${nr} freigegeben`,
      diskussion: (nr) => `hat in #${nr} kommentiert`,
      projekt: (nr) => `hat Pull Request #${nr} gemerged`,
    };
    const stand = { plaetze: 12, teilnehmer: [], aktivitaet: [], aktualisiert: null };
    let nummer = 14;
    const person = (name) => ({ login: name.toLowerCase().replace(/\W+/g, '-').replace(/-$/, ''), name, avatar: null, erledigt: {} });
    const erledigen = (t, s, zeit) => {
      t.erledigt[s.id] = new Date(zeit).toISOString();
      stand.aktivitaet.unshift({ zeit: t.erledigt[s.id], login: t.login, text: texte[s.id](nummer++), url: null });
      stand.aktivitaet.length = Math.min(stand.aktivitaet.length, 20);
    };
    const start = Date.now();
    [7, 6, 5, 5, 4, 4, 3, 3, 2, 1, 1].forEach((ziel, i) => {
      const t = person(namen[i]);
      SCHRITTE.slice(0, ziel).forEach((s, j) => erledigen(t, s, start - (95 - i * 5 - j * 6) * 60000));
      stand.teilnehmer.push(t);
    });
    stand.aktivitaet.sort((a, b) => (a.zeit < b.zeit ? 1 : -1));

    demoDaten = {
      weiter() {
        const offen = stand.teilnehmer.filter((t) => anzahlErledigt(t) < SCHRITTE.length);
        if (stand.teilnehmer.length < namen.length && Math.random() < 0.1) {
          const t = person(namen[stand.teilnehmer.length]);
          erledigen(t, SCHRITTE[0], Date.now());
          stand.teilnehmer.push(t);
        } else if (offen.length && Math.random() < 0.6) {
          const t = offen[Math.floor(Math.random() * offen.length)];
          erledigen(t, SCHRITTE.find((s) => !t.erledigt[s.id]), Date.now());
        }
        stand.aktualisiert = new Date().toISOString();
        return JSON.parse(JSON.stringify(stand));
      },
    };
    return demoDaten;
  }

  // ---------- Start ----------

  legende();
  setInterval(statusZeigen, 15000);
  aktualisieren().then(planen);
})();
