# 🇮🇷 FarsiGo — Learn Persian

A mobile-first, Duolingo-style web app for learning **Persian (Farsi)**, built as a
single static site (`index.html` + `style.css` + `app.js` + data files) with **no
build step, no backend, and no dependencies**. Progress, XP and admin edits are
stored on the learner's own device in `localStorage`.

> **At a glance:** 32 units · 320 lessons · 3,200 planned exercises · 320 target
> words/concepts · 32 fully-conjugated verbs (9 tenses × 6 persons) · 224
> real-world example sentences + 10 grammar sentences · cumulative curriculum
> with spaced repetition · no exercise repeats more than 3 times in the whole
> course · mistake-review round at the end of every lesson · admin mode with a
> per-lesson edit dashboard · **2,828 Persian recordings bundled in `audio/`**
> (2,271 clips + 557 slow 🐢 versions) so every 🔊 works offline on any device.

---

## Table of contents

1. [Quick start](#1-quick-start)
2. [Product specification](#2-product-specification)
3. [Curriculum: the 32 units](#3-curriculum-the-32-units)
4. [Lesson structure](#4-lesson-structure)
5. [Exercise system](#5-exercise-system)
6. [Repetition cap (≤ 3 rule)](#6-repetition-cap--3-rule)
7. [Verbs: one per unit, all tenses × all persons](#7-verbs-one-per-unit-all-tenses--all-persons)
8. [Real-world sentences only](#8-real-world-sentences-only)
9. [Mistake review (second chance)](#9-mistake-review-second-chance)
10. [Admin mode & the edit dashboard](#10-admin-mode--the-edit-dashboard)
11. [Bundled audio (🔊)](#11-bundled-audio-)
12. [Screens & navigation](#12-screens--navigation)
13. [Data model & file layout](#13-data-model--file-layout)
14. [State & persistence](#14-state--persistence)
15. [Algorithms](#15-algorithms)
16. [Admin content-editing workflow](#16-admin-content-editing-workflow)
17. [Audits & verification](#17-audits--verification)
18. [Known limitations](#18-known-limitations)
19. [Troubleshooting](#19-troubleshooting)
20. [Future work](#20-future-work)

---

## 1. Quick start

```bash
cd persian-app
python3 -m http.server 8000 --bind 0.0.0.0
# open http://localhost:8000 in a browser (mobile viewport recommended)
```

Or open `index.html` from any static host. The app is mobile-first:
the layout is capped at 480 px wide and designed for one-thumb use; on desktop
it renders as a centred phone-like column.

**First run:** tap **Unit 1 · Lesson 1** (⭐ on the path) → study the teach card
→ *Start Exercises* → complete the 10 exercises → if you made mistakes, finish
the **Mistake Review** round → lesson completes (+20 XP, next lesson unlocks).

---

## 2. Product specification

### 2.1 Purpose

Teach Persian (Farsi) to English speakers in a game-like, bite-size format
modelled on Duolingo's learning path: short lessons, immediate feedback,
hearts, XP, streaks, and a winding path of lessons grouped into themed units.

### 2.2 Target platform & constraints

| Item | Specification |
|---|---|
| Platform | Mobile web (works on desktop browsers too) |
| Layout | Mobile-first, max width 480 px, bottom navigation, sticky headers |
| Runtime | Vanilla HTML/CSS/JavaScript only — no frameworks, no build, no server code |
| Persistence | `localStorage` only (per-device; no accounts, no sync) |
| Audio | **2,828 pre-recorded MP3 clips bundled in `audio/`** (eSpeak-NG, voice `fa`) — see §11 |
| Language direction | English UI is LTR; **all Persian sentence input/display is RTL** (`dir="rtl"`, `lang="fa"`) |
| Offline | Fully offline: all content **and all audio** are local files — no voices to install, no network |

### 2.3 Gamification

- **Hearts:** 5 per lesson; a wrong answer in the main round costs 1 heart.
  Hearts refill every lesson. (Unlimited in admin mode.)
- **XP:** +20 XP for first completion of a lesson, +5 XP for replays.
- **Streak:** stored day counter shown in the header (🔥).
- **Progression:** lessons unlock sequentially — a lesson opens when the
  previous one is completed. (No locks in admin mode.)
- **Stars on completion:** ⭐⭐⭐ no mistakes · ⭐⭐ 1–2 mistakes · ⭐ completed
  with 3+ mistakes (after the mistake-review round).

### 2.4 Scale

| Content | Count |
|---|---|
| Units | 32 |
| Lessons per unit | 10 |
| Total lessons | 320 |
| Exercises per lesson | exactly 10 |
| Total planned exercises | 3,200 |
| Target words/concepts | 320 (10 per unit) |
| Unit verbs | 32 (1 per unit) |
| Verb forms per verb | 54 (9 tenses × 6 persons) = 1,728 forms total |
| Real-world sentences | 224 (7 per unit) |
| Grammar sentences | 10 (1 per grammar pattern) |
| Grammar patterns | 10 |

---

## 3. Curriculum: the 32 units

Each unit has a **theme**, **10 target words/concepts**, **one unit verb**,
cultural notes, and 7 real-world sentences. Units progress from survival
basics (greetings, family, numbers, food) through everyday life (city, travel,
work, shopping, health) to Iranian culture (Nowruz, poetry, ta'arof, festivals)
and advanced registers (formal Persian, media, proverbs).

| # | Unit | Unit verb |
|---|---|---|
| 1 | 👋 Greetings & Basics | رفتن — *raftan* (to go) |
| 2 | 👨‍👩‍👧 Family | داشتن — *dâshtan* (to have) |
| 3 | 🔢 Numbers & Time | پرسیدن — *porsidan* (to ask) |
| 4 | 🍚 Food & Drink | خوردن — *khordan* (to eat) |
| 5 | 🎨 Colors & Description | دیدن — *didan* (to see) |
| 6 | 🩺 Body & Health | خوابیدن — *khâbidan* (to sleep) |
| 7 | 👕 Clothes | پوشیدن — *pushidan* (to wear) |
| 8 | 🏠 Home & House | آمدن — *âmadan* (to come) |
| 9 | 🏙️ City & Places | خریدن — *kharidan* (to buy) |
| 10 | 🧭 Travel & Directions | رسیدن — *residan* (to arrive) |
| 11 | 🌦️ Weather & Nature | شدن — *shodan* (to become) |
| 12 | 🐈 Animals | پریدن — *paridan* (to fly / jump) |
| 13 | 💼 Work & Jobs | ساختن — *sâkhtan* (to build / make) |
| 14 | 📚 School & Learning | خواندن — *khândan* (to read) |
| 15 | 🛍️ Shopping & Money | فروختن — *forukhtan* (to sell) |
| 16 | 😊 Emotions | خندیدن — *khandidan* (to laugh) |
| 17 | ⏰ Daily Routine | برخاستن — *barkhâstan* (to get up) |
| 18 | ⚽ Sports & Hobbies | دویدن — *davidan* (to run) |
| 19 | 🎵 Music & Art | نواختن — *navâkhtan* (to play (instrument)) |
| 20 | 📱 Technology | فرستادن — *ferestâdan* (to send) |
| 21 | 🍢 Iranian Food Culture | پختن — *pokhtan* (to cook) |
| 22 | 🌸 Nowruz & Traditions | بخشیدن — *bakhshidan* (to give / forgive) |
| 23 | 📜 Poetry & History | نوشتن — *neveshtan* (to write) |
| 24 | 🎉 Festivals & Calendar | سوختن — *sukhtan* (to burn) |
| 25 | 🚌 Transport | راندن — *rândan* (to drive) |
| 26 | 🍽️ Restaurant & Ta'arof | پذیرفتن — *paziroftan* (to accept / receive) |
| 27 | ❤️ Love & Friendship | خواستن — *khâstan* (to want) |
| 28 | 🎩 Formal Persian | گفتن — *goftan* (to say / tell) |
| 29 | 📰 Media & News | شنیدن — *shenidan* (to hear) |
| 30 | 🌍 Environment | کاشتن — *kâshtan* (to plant) |
| 31 | 💬 Conversation Mastery | فهمیدن — *fahmidan* (to understand) |
| 32 | 🦉 Proverbs & Idioms | آموختن — *âmukhtan* (to learn) |

The machine-readable source of truth is `data.js` (`UNITS`), `verbs.js`
(`VERBS`) and `sentences.js` (`REAL_SENTENCES`), all in the same unit order.

---

## 4. Lesson structure

Every lesson (Unit *U*, Lesson *L*, global number *G = (U−1)×10 + L*, 1–320)
consists of:

### 4.1 Teach card (before the exercises)

1. **New word/concept** — Persian script (large), transliteration, English
   gloss, and a 🔊 listen button.
2. **Real-world example sentence** from that unit (Persian RTL + English).
3. **A real sentence from earlier material** — showing the new material in the
   context of what has already been covered.
4. **Grammar box** — the lesson's grammar focus (see §4.2) with explanation
   and example, plus the list of grammar patterns known so far.
5. **Unit verb box** — the unit verb with the **full 6-person conjugation
   table** for this lesson's tense (Persian + transliteration); Lesson 10
   shows a 9-tense summary instead (see §7).
6. **Culture box** — an Iranian culture/tradition/history note for the unit.
7. **"Builds on" box** — number of words learned so far, units covered, and
   the recent words that will keep being practised.

### 4.2 Grammar progression

Ten grammar patterns are introduced during Unit 1 and then reused for the
rest of the course: Ezafe linker · present tense *mi-* · questions · plurals
with *-hâ* · negation · object marker *râ* · comparatives *-tar* · past tense ·
formal *shomâ* vs informal *to* · possessive endings. Later lessons apply
these patterns to new vocabulary instead of re-teaching them.

### 4.3 Cumulative ("builds-on") rule

A lesson may only use material from lessons **≤ itself**: vocabulary items,
grammar patterns (Unit 1's ten, thereafter all), real-world sentences from
units ≤ the current unit, and the current unit's verb. Exercises deliberately
recycle earlier material (spaced repetition):

- cumulative picks sample earlier words **systematically across all eras**
  (oldest units → most recent) with a rotating window, so over time every
  earlier word returns;
- sentence exercises draw from the real-sentence bank of covered units,
  preferring sentences that contain words already learned;
- admin-edited words immediately flow into later lessons' cumulative
  exercises as well.

---

## 5. Exercise system

Each lesson has **exactly 10 exercises**. The default (pre-repair) composition:

| # | Slot | Type |
|---|---|---|
| 1 | New word | Single-word picking (Farsi → English or reverse) |
| 2 | New word | Typing (type transliteration or Persian script; accent-insensitive) |
| 3 | Earlier word | Single-word picking (cumulative review) |
| 4 | Earlier word | Single-word picking (cumulative review) |
| 5 | Sentence | **Full-sentence picking:** build a real Persian sentence from a word bank (RTL) |
| 6 | Sentence | Build a real sentence from earlier lessons |
| 7 | Unit verb | Pick the correctly conjugated form (all 6 persons as options) |
| 8 | Unit verb | Type the conjugated form for a named person + tense |
| 9 | Listening | 🎧 Hear a real sentence, pick its English translation |
| 10 | Unit verb listening | 🎧 Hear a conjugated form, pick who is doing it / its translation |

Exercise kinds used across the app:

- **pick** — multiple choice (translations, conjugations, listening
  comprehension). Correct answer is always among the options (audited).
- **build** — tap Persian word chips to assemble a sentence **right-to-left**;
  tapping a placed chip removes it. The shuffled chips always match the
  answer token-for-token (audited).
- **type** — free typing. Persian answers accept the transliteration
  (diacritics ignored, e.g. `salam` = *salâm*) **or** Persian script; the
  input is `dir="auto"` so Persian text flows RTL and Latin text LTR.
- **listening** variants of pick/type — the prompt is only audio (🔊);
  the Persian transcript is hidden from learners (but visible in admin mode,
  see §10).

Feedback: every answer gets immediate ✅/❌ feedback with the correct answer,
a replay-listen button where relevant, and (for mistakes) a note that the
exercise will return in the mistake-review round (§9).

---

## 6. Repetition cap (≤ 3 rule)

**Rule:** one identical exercise — identity = *kind + spoken text + prompt +
answer* (so the same word tested by picking vs typing vs listening counts as
different exercises) — may appear **at most 3 times in the entire
320-lesson curriculum**, and **never twice within one lesson**.

Implementation (see also §15):

- Lessons are *planned* in teaching order; a global usage counter tracks every
  exercise assigned so far.
- Each lesson is first generated from deterministic seeded variants; slots
  take the first variant whose exercises are all still under the cap.
- Any slot still over the cap is **repaired**: converted to another form of
  the same content (pick ↔ type ↔ listen ↔ build), or swapped for a fresh
  real sentence / word that still has remaining uses.
- Audited result: 3,200 exercises, **maximum repeat = 3, zero exercises over
  the cap**, planning takes < 1 s (incremental: opening lesson *G* only plans
  lessons up to *G*, in order).

---

## 7. Verbs: one per unit, all tenses × all persons

Every unit teaches **one verb** (listed in §3) through the exercises, not just
on the teach card.

### 7.1 Tense/aspect system (9 forms)

Taught one per lesson — Lessons 1–9 in this order, Lesson 10 = mixed review:

| Lesson | Tense | Persian formation (example: رفتن *raftan*, "to go") |
|---|---|---|
| 1 | Present simple | *mi-* + present stem + ending — **می‌روم** *miravam* "I go" |
| 2 | Present continuous | *dâram* + present simple — **دارم می‌روم** "I am going" |
| 3 | Present perfect | participle + *-am/-i/ast…* — **رفته‌ام** *rafte-am* "I have gone" |
| 4 | Past simple | past stem + ending — **رفتم** *raftam* "I went" |
| 5 | Past continuous | *mi-* + past stem + ending — **می‌رفتم** "I was going" |
| 6 | Past perfect | participle + *budam…* — **رفته بودم** "I had gone" |
| 7 | Future simple | *khâham…* + past stem — **خواهم رفت** "I will go" |
| 8 | Future continuous | *dar hâl-e … khâham bud* — **در حال رفتن خواهم بود** "I will be going" |
| 9 | Future perfect | participle + *khâham bud* — **رفته خواهم بود** "I will have gone" |
| 10 | **Mixed review** | drills rotate across all 9 tenses |

### 7.2 Persons (6)

من *man* (I) · تو *to* (you, informal) · او *u* (he/she) · ما *mâ* (we) ·
شما *shomâ* (you, plural/formal) · آن‌ها *ânhâ* (they).

Forms are **generated programmatically** from each verb's stored past stem,
present stem and participle pattern (32 verbs × 9 tenses × 6 persons = 1,728
forms), e.g. می‌گویم *miguyam* "I say", داریم می‌رویم "we are going",
رفته بودند "they had gone", خواهد رفت "he/she will go".

### 7.3 Verb exercises (3 of every lesson's 10)

1. **Pick the form** — named person + tense; **all 6 persons are the options**
   (Persian forms, RTL), so learners compare the whole paradigm.
2. **Type the form** — given the English ("she was eating"), type the Persian
   (transliteration or script).
3. **Listen & identify** — hear a form, choose its English translation / who
   is doing it. Persons rotate by lesson so all six are drilled across the
   unit; informal *to* and formal *shomâ* are kept distinct in the options.

---

## 8. Real-world sentences only

Sentence exercises never machine-assemble word combinations. All sentences
come from a curated bank of natural Persian as actually used in Iran —
greetings, bazaar bargaining, taxis, home life, Nowruz, ta'arof, idioms —
e.g. «سلام! چطوری؟», «ببخشید، ایستگاه مترو کجاست؟», «این چنده؟ تخفیف می‌دی؟»,
«دلم برات تنگ شده», «نوش جان!», «دستت درد نکنه!».

- 7 sentences per unit (`sentences.js: REAL_SENTENCES`, same unit order),
  plus 10 grammar-demonstration sentences (`GRAMMAR_SENTENCES`).
- A lesson may only use sentences from units **≤ its own unit**, preferring
  sentences containing already-learned words.
- Audit: every sentence-builder answer, listening prompt and teach-card
  example across all 320 lessons is a member of this bank (taught multi-word
  vocabulary phrases such as شب بخیر "good night" are vocabulary, not
  sentences).

---

## 9. Mistake review (second chance)

- Any exercise answered incorrectly in the main round is remembered; the
  feedback says it will return at the end of the lesson.
- After exercise 10, **instead of completing**, the lesson enters an orange
  **↩️ MISTAKE REVIEW** round with exactly the missed exercises.
- Getting one wrong *again* in review sends it to the back of the review
  queue for one more attempt (no heart loss during review).
- The completion screen reports: *"↩️ Mistake review done! You re-answered
  the N exercises you missed and got them right in the end."*
- A perfect lesson skips review and completes immediately.

Verified by an automated simulation (wrong → queued → not completed →
reviewed → re-queued on a second miss → completed with XP and unlock).

---

## 10. Admin mode & the edit dashboard

Tap **🔐 Admin** (top-right header) to enter admin mode (🛠️ Admin ON banner):

- **No locked lessons** — all 320 lessons are open on the path.
- **Unlimited hearts** — hearts display ❤️ ∞ and never decrease.
- **🎧 Listening transcripts visible** — under every listening exercise's 🔊
  button, admins see the spoken Persian text (RTL, dashed orange box,
  "🛠️ ADMIN — SPOKEN TEXT"). Learners never see it.
- **✏️ Edit on every lesson** — an orange Edit button under each lesson on
  the path, plus "✏️ Edit this lesson" inside its teach card.

The **edit dashboard** (per lesson) edits and persists:

| Field | Notes |
|---|---|
| English word/concept | required |
| Persian (script) | RTL input, required |
| Transliteration | required |
| Example sentence (Persian / English) | defaults to a real sentence of the unit |
| Grammar title / explanation / example | defaults to the lesson's grammar pattern |
| Culture note | defaults to the unit's culture note |
| Unit theme | applies unit-wide |

Actions: **👀 Preview teach card**, **💾 Save**, **↩️ Reset this lesson to
original**, Cancel. Edited lessons are marked 📝 on the path. Saving from
inside a lesson reloads that lesson with the new content.

Edits are stored as per-lesson overrides in `localStorage`
(`store.custom["<unit>-<lesson>"]`, plus `store.customUnits`) and merged over
the original data at render/generation time — so an edited word immediately
changes its teach card, its exercises, **and all later cumulative/review and
verb-adjacent material that reuses it**; the exercise planner cache is
invalidated and rebuilt under the ≤3 cap with the new content.

---

## 11. Bundled audio (🔊)

**Every Persian string the app can say is a pre-recorded MP3 that ships in the
repository** — 2,271 recordings plus 557 slower 🐢 variants (2,828 clips,
≈17 MB). Nothing is synthesised while the app runs and nothing is fetched from
the network, so pronunciation is identical on every phone, tablet and desktop,
and the whole course works completely offline.

| Recorded content | Clips | Example |
|---|---|---|
| Unit words (the 320 lesson targets) | 320 | `آب` — âb — water |
| Real-world sentences + grammar sentences | 234 | `سلام! چطوری؟` — Hello! How are you? |
| Every conjugation: 32 verbs × 9 tenses × 6 persons | 1,728 | `دارم می‌روم` — dâram miravam — I am going |
| Grammar examples, teach-card sentences, RTL prompts & options | (in the above) | `کتابِ بزرگ` — the big book |

How it works:

- `audio/index.js` is a generated manifest mapping each Persian string to its
  file (`audio/<xx>/<sha1>.mp3`), so the app never guesses a path. Keys are
  whitespace-normalised, so text from the data files always matches.
- **🔊** plays the recording, **🐢** plays it more slowly (words and sentences
  only — 1,728 verb forms are normal speed).
- Playback uses the browser's built-in `<audio>` support (MP3, mono,
  22.05 kHz, 32 kbps) — no libraries, no Web Audio, no codecs to install.
- One reused `<audio>` element means a new 🔊 always stops the previous one;
  the current exercise's clip is pre-loaded, and iOS/Safari's "sound only
  after a tap" rule is handled by unlocking playback with a silent clip on the
  first tap of the session (so the automatic 🎧 prompts work from lesson 1).
- **Custom text** — a word a teacher types in the admin editor — has no
  recording yet. It falls back to the device's own Persian voice when one is
  installed, with a short explanation when it is not. Rebuild the pack and it
  gets a recording too.
- **Profile → 🔊 Audio check** plays a sample and reports how many recordings
  are bundled plus whether the device has its own Persian voice.

### Rebuilding the audio pack

The clips are generated by `tools/build_audio.py` with **eSpeak-NG** (Persian
voice `fa`), from the same strings the app itself produces:

```bash
python3 tools/build_audio.py                  # rebuild everything (~15 s)
python3 tools/build_audio.py --only-missing   # just new/changed strings
node tools/audit_audio.mjs                    # verify every 🔊 has a file
```

`build_audio.py` first runs `tools/collect_strings.mjs`, which loads the real
app in a DOM stub and walks all 320 lessons to find every string that can be
spoken (words, real sentences, all 1,728 conjugations, grammar examples). It
then trims/normalises each waveform and encodes it to MP3. Dependencies
(eSpeak-NG, LAME, numpy) are fetched into `~/.cache/parlingo-tts` — nothing is
installed system-wide.

After editing `data.js`, `sentences.js` or `verbs.js`, re-run the builder and
`git add audio`; `node tools/audit_audio.mjs` then fails loudly if any 🔊
button would be silent.

---

## 12. Screens & navigation

| Screen | Contents |
|---|---|
| **Learn (path)** | Header (🇮🇷 FA · 🔥 streak · 💎 XP · ❤️ hearts · 🔐 Admin), admin banner, 32 unit banners (colour, icon, Guidebook) with a winding path of 10 lesson nodes each (⭐ available, 👑/✔ done, 🔒 locked, 📝 edited, ✏️ Edit in admin) |
| **Lesson** | ✕ quit, progress bar, hearts, teach card → 10 exercises → mistake-review round → completion screen |
| **Edit dashboard** | Per-lesson content editor (§10) |
| **Bottom nav** | 🏠 Learn · 📚 Units (all 32 units with per-unit progress) · 🎧 Listen (random listening practice) · 👤 Profile (streak/XP/lessons, voice test, reset progress) |
| **Guidebook sheet** | Per-unit theme, culture note, unit verb, word list, Start Unit |

---

## 13. Data model & file layout

```
persian-app/
├── index.html    # screens: path, lesson, edit dashboard, nav, toast/sheet
├── style.css     # mobile-first styles (480 px column), RTL sentence styles
├── data.js       # UNITS[32]: theme, icon, colour, taglines, culture note,
│                 #   words[10] = [english, farsi, transliteration];
│                 #   GRAMMAR[10]: [title, explanation, example]
├── sentences.js  # REAL_SENTENCES[32][7] = {fa, en}; GRAMMAR_SENTENCES[10]
├── verbs.js      # VERBS[32] stems & English forms; TENSES[9]; PERSONS[6];
│                 #   conjugate(verb, tenseIdx, personIdx) -> {fa, tr, en, ...}
├── app.js        # state, path rendering, exercise planner/generator,
│                 #   lesson flow, mistake review, admin/editor,
│                 #   bundled-audio player (🔊/🐢) + device-voice fallback
├── audio/        # 2,828 pre-recorded Persian MP3s (≈17 MB), hash-sharded
│   └── index.js  #   generated manifest: "فارسی" -> "audio/xx/<hash>.mp3"
├── tools/        # build_audio.py (pack builder), collect_strings.mjs,
│                 #   audit_audio.mjs, browser_test.mjs (jsdom), app_sandbox.mjs
└── readme.md     # this file
```

`UNITS[u][6][l]` is target word *l* of unit *u*: `[english, farsi,
transliteration]`. Content is plain data — the entire curriculum can be
edited in these files without touching logic (or at runtime via admin mode).

---

## 14. State & persistence

`localStorage["farsiGo"]`:

```jsonc
{
  "done":   { "0-0": true, "0-1": true },   // "<unit>-<lesson>" (0-based)
  "xp":     120,
  "streak": 1,
  "admin":  false,
  "custom": {                                 // admin lesson edits
    "3-2": { "en": "…", "fa": "…", "tr": "…", "exFa": "…", "exEn": "…",
             "gTitle": "…", "gText": "…", "gEx": "…", "culture": "…" }
  },
  "customUnits": { "3": { "theme": "…", "culture": "…" } }
}
```

Effective content = original data merged with `custom` overrides
(`effWord()` / `effTeach()` in `app.js`). Resetting progress (Profile)
clears the entry and reloads.

---

## 15. Algorithms

- **Deterministic generation:** all randomness comes from a per-lesson seeded
  PRNG (`seeded()`), so a lesson's exercises are stable across visits and the
  planner's decisions are reproducible.
- **Cumulative sampling (`cumulativePicks`):** starting from a seeded offset,
  picks earlier words at a stride across the whole learned range (all eras),
  rotating every lesson.
- **Exercise planning (`planLesson` / `ensureUpTo`):** planned strictly in
  teaching order with a global signature counter
  (`exerciseSig = kind | listening? | prompt | spoken | answer`). Slots accept
  the first seeded variant under the ≤3 cap and not already used in that
  lesson; remaining slots are repaired by form conversion
  (`convertExercise`, `sentenceForms`, `wordForms`) or fresh-content scan.
  Plans are cached per session and invalidated on admin edits.
- **Answer checking:** exact match for pick/build; for typing, normalised
  comparison (lowercase, diacritics stripped, punctuation/spaces removed) so
  `salam`, `salâm` and سلام are equivalent where applicable.
- **Conjugation (`conjugate`):** builds all 54 forms per verb from stems:
  present simple *mi-+present stem+endings*, present continuous
  *dâr-+present simple*, perfects from the participle (*past stem + -e*)
  with *-am…/budam/khâham bud* auxiliaries, past continuous *mi-+past stem*,
  futures with *khâham…* (+ *dar hâl-e … bud* for future continuous).
  English glosses are generated with correct auxiliaries
  (am/are/is, was/were, have/has, will…).

---

## 16. Admin content-editing workflow

1. Tap **🔐 Admin** (header). Optionally jump anywhere — everything is unlocked.
2. Tap **✏️ Edit** under a lesson (or inside its teach card).
3. Change fields → **👀 Preview** → **💾 Save**. The lesson, its exercises,
   and later lessons reusing that word update immediately; edited lessons
   show 📝 on the path.
4. **↩️ Reset this lesson** deletes the override and restores original data.
5. While in admin, the spoken text of every listening exercise is shown, and
   🔊/🐢 play the bundled recording. **Text you have just typed has no
   recording yet** — until the pack is rebuilt (see §11) the app falls back to
   the device's Persian voice for it.

---

## 17. Audits & verification

The curriculum is verified by automated Node test harnesses (DOM-stubbed)
that load the real data + app code and assert, over **all 320 lessons**:

- every lesson yields exactly 10 exercises (3,200 total), exactly 3 of them
  verb drills, with no duplicate options;
- **no exercise signature repeats more than 3 times curriculum-wide** (and
  never twice in one lesson);
- every multiple-choice answer is present in its options; every
  sentence-builder's chips match its answer exactly;
- every teach-card example, builder answer and listening sentence comes from
  the real-sentence bank;
- conjugations spot-check correctly (e.g. می‌روم، می‌گویم، می‌آیم،
  داریم می‌رویم، رفته بودند، خواهد رفت) for all 32 verbs × 9 tenses × 6 persons;
- the full lesson flow (answers, mistakes, mistake-review queue, XP, unlock)
  behaves as specified (§9), and admin mode unlocks everything, shows
  transcripts, and propagates edits into later lessons;
- **the audio pack is complete:** `node tools/audit_audio.mjs` plays all 320
  lessons by answering every exercise correctly, renders every teach card and
  scans every generated 🔊 button, then checks each manifest entry against the
  files on disk — currently 2,262 distinct spoken strings, 2,828 clips, 0
  device-voice fallbacks.
- **the page really plays that audio:** `node tools/browser_test.mjs` (jsdom,
  needs `npm i jsdom`) serves the site, loads `index.html`, clicks every 🔊/🐢
  of a lesson and asserts each click plays exactly the file the manifest
  promises, that the sample files answer 200 and that the sheets still work.

---

## 18. Known limitations

- **The audio is a fixed recording set:** all 2,828 clips use one eSpeak-NG
  Persian voice (clear but synthetic) at one speed (plus the 🐢 slow variant
  for words and sentences) — there is no choice of accent or speaker yet. Text
  typed in the admin editor stays on the device voice until the pack is rebuilt
  (§11).
- **Progress is per-device** (`localStorage`) — no accounts or cloud sync;
  clearing browser data resets progress and admin edits.
- **Sentence preference:** sentence exercises prefer real sentences
  containing learned words, but since sentences are authentic, they may
  contain individual words not yet formally taught (glossed by the English
  translation).
- **Future continuous** uses the natural periphrasis *dar hâl-e … khâham bud*
  ("I will be in the middle of …-ing") rather than a colloquial progressive.
- Content (words, sentences, verbs) is data-driven and intentionally simple
  to audit; expanding it means adding entries to `data.js` / `sentences.js` /
  `verbs.js` — admin edits only persist on the device where they were made.
- The streak counter is stored locally and does not yet compute calendar-day
  differences.

---

## 19. Troubleshooting

| Problem | Fix |
|---|---|
| No sound on 🔊 / listening exercises | The recordings ship with the app, so no Persian device voice is needed. Check device volume / silent mode, and that the `audio/` folder was deployed next to `index.html` (§11). When the page is embedded in a sandboxed preview, tap the page once first (browsers only allow sound after a tap). |
| A word I typed in the admin editor is silent | Custom text has no recording until you rebuild the pack: `python3 tools/build_audio.py` (§11). Until then the device's own Persian voice is used, if one is installed. |
| A lesson is locked | Finish the previous lesson (or enable 🔐 Admin mode to open everything). |
| Hearts ran out | Hearts refill at the start of each lesson; mistakes in the review round cost nothing. Admin mode = unlimited hearts. |
| My edits disappeared | Edits live in this browser's `localStorage`; check you are in the same browser/profile and didn't clear site data. Profile → Reset Progress also clears edits. |
| Persian text displays left-to-right | Sentence areas are RTL by design; if text still looks wrong, ensure you are on the latest files (hard-refresh) — the viewport `<meta>` must be present. |
| Progress lost | Same-device/same-browser storage only; there is no account sync (§18). |

---

## 20. Future work

- More voices/accents for the audio pack (and 🐢 slow recordings for the verb
  forms), plus per-user playback-speed control.
- Accounts & cloud sync for progress and admin edits; exporting/importing
  custom lesson content (JSON) from the edit dashboard.
- More real-world sentences per unit and sentence-level vocabulary glossing.
- Negative/interrogative conjugation drills and colloquial (spoken) Persian
  variants alongside written forms.
- Calendar-aware streaks, daily goals, and a dedicated verb-paradigm
  practice mode reusing `conjugate()`.
- Leitner-style scheduling driven by per-exercise mistake history (the
  mistake-review data already exists in-session).

---

*Built as a single static folder — copy `persian-app/` anywhere that serves
static files and it runs.*
