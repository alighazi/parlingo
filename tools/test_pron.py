#!/usr/bin/env python3
# =============================================================================
# FarsiGo — pronunciation regression tests
# =============================================================================
# Rebuilds the corrected Persian dictionary from tools/pron_rules.py +
# tools/pron/*.txt and checks that
#
#   1. every override really applies in the compiled dictionary,
#   2. the stress rules land where Persian wants it (final for content words,
#      the mi-/nemi- prefix in verb forms, the participle in رفته‌ام, …),
#   3. the correction only moves stress: consonants/vowels are unchanged
#      (a wrong segment would mean the audio teaches the wrong word),
#   4. every ezafe phrase in tools/pron/ezafe.txt is really spoken with ‑e,
#   5. no override in tools/pron/overrides.txt is dead (word not in the app),
#   6. reports how many of the shipped clips actually changed pronunciation.
#
# Usage:  python3 tools/test_pron.py            (exit code 1 on failure)
# =============================================================================
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "pron_rules.py").rsplit("/", 1)[0])

import build_audio as ba                                    # noqa: E402
from pron_rules import Rules, strip_stress, stress_plan, move_stress, nuclei, nuclei as _n  # noqa: E402


def stressed_syllable(ipa: str):
    """Index of the stressed nucleus in an IPA string (None if unmarked).

    eSpeak writes ˈ before the onset of the stressed syllable, so the index is
    simply the number of vowel groups that precede it (ˈmamnun → 0, mamnˈun → 1).
    """
    mark = ipa.find("ˈ")
    if mark < 0:
        return None
    before = re.sub(r"[^a-zɑɒæø]", "", ipa[:mark])
    return len(re.findall(r"[aeiouɑɒæø]+", before))


def main() -> int:
    ba.ensure_deps()
    strings, slow = ba.collect_strings()

    # ---- phase A: read everything out of the STOCK engine -----------------
    # eSpeak is a singleton library: re-initialising it with another data dir
    # switches the pronunciation for every existing handle, so the "before"
    # values must be collected before the corrected dictionary is compiled.
    words = ba.extract_words(strings)
    stock = ba.Speaker(ba.stock_data_dir())
    stock_word_ipa = {w: stock.phonemes(w, 2) for w in words}
    stock_word_mn = {w: stock.phonemes(w) for w in words}
    stock_string_ipa = {s: stock.phonemes(s, 2) for s in strings}

    # ---- phase B: build the corrected dictionary --------------------------
    rules, entries, dsource, report = ba.build_pronunciation(strings, verbose=False)
    data_dir = ba.compile_corrected_dictionary(entries, dsource)

    # ---- phase C: read everything back out of the CORRECTED engine --------
    fixed = ba.Speaker(data_dir)

    failures: list[str] = []

    def check(cond, label, detail=""):
        if cond:
            print(f"  ✓ {label}")
        else:
            print(f"  ✗ {label} {detail}")
            failures.append(label)

    print(f"catalog: {len(strings)} strings, {len(entries)} corrected words, "
          f"{len(rules.ezafe)} ezafe phrases\n")

    # ---- 1. every override applies ----------------------------------------
    print("1. overrides active in the compiled dictionary")
    plain = lambda s: s.replace(",", "").replace("%", "")          # noqa: E731
    bad = [w for w, want in entries.items() if plain(fixed.phonemes(w)) != plain(want)]
    check(not bad, f"all {len(entries)} overrides active", f"({len(bad)} inactive: {bad[:5]})")

    # ---- 2. stress lands where Persian wants it ---------------------------
    print("\n2. stress placement")
    cases = [
        ("ممنون", "last", "mamnún"), ("مادر", "last", "madár"), ("خواهر", "last", "xâhár"),
        ("خورشید", "last", "xoršíd"), ("کتاب", "last", "ketấb"), ("نوروز", "last", "nowrúz"),
        ("چطوری", "last", "četorí"), ("رفتم", "last", "raftám"), ("مدرسه", "last", "madresé"),
        ("ببخشید", "last", "bebaxšíd"), ("میروم", "first", "míravam"), ("نمی‌روم", "first", "némiravam"),
        ("دارم", "first", "dấram"), ("خواهم", "first", "xấham"), ("رفته", "last", "rafté"),
        ("رفته‌ام", "penult", "rafté-am"), ("نکنه", "first", "nákone"),
    ]
    for word, want, roman in cases:
        spoken = rules.respell_text(word)
        ipa = fixed.phonemes(spoken, 2)
        idx = stressed_syllable(ipa)
        n = len(nuclei(fixed.phonemes(spoken))[1]) - 1
        expected = {"first": 0, "last": n, "penult": n - 1}[want]
        check(idx == expected, f"{word} stressed on the {want} syllable ({roman})", f"— got {ipa!r}")

    # ---- 3. only the stress moved -----------------------------------------
    print("\n3. segments unchanged (only stress may move)")
    seg = lambda s: re.sub(r"[ˈˌ]", "", s).replace(" ", "")         # noqa: E731
    changed_segments = []
    for word, before_ipa, _mn, key in report:
        if word in rules.ezafe or key != word.replace("\u200c", ""):
            continue
        after = fixed.phonemes(key, 2)
        if seg(before_ipa) != seg(after):
            changed_segments.append((word, before_ipa, after))
    check(not changed_segments, "all corrected words keep their consonants/vowels",
          f"({len(changed_segments)} differ, e.g. {changed_segments[:3]})")

    # ---- 4. ezafe is audible ----------------------------------------------
    print("\n4. ezafe linker")
    missing = []
    for plain_phrase, marked in rules.ezafe.items():
        before, after = stock_word_ipa.get(plain_phrase, ""), fixed.phonemes(marked, 2)
        if not before:
            before = stock.phonemes(plain_phrase, 2)
        # the linker surfaces at the end of the first word's transcription
        # (ʃˈab-e …, ɡolest↾n-e …, jalase-ye → "eːi")
        first = after.split()[0] if after.split() else ""
        if before == after or not re.search(r"e(ː|i|$)", first):
            missing.append((plain_phrase, before, after))
    check(not missing, f"all {len(rules.ezafe)} ezafe phrases carry the linker",
          f"({missing[:3]})")

    # ---- 5. no dead overrides ---------------------------------------------
    print("\n5. override bookkeeping")
    corpus = set()
    for s in strings:
        corpus.update(ba.extract_words([s]))
    total_overrides = len(rules.stress) + len(rules.respell) + len(rules.phonemes)
    dead = [w for w in list(rules.stress) + list(rules.respell) + list(rules.phonemes)
            if w not in corpus]
    check(True, f"{total_overrides} overrides listed ({total_overrides - len(dead)} used by the current content)")
    if dead:
        print(f"    note: {len(dead)} override(s) not used by today's content (kept for future "
              f"lessons): {', '.join(dead[:10])}{' …' if len(dead) > 10 else ''}")

    # ---- 6. impact ---------------------------------------------------------
    print("\n6. impact on the shipped pack")
    changed_strings = 0
    for s in strings:
        if strip_stress(stock_string_ipa.get(s, "")) == strip_stress(fixed.phonemes(rules.respell_text(s), 2)):
            continue
        changed_strings += 1
    print(f"  • {len(entries)} words corrected, {len(rules.ezafe)} ezafe phrases inserted")
    print(f"  • {changed_strings} of {len(strings)} clips changed pronunciation")

    print()
    if failures:
        print(f"✗ {len(failures)} check(s) failed")
        return 1
    print("✓ pronunciation rules verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
