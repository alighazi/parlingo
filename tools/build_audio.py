#!/usr/bin/env python3
# =============================================================================
# FarsiGo — build the bundled Persian audio pack
# =============================================================================
# The app ships pre-recorded Persian speech for every word, sentence and verb
# form it can display (no server, no network, no device text-to-speech needed).
# This tool regenerates that pack from the content data files:
#
#   1. tools/collect_strings.mjs walks the whole 320-lesson curriculum inside a
#      DOM stub and prints every Persian string the app can speak.
#   2. eSpeak-NG (Persian voice "fa") synthesises each string.
#   3. The waveform is trimmed, peak-normalised and encoded to MP3 (mono).
#   4. audio/<xx>/<hash>.mp3 files are written and audio/index.js is generated
#      (the text -> file manifest the app loads).
#
# Usage
#   python3 tools/build_audio.py                 # rebuild everything
#   python3 tools/build_audio.py --only-missing  # add just new/changed clips
#   python3 tools/build_audio.py --limit 25      # smoke test on a few strings
#   python3 tools/build_audio.py --rate 135 --slow-rate 95 --bitrate 32
#
# Dependencies are fetched automatically into a cache directory (default
# ~/.cache/parlingo-tts, override with PARLINGO_TTS_CACHE) — nothing is
# installed system-wide and nothing outside audio/ is written.
# =============================================================================
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "audio"
MANIFEST = AUDIO_DIR / "index.js"
CACHE = pathlib.Path(os.environ.get("PARLINGO_TTS_CACHE", pathlib.Path.home() / ".cache" / "parlingo-tts"))

ESPEAK_WHEEL = ("espeakng_loader", "espeakng-loader",
                "espeakng_loader-0.2.4-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl")
NEEDED = ["numpy", "lameenc"]

SAMPLE_RATE = 22050          # eSpeak-NG Persian output rate
ESPEAK_RATE_WPM = 135        # normal speed (eSpeak default is 175)
SLOW_WPM = 95                # 🐢 speed
BITRATE_KBPS = 32            # MP3, mono
SILENCE_FLOOR = 300          # 16-bit amplitude threshold for trimming


# --------------------------------------------------------------------------- #
# dependency provisioning
# --------------------------------------------------------------------------- #
def _pip_download(pkg: str, dest: pathlib.Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.glob(f"{pkg.replace('-', '_')}*")) or any(dest.glob(f"{pkg}*")):
        return
    cmd = [sys.executable, "-m", "pip", "download", pkg, "--no-deps", "-d", str(dest), "-q"]
    print(f"  fetching {pkg} …")
    subprocess.run(cmd, check=True)


def ensure_deps() -> None:
    """Make numpy, lameenc and libespeak-ng available inside the cache."""
    libs = CACHE / "pylibs"
    for pkg in NEEDED:
        if not any(libs.glob(f"{pkg}*")):
            _pip_download(pkg, libs)
    if str(libs) not in sys.path:
        sys.path.insert(0, str(libs))

    espeak = CACHE / "espeak" / "espeakng_loader"
    if not (espeak / "libespeak-ng.so.1").exists():
        whl = CACHE / "wheels" / ESPEAK_WHEEL[2]
        if not whl.exists():
            whl.parent.mkdir(parents=True, exist_ok=True)
            print(f"  fetching {ESPEAK_WHEEL[1]} …")
            subprocess.run([sys.executable, "-m", "pip", "download", ESPEAK_WHEEL[1], "--no-deps",
                            "-d", str(whl.parent), "-q"], check=True)
        print("  unpacking eSpeak-NG …")
        with zipfile.ZipFile(whl) as z:
            z.extractall(CACHE / "espeak")


# --------------------------------------------------------------------------- #
# eSpeak-NG wrapper (ctypes — no python package needed at run time)
# --------------------------------------------------------------------------- #
class Speaker:
    AUDIO_OUTPUT_RETRIEVAL = 1
    espeakRATE = 1

    def __init__(self) -> None:
        base = CACHE / "espeak" / "espeakng_loader"
        self.lib = ctypes.CDLL(str(base / "libespeak-ng.so.1"))
        lib = self.lib
        lib.espeak_Initialize.restype = ctypes.c_int
        lib.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        lib.espeak_ng_SetVoiceByName.restype = ctypes.c_int
        lib.espeak_ng_SetVoiceByName.argtypes = [ctypes.c_char_p]
        lib.espeak_ng_Synthesize.restype = ctypes.c_int
        lib.espeak_ng_Synthesize.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t,
                                             ctypes.c_uint, ctypes.c_int, ctypes.c_uint,
                                             ctypes.c_void_p, ctypes.c_void_p]
        lib.espeak_SetParameter.restype = ctypes.c_int
        lib.espeak_SetParameter.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        lib.espeak_Synchronize.restype = ctypes.c_int
        lib.espeak_SetSynthCallback.argtypes = [self._cbtype]

        self.sample_rate = lib.espeak_Initialize(self.AUDIO_OUTPUT_RETRIEVAL, 4096,
                                                 str(base / "espeak-ng-data").encode(), 0)
        if self.sample_rate <= 0:
            raise RuntimeError("could not initialise eSpeak-NG")
        rc = lib.espeak_ng_SetVoiceByName(b"fa")
        if rc != 0:
            raise RuntimeError(f"eSpeak-NG has no Persian voice (rc={rc})")
        self._chunks: list[bytes] = []
        self._cb = self._cbtype(self._on_audio)
        lib.espeak_SetSynthCallback(self._cb)
        self.set_rate(ESPEAK_RATE_WPM)

    _cbtype = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)

    def _on_audio(self, wav, n, events):  # noqa: ANN001 - ctypes callback
        if n > 0:
            self._chunks.append(ctypes.string_at(wav, n * 2))
        return 0

    def set_rate(self, wpm: int) -> None:
        self.lib.espeak_SetParameter(self.espeakRATE, int(wpm), 0)

    def wav(self, text: str) -> bytes:
        """Synthesise text, return raw 16-bit mono little-endian PCM."""
        self._chunks.clear()
        raw = text.encode("utf-8")
        self.lib.espeak_ng_Synthesize(raw, len(raw), 0, 0, 0, 0, None, None)
        self.lib.espeak_Synchronize()
        return b"".join(self._chunks)


def clip_name(text: str, slow: bool) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    suffix = "-slow" if slow else ""
    return f"{digest[:2]}/{digest[:16]}{suffix}.mp3"


# --------------------------------------------------------------------------- #
# worker
# --------------------------------------------------------------------------- #
_SPEAKER: Speaker | None = None


def _worker_init() -> None:
    global _SPEAKER
    import numpy  # noqa: F401  (imported here so child processes have it)
    _SPEAKER = Speaker()


def _render(job):
    """job = (key, slow, relative_path, only_missing) -> (key, slow, path, written)"""
    import numpy as np
    import lameenc

    key, slow, rel, only_missing = job
    dest = AUDIO_DIR / rel
    if only_missing and dest.exists():
        return key, slow, rel, False

    assert _SPEAKER is not None
    _SPEAKER.set_rate(SLOW_WPM if slow else ESPEAK_RATE_WPM)
    pcm = _SPEAKER.wav(key)
    if not pcm:
        raise RuntimeError(f"no audio produced for {key!r}")

    sr = _SPEAKER.sample_rate
    a = np.frombuffer(pcm, dtype="<i2")
    loud = np.nonzero(np.abs(a) > SILENCE_FLOOR)[0]
    if loud.size:                      # trim leading/trailing silence
        head = max(0, loud[0] - int(sr * 0.035))
        tail = min(a.size, loud[-1] + int(sr * 0.09))
        a = a[head:tail]
    peak = int(np.abs(a).max()) if a.size else 0
    if peak:
        a = (a.astype(np.float32) * (0.9 * 32767 / peak)).astype(np.int16)

    enc = lameenc.Encoder()
    enc.set_bit_rate(BITRATE_KBPS)
    enc.set_in_sample_rate(sr)
    enc.set_channels(1)
    enc.set_quality(2)
    data = enc.encode(a.astype("<i2").tobytes()) + enc.flush()

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(data))
    return key, slow, rel, True


def _silence_clip() -> None:
    """A tiny silent MP3 used to unlock <audio> playback on iOS after a tap."""
    import lameenc
    import numpy as np

    dest = AUDIO_DIR / "silence.mp3"
    if dest.exists():
        return
    a = np.zeros(int(SAMPLE_RATE * 0.04), dtype="<i2")
    enc = lameenc.Encoder()
    enc.set_bit_rate(BITRATE_KBPS)
    enc.set_in_sample_rate(SAMPLE_RATE)
    enc.set_channels(1)
    enc.set_quality(2)
    dest.write_bytes(bytes(enc.encode(a.tobytes()) + enc.flush()))


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def collect_strings() -> tuple[list[str], list[str]]:
    print("→ collecting strings from the app (tools/collect_strings.mjs) …")
    node = shutil.which("node")
    if not node:
        sys.exit("node is required to collect the strings (tools/collect_strings.mjs)")
    out = subprocess.run([node, str(ROOT / "tools" / "collect_strings.mjs")],
                         check=True, capture_output=True, text=True).stdout
    data = json.loads(out)
    return data["strings"], data["slow"]


def write_manifest(manifest: dict[str, str], slow: dict[str, str], extra: dict) -> None:
    lines = [
        "// AUTO-GENERATED FILE — do not edit by hand.",
        "// Built by tools/build_audio.py — see readme.md §11 (bundled audio).",
        f"// {len(manifest)} Persian clips (+{len(slow)} slow 🐢 variants), recorded with eSpeak-NG (voice: fa).",
        "const FA_AUDIO = {",
    ]
    for key in sorted(manifest):
        lines.append(f"{json.dumps(key, ensure_ascii=False)}:{json.dumps(manifest[key])},")
    lines.append("};")
    lines.append("const FA_AUDIO_SLOW = {")
    for key in sorted(slow):
        lines.append(f"{json.dumps(key, ensure_ascii=False)}:{json.dumps(slow[key])},")
    lines.append("};")
    lines.append("const FA_AUDIO_META = " + json.dumps(extra, ensure_ascii=False) + ";")
    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the bundled FarsiGo audio pack")
    ap.add_argument("--only-missing", action="store_true", help="keep clips that already exist")
    ap.add_argument("--limit", type=int, default=0, help="only render the first N strings (smoke test)")
    ap.add_argument("--jobs", type=int, default=min(8, (os.cpu_count() or 2)), help="parallel workers")
    args = ap.parse_args()

    t0 = time.time()
    ensure_deps()
    strings, slow_list = collect_strings()
    if args.limit:
        strings, slow_list = strings[:args.limit], slow_list[:args.limit]
    print(f"→ {len(strings)} Persian strings (+{len(slow_list)} slow variants)")

    slow_set = set(slow_list)
    jobs = []
    manifest: dict[str, str] = {}
    manifest_slow: dict[str, str] = {}
    seen: dict[str, str] = {}
    for key in strings:
        rel = clip_name(key, False)
        if seen.setdefault(rel, key) != key:      # paranoid hash-collision guard
            rel = rel.replace(".mp3", f"-{hashlib.sha1(key.encode()).hexdigest()[16:24]}.mp3")
        manifest[key] = f"audio/{rel}"
        jobs.append((key, False, rel, args.only_missing))
        if key in slow_set:
            srel = clip_name(key, True)
            manifest_slow[key] = f"audio/{srel}"
            jobs.append((key, True, srel, args.only_missing))

    AUDIO_DIR.mkdir(exist_ok=True)
    _silence_clip()

    print(f"→ synthesising {len(jobs)} clips with eSpeak-NG (fa) …")
    done = 0
    from multiprocessing import Pool
    if args.jobs <= 1:
        _worker_init()
        for job in jobs:
            _render(job)
            done += 1
            if done % 200 == 0:
                print(f"   {done}/{len(jobs)}")
    else:
        with Pool(args.jobs, initializer=_worker_init) as pool:
            for _ in pool.imap_unordered(_render, jobs, chunksize=8):
                done += 1
                if done % 400 == 0:
                    print(f"   {done}/{len(jobs)}")

    write_manifest(manifest, manifest_slow, {
        "voice": "espeak-ng fa", "rate": ESPEAK_RATE_WPM, "slowRate": SLOW_WPM,
        "bitrateKbps": BITRATE_KBPS, "clips": len(manifest), "slowClips": len(manifest_slow),
    })

    # drop clips nothing points at any more (content edited/removed since the
    # last build) so the pack never grows stale files
    keep = {pathlib.Path(p).name for p in list(manifest.values()) + list(manifest_slow.values())}
    orphans = [f for f in AUDIO_DIR.rglob("*.mp3")
               if f.name not in keep and f.name != "silence.mp3"]
    for f in orphans:
        f.unlink()
    if orphans:
        print(f"→ removed {len(orphans)} orphaned clip(s)")

    total = sum(f.stat().st_size for f in AUDIO_DIR.rglob("*.mp3"))
    print(f"✓ {len(manifest)} clips (+{len(manifest_slow)} slow) in audio/ — "
          f"{total / 1048576:.1f} MB, manifest audio/index.js — {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
