#!/usr/bin/env python3
# =============================================================================
# FarsiGo — Persian pronunciation rules for the audio pack
# =============================================================================
# eSpeak-NG's Persian voice gets the *segments* (consonants/vowels) mostly
# right, but it stresses almost every word on the FIRST syllable, because most
# entries of its Persian dictionary carry no stress mark:
#
#     ممنون  ->  mˈamnun   (should be mamnún)
#     مادر   ->  mˈɑdar    (should be madár)
#     میروم  ->  mirˈavam  (should be míravam)
#
# This module re-writes those pronunciations. It is deliberately conservative:
# it only ever MOVES THE STRESS MARK inside the phoneme string eSpeak itself
# produced (and inserts the ezafe linker where Persian requires it), never
# touching the segments. The corrected word list is compiled back into a
# Persian dictionary with espeak_ng_CompileDictionary(), so the fix applies to
# every clip — words inside sentences included.
#
# Rules (Iranian/standard Persian):
#   • content words            → stress the LAST syllable      (mamnún, madár)
#   • می… / نمی… verb forms    → stress the prefix             (míravam)
#   • رفته‌+ام/ای/است/…       → stress the participle (-á-), not the ending
#   • auxiliaries (دارم، خواهم، بودم, …) → keep the first-syllable stress
#   • function words            → left untouched
#   • ezafe linker (*ezafe.txt*) → "noun + adjective/name" gets ‑e
# Everything can be overridden per word in tools/pron/overrides.txt.
#
# CLI (handy for checking a single word):
#   python3 tools/pron_rules.py ممنون مادر میروم "شب یلدا"
# =============================================================================
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
PRON_DIR = HERE / "pron"
OVERRIDES = PRON_DIR / "overrides.txt"
EZAFE = PRON_DIR / "ezafe.txt"
CACHE = pathlib.Path(os.environ.get("PARLINGO_TTS_CACHE", pathlib.Path.home() / ".cache" / "parlingo-tts"))
DICTSOURCE = CACHE / "dictsource"
ESPEAK_REPO = "espeak-ng/espeak-ng"
DICTSOURCE_FILES = ("fa_rules", "fa_list", "fa_emoji")

ZWNJ = "\u200c"          # نیمفاصله
KASRA = "\u0650"         # ezafe linker as written in the dictionary/word list
STRESS, SECONDARY = "'", ","

# ---------------------------------------------------------------- phonology --
# eSpeak Persian mnemonics: these are the vowel symbols it uses for fa…
VOWELS = set("aAeiouE O@3".replace(" ", ""))
# …and the multi-character consonants that must be treated as one symbol.
MULTI_CONSONANTS = ("q1", "dZ", "tS", "dZ", "ts", "dz")
VALVE = ("_", "-")       # separators inside mnemonics

# Words whose stress stays on the first syllable (auxiliaries / clitics).
FIRST_STRESS = {
    # present continuous auxiliary "dâram miravam"
    "دارم", "داری", "دارد", "داریم", "دارید", "دارند",
    # future auxiliary "xâham raft"
    "خواهم", "خواهی", "خواهد", "خواهیم", "خواهید", "خواهند",
    # perfect auxiliary "rafté budam"
    "بودم", "بودی", "بود", "بودیم", "بودید", "بودند",
    # copula / "hast"
    "هستم", "هستی", "هست", "هستیم", "هستید", "هستند",
    "نیستم", "نیستی", "نیست", "نیستیم", "نیستید", "نیستند",
    "است",
    # possessives / light nouns that would sound wrong stressed finally
    "برای",
}

# Verb-person clitics of the perfect: رفته‌ام = rafte + am → stress -á-, not -ám.
PERFECT_CLITICS = {"ام", "ای", "است", "ایم", "اید", "اند"}

# mi-/nemi- prefix pattern on verb forms (written with or without the ZWNJ)
MI_PREFIX = re.compile(r"^(نمی|می)[" + ZWNJ + r"]?")  # نمی/می
BE_PREFIX = re.compile(r"^(ب" + ZWNJ + r"?)(?=[آ-ی]{2,})")  # بِ… subjunctive (only via overrides)

# Function words are short and unstressed: leave eSpeak's own marking alone.
FUNCTION_WORDS = {
    "و", "را", "به", "از", "در", "با", "که", "تا", "هم", "این", "آن", "او", "ما", "من", "تو",
    "شما", "اگر", "ولی", "یا", "بر", "هر", "بی", "چه", "کی", "چی", "یه", "این‌جا", "آنجا",
}


# ------------------------------------------------------------------ helpers --
def strip_stress(mn: str) -> str:
    return mn.replace(STRESS, "").replace(SECONDARY, "")


def _symbols(mn: str):
    """Split a mnemonic string into symbols ('q1' stays one symbol)."""
    out, i = [], 0
    while i < len(mn):
        for multi in MULTI_CONSONANTS:
            if mn.startswith(multi, i):
                out.append(multi)
                i += len(multi)
                break
        else:
            out.append(mn[i])
            i += 1
    return out


def nuclei(mn: str):
    """Start indices (in symbols) of each vowel nucleus."""
    syms = _symbols(mn)
    idx, out = [], []
    for k, s in enumerate(syms):
        if s in VOWELS:
            if not (out and idx[-1] == k - 1):
                idx.append(k)
                out.append(k)
            else:
                idx.append(k)
    # consecutive vowels belong to one nucleus: keep only the first of a run
    groups, prev = [], None
    for k in out:
        if prev is None or k != prev + 1:
            groups.append(k)
        prev = k
    return syms, groups


def move_stress(mn: str, target) -> str:
    """Return `mn` with the primary stress moved to the requested syllable.

    target: 'first' | 'last' | 'penult' | int (0-based nucleus index) | None
    """
    if target is None:
        return mn                                  # keep eSpeak's own marking
    original = mn
    # drop eSpeak's own marks first: leaving a secondary stress "," in front of
    # the new primary one produces an entry the compiler rejects
    mn = mn.replace(STRESS, "").replace(SECONDARY, "")
    syms, groups = nuclei(mn)
    if len(groups) < 2:
        # monosyllables (آب، یک، رفت) are already stressed where they should be
        return original
    if target in ("first", "prefix"):
        i = 0
    elif target == "last":
        i = len(groups) - 1
    elif target == "penult":
        i = len(groups) - 2
    else:
        i = max(0, min(int(target), len(groups) - 1))
    syms.insert(groups[i], STRESS)
    return "".join(syms)


def stress_plan(word: str, kind: str = "", verbose: bool = False):
    """Which syllable should carry the stress for this word?  (None = leave)"""
    w = word.strip()
    if not w or not re.search(r"[\u0600-\u06FF]", w):
        return None
    if w in FUNCTION_WORDS:
        return None
    if w in FIRST_STRESS:
        return "first"
    if ZWNJ in w:
        head, _, tail = w.partition(ZWNJ)
        if tail in PERFECT_CLITICS and head:          # رفته‌ام / خورده‌اند
            return "penult"
    if MI_PREFIX.match(w):                            # میروم / نمیگویم
        return "prefix"   # the mi-/nemi- prefix itself carries the stress
    return "last"


# --------------------------------------------------------------- overrides ---
class Rules:
    """Loaded once per build: overrides + ezafe + optional per-word phonemes."""

    def __init__(self, overrides_path=OVERRIDES, ezafe_path=EZAFE):
        self.stress: dict[str, object] = {}       # word -> 'first'|'last'|'penult'|int|None
        self.respell: dict[str, str] = {}         # word -> text eSpeak reads instead
        self.phonemes: dict[str, str] = {}        # word -> full mnemonic
        self.ezafe: dict[str, str] = {}           # phrase -> phrase with ِ inserted
        self._read(overrides_path, self._parse_override)
        self._read(ezafe_path, self._parse_ezafe)
        self.version = hashlib.sha1(json.dumps(
            [sorted(map(str, self.stress.items())), sorted(self.respell.items()),
             sorted(self.phonemes.items()), sorted(self.ezafe.items())],
            ensure_ascii=False).encode()).hexdigest()[:12]

    @staticmethod
    def _read(path: pathlib.Path, handler) -> None:
        if not path.exists():
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            parts = line.split(None, 1) if "\t" not in line else line.split("\t")
            if len(parts) < 2:
                continue
            handler(parts[0].strip(), parts[1].strip())

    def _parse_override(self, word: str, value: str) -> None:
        """overrides.txt:  word <TAB> directive
        !first | !last | !penult | !none   move/keep the stress
        @<text>                            read this spelling instead of the word
        mn:<phonemes>                      use these phonemes verbatim
        """
        if value.startswith("!"):
            what = value[1:].strip()
            self.stress[word] = None if what in ("none", "keep", "") else what
        elif value.startswith("@"):
            self.respell[word] = value[1:]
        elif value.startswith("mn:"):
            self.phonemes[word] = value[3:].strip()
        else:
            self.stress[word] = value

    def _parse_ezafe(self, plain: str, marked: str) -> None:
        self.ezafe[plain] = marked

    # -- text level ---------------------------------------------------------
    def respell_text(self, text: str) -> str:
        """Apply respellings and ezafe to a full string before synthesis."""
        for word, fixed in self.respell.items():
            if word in text:
                text = re.sub(r"(?<![\u0600-\u06FF])" + re.escape(word) + r"(?![\u0600-\u06FF\u200c])", fixed, text)
        for plain, marked in self.ezafe.items():          # longest phrase first
            if plain in text:
                text = text.replace(plain, marked)
        return text


# ------------------------------------------------- dictsource + compilation --
def fetch_dictsource(verbose: bool = True) -> pathlib.Path:
    """Download eSpeak-NG's Persian dictionary sources (GPL — kept in the
    cache, not in the repository; the compiled clips are the shipped artefact)."""
    DICTSOURCE.mkdir(parents=True, exist_ok=True)
    for name in DICTSOURCE_FILES:
        dest = DICTSOURCE / name
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        url = f"https://api.github.com/repos/{ESPEAK_REPO}/contents/dictsource/{name}"
        if verbose:
            print(f"  fetching espeak-ng dictsource {name} …")
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github.raw",
            "User-Agent": "parlingo-build-audio",
            "Authorization": f"Bearer {os.environ.get('GH_TOKEN', os.environ.get('GITHUB_TOKEN', ''))}",
        })
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        if len(data) < 1000:
            raise RuntimeError(f"dictsource {name} looks truncated ({len(data)} bytes)")
        dest.write_bytes(data)
    return DICTSOURCE


def dictsource_fingerprint() -> str:
    h = hashlib.sha1()
    for name in DICTSOURCE_FILES:
        f = DICTSOURCE / name
        if f.exists():
            h.update(f.read_bytes())
    return h.hexdigest()[:12]


def merge_word_list(word_entries: dict[str, str], source_dir: pathlib.Path) -> str:
    """Append `word<TAB>phonemes` overrides to eSpeak's fa_list, dropping the
    stock lines for those words so the override wins."""
    base = (source_dir / "fa_list").read_text(encoding="utf-8", errors="replace")
    keys = set(word_entries)
    kept, replaced = [], 0
    for line in base.splitlines():
        word = line.split("\t", 1)[0].strip()
        if word and word in keys and line.startswith(word):
            replaced += 1
            continue
        kept.append(line)
    out = "\n".join(kept)
    if not out.endswith("\n"):
        out += "\n"
    out += "\n// ---- FarsiGo overrides (generated by tools/pron_rules.py) ----\n"
    for word, phon in sorted(word_entries.items()):
        out += f"{word}\t{phon}\n"
    return out, replaced


# ------------------------------------------------------------------ CLI -----
def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 0
    rules = Rules()
    print(f"rules version {rules.version} · {len(rules.stress)} stress, "
          f"{len(rules.respell)} respell, {len(rules.phonemes)} phoneme, "
          f"{len(rules.ezafe)} ezafe entries")
    try:
        from build_audio import Speaker  # reuse the ctypes wrapper
    except Exception as e:                 # pragma: no cover
        print("cannot import the eSpeak wrapper:", e)
        return 1
    spk = Speaker()
    for text in argv:
        respelled = rules.respell_text(text)
        for word, plan in [(w, stress_plan(w)) for w in re.findall(r"[\u0600-\u06FF\u200c]+", respelled)]:
            mn = spk.phonemes(word)
            target = rules.stress.get(word, plan)
            fixed = rules.phonemes.get(word) or move_stress(mn, target)
            mark = "  " if fixed == mn else "✎ "
            print(f"{mark}{word:14s} {mn:20s} -> {fixed}")
        if respelled != text:
            print(f"   text: {text!r} -> {respelled!r}")
        print(f"   before: {spk.phonemes(text, trace=True)}")
        print(f"   after : {spk.phonemes(respelled, trace=True)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
