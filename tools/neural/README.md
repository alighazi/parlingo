# Neural-voice experiment (Persian Piper vs. the shipped eSpeak pack)

FarsiGo ships 2 828 pre-recorded MP3s made with **eSpeak-NG** (voice `fa`) and a
corrected Persian dictionary — see `readme.md` §11. This folder builds a
listening comparison against a **neural** Persian voice (Piper/VITS) so the
switch can be judged by ear before committing to it.

> **The shipping path is `tools/build_audio.py --engine piper`** — this folder is
> the experiment that chose it. See readme.md §11 (*Voices*).

## Build

```bash
python3 tools/neural/build_demo.py            # everything, ~2 min cold
python3 tools/neural/build_demo.py --skip-fetch
python3 -m http.server 8010 --bind 0.0.0.0    # then open the demo dir
```

Outputs (default `/home/user/neural-demo`, override with `NEURAL_DEMO_DIR`):

| page | what it answers |
|---|---|
| `index.html` | A = shipped eSpeak pack, B = neural voice (own dictionary), C = neural + FarsiGo's stress/ezafe/ZWNJ fixes |
| `neural-vs-espeak.html` | the same, audio inlined so it works from `file://` |
| `quality-ladder.html` | lossless WAV / 48 kbps / 128 kbps / slower pace — is a codec artefact responsible for a “clipped” impression? |
| `ending-fix.html` | the model often stops *at* full voice; this compares the raw ending against a 25 ms fade-out + 140 ms of silence, at three paces |

## What it fetches (nothing is committed)

* eSpeak-NG + numpy/lameenc — via `tools/build_audio.py` → `~/.cache/parlingo-tts`
* `sherpa-onnx==1.13.4`, `onnxruntime==1.27.0` — PyPI → same cache
* the Piper voice — `codeload.github.com/gyroing/Persian-Piper-TTS-WebAssembly`
  (that repo checks the model into git as an Emscripten pack, which is why it is
  reachable when HuggingFace and GitHub release assets are not). It is a 60 MB
  VITS model, 22 050 Hz, espeak-phoneme input.

## Findings worth keeping

* **The model reads eSpeak's compiled dictionary.** Compile a corrected `fa_dict`
  into a copy of the model's `espeak-ng-data`, point `data_dir` at it, and the
  pronunciation changes — verified with a canary (a deliberately absurd
  pronunciation for کتاب) and by listening to stress move (خواهر: 2nd → 1st
  syllable). Its token set includes `ˈ ˌ ː`, so the stress work is not wasted.
* **eSpeak-NG is a singleton.** Re-initialising it with another data dir changes
  pronunciation for handles already open in the process — so every dictionary
  gets its own subprocess (`render_worker.py`). In-process A/B silently compares
  a file against itself.
* **The model's endings are abrupt.** Many clips stop at full speech energy with
  no decay (رتم/رفتم: last 40 ms at 0.05 RMS = speech level), which sounds like
  the audio was trimmed. A 25 ms cosine fade-out + 140 ms of silence fixes it;
  the shipped eSpeak clips always decay naturally.
* Inference is fast: **≈0.1 s per clip** on 4 CPU threads, so a full 2 828-clip
  pack is a ~10-minute build.
* Cost of switching: the pack grows from ~20 MB to ~30–60 MB depending on
  bitrate (48 kbps ≈ 30 MB, 128 kbps ≈ 60 MB), plus a 60 MB build-time model
  dependency. Check the model card's licence before shipping its output.

## Files

* `build_demo.py` — provisioning, dictionary compilation (with read-back gate),
  renders, encoding and the four pages.
* `render_worker.py` — renders a list of phrases with one data dir, in its own
  process; the singleton rule above is why this is separate.
