/* FST AUD 25 – Selbstkontrolle "Verstanden?". Nichts wird gespeichert oder gesendet. */
(() => {
  'use strict';

  // Die Texte folgen der Anleitung (index.html) und der Hilfe (hilfe.html, Begriffe).
  const FRAGEN = [
    {
      begriff: 'Repository',
      frage: 'Was ist ein Repository?',
      antworten: [
        'Der Projektordner mit allen Dateien und ihrer ganzen Geschichte.',
        'Der Vorschlag, Änderungen in den Hauptstand zu übernehmen.',
        'Eine Liste mit Aufgaben, Fragen und Ideen.',
      ],
      richtig: 0,
      erklaerung: 'Im Repository liegen alle Dateien des Projekts, dazu jeder frühere Stand.',
    },
    {
      begriff: 'Branch',
      frage: 'Warum arbeitest du nicht direkt auf main?',
      antworten: [
        'Weil Änderungen auf main nach einigen Tagen automatisch gelöscht werden.',
        'Weil auf main nur landen soll, was geprüft wurde. Dein Branch lässt main unverändert.',
        'Weil ein Branch Dateien schneller speichert als main.',
      ],
      richtig: 1,
      erklaerung: 'Auf deinem Branch kannst du in Ruhe arbeiten. Erst nach der Prüfung kommt die Änderung in main.',
    },
    {
      begriff: 'Commit',
      frage: 'Was ist ein Commit?',
      antworten: [
        'Eine Freigabe durch eine andere Person.',
        'Ein eigener Zweig, auf dem du arbeitest.',
        'Ein gespeicherter Zwischenstand mit einer kurzen Beschreibung.',
      ],
      richtig: 2,
      erklaerung: 'Mit „Commit changes“ speicherst du einen Stand und beschreibst kurz, was sich geändert hat.',
    },
    {
      begriff: 'Pull Request',
      frage: 'Was ist ein Pull Request?',
      antworten: [
        'Das Herunterladen des Repositorys auf deinen PC.',
        'Der Vorschlag, die Änderungen aus deinem Branch in main zu übernehmen.',
        'Der Eintrag in der Aufgabenliste für einen Fehler.',
      ],
      richtig: 1,
      erklaerung: 'Ein Pull Request schlägt vor, deinen Branch in main zu übernehmen. Dort wird er geprüft.',
    },
    {
      begriff: 'Review',
      frage: 'Wer gibt deinen Pull Request frei, und wann darfst du mergen?',
      antworten: [
        'Eine andere Person gibt ihn mit „Approve“ frei. Erst danach darfst du mergen.',
        'Du gibst ihn selbst frei, sobald du mit deiner Änderung zufrieden bist.',
        'Niemand. GitHub merged den Pull Request nach einer Stunde automatisch.',
      ],
      richtig: 0,
      erklaerung: 'Vier Augen sehen mehr als zwei. Deshalb prüft immer eine andere Person, bevor etwas in main kommt.',
    },
    {
      begriff: 'Issue',
      frage: 'Was ist ein Issue?',
      antworten: [
        'Eine Fehlermeldung von GitHub, wenn ein Merge nicht klappt.',
        'Eine Kopie des Repositorys im eigenen Konto.',
        'Ein Eintrag in der Aufgabenliste: Frage, Idee, Fehler oder Thema.',
      ],
      richtig: 2,
      erklaerung: 'In Issues sammeln wir Fragen, Ideen und Themen und besprechen sie in Kommentaren.',
    },
  ];

  const form = document.getElementById('quiz');
  const ergebnis = document.getElementById('ergebnis');
  const nochmal = document.getElementById('nochmal');
  if (!form || !ergebnis || !nochmal) return;

  let beantwortet = 0;
  let richtige = 0;

  function el(tag, klasse, text) {
    const e = document.createElement(tag);
    if (klasse) e.className = klasse;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function marke(knopf, text) {
    knopf.appendChild(el('span', 'marke', text));
  }

  function antworten(frage, rueckmeldung, knoepfe, gewaehlt) {
    if (frage.fertig) return;
    frage.fertig = true;
    const ok = gewaehlt === frage.richtig;
    knoepfe.forEach((k, i) => {
      k.setAttribute('aria-disabled', 'true');
      if (i === frage.richtig) {
        k.classList.add('richtig');
        marke(k, ok ? 'Richtig, deine Antwort' : 'Richtig');
      } else if (i === gewaehlt) {
        k.classList.add('falsch');
        marke(k, 'Falsch, deine Antwort');
      }
    });
    rueckmeldung.textContent = '';
    rueckmeldung.appendChild(el('b', ok ? 'ok' : 'fehler', ok ? 'Richtig. ' : 'Nicht ganz. '));
    rueckmeldung.appendChild(document.createTextNode(frage.erklaerung));
    beantwortet += 1;
    if (ok) richtige += 1;
    if (beantwortet === FRAGEN.length) zeigeErgebnis();
  }

  function zeigeErgebnis() {
    const fehler = FRAGEN.length - richtige;
    let satz;
    if (fehler === 0) satz = 'Alles richtig. Du weißt jetzt, wie die Arbeit mit GitHub abläuft.';
    else if (richtige >= 4) satz = 'Das meiste sitzt. Lies die Begriffe, die nicht gestimmt haben, noch einmal nach.';
    else satz = 'Einiges ist noch unklar. Das ist am Anfang normal. Lies die Begriffe in Ruhe nach und versuch es noch einmal.';
    ergebnis.textContent = '';
    ergebnis.appendChild(el('p', 'summe', `${richtige} von ${FRAGEN.length} richtig`));
    ergebnis.appendChild(el('p', '', satz));
    if (fehler > 0) {
      const p = el('p', 'leise');
      p.appendChild(document.createTextNode('Nachlesen: '));
      const a = el('a', '', 'Hilfe, Abschnitt Begriffe');
      a.href = 'hilfe.html#begriffe';
      p.appendChild(a);
      p.appendChild(document.createTextNode('.'));
      ergebnis.appendChild(p);
    }
    nochmal.hidden = false;
  }

  function aufbauen() {
    beantwortet = 0;
    richtige = 0;
    form.textContent = '';
    ergebnis.textContent = '';
    nochmal.hidden = true;
    FRAGEN.forEach((f, nr) => {
      const frage = { ...f, fertig: false };
      const set = el('fieldset', 'frage');
      set.tabIndex = -1;
      const legende = el('legend');
      legende.appendChild(el('span', 'leise', `Frage ${nr + 1} von ${FRAGEN.length}`));
      legende.appendChild(document.createTextNode(f.frage));
      set.appendChild(legende);
      const rueckmeldung = el('p', 'rueckmeldung');
      rueckmeldung.setAttribute('aria-live', 'polite');
      const knoepfe = f.antworten.map((text, i) => {
        const k = el('button', 'antwort', text);
        k.type = 'button';
        k.addEventListener('click', () => antworten(frage, rueckmeldung, knoepfe, i));
        set.appendChild(k);
        return k;
      });
      set.appendChild(rueckmeldung);
      form.appendChild(set);
    });
  }

  nochmal.addEventListener('click', () => {
    aufbauen();
    const erste = form.querySelector('fieldset');
    erste.scrollIntoView();
    erste.focus({ preventScroll: true });
  });

  aufbauen();
})();
