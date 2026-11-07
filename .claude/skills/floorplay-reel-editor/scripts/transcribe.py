#!/usr/bin/env python3
"""Word-level transcript with timings (faster-whisper, small.en).

Usage: python3 transcribe.py VIDEO OUT_words.json [--from S --to E]
Prints words with gaps >0.35s marked, so pauses and retakes are easy to spot.
Re-run with --from/--to on any stretch where timings look stretched (a long
word usually hides a repeated phrase / retake the model merged).
Needs: pip install faster-whisper; hosts huggingface.co + its CDN (us.aws.cdn.hf.co).
"""
import argparse, json, subprocess
import numpy as np
from faster_whisper import WhisperModel

ap = argparse.ArgumentParser()
ap.add_argument("video"); ap.add_argument("out")
ap.add_argument("--from", dest="t0", type=float, default=0); ap.add_argument("--to", dest="t1", type=float)
a = ap.parse_args()
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", a.video, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
audio = audio[int(a.t0 * 16000): int(a.t1 * 16000) if a.t1 else None]
m = WhisperModel("small.en", device="cpu", compute_type="int8")
kw = dict(word_timestamps=True)
if a.t1:
    kw.update(condition_on_previous_text=False,
              initial_prompt="Transcribe every word verbatim including repeats, ums and false starts.")
segs, _ = m.transcribe(audio, **kw)
words = [{"w": w.word.strip(), "s": round(a.t0 + w.start, 2), "e": round(a.t0 + w.end, 2)} for s in segs for w in s.words]
json.dump(words, open(a.out, "w"))
prev = a.t0
for w in words:
    if w["s"] - prev > 0.35:
        print(f"   [gap {w['s'] - prev:.2f}s]")
    flag = "  <-- long, check for retake" if w["e"] - w["s"] > 1.2 else ""
    print(f"{w['s']:6.2f}-{w['e']:6.2f} {w['w']}{flag}")
    prev = w["e"]
