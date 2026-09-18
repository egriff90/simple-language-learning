/* Sentences: cloze flashcards from classic literature, with simple spaced repetition.
   All progress lives in localStorage, keyed per language. No build step, no server logic. */
(() => {
  const MIN = 60 * 1000;
  const DAY = 24 * 60 * MIN;
  const RELEARN_DELAY = 5 * MIN;
  const RECENT_WINDOW = 3;
  const DEFAULT_SETTINGS = { newPerDay: 10, autoAudio: true, showFirst: false };

  const $ = (id) => document.getElementById(id);
  const el = {
    lang: $("lang"), stats: $("stats"), card: $("card"), source: $("source"),
    preTranslation: $("pre-translation"), form: $("answer-form"), sentence: $("sentence"),
    feedback: $("feedback"), verdict: $("verdict"), translation: $("translation"),
    speakBtn: $("speak-btn"), nextBtn: $("next-btn"), hint: $("hint"),
    done: $("done"), doneSummary: $("done-summary"), moreBtn: $("more-btn"),
    settings: $("settings"), settingsBtn: $("settings-btn"), closeSettings: $("close-settings"),
    newPerDay: $("new-per-day"), autoAudio: $("auto-audio"), showFirst: $("show-first"),
    exportBtn: $("export-btn"), importFile: $("import-file"), resetBtn: $("reset-btn"),
  };

  const state = {
    languages: [], lang: null, cards: [], progress: null, settings: null,
    current: null, phase: "answer", recent: [], session: { reviews: 0, new: 0, right: 0 },
  };

  // ---------- storage ----------
  const key = (name) => `sll:${name}:${state.lang.code}`;
  const load = (k, fallback) => {
    try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
  };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} };
  const saveProgress = () => save(key("progress"), state.progress);
  const saveSettings = () => save(key("settings"), state.settings);
  const today = () => new Date().toISOString().slice(0, 10);

  // ---------- scheduling (simplified SM-2 with a binary grade) ----------
  function newRecord() {
    return { iv: 0, ease: 2.5, due: 0, reps: 0, lapses: 0, history: [] };
  }
  function grade(rec, ok, now) {
    rec.reps += 1;
    rec.history.push([now, ok ? 1 : 0]);
    if (rec.history.length > 50) rec.history.shift();
    if (ok) {
      rec.iv = rec.iv === 0 ? 1 : rec.iv === 1 ? 3 : Math.round(rec.iv * rec.ease);
      rec.ease = Math.min(3, rec.ease + 0.05);
      rec.due = now + rec.iv * DAY;
    } else {
      rec.lapses += 1;
      rec.iv = 0;
      rec.ease = Math.max(1.3, rec.ease - 0.2);
      rec.due = now + RELEARN_DELAY;
    }
  }

  function newAllowance() {
    const p = state.progress;
    return state.settings.newPerDay + (p.extra[today()] || 0);
  }
  function newShownToday() {
    return state.progress.introduced[today()] || 0;
  }

  function pickNext() {
    const now = Date.now();
    const recs = state.progress.cards;
    const notRecent = (c) => !state.recent.includes(c.id);
    const byDue = (a, b) => recs[a.id].due - recs[b.id].due;

    const due = state.cards.filter((c) => recs[c.id] && recs[c.id].due <= now).sort(byDue);
    const fresh = due.filter(notRecent);
    if (fresh.length) return fresh[0];

    if (newShownToday() < newAllowance()) {
      const c = state.cards.find((c) => !recs[c.id]);
      if (c) return c;
    }
    // Cards answered wrong earlier this session, not yet "due" again: show them rather than stop.
    const relearn = state.cards.filter((c) => recs[c.id] && recs[c.id].iv === 0 && recs[c.id].due > now).sort(byDue);
    const relearnFresh = relearn.filter(notRecent);
    if (relearnFresh.length) return relearnFresh[0];
    if (due.length) return due[0];
    if (relearn.length) return relearn[0];
    return null;
  }

  // ---------- answer checking ----------
  const normalise = (s) => s.trim().toLowerCase().replace(/ß/g, "ss").replace(/[.,!?;:"]+$/g, "");
  const isCorrect = (typed, answer) => normalise(typed) === normalise(answer);

  // ---------- speech ----------
  let voices = [];
  function loadVoices() { voices = window.speechSynthesis ? speechSynthesis.getVoices() : []; }
  function pickVoice() {
    const want = state.lang.tts.toLowerCase();
    return voices.find((v) => v.lang.toLowerCase() === want)
      || voices.find((v) => v.lang.toLowerCase().startsWith(want.slice(0, 2)))
      || null;
  }
  function speak(text) {
    if (!window.speechSynthesis) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const v = pickVoice();
    if (v) u.voice = v;
    u.lang = state.lang.tts;
    u.rate = 0.9;
    speechSynthesis.speak(u);
  }
  function canSpeak() { return !!window.speechSynthesis && !!pickVoice(); }

  // ---------- rendering ----------
  function renderStats() {
    const now = Date.now();
    const recs = state.progress.cards;
    const dueCount = state.cards.filter((c) => recs[c.id] && recs[c.id].due <= now).length;
    const seen = Object.keys(recs).length;
    el.stats.textContent = `Due ${dueCount} · New today ${newShownToday()}/${newAllowance()} · Seen ${seen} of ${state.cards.length}`;
  }

  function renderCard(card) {
    state.current = card;
    state.phase = "answer";
    el.card.hidden = false;
    el.done.hidden = true;
    el.feedback.hidden = true;
    el.hint.hidden = false;
    el.source.textContent = `${card.source.author}, ${card.source.title} (${card.source.year})`;
    el.preTranslation.hidden = !state.settings.showFirst;
    el.preTranslation.textContent = card.translation;

    el.sentence.textContent = "";
    const [before, after] = card.cloze.split("___");
    const input = document.createElement("input");
    input.type = "text";
    input.id = "answer";
    input.autocapitalize = "off";
    input.spellcheck = false;
    input.style.width = `${Math.max(3, card.answer.length + 1)}ch`;
    el.sentence.append(before, input, after);
    input.focus();
  }

  function renderFeedback(typed, ok) {
    const card = state.current;
    state.phase = "feedback";
    el.sentence.textContent = "";
    const [before, after] = card.cloze.split("___");
    const okSpan = document.createElement("span");
    okSpan.className = "ok";
    okSpan.textContent = card.answer;
    el.sentence.append(before);
    if (!ok && typed.trim()) {
      const badSpan = document.createElement("span");
      badSpan.className = "bad";
      badSpan.textContent = typed.trim();
      el.sentence.append(badSpan);
    }
    el.sentence.append(okSpan, after);

    el.verdict.textContent = ok ? "Correct" : typed.trim() ? "Not quite" : "Revealed";
    el.verdict.className = `verdict ${ok ? "ok" : "bad"}`;
    el.translation.textContent = card.translation;
    el.preTranslation.hidden = true;
    el.feedback.hidden = false;
    el.hint.hidden = true;
    el.speakBtn.hidden = !canSpeak();
    el.nextBtn.focus();
    if (state.settings.autoAudio && canSpeak()) speak(card.text);
  }

  function renderDone() {
    state.current = null;
    el.card.hidden = true;
    el.done.hidden = false;
    const s = state.session;
    const total = s.reviews + s.new;
    el.doneSummary.textContent = total
      ? `This session: ${total} sentences, ${s.right} right first time (${s.new} new).`
      : "Nothing is due right now. Come back tomorrow, or learn a few more now.";
  }

  function next() {
    renderStats();
    const card = pickNext();
    if (card) renderCard(card); else renderDone();
  }

  // ---------- answering ----------
  function submit() {
    if (state.phase !== "answer" || !state.current) return;
    const card = state.current;
    const input = $("answer");
    const typed = input ? input.value : "";
    const ok = isCorrect(typed, card.answer);
    const now = Date.now();
    const recs = state.progress.cards;
    const isNew = !recs[card.id];
    if (isNew) {
      recs[card.id] = newRecord();
      state.progress.introduced[today()] = newShownToday() + 1;
      state.session.new += 1;
    } else if (recs[card.id].iv > 0) {
      state.session.reviews += 1;
    }
    if (ok && (isNew || recs[card.id].iv > 0)) state.session.right += 1;
    grade(recs[card.id], ok, now);
    state.recent.push(card.id);
    if (state.recent.length > RECENT_WINDOW) state.recent.shift();
    saveProgress();
    renderFeedback(typed, ok);
  }

  el.form.addEventListener("submit", (e) => { e.preventDefault(); submit(); });
  el.nextBtn.addEventListener("click", next);
  el.speakBtn.addEventListener("click", () => state.current && speak(state.current.text));
  el.moreBtn.addEventListener("click", () => {
    state.progress.extra[today()] = (state.progress.extra[today()] || 0) + 5;
    saveProgress();
    next();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || !el.settings.hidden) return;
    if (state.phase === "feedback") { e.preventDefault(); next(); }
  });

  // ---------- settings ----------
  function openSettings() {
    el.newPerDay.value = state.settings.newPerDay;
    el.autoAudio.checked = state.settings.autoAudio;
    el.showFirst.checked = state.settings.showFirst;
    el.settings.hidden = false;
  }
  function closeSettings() {
    state.settings.newPerDay = Math.max(0, parseInt(el.newPerDay.value, 10) || 0);
    state.settings.autoAudio = el.autoAudio.checked;
    state.settings.showFirst = el.showFirst.checked;
    saveSettings();
    el.settings.hidden = true;
    if (state.current && state.phase === "answer") renderCard(state.current); else next();
  }
  el.settingsBtn.addEventListener("click", openSettings);
  el.closeSettings.addEventListener("click", closeSettings);
  el.settings.addEventListener("click", (e) => { if (e.target === el.settings) closeSettings(); });

  el.exportBtn.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify({ lang: state.lang.code, settings: state.settings, progress: state.progress }, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `sentences-progress-${state.lang.code}-${today()}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  });
  el.importFile.addEventListener("change", async () => {
    const file = el.importFile.files[0];
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      if (data.lang !== state.lang.code || !data.progress || !data.progress.cards) throw new Error("wrong language or format");
      state.progress = data.progress;
      state.progress.extra = state.progress.extra || {};
      if (data.settings) state.settings = { ...DEFAULT_SETTINGS, ...data.settings };
      saveProgress(); saveSettings();
      alert("Progress imported.");
    } catch (err) {
      alert(`Could not import: ${err.message}`);
    }
    el.importFile.value = "";
  });
  el.resetBtn.addEventListener("click", () => {
    if (!confirm(`Erase all ${state.lang.name} progress on this device?`)) return;
    state.progress = { cards: {}, introduced: {}, extra: {} };
    state.recent = [];
    state.session = { reviews: 0, new: 0, right: 0 };
    saveProgress();
    closeSettings();
  });

  // ---------- language loading ----------
  async function loadLanguage(code) {
    state.lang = state.languages.find((l) => l.code === code) || state.languages[0];
    save("sll:lastLang", state.lang.code);
    el.lang.value = state.lang.code;
    const res = await fetch(state.lang.cards);
    state.cards = await res.json();
    state.progress = load(key("progress"), { cards: {}, introduced: {}, extra: {} });
    state.progress.extra = state.progress.extra || {};
    state.settings = { ...DEFAULT_SETTINGS, ...load(key("settings"), {}) };
    state.recent = [];
    state.session = { reviews: 0, new: 0, right: 0 };
    document.title = `Sentences · ${state.lang.name}`;
    next();
  }

  async function init() {
    if (window.speechSynthesis) {
      loadVoices();
      speechSynthesis.addEventListener("voiceschanged", loadVoices);
    }
    const res = await fetch("data/languages.json");
    state.languages = await res.json();
    for (const l of state.languages) {
      const opt = document.createElement("option");
      opt.value = l.code;
      opt.textContent = l.name;
      el.lang.append(opt);
    }
    el.lang.addEventListener("change", () => loadLanguage(el.lang.value));
    await loadLanguage(load("sll:lastLang", state.languages[0].code));
  }

  init().catch((err) => {
    el.stats.textContent = `Could not load: ${err.message}. Serve this folder over HTTP (see README).`;
  });
})();
