---
name: floorplay-reel-editor
description: Edit Ali's (@floorplayunfiltered, pelvic health OT) talking-head Instagram reels end to end - download footage from an iCloud shared album, transcribe with word timings, cut dead air and retakes, write a shot-by-shot storyboard, then render a branded 1080x1920 reel with punch-ins, split-screen stat cards, build-on lists, kinetic captions and an end-card CTA in the Floorplay Canva brand kit. Use whenever Ali asks to edit, cut, caption, storyboard or brand a reel, or shares an iCloud/Instagram link with footage or style references.
---

# Floorplay reel editor

Creator: **Ali** (spelled A-L-I, never "Allie" — speech-to-text often gets this wrong; fix it in the transcript and on every card).
Pelvic health occupational therapist · handle **@floorplayunfiltered**.

Deliver, in this order: **storyboard first**, then the rendered reel. The worked example is `scripts/render_reel.py`, the "half of women with painful sex stay silent" reel. Copy it for each new reel and rewrite only the per-reel parts.

## Workflow

1. **Get the footage**
   - iCloud shared album link: `python3 scripts/icloud_download.py <link> footage/`.
   - If the network blocks a host, ask for that exact host. The partition host (`pNN-ckdatabasews.icloud.com`) and content host (`cvws-h2.icloud-content.com`) are printed or visible in the error.
   - Reference reels: `yt-dlp` (needs `www.instagram.com`, `i.instagram.com`, and the `scontent-*.cdninstagram.com` host printed by `yt-dlp -g`). Login-only reels return "empty media response", so ask Ali for the file instead.
   - iPhone clips carry a −90° rotation flag. ffmpeg auto-rotates them to 1080×1920, so don't rotate them again.

2. **Study the references.** For each reel, run:
   - cut detection: `ffmpeg -vf "select='gt(scene,0.3)',showinfo"`
   - a contact sheet: `fps=1/2,scale=216:-1,tile=8x6`
   - a transcript

   List each technique with an example of how it applies to Ali's script (see `references/techniques.md` for the ones already catalogued).

3. **Transcribe the footage.** Run `python3 scripts/transcribe.py footage.mp4 words.json`.
   - Look for gaps over 0.35 s, which are cut points.
   - Look for words lasting over 1.2 s, which are usually a hidden **retake**. Re-run with `--from/--to` over that stretch to get the verbatim words, and keep the cleaner take.
   - Drop filler openers ("Okay, so…").
   - Correct the name to "Ali".

4. **Find the face.** Grab gridded frames (`drawgrid`) and set `FACE` (x, y fractions). Punch-ins centre on it. The split-screen shift moves the face into the lower half.

5. **Write the storyboard** (`STORYBOARD.md` next to the output):
   - a techniques table (reference → how applied)
   - a brand table
   - a shot-by-shot table (edited-timeline time, still, VO line, on-screen text, technique)
   - a cut list
   - finishing notes

   Render stills with `--stills DIR` and embed them. Show Ali the storyboard before or with the final render.

6. **Edit `render_reel.py` for the new script.** Change:
   - `SEGMENTS`: (src_in, src_out, zoom, note). Times snap to frames automatically. Use zoom 1.0 for normal shots, 1.08–1.12 for alternate jump cuts, and 1.18–1.32 for emphasis lines.
   - `RETAKE`: verbatim word timings for any re-transcribed stretch. Also update the removal window in `load_words()`.
   - `HIGHLIGHT`: caption keywords shown in yellow.
   - `build_overlays()`: one block per beat, timed with `at(src_seconds)` on the spoken word.
   - `SPLIT`: the window for the content-top / creator-bottom stat section.
   - `STORYBOARD_TIMES`: one source time per beat.

7. **Render:**
   ```bash
   python3 scripts/render_reel.py --src footage.mp4 --words words.json --stills storyboard --keep-base /tmp/base.mov
   python3 scripts/render_reel.py --src x --base /tmp/base.mov --words words.json --out reel.mp4
   ```
   `--base` reuses the cut, so overlay tweaks re-render in about 1 minute.

8. **QA before delivering:**
   - Tile the stills and look at them. Check that no card clips: keep blocks under 1020 px wide, and drop the font size if needed.
   - Re-transcribe the output and confirm no retake remains and no word is clipped.
   - Check loudness: `ebur128`, target about −14 to −17 LUFS.
   - Keep the file under about 50 MB (crf 21, maxrate 9M).

## Style rules (from the reference analysis)
- Show the **hook headline from frame 1** (no fade), so it doubles as the cover. Pattern: a small italic serif line with one highlighted word, then a big serif caps line.
- **Remove all dead air.** Cut every 1–3 s. Use punch-ins on "let that sink in"-type lines and on the reframe/payoff.
- **Captions:** lowercase, 2–4 words per phrase, at chest height (y about 1400). Inter SemiBold 54 in cream, with an olive edge and a soft shadow. Keywords in yellow. During the split screen they move down to y about 1640.
- **Keyword pops** at the top, in a cream rounded card, echoing the spoken line.
- **Stats section:** split screen, with a cream panel on top (880 px) and the video shifted down 430 px. The panel has a tracked rule label naming the source study, and numbers count up (51%, 3×).
- **Lists:** "many women were taught to…" with numbered items ("01."…) appearing on the spoken word, then struck through, staggered, on the rebuttal.
- **End card:** a script kicker, a serif caps CTA, and an outlined FOLLOW @floorplayunfiltered pill with an arrow (the carousel "SWIPE ⟶" motif).
- Keep text inside Instagram's safe zones: below y 190, x between 90 and 990, and nothing important below y 1700.
- No music is baked in. Tell Ali to add trending audio in Instagram at 10–15%.

## Brand kit
See `references/brand.md`. In short: cream `#FAF8F1`, olive `#2D2B1E`, yellow `#F0E958`. Fonts are Instrument Serif (caps headlines and italic accents), Mrs Saint Delafield (script kicker) and Inter (labels, body, captions), all bundled in `fonts/`. If Canva is connected, re-check the latest designs (`search-designs` → `read-design`) in case the brand has changed. The Canva API does not expose Brand Kit swatches, so read them off on-brand designs.

## Dependencies
- ffmpeg
- python3 with numpy and pillow
- `pip install faster-whisper yt-dlp`
