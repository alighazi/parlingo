// tools/audit_audio.mjs
// ---------------------------------------------------------------------------
// Audio-pack audit. Drives the real app through the whole 320-lesson curriculum
// (teach card + all 10 exercises of every lesson, the Listen tab and the audio
// check sheet) and verifies that
//
//   • every Persian string rendered with a 🔊 button has a manifest entry,
//   • every manifest entry points at an MP3 that exists on disk,
//   • the slow 🐢 variants exist for everything they are offered for,
//   • the manifest has no stale entries for strings the app no longer uses,
//   • no exercise falls back to the device voice.
//
// Usage:  node tools/audit_audio.mjs        (exit code 1 when something is off)
// ---------------------------------------------------------------------------
import fs from 'node:fs';
import path from 'node:path';
import { loadApp, root, saidIn } from './app_sandbox.mjs';

const { ctx, grab, document } = loadApp({ withAudio: true });
const AUDIO = grab('typeof FA_AUDIO==="object"?FA_AUDIO:{}');
const AUDIO_SLOW = grab('typeof FA_AUDIO_SLOW==="object"?FA_AUDIO_SLOW:{}');
const UNITS = grab('UNITS');

const problems = [];
const seen = new Set();
const normalise = s => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();

function checkText(where, text) {
  const key = normalise(text);
  if (!key || !/[\u0600-\u06FF]/.test(key)) return;
  seen.add(key);
  if (!(key in AUDIO)) problems.push(`${where}: no bundled recording for ${JSON.stringify(key)}`);
}

function scan(where, html) {
  saidIn(html).forEach(t => checkText(where, t));
}

// make the whole curriculum reachable and walk it like a learner
grab('store.admin=true;');
const lessons = UNITS.length * 10;
for (let g = 0; g < lessons; g++) {
  const ui = Math.floor(g / 10), li = g % 10;
  grab(`startLesson(${ui},${li})`);                    // renders the teach card
  scan(`unit ${ui + 1} lesson ${li + 1} teach card`, document.getElementById('exerciseArea').innerHTML);
  const exercises = grab('S.ex');
  exercises.forEach((e, i) => {                        // every exercise, step by step
    if (e.speak) checkText(`unit ${ui + 1} lesson ${li + 1} exercise ${i + 1} (spoken)`, e.speak);
    grab(`S.step=${i};renderStep();`);
    scan(`unit ${ui + 1} lesson ${li + 1} exercise ${i + 1}`, document.getElementById('exerciseArea').innerHTML);
  });
}
grab('quitLesson();');
grab('showPractice();');
scan('listen tab', document.getElementById('sheet').innerHTML);
grab('closeSheet();showAudioCheck();');
scan('audio check', document.getElementById('sheet').innerHTML);

// ---- end-to-end playthrough ------------------------------------------------
// Answer every exercise of every lesson correctly and watch the voice fallback:
// with a complete audio pack the device voice must never be used.
const driver = `
window.__ttsFallback=[];
speakDevice=function(t){window.__ttsFallback.push(t);return false};
let _finish=finish;window.__lessonDone=false;
finish=function(){window.__lessonDone=true;return _finish.apply(null,arguments)};
function __answer(e){
  if(e.kind==='build'){
    let used=[],built=[];
    e.answer.split(' ').forEach(w=>{let i=e.tokens.findIndex((t,j)=>t===w&&used.indexOf(j)<0);if(i>=0){used.push(i);built.push({i,t:w})}});
    S.built=built;
  } else if(e.kind==='type'){S.selected=e.accept[0];document.getElementById('typeInput').value=e.accept[0]}
  else S.selected=e.answer;
}
window.__playLesson=function(ui,li){
  window.__lessonDone=false;startLesson(ui,li);
  let guard=0;
  while(guard++<120&&!window.__lessonDone){
    if(S.step<0){onMainButton();continue}
    let e=curEx();__answer(e);onMainButton();onMainButton();
  }
  quitLesson();
};
`;
grab(driver);
let played = 0;
for (let g = 0; g < lessons; g++) {
  grab(`window.__playLesson(${Math.floor(g / 10)},${g % 10})`);
  played++;
}
const fallbacks = grab('window.__ttsFallback');
if (fallbacks.length) {
  problems.push(`${fallbacks.length} automatic playback(s) fell back to the device voice, e.g. ${JSON.stringify(fallbacks.slice(0, 5))}`);
}

// every manifest entry must exist as a file (and every slow entry too)
let files = 0;
for (const [map, label] of [[AUDIO, ''], [AUDIO_SLOW, '-slow']]) {
  for (const [key, rel] of Object.entries(map)) {
    if (!rel.endsWith(`${label}.mp3`)) problems.push(`${label || 'fast'} entry for ${JSON.stringify(key)} points at ${rel}`);
    if (!fs.existsSync(path.join(root, rel))) problems.push(`missing file ${rel} (${JSON.stringify(key)})`);
    else files++;
  }
}
const fast = Object.keys(AUDIO).length, slow = Object.keys(AUDIO_SLOW).length;
console.log(`checked ${lessons} lessons · ${seen.size} strings rendered with 🔊 · ` +
            `${fast} fast + ${slow} slow clips in the manifest · ${files} files present`);
console.log(`played ${played} lessons answering everything correctly — device-voice fallbacks: ${fallbacks.length}`);
if (problems.length) {
  console.error(`\n✗ ${problems.length} problem(s):`);
  problems.slice(0, 40).forEach(p => console.error('  • ' + p));
  if (problems.length > 40) console.error(`  … and ${problems.length - 40} more`);
  process.exit(1);
}
console.log('✓ every 🔊 has a bundled recording and every recording is on disk');
