/* Anleitung: Anmeldeformular, passende Links für dich und dein eigener Stand. */
(() => {
  'use strict';
  const { REPO_URL, SCHRITTE } = FST;
  const LOGIN_MUSTER = /^[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38}$/i;

  const $ = (id) => document.getElementById(id);
  const feldName = $('f-name');
  const feldLogin = $('f-login');
  const meldung = $('f-meldung');

  let ich = { login: FST.lesen('login') || '', name: FST.lesen('name') || '' };
  feldName.value = ich.name;
  feldLogin.value = ich.login;

  const steckbrief = (name) => `# ${name || 'Dein Name'}

- Das will ich lernen: Mit Git und GitHub im Team arbeiten
- Lieblingsthema in der Automatisierung:
`;

  const themaVorlage = (name) => `# Titel deines Themas

Geschrieben von ${name || 'deinem Namen'}

## Worum geht es?

Erkläre das Thema in zwei, drei Sätzen.

## Wie funktioniert es?

## Beispiel aus der Praxis

## Quellen

-
`;

  const neueDatei = (ordner, datei, inhalt) =>
    `${REPO_URL}/new/main/${ordner}?filename=${encodeURIComponent(datei)}&value=${encodeURIComponent(inhalt)}`;

  const anmeldeUrl = (name) =>
    `${REPO_URL}/issues/new?template=anmeldung.yml&title=${encodeURIComponent(`Anmeldung: ${name}`)}&name=${encodeURIComponent(name)}`;

  function zeigeMeldung(text, art) {
    meldung.textContent = text;
    meldung.className = `meldung ${art}`;
    meldung.hidden = !text;
  }

  function personalisieren() {
    const hatLogin = LOGIN_MUSTER.test(ich.login);
    document.querySelectorAll('[data-ich-login]').forEach((el) => { el.textContent = hatLogin ? ich.login : 'benutzername'; });
    $('steckbrief-link').href = neueDatei('teilnehmer', `${hatLogin ? ich.login : 'benutzername'}.md`, steckbrief(ich.name));
    $('thema-link').href = neueDatei('projekt/themen', 'nr-thema.md', themaVorlage(ich.name));
    $('ich').hidden = !hatLogin;
    if (hatLogin) $('ich-link').href = `fortschritt.html?ich=${encodeURIComponent(ich.login)}`;
  }

  async function standZeigen() {
    if (!LOGIN_MUSTER.test(ich.login)) return;
    let daten = null;
    try { daten = await FST.fortschrittLaden(); } catch { /* dann ohne Stand */ }
    const t = daten && (daten.teilnehmer || []).find((x) => x.login.toLowerCase() === ich.login.toLowerCase());
    SCHRITTE.forEach((s) => {
      const erledigt = Boolean(t && t.erledigt && t.erledigt[s.id]);
      document.querySelector(`#uebersicht [data-schritt="${s.id}"]`)?.classList.toggle('erledigt', erledigt);
      const nr = document.querySelector(`#schritt-${s.nr} .schritt-nr`);
      if (nr) nr.innerHTML = `Schritt ${s.nr} von 7${erledigt ? ' · <span class="ok">erledigt</span>' : ''}`;
    });
    if (!daten) return;
    $('ich-stand').textContent = t
      ? `${FST.anzahlErledigt(t)} von 7 Schritten sind erledigt.`
      : 'In der Klassenliste tauchst du auf, sobald deine Anmeldung auf GitHub abgeschickt ist.';
  }

  // Ob es das Konto gibt, verrät das Profilbild: Es existiert nur für echte Konten.
  let pruefTimer;
  feldLogin.addEventListener('input', () => {
    clearTimeout(pruefTimer);
    zeigeMeldung('');
    const login = feldLogin.value.trim().replace(/^@/, '');
    if (!LOGIN_MUSTER.test(login)) return;
    pruefTimer = setTimeout(() => {
      const bild = new Image();
      bild.onload = () => { if (feldLogin.value.trim().replace(/^@/, '') === login) zeigeMeldung(`Konto @${login} gefunden.`, 'ok'); };
      bild.onerror = () => { if (feldLogin.value.trim().replace(/^@/, '') === login) zeigeMeldung(`Ein Konto „${login}“ gibt es nicht. Tippfehler?`, 'fehler'); };
      bild.src = `https://github.com/${encodeURIComponent(login)}.png?size=40`;
    }, 700);
  });

  $('anmelde-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const name = feldName.value.trim().replace(/\s+/g, ' ');
    const login = feldLogin.value.trim().replace(/^@/, '');
    if (!name) return zeigeMeldung('Bitte trag deinen Namen ein.', 'fehler');
    if (!LOGIN_MUSTER.test(login)) return zeigeMeldung('Der Benutzername darf nur Buchstaben, Zahlen und einzelne Bindestriche enthalten.', 'fehler');

    ich = { name, login };
    FST.schreiben('name', name);
    FST.schreiben('login', login);
    personalisieren();

    const url = anmeldeUrl(name);
    $('anmelde-link').href = url;
    $('anmelde-erfolg').hidden = false;
    window.open(url, '_blank', 'noopener');
    standZeigen();
  });

  $('ich-aendern').addEventListener('click', () => setTimeout(() => feldName.focus(), 300));

  personalisieren();
  standZeigen();
})();
