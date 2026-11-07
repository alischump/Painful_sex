# Carousel design spec (1080×1350)

| Element | Position / size | Style |
|---|---|---|
| Background | full bleed | `#F1ECE3` paper + Gaussian grain σ5 |
| Series label | x72 y64, rule at y108 | Inter Medium 22, tracking 3.2, olive, "SERIES · 01/06" |
| Handle | right-aligned to x1008, y64 | Inter Medium 22, tracking 1 |
| Kicker | x78 y122 | Mrs Saint Delafield 66 |
| Hero word | x60, top y168 | Instrument Serif 230 (≤6 chars) / 172, lowercase |
| Suffix | x72, baseline = hero baseline + 88 | Instrument Serif Italic 84, yellow bar from baseline−30 to baseline+8 |
| List column | x72, width 462, starts at suffix baseline + 58, must end ≤ 1170 | heads Instrument Serif Italic 46; body Inter Medium 26 (24 when the copy runs long), line height 1.34 |
| Markers | 34 px | love = olive outline circle + check; watch = yellow disc + "!" |
| Arch | x560–1010, y300–1150, round top | tint per product, white glow at top |
| Product | fits (arch_w−110) × (arch_h−230), bottom 70 px above arch floor | cast shadow (olive 30%, blur 22, +22/+16) + floor ellipse |
| Sparkles | 4 per arch | 4-point white stars, twinkling |
| Brand pill | centred under arch, y1172 | "PICTURED: BRAND", Inter 17 tracked, cream with olive outline |
| Footer | y1238–1252 | "PELVIC HEALTH" tracked label left; SWIPE ⟶ pill right (last slide: yellow SAVE THIS) |
| Last-slide tip | x72 y1236, width 720, 2 lines | Inter SemiBold head in caps + Inter 19 body |
| Cover sticker | top-right of arch, −12° | yellow 190 px disc, serif numeral + tracked caption |

Animation (MP4 mode, 7 s at 30 fps):
- Timing: arch rises 0–0.6 s; hero word 0.12 s; product drops 0.35–1.05 s; highlighter wipe 0.8 s; list stagger from 1.05 s; brand pill 1.4 s; footer 1.8 s; tip 2.2 s.
- Loop: product floats 7 px over 3.5 s, sparkles twinkle every 2.2 s, the arrow nudges every 1.6 s, and the cover sticker rocks ±3°.

## Cover (00_cover)
| Element | Spec |
|---|---|
| Title stack | x62 from y140. serif 240 / italic 170 / hero 380 (`title_sizes` overrides). Baseline steps of 0.75 / 0.88 / 0.77 × that line's size. Yellow bar behind the hero word from baseline−0.20×size to baseline+0.035×size |
| Person | transparent cut-out, `person_height` px tall, fingertip at the hero word's baseline+4, soft olive cast shadow, 4 px float |
| Arch | 420×640, centred behind the person, bleeding off the bottom |
| Subtitle | Mrs Saint Delafield 88, wrapped to the column left of the person, from hero baseline+70 |
| Tag | yellow pill, Inter 19 tracked, under the subtitle |
| Sticker | yellow disc at `sticker_xy`, rocking −12° ±3° |
| Sparkles | 3 olive 4-point stars in the clear space right of the hero word |
| Footer | SWIPE pill bottom right only (no PELVIC HEALTH label) |
