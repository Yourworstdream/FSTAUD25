/* Anleitung: Anmeldeformular, persönliche Links und der eigene Fortschritt. */
(() => {
  'use strict';
  const { REPO_URL, SCHRITTE, lesen, schreiben } = FST;
  const LOGIN_MUSTER = /^[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38}$/i;

  const $ = (id) => document.getElementById(id);
  const form = $('anmelde-form');
  const feldName = $('f-name');
  const feldLogin = $('f-login');
  const fehler = $('f-fehler');
  const vorschau = $('login-vorschau');

  let ich = { login: lesen('login') || '', name: lesen('name') || '' };
  feldName.value = ich.name;
  feldLogin.value = ich.login;

  const steckbrief = (name) => `# ${name || 'Dein Name'}

- **Emoji:** 🤖
- **Das will ich lernen:** Mit Git und GitHub im Team arbeiten
- **Lieblingsthema in der Automatisierung:** SPS-Programmierung
`;

  const THEMA_VORLAGE = (name) => `# Thema: Titel deines Themas

> Autor:in: ${name || 'Dein Name'} · Review: Name der prüfenden Person

## Worum geht es?

Erkläre das Thema in 2–3 Sätzen so, dass es jemand aus der Klasse versteht.

## Wie funktioniert es?

Die wichtigsten Grundlagen, gern mit Aufzählungen.

## Beispiel aus der Praxis

Wo begegnet uns das in einer Anlage oder im Betrieb?

## Wichtige Begriffe

| Begriff | Erklärung |
|---------|-----------|
|         |           |

## Quellen

-
`;

  const neueDateiUrl = (ordner, dateiname, inhalt) =>
    `${REPO_URL}/new/main/${ordner}?filename=${encodeURIComponent(dateiname)}&value=${encodeURIComponent(inhalt)}`;

  const anmeldeUrl = (name) =>
    `${REPO_URL}/issues/new?template=anmeldung.yml&title=${encodeURIComponent(`Anmeldung: ${name}`)}&name=${encodeURIComponent(name)}`;

  const loginAusFeld = () => feldLogin.value.trim().replace(/^@/, '');

  // ---------- Personalisierung ----------

  function personalisieren() {
    const hatLogin = LOGIN_MUSTER.test(ich.login);
    const login = hatLogin ? ich.login : 'dein-benutzername';
    document.querySelectorAll('[data-ich-login]').forEach((el) => { el.textContent = login; });
    document.querySelectorAll('[data-ich-name]').forEach((el) => { el.textContent = ich.name || 'Dein Name'; });

    $('steckbrief-link').href = neueDateiUrl('teilnehmer', `${login}.md`, steckbrief(ich.name));
    $('steckbrief-code').textContent = steckbrief(ich.name);
    $('steckbrief-ohne-login').hidden = hatLogin;
    $('thema-link').href = neueDateiUrl('projekt/themen', 'NN-thema.md', THEMA_VORLAGE(ich.name));

    $('ich-leiste').hidden = !hatLogin;
    if (hatLogin) {
      $('ich-avatar').src = `https://github.com/${encodeURIComponent(login)}.png?size=72`;
      $('ich-fortschritt-link').href = `fortschritt.html?ich=${encodeURIComponent(login)}`;
    }
  }

  async function eigenenStandZeigen() {
    if (!LOGIN_MUSTER.test(ich.login)) return;
    const standEl = $('ich-stand');
    let daten;
    try {
      daten = await FST.fortschrittLaden();
    } catch {
      daten = null;
    }
    if (!daten) {
      standEl.textContent = 'Live-Daten sind gerade nicht verfügbar.';
      return;
    }
    const t = (daten.teilnehmer || []).find((x) => x.login.toLowerCase() === ich.login.toLowerCase());
    SCHRITTE.forEach((s) => {
      const erledigt = Boolean(t && t.erledigt && t.erledigt[s.id]);
      document.querySelector(`.weg[data-schritt="${s.id}"]`)?.classList.toggle('erledigt', erledigt);
      const chip = document.querySelector(`[data-meilenstein="${s.id}"]`);
      if (chip) {
        chip.classList.toggle('erledigt', erledigt);
        chip.textContent = `${s.icon} Meilenstein „${s.titel}“${erledigt ? ' – geschafft ✓' : ''}`;
      }
    });
    if (!t) {
      standEl.textContent = 'Noch nicht in der Klassenliste – hast du die Anmeldung auf GitHub abgeschickt?';
      return;
    }
    const n = FST.anzahlErledigt(t);
    const weiter = FST.naechsterSchritt(t);
    standEl.textContent = weiter
      ? `${n} von ${SCHRITTE.length} Schritten geschafft · als Nächstes: Schritt ${weiter.nr} (${weiter.titel})`
      : `Alle ${SCHRITTE.length} Schritte geschafft 🏆`;
  }

  // ---------- Formular ----------

  function zeigeFehler(text) {
    fehler.textContent = text;
    fehler.hidden = false;
  }

  // Prüft ohne API-Limit, ob es das Konto gibt: Das Profilbild existiert nur für echte Konten.
  let pruefTimer;
  function kontoPruefen(login) {
    const bild = vorschau.querySelector('img');
    const text = vorschau.querySelector('span');
    bild.onload = () => {
      if (loginAusFeld() !== login) return;
      vorschau.className = 'login-vorschau ok';
      bild.hidden = false;
      text.textContent = `Konto @${login} gefunden ✓`;
      vorschau.hidden = false;
    };
    bild.onerror = () => {
      if (loginAusFeld() !== login) return;
      vorschau.className = 'login-vorschau fehlt';
      bild.hidden = true;
      text.textContent = `Kein GitHub-Konto „${login}“ gefunden – Tippfehler?`;
      vorschau.hidden = false;
    };
    bild.src = `https://github.com/${encodeURIComponent(login)}.png?size=64`;
  }

  feldLogin.addEventListener('input', () => {
    clearTimeout(pruefTimer);
    vorschau.hidden = true;
    const login = loginAusFeld();
    if (LOGIN_MUSTER.test(login)) pruefTimer = setTimeout(() => kontoPruefen(login), 600);
  });

  feldName.addEventListener('input', () => {
    const woerter = feldName.value.trim().split(/\s+/);
    const letztes = woerter[woerter.length - 1] || '';
    $('name-tipp').hidden = !(woerter.length > 1 && letztes.length > 2 && !letztes.endsWith('.'));
  });

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const name = feldName.value.trim().replace(/\s+/g, ' ');
    const login = loginAusFeld();
    if (!name) return zeigeFehler('Bitte gib deinen Namen ein (Vorname + Anfangsbuchstabe).');
    if (!LOGIN_MUSTER.test(login)) {
      return zeigeFehler('Das sieht nicht wie ein GitHub-Benutzername aus. Erlaubt sind Buchstaben, Zahlen und einzelne Bindestriche.');
    }
    fehler.hidden = true;
    ich = { name, login };
    schreiben('name', name);
    schreiben('login', login);
    personalisieren();

    const url = anmeldeUrl(name);
    $('anmelde-link').href = url;
    $('anmelde-erfolg').hidden = false;
    window.open(url, '_blank', 'noopener');
    eigenenStandZeigen();
  });

  $('ich-aendern').addEventListener('click', () => {
    $('anmeldung').scrollIntoView();
    feldLogin.focus();
  });

  if (ich.login) kontoPruefen(ich.login);

  // ---------- Kopieren-Knöpfe für Codeblöcke ----------

  document.querySelectorAll('pre').forEach((pre) => {
    if (!navigator.clipboard) return;
    const knopf = document.createElement('button');
    knopf.type = 'button';
    knopf.className = 'kopieren';
    knopf.textContent = 'Kopieren';
    knopf.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(pre.querySelector('code').textContent);
        knopf.textContent = 'Kopiert ✓';
      } catch {
        knopf.textContent = 'Nicht möglich';
      }
      setTimeout(() => { knopf.textContent = 'Kopieren'; }, 1800);
    });
    pre.appendChild(knopf);
  });

  // ---------- Inhaltsverzeichnis: aktuellen Abschnitt markieren ----------

  const tocLinks = new Map([...document.querySelectorAll('.toc a')].map((a) => [a.getAttribute('href').slice(1), a]));
  if ('IntersectionObserver' in window) {
    const beobachter = new IntersectionObserver((eintraege) => {
      eintraege.forEach((e) => {
        if (!e.isIntersecting) return;
        tocLinks.forEach((a) => a.classList.remove('aktiv'));
        tocLinks.get(e.target.id)?.classList.add('aktiv');
      });
    }, { rootMargin: '-20% 0px -70% 0px' });
    tocLinks.forEach((_, id) => { const el = $(id); if (el) beobachter.observe(el); });
  }

  personalisieren();
  eigenenStandZeigen();
})();
