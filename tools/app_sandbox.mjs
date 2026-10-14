// tools/app_sandbox.mjs
// ---------------------------------------------------------------------------
// Loads the real app (data.js, sentences.js, verbs.js, audio/index.js when it
// exists, app.js) into a Node VM with a minimal DOM stub, so the build/audit
// tools can drive the app exactly like a browser does — without a browser.
//
// Top-level `const`/`let` of those scripts live in the VM context's lexical
// scope (just like separate <script> tags in a page), so they are read back
// with the `grab(expression)` helper.
// ---------------------------------------------------------------------------
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function makeEl(id) {
  const cls = new Set();
  const attrs = new Map();
  return {
    id,
    classList: {
      add: c => cls.add(c), remove: c => cls.delete(c),
      toggle: (c, v) => (v ? cls.add(c) : cls.delete(c)), contains: c => cls.has(c),
    },
    style: {}, innerHTML: '', textContent: '', value: '', className: '', onclick: null, dataset: {},
    addEventListener() {}, removeEventListener() {}, querySelectorAll: () => [],
    appendChild() {}, focus() {},
    setAttribute(k, v) { attrs.set(k, String(v)) }, getAttribute: k => (attrs.has(k) ? attrs.get(k) : null),
  };
}

export function loadApp({ withAudio = true } = {}) {
  const els = new Map();
  const document = {
    getElementById: id => (els.has(id) ? els.get(id) : (els.set(id, makeEl(id)), els.get(id))),
    querySelectorAll: () => [], createElement: () => makeEl(''), body: makeEl('body'),
    addEventListener() {},
  };
  const localStorage = {
    _d: {}, getItem(k) { return k in this._d ? this._d[k] : null },
    setItem(k, v) { this._d[k] = String(v) }, removeItem(k) { delete this._d[k] },
  };
  const ctx = vm.createContext({
    console, document, localStorage, setTimeout: () => 0, clearTimeout: () => {},
    alert: () => {}, confirm: () => true, location: { reload() {} }, Audio: undefined,
    scrollTo: () => {}, addEventListener: () => {}, focus: () => {},
  });
  ctx.window = ctx;
  ctx.globalThis = ctx;

  const files = ['data.js', 'sentences.js', 'verbs.js'];
  if (withAudio && fs.existsSync(path.join(root, 'audio', 'index.js'))) files.push('audio/index.js');
  files.push('app.js');
  for (const f of files) {
    vm.runInContext(fs.readFileSync(path.join(root, f), 'utf8'), ctx, { filename: f });
  }
  const grab = expr => vm.runInContext(expr, ctx);
  return { ctx, grab, document, els };
}

// HTML attribute values produced by escAttr() hold &amp; &quot; &lt; &gt;
export const unescAttr = s => s
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&amp;/g, '&');

// every data-say="…" value inside a chunk of generated HTML
export function saidIn(html) {
  const out = [];
  const re = /data-say="([^"]*)"/g;
  let m;
  while ((m = re.exec(html || ''))) out.push(unescAttr(m[1]));
  return out;
}
