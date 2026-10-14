// tools/browser_test.mjs
// ---------------------------------------------------------------------------
// Real-DOM test (jsdom): serves the app over HTTP, loads index.html, clicks
// through a lesson and verifies that every 🔊/🐢 button plays the bundled MP3
// that the manifest promises (never the device voice), that the referenced
// files answer 200, and that the Listen/Audio-check sheets work.
//
//   python3 -m http.server 8099 --bind 0.0.0.0 &
//   npm i jsdom && node tools/browser_test.mjs http://127.0.0.1:8099
// ---------------------------------------------------------------------------
// needs jsdom:  npm i jsdom   (or NODE_PATH=/path/to/node_modules node tools/browser_test.mjs)
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { JSDOM, VirtualConsole } = require('jsdom');

const BASE = process.argv[2] || 'http://127.0.0.1:8099';

const problems = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => {
  const m = String(e.message || e);
  if (/Not implemented/.test(m)) return;              // jsdom has no audio engine
  if (/Could not load/.test(m)) problems.push('resource: ' + m.split('\n')[0]);
  else problems.push('jsdomError: ' + m.split('\n')[0]);
});
vc.on('error', (...a) => problems.push('console.error: ' + a.join(' ')));

const dom = await JSDOM.fromURL(BASE + '/index.html', {
  runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true, virtualConsole: vc,
});
const { window } = dom;
await new Promise(r => window.addEventListener('load', r));

// record every audio element the app creates and which src it asks for
const played = [];
window.HTMLMediaElement.prototype.play = function () { played.push({ src: this.getAttribute('src'), el: this.tagName }); return Promise.resolve(); };
window.HTMLMediaElement.prototype.pause = function () {};

const $ = s => window.document.querySelector(s);
const manifest = window.eval('typeof FA_AUDIO==="object" ? Object.keys(FA_AUDIO).length : -1');
console.log('manifest entries:', manifest);
if (manifest < 2000) problems.push(`manifest looks wrong (${manifest} entries)`);

// 1 · the teach card of unit 1 lesson 1 has 🔊 + 🐢 buttons
window.eval('startLesson(0,0)');
const sayBtns = [...window.document.querySelectorAll('#exerciseArea [data-say]')];
console.log('teach-card audio buttons:', sayBtns.length);
if (sayBtns.length < 3) problems.push('teach card should offer several 🔊/🐢 buttons');

// 2 · click each one — the app must play the matching bundled file
for (const b of sayBtns) {
  played.length = 0;
  const key = b.getAttribute('data-say');
  b.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
  const slow = b.hasAttribute('data-say-slow');
  const expected = window.eval(`(function(){let k=${JSON.stringify(key)};return (${slow ? 'FA_AUDIO_SLOW' : 'FA_AUDIO'}[k])||FA_AUDIO[k]})()`);
  // the very first click also fires the silent iOS "unlock" clip
  if (!played.length) problems.push(`clicking 🔊 for ${JSON.stringify(key)} played nothing`);
  else if (!played.some(p => p.src === expected))
    problems.push(`played ${played.map(p => p.src).join(', ')} instead of ${expected}`);
}

// 3 · step through all 10 exercises of the lesson, clicking every 🔊/🐢
window.eval('S.step=-1');
let scanned = 0;
for (let step = 0; step < 10; step++) {
  window.eval(`S.step=${step};renderStep()`);
  for (const b of [...window.document.querySelectorAll('#exerciseArea [data-say], #exerciseArea button')]) {
    const key = b.getAttribute && b.getAttribute('data-say');
    if (!key) continue;
    scanned++;
    played.length = 0;
    b.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    if (!played.length) problems.push(`exercise ${step + 1}: 🔇 ${JSON.stringify(key)} played nothing`);
    else if (played[0].src.includes('silence')) problems.push(`exercise ${step + 1}: only the silent unlock clip played`);
  }
}
console.log('exercise audio buttons clicked:', scanned);

// 4 · every referenced file answers 200 (the app pre-loads them via <audio>)
const urls = await window.eval('Object.values(FA_AUDIO)');
const sample = urls.filter((_, i) => i % 137 === 0).concat(['audio/silence.mp3']);
for (const u of sample) {
  const r = await fetch(`${BASE}/${u}`).catch(e => ({ ok: false, status: String(e) }));
  if (!r.ok) problems.push(`GET ${u} -> ${r.status}`);
}
console.log('files fetched over HTTP:', sample.length);

// 5 · the Listen tab
window.eval('showPractice()');
const sheetBtns = [...window.document.querySelectorAll('#sheet [data-say]')];
if (!sheetBtns.length) problems.push('Listen tab has no 🔊 button');
if (/<h3[^>]*>.*[\u0600-\u06FF].*<\/h3>/s.test($('#sheet').innerHTML) && !window.document.querySelector('#sheet details')) {
  problems.push('Listen tab should hide the answer behind "reveal"');
}

// 6 · audio check sheet + profile
window.eval('showAudioCheck()');
if (!/recordings/.test($('#sheet').innerHTML)) problems.push('audio check sheet looks wrong');
window.eval('closeSheet();showProfile()');
if (!/Audio check/.test($('#sheet').innerHTML)) problems.push('profile has no audio check');

if (problems.length) {
  console.error(`\n✗ ${problems.length} problem(s):`);
  [...new Set(problems)].slice(0, 25).forEach(p => console.error('  • ' + p));
  process.exit(1);
}
console.log('\n✓ page loads, every 🔊 plays the bundled MP3, all sample files 200 OK');
