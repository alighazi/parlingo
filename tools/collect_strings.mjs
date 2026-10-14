// tools/collect_strings.mjs
// ---------------------------------------------------------------------------
// Runs the real app (data.js + sentences.js + verbs.js + app.js) inside the
// DOM stub from tools/app_sandbox.mjs, walks the entire 320-lesson curriculum
// exactly like the browser would, and prints every Persian string the app can
// hand to speak().
//
// Output (stdout, JSON):
//   { "count": N, "slowCount": M, "strings": [ …all spoken strings… ],
//     "slow": [ …subset that also gets a slow 🐢 recording… ] }
//
// The "slow" subset is everything except the 1,728 verb conjugation forms
// (words, real sentences, grammar examples, teach-card sentences).
//
// Usage:  node tools/collect_strings.mjs > /tmp/strings.json
// ---------------------------------------------------------------------------
import { loadApp } from './app_sandbox.mjs';

const { grab } = loadApp({ withAudio: false });
const UNITS = grab('UNITS'), REAL_SENTENCES = grab('REAL_SENTENCES'),
      GRAMMAR_SENTENCES = grab('GRAMMAR_SENTENCES'), VERBS = grab('VERBS'),
      GRAMMAR = grab('GRAMMAR');

const all = new Set(), slow = new Set(), verbs = new Set();
const norm = s => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
const add = (s, isSlow) => {
  const t = norm(s);
  if (!t || !/[\u0600-\u06FF]/.test(t)) return;
  all.add(t);
  if (isSlow) slow.add(t);
};

// 1) every unit word
UNITS.forEach(u => u[6].forEach(w => add(w[1], true)));

// 2) every real sentence + grammar sentence (whole bank, not just those used)
REAL_SENTENCES.flat().forEach(s => add(s.fa, true));
GRAMMAR_SENTENCES.forEach(s => add(s.fa, true));

// 3) every conjugation of every unit verb: 32 verbs x 9 tenses x 6 persons
const conjugate = grab('typeof conjugate==="function"?conjugate:null');
if (conjugate) {
  VERBS.forEach(v => {
    for (let ti = 0; ti < 9; ti++) for (let p = 0; p < 6; p++) {
      const f = norm(conjugate(v, ti, p).fa);
      verbs.add(f);
      add(f, false);
    }
  });
}

// 4) everything the running app actually speaks or shows with a 🔊 button,
//    lesson by lesson (teach cards, generated exercises, RTL prompts/options)
const buildExercises = grab('typeof buildExercises==="function"?buildExercises:null'),
      effTeach = grab('typeof effTeach==="function"?effTeach:null'),
      effWord = grab('typeof effWord==="function"?effWord:null'),
      faPart = grab('typeof faPart==="function"?faPart:null');
for (let g = 0; g < 32 * 10; g++) {
  const ui = Math.floor(g / 10), li = g % 10;
  if (effTeach) { const t = effTeach(ui, li); add(t.exFa, true); add(faPart(t.gEx), true); }
  if (effWord) add(effWord(ui, li)[1], true);
  if (!buildExercises) continue;
  buildExercises(ui, li).forEach(e => {
    add(e.speak);                          // always spoken
    if (e.promptFa) add(e.prompt, true);   // shown big & RTL — gets a 🔊 button
    if (e.rtl) {
      if (e.prompt) add(e.prompt);
      if (e.answer) add(e.answer);
      (e.options || []).forEach(o => add(o));
    }
    if (e.kind === 'build' && e.fa) add(e.fa, true);
  });
}

// 5) grammar example lines ("کتابِ بزرگ — ketâb-e bozorg — the big book"):
//    keep the Persian part before the first dash
GRAMMAR.forEach(g => add(String(g[2]).split('—')[0], true));

const strings = [...all].sort();
const slowList = [...slow].sort();
process.stdout.write(JSON.stringify({
  count: strings.length, slowCount: slowList.length, strings, slow: slowList,
}));
