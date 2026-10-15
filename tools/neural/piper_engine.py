#!/usr/bin/env python3
# =============================================================================
# Persian Piper (VITS) neural voice — provisioning, dictionary, synthesis
# =============================================================================
# Shared by tools/build_audio.py (--engine piper, the shipping path) and
# tools/neural/build_demo.py (the listening comparison).
#
# The voice is third-party and 60 MB, so it is never committed: it is fetched
# from codeload.github.com — that repo checks the model into git as an
# Emscripten pack, which is why it is reachable where HuggingFace and GitHub
# release assets are not. The shipped artefact is still just the MP3 pack.
#
# The model takes eSpeak phonemes as input (its token set includes ˈ ˌ ː), so
# FarsiGo's corrected Persian dictionary can be compiled into a copy of the
# model's own espeak-ng-data and the neural voice will follow it. That is the
# same mechanism the eSpeak pack uses — see tools/pron_rules.py.
# =============================================================================
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

CACHE = pathlib.Path(os.environ.get("PARLINGO_TTS_CACHE", pathlib.Path.home() / ".cache" / "parlingo-tts"))
NEURAL = CACHE / "neural"
PIPER = NEURAL / "piper_fa"
PYLIBS = NEURAL / "pylibs"
WHEELS = CACHE / "wheels" / "neural"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

PIPER_REPO = "gyroing/Persian-Piper-TTS-WebAssembly"
PIPER_BRANCH = "master"                       # NB: the default branch is master, not main
PIPER_TARBALL = f"https://codeload.github.com/{PIPER_REPO}/tar.gz/{PIPER_BRANCH}"
PIPER_MODEL_CARD = "gyroing/Persian-Piper-Model-gyro"
WHEELS_PINS = {"sherpa-onnx": "1.13.4", "onnxruntime": "1.27.0"}
SAMPLE_RATE = 22050
DESCRIPTION = f"piper ({PIPER_MODEL_CARD})"


def refresh_import_paths() -> None:
    """Forget cached "this path does not exist" import results.

    On a cold cache the pylibs directory does not exist while Python first scans
    sys.path, so the interpreter remembers None for that entry; wheels unpacked
    into it later stay invisible until the entry is dropped.
    """
    import importlib
    for p in (str(CACHE / "pylibs"), str(PYLIBS)):
        if p not in sys.path:
            sys.path.insert(0, p)
        sys.path_importer_cache.pop(p, None)
    importlib.invalidate_caches()


def ensure_loader_path() -> bool:
    """Make the dynamic loader find libonnxruntime.so.

    sherpa-onnx links against "libonnxruntime.so" (no version suffix), which is
    not in any default search path. LD_LIBRARY_PATH is read once by ld.so at
    process start, so a process that has to *add* it must re-exec itself —
    returns True when that is required.
    """
    capi = PYLIBS / "onnxruntime" / "capi"
    current = os.environ.get("LD_LIBRARY_PATH", "")
    if str(capi) in current.split(":"):
        return False
    os.environ["LD_LIBRARY_PATH"] = f"{capi}:{current}" if current else str(capi)
    return True


def stock_data_dir() -> pathlib.Path:
    """The model's own espeak-ng-data — what 'its own dictionary' means."""
    return PIPER / "espeak-ng-data"


# ------------------------------------------------------------------ provisioning
def provision(skip_fetch: bool = False, verbose: bool = True) -> None:
    """Make numpy/lameenc (repo cache) and sherpa-onnx/onnxruntime importable."""
    refresh_import_paths()
    if skip_fetch:
        return
    PYLIBS.mkdir(parents=True, exist_ok=True)
    WHEELS.mkdir(parents=True, exist_ok=True)
    have = {p.name.split("-")[0] for p in PYLIBS.glob("*.dist-info")}
    if not all(k in have for k in WHEELS_PINS):
        if verbose:
            print("   fetching sherpa-onnx + onnxruntime …")
        subprocess.run([sys.executable, "-m", "pip", "download",
                        *[f"{k}=={v}" for k, v in WHEELS_PINS.items()],
                        "-d", str(WHEELS), "--no-deps", "-q"], check=True)
        for whl in WHEELS.glob("*.whl"):
            with zipfile.ZipFile(whl) as z:
                z.extractall(PYLIBS)
    # sherpa-onnx dlopen()s "libonnxruntime.so" with no version suffix
    capi = PYLIBS / "onnxruntime" / "capi"
    so = sorted(capi.glob("libonnxruntime.so.1.*"))
    if so and not (capi / "libonnxruntime.so").exists():
        (capi / "libonnxruntime.so").symlink_to(so[0].name)
    refresh_import_paths()


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


def fetch_model(verbose: bool = True) -> pathlib.Path:
    PIPER.mkdir(parents=True, exist_ok=True)
    if (PIPER / "model.onnx").exists() and (PIPER / "tokens.txt").exists() \
            and (stock_data_dir() / "fa_dict").exists():
        return PIPER
    tar_path = PIPER / "repo.tar.gz"
    if not tar_path.exists() or tar_path.stat().st_size < 1_000_000:
        if verbose:
            print(f"   fetching the Piper voice ({PIPER_TARBALL}) …")
        urllib.request.urlretrieve(PIPER_TARBALL, tar_path)
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
    if verbose:
        print(f"   voice cached: model.onnx {(PIPER/'model.onnx').stat().st_size/1048576:.1f} MB, "
              f"{sum(1 for _ in stock_data_dir().rglob('*') if _.is_file())} espeak-ng-data files")
    return PIPER


def model_fingerprint() -> str:
    """Stable id of the exact weights in use (size + md5), for build-info."""
    import hashlib
    model = PIPER / "model.onnx"
    if not model.exists():
        return "missing"
    h = hashlib.md5()
    with open(model, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return f"{h.hexdigest()[:12]}-{model.stat().st_size}"


# ------------------------------------------------------------- dictionary build
def compiled_data_dir(entries: dict[str, str], dsource: pathlib.Path, verbose: bool = True) -> pathlib.Path:
    """Compile FarsiGo's corrected fa_dict into a copy of the model's espeak data.

    Read back every entry through our own eSpeak-NG build before returning: a
    dictionary entry that silently fails to apply would ship the wrong
    pronunciation for that word, which is exactly the class of bug the eSpeak
    pack's gate exists to catch.
    """
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import build_audio as ba
    from pron_rules import merge_word_list

    dest = PIPER / "espeak-ng-data-corrected"
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(stock_data_dir(), dest)
    out = PIPER / "dictsource-corrected"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    for name in ("fa_rules", "fa_emoji"):
        shutil.copy(dsource / name, out / name)
    merged, replaced = merge_word_list(entries, dsource)
    (out / "fa_list").write_text(merged, encoding="utf-8")
    if verbose:
        print(f"→ dictionary: {len(entries)} entries ({replaced} stock lines replaced) → {out.name}")

    speaker = ba.Speaker(dest)
    if speaker.compile_dictionary(out) != 0:
        raise SystemExit("espeak_ng_CompileDictionary failed")
    plain = lambda s: s.replace(",", "").replace("%", "").strip()          # noqa: E731
    bad = [w for w, want in entries.items() if plain(speaker.phonemes(w)) != plain(want)]
    if bad:
        for w, _ in list((w, entries[w]) for w in bad[:10]):
            pass
        raise SystemExit(f"refusing to build: {len(bad)} overrides did not apply, e.g. {bad[:5]}")
    if verbose:
        print(f"→ verified: all {len(entries)} overrides are active in the model's dictionary")
    return dest


# ------------------------------------------------------------------- synthesis
class PiperVoice:
    """One loaded voice. eSpeak-NG is a singleton — never mix data dirs in a process."""

    def __init__(self, data_dir: pathlib.Path, threads: int = 2) -> None:
        refresh_import_paths()
        import sherpa_onnx
        self.sample_rate = SAMPLE_RATE
        self._tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(PIPER / "model.onnx"), tokens=str(PIPER / "tokens.txt"),
                    data_dir=str(data_dir), noise_scale=0.667, noise_scale_w=0.8, length_scale=1.0),
                num_threads=max(1, int(threads)), provider="cpu"),
            max_num_sentences=1))

    def synth(self, text: str, speed: float = 1.0):
        """Return int16 PCM. speed < 1 = slower (learner pace)."""
        import numpy as np
        audio = self._tts.generate(text, sid=0, speed=float(speed))
        return (np.clip(np.asarray(audio.samples), -1, 1) * 32767).astype("<i2")


def neural_env() -> dict:
    """Environment for a subprocess that must import sherpa-onnx."""
    e = dict(os.environ)
    e["LD_LIBRARY_PATH"] = str(PYLIBS / "onnxruntime" / "capi")
    e["PYTHONPATH"] = f"{PYLIBS}:{CACHE/'pylibs'}"
    return e


if __name__ == "__main__":                                   # tiny CLI for debugging
    provision()
    fetch_model()
    print("voice:", PIPER, "| fingerprint:", model_fingerprint())
    voice = PiperVoice(stock_data_dir())
    for text in ("کتاب", "ممنون", "شب یلدا نزدیکه."):
        pcm = voice.synth(text)
        print(f"  {text:20s} {len(pcm)/SAMPLE_RATE:5.2f}s at speed 1.0")
