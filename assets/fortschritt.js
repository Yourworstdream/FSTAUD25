/* Klassenliste: lädt fortschritt.json alle 10 Sekunden neu.
   Die Datei berechnet die Action .github/workflows/fortschritt.yml nach jeder Aktivität im Repository. */
(() => {
  'use strict';
  const { SCHRITTE, escape, relativeZeit, uhrzeit, anzahlErledigt } = FST;

  const params = new URLSearchParams(location.search);
  const DEMO = params.has('demo');
  const ICH = (params.get('ich') || '').toLowerCase();
  const BEAMER = params.has('beamer');
  const INTERVALL = DEMO ? 5000 : 10000;
  const VERALTET_NACH = 24 * 60 * 60 * 1000; // GitHub startet geplante Läufe oft nur alle paar Stunden
  const HAKEN = '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  // Wer wartet worauf: Reihenfolge = Dringlichkeit. Die Typen liefert .github/scripts/fortschritt.js.
  const OFFEN = [
    { typ: 'hilfe', titel: 'Braucht Hilfe', kurz: 'braucht Hilfe' },
    { typ: 'einladung', titel: 'Wartet auf die Einladung', kurz: 'wartet auf Einladung' },
    { typ: 'aendern', titel: 'Soll überarbeiten', kurz: 'soll überarbeiten' },
    { typ: 'merge', titel: 'Kann mergen', kurz: 'kann mergen' },
    { typ: 'review', titel: 'Wartet auf ein Review', kurz: 'wartet auf Review' },
  ];

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

  function offenListe() {
    return ((daten && daten.offen) || []).filter((o) => o && o.login && OFFEN.some((art) => art.typ === o.typ));
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

    const offen = offenListe();
    const haengtAn = (t) => OFFEN.find((art) => offen.some((o) => o.typ === art.typ && String(o.login).toLowerCase() === key(t)));
    const standHtml = (t) => {
      const art = haengtAn(t);
      const n = anzahlErledigt(t);
      if (art) return `<td class="stand wartet" title="${n} von 7 Schritten">${escape(art.kurz)}</td>`;
      return `<td class="stand">${n === SCHRITTE.length ? 'fertig' : `${n}/7`}</td>`;
    };

    const zeilen = liste.map((t) => {
      const zellen = SCHRITTE.map((s) => {
        const id = `${key(t)}|${s.id}`;
        return t.erledigt[s.id]
          ? `<td class="ja${neu(id) ? ' neu' : ''}" title="${escape(s.text)}">${HAKEN}<span class="visuell-versteckt">erledigt</span></td>`
          : '<td class="nein"><span class="visuell-versteckt">offen</span></td>';
      }).join('');
      return `<tr${key(t) === ICH ? ' class="ich"' : ''}><th scope="row">${personHtml(t)}</th>${zellen}${standHtml(t)}</tr>`;
    });
    for (let i = liste.length; i < plaetze; i++) {
      zeilen.push(`<tr class="frei"><th scope="row">frei</th>${'<td></td>'.repeat(SCHRITTE.length)}<td class="stand"></td></tr>`);
    }
    const summen = SCHRITTE.map((s) => `<td>${liste.filter((t) => t.erledigt[s.id]).length}</td>`).join('');
    const fuss = `<tfoot><tr><th scope="row">erledigt</th>${summen}<td class="stand"></td></tr></tfoot>`;
    $('liste').innerHTML = `${kopf}<tbody>${zeilen.join('')}</tbody>${fuss}`;

    const schritte = liste.reduce((summe, t) => summe + anzahlErledigt(t), 0);
    const prozent = Math.round((schritte / (plaetze * SCHRITTE.length)) * 100);
    const fertig = liste.filter((t) => anzahlErledigt(t) === SCHRITTE.length).length;
    $('zusammenfassung').textContent = `${liste.length} von ${plaetze} angemeldet · ${fertig} fertig · ${prozent} % aller Schritte erledigt`;

    renderOffen(offen);
    renderVerlauf(liste);
    bekannteSchritte = erledigtJetzt;
  }

  // „Jetzt zu tun“: wer gerade auf jemand anderen wartet. Fehlt die Liste in den Daten, bleibt der Bereich weg.
  function renderOffen(offen) {
    const bereich = $('offen-bereich');
    bereich.hidden = !(daten && Array.isArray(daten.offen));
    if (bereich.hidden) return;
    if (!offen.length) {
      $('offen').innerHTML = '<p class="leise">Gerade wartet niemand.</p>';
      return;
    }
    $('offen').innerHTML = OFFEN.map((art) => {
      const eintraege = offen.filter((o) => o.typ === art.typ);
      if (!eintraege.length) return '';
      const punkte = eintraege.map((o) => {
        const url = typeof o.url === 'string' && o.url.startsWith('https://github.com/') ? o.url : null;
        const wer = `${escape(o.name || o.login)}${art.typ === 'einladung' ? ` <span class="login">@${escape(o.login)}</span>` : ''}`;
        const seit = o.seit ? `<span class="seit">${escape(relativeZeit(o.seit).replace(/^vor /, 'seit '))}</span>` : '';
        return `<li>${url ? `<a href="${escape(url)}">${wer}</a>` : wer}${seit}</li>`;
      }).join('');
      const zusatz = art.typ === 'einladung'
        ? ` <a class="aktion" href="${escape(FST.REPO_URL)}/settings/access">einladen</a>`
        : '';
      return `<h3>${escape(art.titel)} <span class="zahl">${eintraege.length}</span>${zusatz}</h3><ul>${punkte}</ul>`;
    }).join('');
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
      html = `Die Daten sind vom ${escape(uhrzeit(daten.aktualisiert))} Uhr. Ist seitdem etwas auf GitHub passiert, läuft die automatische Aktualisierung gerade nicht.`;
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
      el.textContent = `Stand ${uhrzeit(daten.aktualisiert)} Uhr`;
      el.title = `aktualisiert ${relativeZeit(daten.aktualisiert)}, die Seite prüft alle ${INTERVALL / 1000} Sekunden`;
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
        const neueSignatur = JSON.stringify([neu.teilnehmer, neu.aktivitaet, neu.plaetze, neu.offen]);
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

  // Im Hintergrund-Tab nicht abrufen; beim Zurückkommen lädt visibilitychange sofort neu.
  function planen() {
    setTimeout(() => (document.hidden ? Promise.resolve() : aktualisieren()).then(planen), INTERVALL);
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
    if (!document.fullscreenElement && !BEAMER) vollbildSetzen(false);
  });
  // fortschritt.html?beamer startet gleich in der Beamer-Ansicht (echtes Vollbild dann mit F11).
  if (BEAMER) vollbildSetzen(true);

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
        stand.offen = stand.teilnehmer.flatMap((t) => {
          const eintrag = (typ, seit) => ({ typ, login: t.login, name: t.name, text: '', url: null, seit });
          if (t.erledigt.anmeldung && !t.erledigt.team) return [eintrag('einladung', t.erledigt.anmeldung)];
          if (t.erledigt.pr && !t.erledigt.merge) return [eintrag(t.login.length % 2 ? 'review' : 'merge', t.erledigt.pr)];
          return [];
        });
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
