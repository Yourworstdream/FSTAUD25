/* Live-Fortschritt: lädt fortschritt.json regelmäßig neu und zeigt Änderungen sofort an.
   Die Datei wird von der Action .github/workflows/fortschritt.yml nach jeder Aktivität
   im Repository neu berechnet und auf GitHub Pages veröffentlicht. */
(() => {
  'use strict';
  const { SCHRITTE, escape, relativeZeit, datumZeit, anzahlErledigt, naechsterSchritt, sichereUrl, avatarHtml } = FST;

  const params = new URLSearchParams(location.search);
  const DEMO = params.has('demo');
  const ICH = (params.get('ich') || '').toLowerCase();
  const INTERVALL = DEMO ? 4000 : 20000;
  const VERALTET_NACH = 45 * 60 * 1000;
  const ICONS = { anmeldung: '📝', team: '🤝', pr: '🌿', merge: '✅', review: '👀', kommentar: '💬', issue: '🧩', projekt: '🚀' };

  const $ = (id) => document.getElementById(id);

  let daten = null;              // zuletzt empfangene Daten
  let status = 'laden';          // laden | ok | leer | fehler
  let signatur = '';             // erkennt, ob sich etwas geändert hat
  let bekannt = null;            // login -> Set erledigter Schritte, für „neu geschafft“
  let bekannteAktivitaet = new Set();
  let hervorheben = new Set();
  let erstesRendern = true;
  let letzterAbruf = 0;
  const alteBreiten = new Map();

  const sortierung = $('sortierung');
  sortierung.value = FST.lesen('sortierung') || 'fortschritt';
  sortierung.addEventListener('change', () => {
    FST.schreiben('sortierung', sortierung.value);
    render();
  });

  // ---------- Hilfen ----------

  const vergleich = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  const key = (t) => String(t.login).toLowerCase();

  function teilnehmerListe() {
    return (daten.teilnehmer || []).filter((t) => t && t.login).map((t) => ({ ...t, name: t.name || t.login, erledigt: t.erledigt || {} }));
  }

  function letzterSchrittZeit(t) {
    return Object.values(t.erledigt).filter((z) => typeof z === 'string').sort().pop() || '';
  }

  function sortieren(liste) {
    const nachName = (a, b) => a.name.localeCompare(b.name, 'de');
    const kopie = [...liste];
    if (sortierung.value === 'name') return kopie.sort(nachName);
    if (sortierung.value === 'aktiv') {
      return kopie.sort((a, b) => vergleich(b.letzteAktivitaet || '', a.letzteAktivitaet || '') || nachName(a, b));
    }
    // Mehr Schritte zuerst; bei Gleichstand, wer den Stand zuerst erreicht hat
    return kopie.sort((a, b) => anzahlErledigt(b) - anzahlErledigt(a)
      || vergleich(letzterSchrittZeit(a), letzterSchrittZeit(b)) || nachName(a, b));
  }

  // Balken starten bei der alten Breite und wachsen dann auf die neue (CSS-Transition).
  function breite(schluessel, prozent, extraStil = '') {
    return `data-key="${escape(schluessel)}" data-breite="${prozent}" style="width:${alteBreiten.get(schluessel) ?? 0}%;${extraStil}"`;
  }
  function alteBreitenMerken() {
    document.querySelectorAll('[data-key][data-breite]').forEach((el) => alteBreiten.set(el.dataset.key, el.dataset.breite));
  }
  function breitenAnimieren() {
    requestAnimationFrame(() => requestAnimationFrame(() => {
      document.querySelectorAll('[data-breite]').forEach((el) => { el.style.width = `${el.dataset.breite}%`; });
    }));
  }
  // Der Farbverlauf soll über die volle Breite laufen, egal wie lang der Balken ist.
  const verlaufGroesse = (prozent) => (prozent > 0 ? `background-size:${(100 / prozent) * 100}% 100%;` : '');

  // ---------- Anzeige ----------

  function karteHtml(t) {
    const n = anzahlErledigt(t);
    const prozent = Math.round((n / SCHRITTE.length) * 100);
    const weiter = naechsterSchritt(t);
    const fertig = n === SCHRITTE.length;
    const k = key(t);
    const chips = SCHRITTE.map((s) => {
      const wann = t.erledigt[s.id];
      const klasse = wann ? 'ok' : (weiter && weiter.id === s.id ? 'dran' : '');
      const titel = wann
        ? `${s.nr} · ${s.titel} – geschafft${typeof wann === 'string' ? ` am ${datumZeit(wann)}` : ''}`
        : `${s.nr} · ${s.titel} – noch offen`;
      return `<li class="chip ${klasse}" style="--farbe:${s.farbe}" title="${escape(titel)}"><span aria-hidden="true">${s.icon}</span><span class="visuell-versteckt">${escape(titel)}</span></li>`;
    }).join('');
    const z = t.zahlen || {};
    const klassen = ['karte', fertig && 'fertig', k === ICH && 'ich', hervorheben.has(k) && 'neu'].filter(Boolean).join(' ');
    return `
      <article class="${klassen}" data-login="${escape(k)}">
        ${fertig ? '<span class="pokal" title="Alle Schritte geschafft">🏆</span>' : ''}
        <div class="karte-kopf">
          ${avatarHtml(t)}
          <div class="karte-name">
            <strong title="${escape(t.name)}">${escape(t.name)}${t.emoji ? ` <span aria-hidden="true">${escape(t.emoji)}</span>` : ''}</strong>
            <a href="https://github.com/${encodeURIComponent(t.login)}" target="_blank" rel="noopener">@${escape(t.login)}</a>
          </div>
          <div class="karte-zahl">${n}<small>/${SCHRITTE.length}</small></div>
        </div>
        <div class="balken" role="progressbar" aria-label="Fortschritt von ${escape(t.name)}" aria-valuemin="0" aria-valuemax="${SCHRITTE.length}" aria-valuenow="${n}">
          <span ${breite(`karte-${k}`, prozent, verlaufGroesse(prozent))}></span>
        </div>
        <ol class="chips" aria-label="Schritte">${chips}</ol>
        <p class="naechster">${weiter
          ? `Als Nächstes: <a href="./#schritt-${weiter.nr}">${weiter.icon} ${escape(weiter.titel)}</a>`
          : '🏆 Alle Schritte geschafft!'}</p>
        <div class="karte-fuss">
          <span title="Pull Requests">🌿 ${Number(z.prs) || 0} ${Number(z.prs) === 1 ? 'PR' : 'PRs'}</span>
          <span title="Geprüfte Pull Requests">👀 ${Number(z.reviews) || 0}</span>
          <span title="Kommentare">💬 ${Number(z.kommentare) || 0}</span>
          ${t.letzteAktivitaet ? `<span class="zeit" title="Zuletzt aktiv" data-zeit="${escape(t.letzteAktivitaet)}">${escape(relativeZeit(t.letzteAktivitaet))}</span>` : ''}
        </div>
      </article>`;
  }

  const freiHtml = (nr) => `
      <div class="karte frei">
        <span class="avatar" aria-hidden="true">${nr}</span>
        <b>Freier Platz</b>
        <a href="./#anmeldung">Jetzt anmelden →</a>
      </div>`;

  function renderKennzahlen(liste, plaetze) {
    const summe = (feld) => liste.reduce((s, t) => s + (Number(t.zahlen && t.zahlen[feld]) || 0), 0);
    const schritte = liste.reduce((s, t) => s + anzahlErledigt(t), 0);
    const prozent = Math.round((schritte / (plaetze * SCHRITTE.length)) * 100);
    const fertig = liste.filter((t) => anzahlErledigt(t) === SCHRITTE.length).length;
    const frei = plaetze - liste.length;

    $('k-angemeldet').innerHTML = `${liste.length}<small> / ${plaetze}</small>`;
    $('k-angemeldet-zusatz').textContent = frei > 0 ? `${frei} ${frei === 1 ? 'Platz' : 'Plätze'} frei` : 'Alle Plätze belegt 🎉';
    $('k-fortschritt').textContent = `${prozent} %`;
    const balken = $('k-fortschritt-balken');
    balken.dataset.breite = prozent;
    balken.style.backgroundSize = prozent ? `${(100 / prozent) * 100}% 100%` : '';
    $('k-fortschritt-zusatz').textContent = fertig ? `🏆 ${fertig}× alle ${SCHRITTE.length} Schritte geschafft` : `${schritte} von ${plaetze * SCHRITTE.length} Schritten erledigt`;
    $('k-prs').textContent = summe('prs');
    $('k-prs-zusatz').textContent = `${summe('gemerged')} davon gemerged`;
    $('k-reviews').textContent = summe('reviews');
    $('k-reviews-zusatz').textContent = `Reviews · ${summe('kommentare')} Kommentare`;
  }

  function renderKarten(liste, plaetze) {
    const karten = sortieren(liste).map(karteHtml);
    for (let i = liste.length; i < plaetze; i++) karten.push(freiHtml(i + 1));
    $('karten').innerHTML = karten.join('');
  }

  function renderTrichter(liste, plaetze) {
    $('trichter').innerHTML = SCHRITTE.map((s) => {
      const anzahl = liste.filter((t) => t.erledigt[s.id]).length;
      const prozent = Math.min(100, Math.round((anzahl / plaetze) * 100));
      return `<li style="--farbe:${s.farbe}" title="${escape(s.text)}">
          <span aria-hidden="true">${s.icon}</span><span>${s.nr} · ${escape(s.titel)}</span><span class="anz">${anzahl}/${plaetze}</span>
          <span class="t-balken"><span ${breite(`schritt-${s.id}`, prozent)}></span></span>
        </li>`;
    }).join('');
  }

  function renderFeed(aktivitaet, namen) {
    const liste = (Array.isArray(aktivitaet) ? aktivitaet : []).slice(0, 40);
    const id = (a) => `${a.zeit}|${a.login}|${a.typ}|${a.text}`;
    if (!liste.length) {
      $('feed').innerHTML = '<li class="leer">Noch keine Aktivität – sobald jemand etwas auf GitHub macht, erscheint es hier.</li>';
    } else {
      $('feed').innerHTML = liste.map((a) => {
        const neu = !erstesRendern && !bekannteAktivitaet.has(id(a));
        const url = sichereUrl(a.url, 'https://github.com/');
        const name = namen.get(String(a.login).toLowerCase()) || a.login;
        const inhalt = `<span class="f-icon" aria-hidden="true">${ICONS[a.typ] || '•'}</span>
          <span><b>${escape(name)}</b> ${escape(a.text)}<time data-zeit="${escape(a.zeit)}" datetime="${escape(a.zeit)}">${escape(relativeZeit(a.zeit))}</time></span>`;
        const koerper = url ? `<a href="${escape(url)}" target="_blank" rel="noopener">${inhalt}</a>` : `<div class="eintrag">${inhalt}</div>`;
        return `<li${neu ? ' class="neu"' : ''}>${koerper}</li>`;
      }).join('');
    }
    bekannteAktivitaet = new Set(liste.map(id));
  }

  function banner(html, art = '') {
    const b = $('banner');
    b.className = `banner ${art}`;
    b.innerHTML = html;
    b.hidden = !html;
  }

  function bannerAktualisieren() {
    if (DEMO) {
      return banner('<p>🎭 <b>Demo-Modus:</b> Das sind Beispieldaten, die sich alle paar Sekunden ändern – so sieht es aus, wenn die Klasse loslegt.</p><a class="knopf klein-k" href="fortschritt.html">Echte Daten anzeigen</a>', 'info');
    }
    if (status === 'leer') {
      return banner('<p>⏳ <b>Noch keine Live-Daten.</b> Sobald die Action „Fortschritt &amp; Webseite“ einmal gelaufen ist, erscheinen hier alle Anmeldungen (Admin: siehe Anleitung → „Für den Admin“).</p><a class="knopf klein-k" href="fortschritt.html?demo">Demo ansehen</a>');
    }
    if (status === 'fehler' && !daten) {
      const lokal = location.protocol === 'file:';
      return banner(lokal
        ? '<p>📁 Diese Seite wurde direkt als Datei geöffnet. Live-Daten gibt es nur auf GitHub Pages.</p><a class="knopf klein-k" href="fortschritt.html?demo">Demo ansehen</a>'
        : '<p>📡 Die Live-Daten konnten nicht geladen werden. Es wird automatisch weiter versucht.</p>');
    }
    if (daten && daten.aktualisiert && Date.now() - new Date(daten.aktualisiert).getTime() > VERALTET_NACH) {
      return banner(`<p>🕓 Die Daten sind vom ${escape(datumZeit(daten.aktualisiert))}. Normalerweise aktualisieren sie sich spätestens alle 10 Minuten – läuft die Action?</p>`);
    }
    if (daten && Array.isArray(daten.hinweise) && daten.hinweise.length) {
      return banner(`<p>ℹ️ ${daten.hinweise.map(escape).join('<br>')}</p>`, 'info');
    }
    banner('');
  }

  function render() {
    if (!daten) return;
    const liste = teilnehmerListe();
    const plaetze = Math.max(Number(daten.plaetze) || 12, liste.length, 1);
    const klasse = daten.klasse || 'Klasse';
    $('titel').textContent = `Live-Fortschritt · ${klasse}`;
    document.title = `${klasse} · Live-Fortschritt`;

    alteBreitenMerken();
    renderKennzahlen(liste, plaetze);
    renderKarten(liste, plaetze);
    renderTrichter(liste, plaetze);
    renderFeed(daten.aktivitaet, new Map(liste.map((t) => [key(t), t.name])));
    breitenAnimieren();
    bannerAktualisieren();

    if (erstesRendern && ICH) {
      document.querySelector(`.karte[data-login="${CSS.escape(ICH)}"]`)?.scrollIntoView({ block: 'center' });
    }
    erstesRendern = false;
  }

  // ---------- Neuigkeiten: Toasts, Aufleuchten, Konfetti ----------

  function toast(icon, html, farbe) {
    const box = $('toasts');
    const el = document.createElement('div');
    el.className = 'toast';
    el.style.setProperty('--farbe', farbe);
    el.innerHTML = `<span class="t-icon" aria-hidden="true">${icon}</span><div>${html}</div>`;
    box.appendChild(el);
    while (box.children.length > 4) box.firstElementChild.remove();
    setTimeout(() => {
      el.classList.add('weg');
      setTimeout(() => el.remove(), 450);
    }, 6500);
  }

  function neuigkeitenErkennen(liste) {
    const jetzt = new Map(liste.map((t) => [key(t), new Set(SCHRITTE.filter((s) => t.erledigt[s.id]).map((s) => s.id))]));
    const neu = new Set();
    if (bekannt) {
      for (const t of liste) {
        const vorher = bekannt.get(key(t));
        const nachher = jetzt.get(key(t));
        if (!vorher) {
          neu.add(key(t));
          toast('👋', `<b>${escape(t.name)}</b> ist jetzt dabei!`, '#6366f1');
          continue;
        }
        const dazu = SCHRITTE.filter((s) => nachher.has(s.id) && !vorher.has(s.id));
        if (!dazu.length) continue;
        neu.add(key(t));
        const s = dazu[dazu.length - 1];
        toast(s.icon, `<b>${escape(t.name)}</b> hat Schritt ${s.nr} „${escape(s.titel)}“ geschafft!`, s.farbe);
        if (nachher.size === SCHRITTE.length) {
          toast('🏆', `<b>${escape(t.name)}</b> hat alle ${SCHRITTE.length} Schritte geschafft!`, '#f59e0b');
          konfetti();
        }
      }
    }
    bekannt = jetzt;
    return neu;
  }

  function konfetti() {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const canvas = $('konfetti');
    const ctx = canvas.getContext('2d');
    const w = innerWidth;
    const h = innerHeight;
    canvas.hidden = false;
    canvas.width = w * devicePixelRatio;
    canvas.height = h * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    const farben = SCHRITTE.map((s) => s.farbe);
    const teile = Array.from({ length: 170 }, () => ({
      x: w / 2, y: h / 3,
      vx: (Math.random() - 0.5) * 18, vy: -Math.random() * 15 - 4, g: 0.3 + Math.random() * 0.2,
      b: 6 + Math.random() * 6, l: 8 + Math.random() * 8, r: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.3,
      farbe: farben[Math.floor(Math.random() * farben.length)],
    }));
    const start = performance.now();
    const bild = (zeit) => {
      ctx.clearRect(0, 0, w, h);
      for (const t of teile) {
        t.vy += t.g; t.vx *= 0.99; t.x += t.vx; t.y += t.vy; t.r += t.vr;
        ctx.save();
        ctx.translate(t.x, t.y);
        ctx.rotate(t.r);
        ctx.fillStyle = t.farbe;
        ctx.fillRect(-t.b / 2, -t.l / 2, t.b, t.l);
        ctx.restore();
      }
      if (zeit - start < 3600) requestAnimationFrame(bild);
      else canvas.hidden = true;
    };
    requestAnimationFrame(bild);
  }

  // ---------- Status-Anzeige oben ----------

  function statusZeigen() {
    const el = $('live');
    const text = $('live-text');
    el.classList.remove('ok', 'alt', 'fehler', 'demo');
    el.title = letzterAbruf
      ? `Zuletzt geprüft um ${new Date(letzterAbruf).toLocaleTimeString('de-DE')} · prüft alle ${INTERVALL / 1000} s`
      : '';
    if (DEMO) {
      el.classList.add('demo');
      text.textContent = 'Demo · simuliert';
    } else if (status === 'fehler') {
      el.classList.add('fehler');
      text.textContent = daten && daten.aktualisiert ? `offline · Stand ${relativeZeit(daten.aktualisiert)}` : 'keine Verbindung';
    } else if (status === 'leer') {
      el.classList.add('alt');
      text.textContent = 'noch keine Daten';
    } else if (daten && daten.aktualisiert) {
      const alt = Date.now() - new Date(daten.aktualisiert).getTime() > VERALTET_NACH;
      el.classList.add(alt ? 'alt' : 'ok');
      text.textContent = `Stand: ${relativeZeit(daten.aktualisiert)}`;
    } else {
      text.textContent = 'verbinde …';
    }
  }

  function zeitenAktualisieren() {
    document.querySelectorAll('[data-zeit]').forEach((el) => { el.textContent = relativeZeit(el.dataset.zeit); });
    statusZeigen();
  }

  // ---------- Daten holen ----------

  function uebernehmen(neu) {
    daten = neu;
    const neueSignatur = JSON.stringify([neu.teilnehmer, neu.aktivitaet, neu.plaetze, neu.klasse, neu.hinweise]);
    if (neueSignatur === signatur) {
      bannerAktualisieren();
      return;
    }
    signatur = neueSignatur;
    hervorheben = neuigkeitenErkennen(teilnehmerListe());
    render();
    hervorheben = new Set();
  }

  async function aktualisieren() {
    try {
      const neu = DEMO ? demo().naechster() : await FST.fortschrittLaden();
      letzterAbruf = Date.now();
      if (neu) {
        status = 'ok';
        uebernehmen(neu);
      } else {
        status = 'leer';
        daten = null;
        signatur = '';
        uebernehmenLeer();
      }
    } catch (fehler) {
      console.warn('Live-Daten nicht geladen:', fehler);
      status = 'fehler';
      if (!daten) uebernehmenLeer();
    }
    statusZeigen();
  }

  // Ohne Daten trotzdem die 12 freien Plätze zeigen.
  function uebernehmenLeer() {
    daten = { klasse: 'FST AUD 25', plaetze: 12, teilnehmer: [], aktivitaet: [] };
    render();
    daten = null;
    erstesRendern = true;
    bannerAktualisieren();
  }

  function planen() {
    setTimeout(async () => {
      await aktualisieren();
      planen();
    }, INTERVALL);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && Date.now() - letzterAbruf > 5000) aktualisieren();
  });

  // ---------- Beamer-Modus ----------

  const beamerKnopf = $('beamer');
  function beamerSetzen(an) {
    document.documentElement.classList.toggle('beamer', an);
    beamerKnopf.textContent = an ? '✕ Beamer-Modus beenden' : '⛶ Beamer-Modus';
  }
  beamerKnopf.addEventListener('click', async () => {
    const an = !document.documentElement.classList.contains('beamer');
    beamerSetzen(an);
    try {
      if (an && !document.fullscreenElement) await document.documentElement.requestFullscreen();
      if (!an && document.fullscreenElement) await document.exitFullscreen();
    } catch { /* Vollbild nicht erlaubt – der Beamer-Modus funktioniert trotzdem */ }
  });
  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement) beamerSetzen(false);
  });

  // ---------- Demo-Daten ----------

  let demoInstanz = null;
  function demo() {
    if (demoInstanz) return demoInstanz;
    const personen = [
      ['Lena K.', 'lena-k', '🤖'], ['Jonas M.', 'jonas-m', '⚡'], ['Aylin S.', 'aylin-s', '🔧'], ['Tim B.', 'tim-b', '🦾'],
      ['Mara W.', 'mara-w', '📟'], ['Niklas H.', 'niklas-h', '🛠️'], ['Sophie R.', 'sophie-r', '💡'], ['Deniz A.', 'deniz-a', '🔌'],
      ['Paul F.', 'paul-f', '⚙️'], ['Emma L.', 'emma-l', '🧠'], ['Luca T.', 'luca-t', '📡'], ['Mia G.', 'mia-g', '🧪'],
    ];
    const texte = {
      anmeldung: () => ['anmeldung', 'hat sich angemeldet'],
      team: () => ['team', 'ist jetzt Collaborator im Repository'],
      pr: (nr) => ['pr', `hat PR #${nr} geöffnet: „Steckbrief“`],
      merge: (nr) => ['merge', `PR #${nr} wurde gemerged`],
      review: (nr) => ['review', `hat PR #${nr} freigegeben ✅`],
      diskussion: (nr) => ['kommentar', `hat in #${nr} kommentiert`],
      projekt: (nr) => ['projekt', `PR #${nr} wurde gemerged: „Wiki-Seite“`],
    };
    const zustand = { klasse: 'FST AUD 25', plaetze: 12, teilnehmer: [], aktivitaet: [], aktualisiert: null };
    let nummer = 14;

    const neuePerson = ([name, login, emoji]) => ({
      login, name, emoji, avatar: null, erledigt: {}, letzteAktivitaet: null,
      zahlen: { prs: 0, gemerged: 0, reviews: 0, kommentare: 0 },
    });
    const schrittMachen = (t, s, zeit) => {
      const iso = new Date(zeit).toISOString();
      t.erledigt[s.id] = iso;
      t.letzteAktivitaet = iso;
      if (s.id === 'pr' || s.id === 'projekt') t.zahlen.prs += 1;
      if (s.id === 'merge' || s.id === 'projekt') t.zahlen.gemerged += 1;
      if (s.id === 'review') t.zahlen.reviews += 1;
      if (s.id === 'diskussion') t.zahlen.kommentare += 2;
      const [typ, text] = texte[s.id](nummer++);
      zustand.aktivitaet.unshift({ zeit: iso, login: t.login, typ, text, url: null });
      zustand.aktivitaet.length = Math.min(zustand.aktivitaet.length, 40);
    };

    // Startzustand: 11 von 12 angemeldet, unterschiedlich weit
    const start = Date.now();
    const ziele = [7, 6, 5, 5, 4, 4, 3, 3, 2, 1, 1];
    personen.slice(0, 11).forEach((p, i) => {
      const t = neuePerson(p);
      SCHRITTE.slice(0, ziele[i]).forEach((s, j) => schrittMachen(t, s, start - (95 - i * 5 - j * 6) * 60000));
      zustand.teilnehmer.push(t);
    });
    zustand.aktivitaet.sort((a, b) => vergleich(b.zeit, a.zeit));

    demoInstanz = {
      naechster() {
        const offen = zustand.teilnehmer.filter((t) => anzahlErledigt(t) < SCHRITTE.length);
        if (zustand.teilnehmer.length < personen.length && Math.random() < 0.12) {
          const t = neuePerson(personen[zustand.teilnehmer.length]);
          schrittMachen(t, SCHRITTE[0], Date.now());
          zustand.teilnehmer.push(t);
        } else if (offen.length && Math.random() < 0.65) {
          const t = offen[Math.floor(Math.random() * offen.length)];
          schrittMachen(t, naechsterSchritt(t), Date.now());
        }
        zustand.aktualisiert = new Date().toISOString();
        return JSON.parse(JSON.stringify(zustand));
      },
    };
    return demoInstanz;
  }

  // ---------- Start ----------

  setInterval(zeitenAktualisieren, 15000);
  aktualisieren().then(planen);
})();
