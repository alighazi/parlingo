#!/usr/bin/env python3
"""Render phrases with the Persian Piper voice through ONE espeak data dir.

Must be one process per data dir: eSpeak-NG is a singleton library, so
re-initialising it with another data dir hijacks the pronunciation of every
handle already open in the process — including the one sherpa-onnx holds.
Running each dictionary in its own process is what makes an A/B comparison real.

Called by build_demo.py; not meant to be run by hand (but it can be).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import wave

import numpy as np
import sherpa_onnx

ap = argparse.ArgumentParser()
ap.add_argument("--model-dir", required=True, help="dir holding model.onnx + tokens.txt")
ap.add_argument("--data-dir", required=True, help="espeak-ng-data the model should phonemize with")
ap.add_argument("--out", required=True)
ap.add_argument("--texts", required=True, help="JSON file with a list of strings")
ap.add_argument("--length-scale", type=float, default=1.0, help="1.0 = model speed, higher = slower")
ap.add_argument("--noise", type=float, default=0.667)
ap.add_argument("--noise-w", type=float, default=0.8)
args = ap.parse_args()

model_dir = pathlib.Path(args.model_dir)
texts = json.loads(pathlib.Path(args.texts).read_text(encoding="utf-8"))

tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
    model=sherpa_onnx.OfflineTtsModelConfig(
        vits=sherpa_onnx.OfflineTtsVitsModelConfig(
            model=str(model_dir / "model.onnx"), tokens=str(model_dir / "tokens.txt"),
            data_dir=args.data_dir, noise_scale=args.noise, noise_scale_w=args.noise_w,
            length_scale=args.length_scale),
        num_threads=4, provider="cpu"),
    max_num_sentences=1))

out = pathlib.Path(args.out)
out.mkdir(parents=True, exist_ok=True)
for i, text in enumerate(texts):
    audio = tts.generate(text, sid=0, speed=1.0)
    samples = np.array(audio.samples)
    w = wave.open(str(out / f"{i:02d}.wav"), "wb")
    w.setparams((1, 2, audio.sample_rate, len(samples), "NONE", ""))
    w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())
    w.close()
    print(f"{i:02d} {len(samples)/audio.sample_rate:5.2f}s  {text}")
