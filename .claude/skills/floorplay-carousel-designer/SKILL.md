---
name: floorplay-carousel-designer
description: Design Ali's (@floorplayunfiltered, pelvic health OT) educational Instagram carousels in the clean-girl editorial "Lube Edit" style - one topic per 1080x1350 slide with an oversized lowercase serif word layered behind a cut-out product in a soft tinted arch, "why we love it" / "watch out for" lists, highlighter suffix, script kicker and SWIPE pill in the Floorplay brand kit. Pulls slide content from Notion, cuts out brand product photos, shows a storyboard for approval before export, then exports PNG stills (or MP4 loops). Use whenever Ali asks for a carousel, an Instagram post with several slides, a product or type comparison, or "same style as the lube carousel".
---

# Floorplay carousel designer

Creator: **Ali** (A-L-I), pelvic health OT, **@floorplayunfiltered**. The approved first use was **The Lube Edit**: 6 slides on water, silicone, oil, aloe, fertility-friendly and CBD lube. It is reproduced exactly by `examples/lube_edit/` (see `examples/lube_edit/preview.jpg`).

**Order of work:** content → photos → **storyboard, then wait for Ali's OK** → export. Never export before she approves.

## 1. Content
- Ali keeps topics in Notion. Search for the page title, fetch it, and use **her wording**, lightly shortened. Never add medical claims that aren't on her page.
- Per slide, aim for 2–4 "love" points and 2–3 "watch" points. Each point should be at most about 75 characters so the left column fits. The renderer prints `column ends at y…`, which must stay **≤ 1170**. If it's higher, shorten the copy (or the font steps down from 26 to 24 automatically once the copy passes 300 characters).
- Each slide also needs:
  - `word`: lowercase, 6 characters or fewer sets at 230 px, longer at 172 px
  - `suffix`: italic, highlighted
  - `kicker`: script line, 25 characters or fewer
- A general rule of thumb goes in the last slide's `tip` (`"head: body"`). It replaces the PELVIC HEALTH footer and the last slide gets a yellow SAVE THIS button.
- Write `content.json` (copy `examples/lube_edit/content.json`):
  - top level: `series` (tracked label, e.g. "THE LUBE EDIT"), `sticker` (cover badge `["6", "TYPES OF LUBE"]` or `null`), `products_dir`
  - per slide: `key`, `word`, `suffix`, `kicker`, `tint` [r, g, b], `product` (png name), `brand` (pill text), `love[]`, `watch[]`, optional `tip`

## 2. Product photos
- Use the photos Ali sends. Copy them into the project, and **never use brand images she didn't supply**.
- Cut each one out: `python3 scripts/cutout.py in.jpg products/<name>.png --crop L,T,R,B [--mode model|white|rect] [--trim-top N]`.
  - `model` is the default and suits bottles and tubes.
  - Use `white` for white or pale products on white backgrounds.
  - Use `rect` for flat cartons.
  - Crop off screenshot UI (cards, captions, borders) first.
- Preview every cut-out on a tan background and fix ragged edges before designing.
- Low-resolution sources (under about 600 px) render soft, so ask Ali for a bigger image if one matters.
- **Arch tints** should be a muted, desaturated version of the product's own color, about 85–90% lightness. The lube set: mist blue `(219,229,231)`, stone `(228,226,222)`, sand `(236,226,210)`, sage `(222,227,211)`, lavender `(225,226,236)`, blush `(241,222,215)`.

## 3. Storyboard (show it, then stop)
```bash
python3 scripts/carousel.py --content path/content.json --storyboard path/storyboard
```
- This writes three frames per slide (0.4 s, 1.3 s, final), `contact_sheet.jpg` and `finals_strip.jpg`. Look at them yourself for clipping, overlaps and cut-out quality before showing Ali.
- Write `STORYBOARD.md`, following `references/storyboard_template.md`:
  - a reference-technique table
  - a brand table
  - a slide-by-slide table with frames, copy, product and animation
  - a draft caption with hashtags, and alt text
  - open questions, which must cover whether any brands are **sponsored** (#ad or paid-partnership label) and whether she wants **stills or MP4 loops**
- Send Ali the strip, the contact sheet and the md, then wait.

## 4. Export (after approval)
```bash
python3 scripts/carousel.py --content path/content.json --export path/output --stills-only   # PNGs (Ali's default)
python3 scripts/carousel.py --content path/content.json --export path/output                 # + 7 s MP4 loops
```
PNGs are 1080×1350 RGB, uploaded in order 01→N. In MP4 mode, slide 1 is fully built from frame 0 (it's the feed thumbnail), while the other slides build in over about 2 s and then loop with ambient motion.

## Design system (don't drift)
See `references/design.md` for exact positions. In short:
- warm greige paper `#F1ECE3` with film grain
- "SERIES · 0N/0N" tracked label with a rule (top left), handle (top right)
- script kicker, a huge lowercase **Instrument Serif** word, and an italic suffix on a yellow `#F0E958` highlighter
- left column with italic-serif section heads, olive check markers for "love" and yellow "!" markers for "watch"
- right-hand arch (x 560–1010, y 300–1150) holding the product with a cast shadow, a floor shadow and sparkles
- "PICTURED: BRAND" pill under the arch
- footer: PELVIC HEALTH on the left, an outlined **SWIPE ⟶** pill on the right
- text olive `#2D2B1E`, pills cream `#FAF8F1`
- fonts bundled in `fonts/`

Reference look: clean-girl beauty carousels (two posts by @luizemacata) with neutral paper, flat-lay cut-out products, oversized lowercase serif hero words and live-photo motion.

## Dependencies
- python3 with numpy, pillow and scipy
- `pip install "rembg[cpu]"` for the cut-outs
- ffmpeg, only for MP4 export
