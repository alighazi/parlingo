#!/usr/bin/env python3
# =============================================================================
# FarsiGo — neural-voice experiment (Persian Piper vs. the shipped eSpeak pack)
# =============================================================================
# Builds a listening comparison from scratch, idempotently:
#
#   A  the clips that ship in audio/ today   (eSpeak-NG, corrected stress)
#   B  the neural Persian Piper voice with its own stock dictionary
#   C  the same neural voice with FarsiGo's pronunciation fixes compiled into
#      its dictionary (stress rules, ezafe linker, ZWNJ join)
#
# and writes four self-contained pages into the demo dir:
#
#   index.html             A/B/C comparison, MP3s served next to the page
#   neural-vs-espeak.html  the same, audio inlined as data URIs
#   quality-ladder.html    lossless / 48 / 128 kbps / slower pace
#   ending-fix.html        the "trimmed" diagnosis: raw end vs fade-out + silence
#
# Everything (deps, model, dictionary) is fetched on demand:
#   * eSpeak-NG + numpy/lameenc via tools/build_audio.py → ~/.cache/parlingo-tts
#   * sherpa-onnx 1.13.4 + onnxruntime 1.27.0 from PyPI → same cache
#   * the Piper voice from codeload.github.com (the repo checks the model into
#     git as an Emscripten pack, which is why it is reachable at all)
#
# Usage:
#   python3 tools/neural/build_demo.py                 # everything
#   python3 tools/neural/build_demo.py --skip-fetch    # reuse a cached model
#   NEURAL_DEMO_DIR=/tmp/demo python3 tools/neural/build_demo.py
#
# Note on the model: eSpeak-NG is a *singleton* — re-initialising it with a
# different data dir changes the pronunciation for handles already open in that
# process. Every render therefore runs in its own subprocess (render_worker.py).
# =============================================================================
from __future__ import annotations

import base64
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import wave
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent                                     # repo root
CACHE = pathlib.Path(os.environ.get("PARLINGO_TTS_CACHE", pathlib.Path.home() / ".cache" / "parlingo-tts"))
NEURAL = CACHE / "neural"
PIPER = NEURAL / "piper_fa"
PYLIBS = NEURAL / "pylibs"
WHEELS = CACHE / "wheels" / "neural"
DEMO = pathlib.Path(os.environ.get("NEURAL_DEMO_DIR", "/home/user/neural-demo"))

# numpy/lameenc (repo cache) and sherpa-onnx/onnxruntime (neural cache)
for _p in (str(CACHE / "pylibs"), str(PYLIBS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PIPER_REPO = "gyroing/Persian-Piper-TTS-WebAssembly"
PIPER_BRANCH = "master"                       # NB: the default branch is master
PIPER_TARBALL = f"https://codeload.github.com/{PIPER_REPO}/tar.gz/{PIPER_BRANCH}"
NEURAL_WHEELS = {"sherpa-onnx": "1.13.4", "onnxruntime": "1.27.0"}

SR = 22050
BITRATE = 48               # kbps for the demo clips (the shipped pack uses 32)
PEAK = 0.9                 # −0.9 dBFS, matches tools/build_audio.py
FADE_MS = 25               # cosine fade-out …
SILENCE_MS = 140           # … plus this much silence: the "trimmed" fix
TRIM_FLOOR = 150

PHRASES = [
    ("کتاب", "ketâb — book"),
    ("ممنون", "mamnún — thanks"),
    ("مادر", "madár — mother"),
    ("خورشید", "xoršid — sun"),
    ("می\u200cروم", "míravam — I go"),
    ("رفتم", "raftám — I went"),
    ("سلام! چطوری؟", "salâm! četorí? — hello! how are you?"),
    ("شب یلدا نزدیکه.", "šab-e yaldâ nazdike — Yalda night is near"),
    ("آب خنک داری؟", "âb-e xonak dâri? — do you have cold water?"),
    ("هوای تهران امروز آلوده‌ست.", "havâ-ye tehrân emruz âlude-st — Tehran's air is polluted today"),
]


# --------------------------------------------------------------- provisioning --
def _refresh_import_paths() -> None:
    """Forget cached "this path does not exist" import results.

    On a cold cache the pylibs directory does not exist while Python first scans
    sys.path, so it stores None in sys.path_importer_cache for that entry; the
    files unpacked into it later stay invisible until the entry is dropped.
    """
    import importlib
    for p in (str(CACHE / "pylibs"), str(PYLIBS)):
        if p not in sys.path:
            sys.path.insert(0, p)
        sys.path_importer_cache.pop(p, None)
    importlib.invalidate_caches()


def provision(skip_fetch: bool = False) -> None:
    """eSpeak-NG + numpy/lameenc via the repo builder, then the neural runtime."""
    sys.path.insert(0, str(ROOT / "tools"))
    import build_audio as ba
    print("1. provisioning eSpeak-NG, numpy, lameenc")
    ba.ensure_deps()
    # ensure_deps() only *downloads* numpy/lameenc — unpack them so they import
    for whl in (CACHE / "pylibs").glob("*.whl"):
        with zipfile.ZipFile(whl) as z:
            z.extractall(CACHE / "pylibs")
        print(f"   unpacked {whl.name}")

    if not skip_fetch:
        print("2. provisioning the neural runtime (sherpa-onnx + onnxruntime)")
        PYLIBS.mkdir(parents=True, exist_ok=True)
        WHEELS.mkdir(parents=True, exist_ok=True)
        have = {p.name.split("-")[0] for p in PYLIBS.glob("*.dist-info")}
        if not all(k in have for k in NEURAL_WHEELS):
            subprocess.run([sys.executable, "-m", "pip", "download",
                            *[f"{k}=={v}" for k, v in NEURAL_WHEELS.items()],
                            "-d", str(WHEELS), "--no-deps", "-q"], check=True)
            for whl in WHEELS.glob("*.whl"):
                with zipfile.ZipFile(whl) as z:
                    z.extractall(PYLIBS)
        # sherpa-onnx dlopen()s "libonnxruntime.so" with no version suffix
        capi = PYLIBS / "onnxruntime" / "capi"
        so = sorted(capi.glob("libonnxruntime.so.1.*"))
        if so and not (capi / "libonnxruntime.so").exists():
            (capi / "libonnxruntime.so").symlink_to(so[0].name)
        print("   neural runtime ready")
    _refresh_import_paths()


def _loadpackage_meta(loader: str) -> dict:
    """Parse `loadPackage({...})` out of the Emscripten loader (brace-matched)."""
    start = loader.index("{", loader.index("loadPackage("))
    depth, end = 0, start
    while True:
        if loader[end] == "{":
            depth += 1
        elif loader[end] == "}":
            depth -= 1
            if depth == 0:
                break
        end += 1
    return json.loads(loader[start:end + 1])


def fetch_model() -> None:
    PIPER.mkdir(parents=True, exist_ok=True)
    tar_path = PIPER / "repo.tar.gz"
    if (PIPER / "model.onnx").exists() and (PIPER / "tokens.txt").exists() \
            and (PIPER / "espeak-ng-data" / "fa_dict").exists():
        print("3. Piper voice already cached")
        return
    if not tar_path.exists() or tar_path.stat().st_size < 1_000_000:
        print(f"3. fetching the Piper voice ({PIPER_TARBALL})")
        urllib.request.urlretrieve(PIPER_TARBALL, tar_path)
    print(f"   tarball: {tar_path.stat().st_size / 1048576:.1f} MB")
    with tarfile.open(tar_path) as tf:
        root = tf.getnames()[0].split("/")[0]
        loader = tf.extractfile(f"{root}/sherpa-onnx-wasm-main.js").read().decode("utf-8", "replace")
        meta = _loadpackage_meta(loader)
        data = tf.extractfile(f"{root}/sherpa-onnx-wasm-main.data").read()
    for f in meta["files"]:
        if "start" not in f:
            continue
        name = f["filename"].lstrip("/")
        if name in ("model.onnx", "tokens.txt") or name.startswith("espeak-ng-data/"):
            out = PIPER / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data[f["start"]:f["end"]])
    print(f"   model.onnx {(PIPER/'model.onnx').stat().st_size/1048576:.1f} MB, "
          f"tokens.txt {(PIPER/'tokens.txt').stat().st_size} B, "
          f"espeak-ng-data {sum(1 for _ in (PIPER/'espeak-ng-data').rglob('*') if _.is_file())} files")


# ------------------------------------------------------------------ accuracy --
def corrected_data_dir(rules, entries, dsource) -> pathlib.Path:
    """Compile the corrected fa_dict into a copy of the MODEL's espeak data."""
    sys.path.insert(0, str(ROOT / "tools"))
    import build_audio as ba
    from pron_rules import merge_word_list

    dest = PIPER / "espeak-ng-data-corrected"
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(PIPER / "espeak-ng-data", dest)
    out = PIPER / "dictsource-corrected"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    for name in ("fa_rules", "fa_emoji"):
        shutil.copy(dsource / name, out / name)
    merged, replaced = merge_word_list(entries, dsource)
    (out / "fa_list").write_text(merged, encoding="utf-8")
    print(f"4. dictionary: {len(entries)} entries, {replaced} stock lines replaced")

    speaker = ba.Speaker(dest)
    if speaker.compile_dictionary(out) != 0:
        raise SystemExit("espeak_ng_CompileDictionary failed")
    plain = lambda s: s.replace(",", "").replace("%", "").strip()          # noqa: E731
    bad = [w for w, want in entries.items() if plain(speaker.phonemes(w)) != plain(want)]
    if bad:
        raise SystemExit(f"refusing to build: {len(bad)} overrides did not apply, e.g. {bad[:5]}")
    print(f"   verified: all {len(entries)} overrides are active in the model's dictionary")
    return dest


# -------------------------------------------------------------------- render --
def neural_env() -> dict:
    e = dict(os.environ)
    e["LD_LIBRARY_PATH"] = str(PYLIBS / "onnxruntime" / "capi")
    e["PYTHONPATH"] = f"{PYLIBS}:{CACHE/'pylibs'}"
    return e


def render(texts: list[str], data_dir: pathlib.Path, tag: str, length_scale: float = 1.0) -> pathlib.Path:
    tmp = pathlib.Path("/tmp") / f"texts-{tag}.json"
    tmp.write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")
    out = pathlib.Path("/tmp") / f"render-{tag}"
    shutil.rmtree(out, ignore_errors=True)
    subprocess.run([sys.executable, str(HERE / "render_worker.py"),
                    "--model-dir", str(PIPER), "--data-dir", str(data_dir),
                    "--out", str(out), "--texts", str(tmp), "--length-scale", str(length_scale)],
                   check=True, env=neural_env(), stdout=subprocess.DEVNULL)
    print(f"   rendered {len(texts)} clips → {out.name} (length_scale={length_scale})")
    return out


def load_wav(path: pathlib.Path):
    import numpy as np
    w = wave.open(str(path), "rb")
    a = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32)
    w.close()
    return a


def normalise(a, *, peak: float = PEAK, fade_ms: float = 0.0, end_silence_ms: float = 0.0):
    """Trim, peak-normalise, then give the clip a proper ending.

    The Piper model often stops *at* full speech energy — no decay, no trailing
    silence — which is heard as the audio being trimmed. A cosine fade-out plus
    a moment of silence makes a clip finish like a finished utterance.
    """
    import numpy as np
    loud = np.nonzero(np.abs(a) > TRIM_FLOOR)[0]
    if loud.size:
        a = a[max(0, loud[0] - int(SR * 0.03)):min(a.size, loud[-1] + int(SR * 0.06))]
    a = a * (peak * 32767 / (float(np.abs(a).max()) or 1.0))
    if fade_ms:
        n = int(SR * fade_ms / 1000)
        a = a.copy()
        a[-n:] *= np.cos(np.linspace(0, np.pi / 2, n)) ** 2
    if end_silence_ms:
        a = np.concatenate([a, np.zeros(int(SR * end_silence_ms / 1000), dtype=np.float32)])
    return a.astype("<i2")


def encode_mp3(a, dest: pathlib.Path, kbps: int = BITRATE) -> None:
    import lameenc
    enc = lameenc.Encoder()
    enc.set_bit_rate(kbps)
    enc.set_in_sample_rate(SR)
    enc.set_channels(1)
    enc.set_quality(0 if kbps >= 128 else 2)
    dest.write_bytes(bytes(enc.encode(a.astype("<i2").tobytes()) + enc.flush()))


def write_wav(a, dest: pathlib.Path) -> None:
    w = wave.open(str(dest), "wb")
    w.setparams((1, 2, SR, len(a), "NONE", ""))
    w.writeframes(a.astype("<i2").tobytes())
    w.close()


def end_level(a) -> float:
    """RMS of the final 40 ms: ≈0 means the clip ends in silence."""
    import numpy as np
    x = a.astype(np.float32) / 32768
    return float(np.sqrt((x[-int(0.04 * SR):] ** 2).mean()))


def data_uri(p: pathlib.Path) -> str:
    return ("data:audio/wav;base64," if p.suffix == ".wav" else "data:audio/mpeg;base64,") \
        + base64.b64encode(p.read_bytes()).decode()


# --------------------------------------------------------------------- pages --
STYLE = """ :root {{ color-scheme: dark }}
 * {{ box-sizing: border-box }}
 body {{ font: 15px/1.55 system-ui,-apple-system,sans-serif; background:#0f1116; color:#e9ebf2; margin:0; padding:22px 16px 60px }}
 main {{ max-width:720px; margin:0 auto }}
 h1 {{ font-size:21px; margin:0 0 6px }}
 p.sub {{ color:#98a0b3; margin:0 0 20px; font-size:13.5px }}
 .row {{ background:#161922; border:1px solid #232838; border-radius:12px; padding:14px; margin-bottom:12px }}
 .head {{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:10px }}
 .fa {{ font-size:23px; direction:rtl }}
 .tr {{ color:#7f8798; font-size:12.5px }}
 .track {{ display:grid; grid-template-columns:20px 1fr; gap:2px 8px; margin-bottom:7px; align-items:center }}
 .tk {{ display:grid; gap:3px; margin-bottom:9px }}
 .tag {{ grid-row:1/3; width:20px; height:20px; border-radius:50%; display:grid; place-items:center; font-size:11px; font-weight:700; color:#0f1116 }}
 .tag.a {{ background:#8f9bb3 }} .tag.b {{ background:#6ea8fe }} .tag.c {{ background:#7ee0a5 }}
 .lab {{ font-size:12px; color:#c3cad8 }} .m {{ color:#6f7788 }}
 audio {{ width:100%; height:32px; grid-column:2 }}
 .foot {{ border-top:1px solid #232838; margin-top:20px; padding-top:14px; font-size:12.5px; color:#8b93a6 }}
 code {{ background:#1a1f2b; padding:1px 5px; border-radius:4px; font-size:12px }}"""


def abc_page(uri) -> str:
    rows = []
    for i, (phrase, gloss) in enumerate(PHRASES):
        tracks = []
        for tag, cls, label in (("A", "a", "shipped pack · eSpeak-NG, corrected stress"),
                                ("B", "b", "neural Piper · its own dictionary"),
                                ("C", "c", "neural Piper + FarsiGo's stress fixes")):
            tracks.append(f"""<div class="track"><span class="tag {cls}">{tag}</span>
       <span class="lab">{label}</span><audio controls preload="none" src="{uri(f'{tag}{i:02d}.mp3')}"></audio></div>""")
        rows.append(f"""<div class="row"><div class="head"><span class="fa" dir="rtl" lang="fa">{phrase}</span>
      <span class="tr">{gloss}</span></div>{''.join(tracks)}</div>""")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FarsiGo — neural voice vs. the shipped eSpeak pack</title>
<style>{STYLE}</style></head><body><main>
<h1>Neural voice vs. the shipped pack</h1>
<p class="sub">Same Persian text, three renderings — headphones recommended. Pick the voice you want in the app.</p>
{''.join(rows)}
<div class="foot">
<p><b>A</b> — what ships today: eSpeak-NG Persian formant synthesis with this repo's corrected stress dictionary (2 828 clips, 20 MB, fully offline).</p>
<p><b>B</b> — the neural Persian Piper voice (VITS, 60 MB, 22 050 Hz) driven by its own stock eSpeak dictionary.</p>
<p><b>C</b> — the same neural model with FarsiGo's pronunciation fixes compiled into its dictionary: the stress rules, the ezafe linker (شبِ یلدا، آبِ خنک) and the ZWNJ join, applied before synthesis.</p>
<p>Neural clips now end with a 25 ms fade-out and 140 ms of silence, because the model's raw output often stops at full voice.</p>
<p>Model: <code>gyroing/Persian-Piper-TTS-WebAssembly</code> (voice card <code>gyroing/Persian-Piper-Model-gyro</code>); inference with sherpa-onnx 1.13.4 on CPU, ≈0.1 s per clip.</p>
</div></main></body></html>"""


def ladder_page(uri) -> str:
    variants = lambda i: [("1 · lossless WAV (no codec at all)", f"ladder/{i:02d}-lad_100.wav"),
                          ("2 · MP3 48 kbps (what the first demo used)", f"ladder/{i:02d}-lad_100.mp3"),
                          ("3 · MP3 128 kbps", f"ladder/{i:02d}-lad_100-128.mp3"),
                          ("4 · MP3 128 kbps, slower pace", f"ladder/{i:02d}-lad_125-128.mp3"),
                          ("5 · lossless WAV, slower pace", f"ladder/{i:02d}-lad_125.wav")]
    rows = []
    for i, phrase in enumerate(p for p, _ in PHRASES[:3]):
        tracks = "".join(f"""<div class="tk"><span class="lab">{label}</span>
       <audio controls preload="none" src="{uri(rel)}"></audio></div>""" for label, rel in variants(i))
        rows.append(f"""<div class="row"><div class="fa" dir="rtl" lang="fa">{phrase}</div>{tracks}</div>""")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FarsiGo — neural audio quality ladder</title>
<style>{STYLE}</style></head><body><main>
<h1>Where does the &ldquo;clipped&rdquo; sound come from?</h1>
<p class="sub">The same three phrases, five ways. Play them top to bottom in each box — the first is the model's output with no codec at all.</p>
{''.join(rows)}
<div class="foot"><p>The 48 kbps clips measure clean — sample peaks 0.85–0.92, <i>zero</i> full-scale samples, true peak ≤ −0.7 dBFS — so nothing is mathematically clipped. That leaves the encoder, which is the same bitrate the eSpeak pack uses but has far more spectrum to carry.</p>
<p>Lossless isn't an option for 2 828 clips: 128 kbps mono ≈ 60 MB, 96 kbps ≈ 45 MB, 64 kbps ≈ 34 MB, against 20 MB today.</p></div>
</main></body></html>"""


def ending_page(mp3: dict) -> str:
    labels = {
        1: "as it was heard — ends at full voice (the “trimmed” one)",
        2: "proper ending (25 ms fade + 140 ms silence)",
        3: "proper ending, 1.25× slower",
        4: "proper ending, 1.35× slower (learner pace)",
        5: "C + proper ending, 1.25× slower (FarsiGo stress/ezafe fixes)",
    }
    rows = []
    for i, (phrase, gloss) in enumerate(PHRASES):
        tracks = []
        for v in (1, 2, 3, 4, 5):
            path, dur, end = mp3[(i, v)]
            tracks.append(f"""<div class="tk"><span class="lab">{labels[v]}<span class="m"> · {dur:.2f}s · ends at {end:.4f}</span></span>
       <audio controls preload="none" src="{data_uri(path)}"></audio></div>""")
        rows.append(f"""<div class="row"><div class="head"><span class="fa" dir="rtl" lang="fa">{phrase}</span>
      <span class="tr">{gloss}</span></div>{''.join(tracks)}</div>""")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FarsiGo — giving the neural voice a proper ending</title>
<style>{STYLE}</style></head><body><main>
<h1>Giving the neural voice a proper ending</h1>
<p class="sub">Row 1 is the clip as first heard. Rows 2–4 keep the same voice and add a fade-out plus a moment of silence, at three paces; row 5 also applies this repo's pronunciation fixes. After each label: clip length, then the loudness of its final 40 ms — speech runs around 0.02–0.05, a proper ending is 0.0000.</p>
{''.join(rows)}
<div class="foot"><p>Nothing was clip-cut in the pipeline: the raw model output is 0.43 s for کتاب against 0.50 s in the shipped clip, i.e. it is padded, not trimmed. The model itself simply stops mid-voice — for رفتم and هوای تهران… speech energy runs into the very last sample, while the eSpeak pack always decays into silence. Rows 2–5 fix that.</p>
<p>Tell me the row number you want (and the pace) and every clip in the pack can be rendered that way.</p></div>
</main></body></html>"""


# ---------------------------------------------------------------------- main --
def main() -> None:
    skip_fetch = "--skip-fetch" in sys.argv
    DEMO.mkdir(parents=True, exist_ok=True)
    provision(skip_fetch)
    fetch_model()

    sys.path.insert(0, str(ROOT / "tools"))
    import build_audio as ba
    print("   collecting the app's Persian strings …")
    strings, _ = ba.collect_strings()
    rules, entries, dsource, _ = ba.build_pronunciation(strings, verbose=False)
    corr_dir = corrected_data_dir(rules, entries, dsource)

    print("5. rendering (one process per dictionary — eSpeak is a singleton)")
    plain = [p for p, _ in PHRASES]
    respelled = [rules.respell_text(p) for p in plain]
    stock = PIPER / "espeak-ng-data"
    r_stock_100 = render(plain, stock, "stock100", 1.0)
    r_stock_125 = render(plain, stock, "stock125", 1.25)
    r_stock_135 = render(plain, stock, "stock135", 1.35)
    r_corr_100 = render(respelled, corr_dir, "corr100", 1.0)
    r_corr_125 = render(respelled, corr_dir, "corr125", 1.25)

    print("6. encoding")
    shots = dict()
    for i, (phrase, _) in enumerate(PHRASES):
        shots[(i, 1)] = normalise(load_wav(r_stock_100 / f"{i:02d}.wav"), fade_ms=0, end_silence_ms=0)
        shots[(i, 2)] = normalise(load_wav(r_stock_100 / f"{i:02d}.wav"), fade_ms=FADE_MS, end_silence_ms=SILENCE_MS)
        shots[(i, 3)] = normalise(load_wav(r_stock_125 / f"{i:02d}.wav"), fade_ms=FADE_MS, end_silence_ms=SILENCE_MS)
        shots[(i, 4)] = normalise(load_wav(r_stock_135 / f"{i:02d}.wav"), fade_ms=FADE_MS, end_silence_ms=SILENCE_MS)
        shots[(i, 5)] = normalise(load_wav(r_corr_125 / f"{i:02d}.wav"), fade_ms=FADE_MS, end_silence_ms=SILENCE_MS)

    mp3_info = {}
    for key, samples in shots.items():
        dest = DEMO / f"F{key[0]:02d}v{key[1]}.mp3"
        encode_mp3(samples, dest)
        mp3_info[key] = (dest, len(samples) / SR, end_level(samples))

    # A — copies of the shipped clips; B/C — neural, with the proper ending
    manifest = json.loads(subprocess.run(
        ["node", "-e", "const fs=require('fs');"
                      "eval(fs.readFileSync('audio/index.js','utf8').replace(/const FA_AUDIO/g,'global.FA_AUDIO'));"
                      "console.log(JSON.stringify(global.FA_AUDIO));"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    for i, (phrase, _) in enumerate(PHRASES):
        rel = manifest.get(" ".join(phrase.split()))
        if not rel:
            raise SystemExit(f"no shipped clip for {phrase!r}")
        shutil.copyfile(ROOT / rel, DEMO / f"A{i:02d}.mp3")
    for tag, src_dir, texts in (("B", r_stock_100, plain), ("C", r_corr_100, respelled)):
        for i in range(len(PHRASES)):
            encode_mp3(normalise(load_wav(src_dir / f"{i:02d}.wav"), fade_ms=FADE_MS, end_silence_ms=SILENCE_MS),
                       DEMO / f"{tag}{i:02d}.mp3")

    (DEMO / "ladder").mkdir(exist_ok=True)
    for i in range(len(PHRASES[:3])):
        for tag, src_dir in (("lad_100", r_stock_100), ("lad_125", r_stock_125)):
            a = normalise(load_wav(src_dir / f"{i:02d}.wav"), peak=0.708, fade_ms=5, end_silence_ms=120)
            write_wav(a, DEMO / f"ladder/{i:02d}-{tag}.wav")
            encode_mp3(a, DEMO / f"ladder/{i:02d}-{tag}.mp3", 48)
            encode_mp3(a, DEMO / f"ladder/{i:02d}-{tag}-128.mp3", 128)

    print("7. writing pages")
    (DEMO / "index.html").write_text(abc_page(lambda rel: rel), encoding="utf-8")
    (DEMO / "neural-vs-espeak.html").write_text(abc_page(lambda rel: data_uri(DEMO / rel)), encoding="utf-8")
    (DEMO / "quality-ladder.html").write_text(ladder_page(lambda rel: data_uri(DEMO / rel)), encoding="utf-8")
    (DEMO / "ending-fix.html").write_text(ending_page(mp3_info), encoding="utf-8")

    print("\nbuilt →", DEMO)
    for p in ("index.html", "neural-vs-espeak.html", "quality-ladder.html", "ending-fix.html"):
        print(f"  {p:24s} {(DEMO/p).stat().st_size/1024:6.0f} KB")
    print("  endings:", " ".join(f"v{v}={'silence' if max(i[2] for k,i in mp3_info.items() if k[1]==v) < 0.001 else 'VOICE'}"
                                 for v in (1, 2, 3, 4, 5)))
    print(f"  clips: {len(list(DEMO.glob('*.mp3')))} mp3 beside the pages, "
          f"{len(list((DEMO/'ladder').iterdir()))} in ladder/")
    print("\nserve with:  python3 -m http.server 8010 --bind 0.0.0.0   (cwd = demo dir)")


if __name__ == "__main__":
    main()
