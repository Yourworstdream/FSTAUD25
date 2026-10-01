/* Ganz einfach erklärt: Schritte abhaken und Link zum eigenen Steckbrief. */
(() => {
  'use strict';
  const { REPO_URL, lesen, schreiben } = FST;
  const LOGIN_MUSTER = /^[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38}$/i;
  const $ = (id) => document.getElementById(id);

  // ---------- Abhaken ----------

  const schritte = Array.from(document.querySelectorAll('.schritt'));
  let erledigt;
  try { erledigt = new Set(JSON.parse(lesen('einfach') || '[]')); } catch { erledigt = new Set(); }

  function anzeigen() {
    schritte.forEach((s) => {
      const fertig = erledigt.has(s.dataset.schritt);
      s.classList.toggle('erledigt', fertig);
      s.querySelector('.geschafft').setAttribute('aria-pressed', String(fertig));
    });
    $('anzahl-geschafft').textContent = erledigt.size;
    $('balken-geschafft').style.width = `${(erledigt.size / schritte.length) * 100}%`;
  }

  schritte.forEach((s) => {
    s.querySelector('.geschafft').addEventListener('click', () => {
      const nr = s.dataset.schritt;
      if (erledigt.has(nr)) erledigt.delete(nr);
      else erledigt.add(nr);
      schreiben('einfach', JSON.stringify([...erledigt]));
      anzeigen();
    });
  });
  anzeigen();

  // ---------- Steckbrief-Link (Schritt 3) ----------

  const feldLogin = $('sb-login');
  const feldName = $('sb-name');
  const link = $('sb-link');
  const hinweis = $('sb-hinweis');
  feldLogin.value = lesen('login') || '';
  feldName.value = lesen('name') || '';

  const steckbrief = (name) => `# ${name || 'Dein Name'}

- **Emoji:** 🤖
- **Das will ich lernen:** Mit Git und GitHub im Team arbeiten
- **Lieblingsthema in der Automatisierung:** SPS-Programmierung
`;

  function linkSetzen() {
    const login = feldLogin.value.trim().replace(/^@/, '');
    const name = feldName.value.trim();
    const ok = LOGIN_MUSTER.test(login);
    link.classList.toggle('gesperrt', !ok);
    link.href = ok
      ? `${REPO_URL}/new/main/teilnehmer?filename=${encodeURIComponent(`${login}.md`)}&value=${encodeURIComponent(steckbrief(name))}`
      : `${REPO_URL}/new/main/teilnehmer`;
    hinweis.textContent = ok
      ? `GitHub macht die Datei ${login}.md auf. Name und Text sind schon drin.`
      : 'Erst oben deinen Benutzernamen eintragen. Sonst musst du den Dateinamen selbst schreiben.';
    if (ok) schreiben('login', login);
    if (name) schreiben('name', name);
  }

  feldLogin.addEventListener('input', linkSetzen);
  feldName.addEventListener('input', linkSetzen);
  $('steckbrief-form').addEventListener('submit', (e) => e.preventDefault());
  linkSetzen();
})();
