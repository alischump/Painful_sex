#!/usr/bin/env python3
"""
Floorplay Unfiltered reel editor.

Turns the raw teleprompter take into an edited reel using the techniques pulled
from the reference reel (see STORYBOARD.md): dead-air + retake removal, jump-cut
punch-ins, top headline cards, split-screen "green-screen style" stat cards,
a build-on list with strike-throughs, lowercase kinetic captions with keyword
highlights, and an end card CTA — all in the Canva brand kit styling.

Usage:
  python3 render.py --src source.mp4 --out reel.mp4            # full render
  python3 render.py --src source.mp4 --stills OUT_DIR          # storyboard stills
"""
import argparse, json, math, os, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30

# ---- Brand kit (from Canva "Carousel" / "Did You Know" designs) -------------
CREAM = (250, 248, 241)   # #faf8f1 background
OLIVE = (45, 43, 30)      # #2d2b1e text / rules
YELLOW = (240, 233, 88)   # #f0e958 handle accent
SERIF = "InstrumentSerif-Regular.ttf"     # condensed serif caps headlines
SERIF_I = "InstrumentSerif-Italic.ttf"    # italic serif accents
SCRIPT = "MrsSaintDelafield-Regular.ttf"  # handwritten script kicker
SANS = "Inter-Medium.otf"                 # tracked labels / body
SANS_B = "Inter-SemiBold.otf"             # captions
HANDLE = "@floorplayunfiltered"

_fonts = {}
def F(name, size):
    k = (name, size)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(os.path.join(HERE, "fonts", name), size)
    return _fonts[k]

# ---- Edit decision list (source seconds) -----------------------------------
FACE = (0.44, 0.44)  # face centre in the source frame, as fractions
# (src_in, src_out, punch-in zoom, note)
SEGMENTS = [
    (1.30, 5.42, 1.00, "hook: almost half... never tell their partner"),
    (5.48, 6.80, 1.28, "punch-in: let that sink in"),
    (7.18, 9.92, 1.08, "intro: my name is Ali"),
    (10.30, 11.70, 1.00, "let's get into it"),
    (14.92, 21.86, 1.00, "study + 51% (second, clean take)"),
    (22.18, 26.22, 1.00, "little or no pleasure"),
    (26.40, 30.06, 1.00, "3x more likely"),
    (30.40, 33.16, 1.10, "many women were taught"),
    (33.40, 37.10, 1.00, "minimize / partner first"),
    (37.30, 41.76, 1.12, "but pain isn't normal"),
    (42.06, 43.22, 1.18, "that's not biology"),
    (43.26, 44.46, 1.32, "that's bad education"),
    (45.00, 50.90, 1.00, "CTA"),
]
SEGMENTS = [(round(s * FPS) / FPS, round(e * FPS) / FPS, z, n) for s, e, z, n in SEGMENTS]
OUT0 = []
_t = 0.0
for s, e, z, n in SEGMENTS:
    OUT0.append(_t)
    _t += e - s
DURATION = _t

def at(src_t):
    """Map a source timestamp to the edited timeline."""
    for (s, e, _, _), o in zip(SEGMENTS, OUT0):
        if s - 0.06 <= src_t <= e + 0.06:
            return o + min(max(src_t - s, 0), e - s)
    raise ValueError(f"{src_t} is in a removed section")

# ---- Words / captions ---------------------------------------------------------
# The automatic transcript merged the fumbled first take; this is the verbatim
# re-transcription of 14.9–17.5 s (the take we keep).
RETAKE = [("A", 14.94, 15.30), ("study", 15.30, 15.58), ("in", 15.58, 15.98), ("the", 15.98, 16.08),
          ("Journal", 16.08, 16.28), ("of", 16.28, 16.46), ("Sexual", 16.46, 16.72),
          ("Medicine", 16.72, 17.12), ("found", 17.12, 17.34), ("that", 17.34, 17.48)]
HIGHLIGHT = {"half", "painful", "never", "51%", "pain", "pleasure", "silence", "three", "discomfort",
             "biology", "education", "matters", "share", "follow", "normalize"}

def load_words():
    raw = json.load(open(os.path.join(HERE, "data", "transcript_words.json")))
    words = [w for w in raw if not (11.8 <= w["s"] < 17.45)]
    words += [{"w": a, "s": s, "e": e} for a, s, e in RETAKE]
    words.sort(key=lambda w: w["s"])
    merged = []
    for w in words:  # "51" "%" -> "51%"
        if w["w"] == "%" and merged:
            merged[-1] = dict(merged[-1], w=merged[-1]["w"] + "%", e=w["e"])
        else:
            merged.append(dict(w))
    out = []
    for w in merged:
        try:
            out.append(dict(w, os=at(w["s"]), oe=at(min(w["e"], w["s"] + 1.2))))
        except ValueError:
            pass
    return out

def caption_groups(words):
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        end_punct = w["w"][-1] in ".,?!"
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["os"] - w["oe"]) if nxt else 9
        if end_punct or len(cur) >= 4 or gap > 0.3 or nxt is None:
            groups.append(cur)
            cur = []
    res = []
    for gi, g in enumerate(groups):
        t0 = g[0]["os"]
        t1 = groups[gi + 1][0]["os"] if gi + 1 < len(groups) else DURATION
        t1 = min(t1, g[-1]["oe"] + 0.6)
        toks = [w["w"].strip(".,?!").lower() for w in g]
        res.append((t0, t1, toks))
    return res

# ---- Drawing helpers -----------------------------------------------------------
def text_w(font, s):
    return font.getlength(s)

def rich_block(lines, width=None, align="center", pad=(56, 44), bg=CREAM, bg_alpha=236, radius=40,
               strikes=None, markers=None):
    """lines: list of (runs, line_height) where runs = [(text, font, colour)].
    strikes: {line_index: progress 0..1} draws an olive strike-through.
    markers: {(line_index, run_index): progress} yellow highlighter behind a run."""
    strikes = strikes or {}
    markers = markers or {}
    lw = [sum(text_w(f, t) for t, f, c in runs) for runs, lh in lines]
    inner_w = max(width - 2 * pad[0], max(lw)) if width else max(lw)
    total_h = sum(lh for _, lh in lines)
    bw = int(inner_w + 2 * pad[0])
    bh = int(total_h + 2 * pad[1])
    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if bg is not None:
        d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=radius, fill=bg + (bg_alpha,))
    y = pad[1]
    for li, ((runs, lh), w_) in enumerate(zip(lines, lw)):
        x = pad[0] + {"left": 0, "center": (inner_w - w_) / 2, "right": inner_w - w_}[align]
        asc = max(f.getmetrics()[0] for _, f, _ in runs)
        desc = max(f.getmetrics()[1] for _, f, _ in runs)
        base = y + (lh + asc - desc) / 2
        x0 = x
        for ri, (t, f, c) in enumerate(runs):
            tw = text_w(f, t)
            p = markers.get((li, ri))
            if p:
                size = f.size
                d.rectangle([x - 8, base - size * 0.52, x - 8 + (tw + 16) * min(p, 1), base + size * 0.08],
                            fill=YELLOW + (255,))
            d.text((x, base), t, font=f, fill=c + (255,), anchor="ls")
            x += tw
        if li in strikes and strikes[li] > 0:
            sy = base - runs[0][1].size * 0.3
            d.line([x0 - 6, sy, x0 - 6 + (w_ + 12) * min(strikes[li], 1), sy], fill=OLIVE + (255,), width=5)
        y += lh
    return img

def rule_label(text, size=28, rule=True, colour=OLIVE):
    """'PELVIC HEALTH' tracked label with the carousel's underline rule."""
    f = F(SANS, size)
    track = size * 0.12
    tw = sum(text_w(f, ch) + track for ch in text)
    img = Image.new("RGBA", (int(tw + 20), int(size * 2.2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 0
    for ch in text:
        d.text((x, size * 1.1), ch, font=f, fill=colour + (255,), anchor="ls")
        x += text_w(f, ch) + track
    if rule:
        d.line([0, size * 1.75, tw + 20, size * 1.75], fill=colour + (255,), width=2)
    return img

def pill(text, size=30, arrow=True):
    """Outlined pill button like the carousel's 'SWIPE ⟶'."""
    f = F(SANS, size)
    tw = text_w(f, text)
    aw = 90 if arrow else 0
    w, h = int(tw + aw + 90), int(size * 2.6)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([1, 1, w - 2, h - 2], radius=h // 2, fill=CREAM + (255,), outline=OLIVE + (255,), width=3)
    d.text((45, h / 2), text, font=f, fill=OLIVE + (255,), anchor="lm")
    if arrow:
        ax = 45 + tw + 25
        d.line([ax, h / 2, ax + 60, h / 2], fill=OLIVE + (255,), width=3)
        d.line([ax + 48, h / 2 - 10, ax + 60, h / 2], fill=OLIVE + (255,), width=3)
        d.line([ax + 48, h / 2 + 10, ax + 60, h / 2], fill=OLIVE + (255,), width=3)
    return img

def handle_tag(size=34):
    f = F(SANS_B, size)
    tw = text_w(f, HANDLE)
    w, h = int(tw + 56), int(size * 2.0)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=YELLOW + (255,))
    d.text((28, h / 2), HANDLE, font=f, fill=OLIVE + (255,), anchor="lm")
    return img

_cap_cache = {}
def caption_img(toks):
    key = tuple(toks)
    if key in _cap_cache:
        return _cap_cache[key]
    f = F(SANS_B, 54)
    space = text_w(f, " ")
    maxw = 800
    lines, cur, cw = [], [], 0
    for t in toks:
        tw = text_w(f, t)
        if cur and cw + space + tw > maxw:
            lines.append(cur); cur, cw = [], 0
        cur.append(t); cw += (space if cw else 0) + tw
    lines.append(cur)
    lh = 70
    w = int(max(sum(text_w(f, t) for t in l) + space * (len(l) - 1) for l in lines)) + 40
    h = lh * len(lines) + 40
    txt = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dt, ds = ImageDraw.Draw(txt), ImageDraw.Draw(sh)
    for li, l in enumerate(lines):
        lw = sum(text_w(f, t) for t in l) + space * (len(l) - 1)
        x = (w - lw) / 2
        y = 20 + li * lh + lh / 2
        for t in l:
            col = YELLOW if t in HIGHLIGHT else CREAM
            ds.text((x, y + 3), t, font=f, fill=OLIVE + (200,), anchor="lm", stroke_width=6, stroke_fill=OLIVE + (200,))
            dt.text((x, y), t, font=f, fill=col + (255,), anchor="lm", stroke_width=2, stroke_fill=OLIVE + (255,))
            x += text_w(f, t) + space
    sh = sh.filter(ImageFilter.GaussianBlur(7))
    img = Image.alpha_composite(sh, txt)
    _cap_cache[key] = img
    return img

# ---- Animation helpers -------------------------------------------------------
def ease_out_back(p):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2

def ease_io(p):
    p = min(max(p, 0), 1)
    return p * p * (3 - 2 * p)

class El:
    """A timed overlay. `make(lt)` returns the RGBA image for local time lt."""
    def __init__(self, t0, t1, make, x="center", y=0, anim="pop", dur=0.24, out=0.16, layer=1):
        self.t0, self.t1, self.make, self.x, self.y = t0, t1, make, x, y
        self.anim, self.dur, self.out, self.layer = anim, dur, out, layer

    def state(self, t):
        if not (self.t0 <= t < self.t1):
            return None
        lt = t - self.t0
        p = min(lt / self.dur, 1) if self.dur else 1
        alpha, scale, dx, dy = 1.0, 1.0, 0, 0
        if self.anim == "pop":
            alpha = min(1, p * 2.2)
            scale = 0.82 + 0.18 * ease_out_back(p)
        elif self.anim == "fade":
            alpha = ease_io(p)
        elif self.anim == "slide_left":
            alpha = ease_io(p); dx = -60 * (1 - ease_io(p))
        elif self.anim == "rise":
            alpha = ease_io(p); dy = 40 * (1 - ease_io(p))
        if self.out and self.t1 - t < self.out:
            alpha *= (self.t1 - t) / self.out
        return lt, alpha, scale, dx, dy

def blend(frame, img, x, y, alpha=1.0):
    a = np.asarray(img, dtype=np.float32)
    h, w = a.shape[:2]
    x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 >= x1 or y0 >= y1:
        return
    sub = a[y0 - y:y1 - y, x0 - x:x1 - x]
    al = sub[..., 3:4] / 255.0 * alpha
    reg = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (reg * (1 - al) + sub[..., :3] * al).astype(np.uint8)

def draw_el(frame, el, t):
    st = el.state(t)
    if st is None:
        return
    lt, alpha, scale, dx, dy = st
    img = el.make(lt)
    if img is None or alpha <= 0.01:
        return
    w0, h0 = img.size
    if abs(scale - 1) > 0.005:
        img = img.resize((max(1, int(w0 * scale)), max(1, int(h0 * scale))), Image.BILINEAR)
    w, h = img.size
    x = (W - w0) / 2 if el.x == "center" else el.x
    x += (w0 - w) / 2 + dx
    y = el.y + (h0 - h) / 2 + dy
    blend(frame, img, x, y, alpha)

def static(img):
    return lambda lt: img

# ---- The storyboard, as overlays ---------------------------------------------
SPLIT = (at(14.92), at(30.0))     # split-screen window for the study stats
SPLIT_CARD_H, SPLIT_SHIFT = 880, 430

def split_progress(t):
    a, b = SPLIT
    if t < a or t >= b:
        return 0.0
    return ease_io(min((t - a) / 0.3, (b - t) / 0.3, 1))

def build_overlays():
    els = []
    S, SI, SC = SERIF, SERIF_I, SCRIPT
    # B1 HOOK — headline card, visible on frame 1 (thumbnail) ------------------
    hook = rich_block([
        ([("why ", F(SI, 72), OLIVE), ("half", F(SI, 72), OLIVE), (" of women with", F(SI, 72), OLIVE)], 78),
        ([("painful sex", F(SI, 72), OLIVE)], 78),
        ([("STAY SILENT", F(S, 150), OLIVE)], 150),
    ], markers={(0, 1): 1.0})
    els.append(El(0, at(6.78), static(hook), y=210, anim=None))
    # B2 "let that sink in." — small italic pop under the card ----------------
    sink = rich_block([([("let that sink in.", F(SI, 66), OLIVE)], 74)], pad=(34, 18), radius=30)
    els.append(El(at(5.58), at(6.78), static(sink), y=650))
    # B3 INTRO — carousel-style name card + handle ---------------------------
    def intro(lt):
        card = Image.new("RGBA", (760, 420), (0, 0, 0, 0))
        bg = Image.new("RGBA", card.size, (0, 0, 0, 0))
        ImageDraw.Draw(bg).rounded_rectangle([0, 0, 759, 419], radius=40, fill=CREAM + (236,))
        card = Image.alpha_composite(card, bg)
        card.alpha_composite(rule_label("PELVIC HEALTH"), (56, 40))
        name = rich_block([([("ALI", F(S, 190), OLIVE)], 170)], bg=None, pad=(0, 0), align="left")
        card.alpha_composite(name, (52, 92))
        role = rich_block([([("occupational therapist", F(SC, 92), OLIVE)], 100)], bg=None, pad=(0, 0), align="left")
        card.alpha_composite(role, (60, 280))
        return card
    els.append(El(at(7.26), at(9.92), intro, x=80, y=230, anim="slide_left", dur=0.3))
    els.append(El(at(8.2), at(9.92), static(handle_tag()), x=110, y=680, anim="pop"))
    # B4 "let's get into it" -----------------------------------------------
    gi = rich_block([([("let's get ", F(SI, 84), OLIVE), ("into it", F(SI, 84), OLIVE)], 90)],
                    pad=(40, 22), markers={(0, 1): 1.0}, radius=32)
    els.append(El(at(10.36), at(11.70), static(gi), y=330))
    # B5 SPLIT-SCREEN STATS (green-screen layout: content top, creator below) --
    a, b = SPLIT
    els.append(El(a + 0.2, b - 0.15, static(rule_label("A STUDY IN THE JOURNAL OF SEXUAL MEDICINE", 26)),
                  x=96, y=190, anim="fade", layer=2))
    journal = rich_block([([("The Journal of", F(SI, 96), OLIVE)], 100),
                          ([("SEXUAL MEDICINE", F(S, 150), OLIVE)], 140)], bg=None, align="left", pad=(0, 0))
    els.append(El(at(16.08), at(17.70), static(journal), x=96, y=330, anim="rise", layer=2))

    def counter(target, suffix, start_t, size=330):
        cache = {}
        def make(lt):
            p = ease_io(min(lt / 0.7, 1))
            v = int(round(target * p))
            if v not in cache:
                cache[v] = rich_block([([(f"{v}{suffix}", F(S, size), OLIVE)], size * 0.92)],
                                      bg=None, align="left", pad=(0, 0))
            return cache[v]
        return make
    els.append(El(at(17.72), at(22.2), counter(51, "%", at(17.72)), x=90, y=280, anim="fade", dur=0.1, layer=2))
    sub51 = rich_block([([("of women with painful sex", F(SANS, 52), OLIVE) ], 70),
                        ([("told their partner.", F(SANS, 52), OLIVE) ], 70)], bg=None, align="left", pad=(0, 0))
    els.append(El(at(20.78), at(22.2), static(sub51), x=100, y=620, anim="rise", layer=2))
    lp = rich_block([([("little or no", F(SI, 110), OLIVE)], 110),
                     ([("PLEASURE?", F(S, 190), OLIVE)], 170)], bg=None, align="left", pad=(0, 0))
    els.append(El(at(23.36), at(26.24), static(lp), x=96, y=300, anim="rise", layer=2))
    sil = rich_block([([("silence", F(SANS, 52), OLIVE), (" was even more common.", F(SANS, 52), OLIVE) ], 70)],
                     bg=None, align="left", pad=(0, 0), markers={(0, 0): 1.0})
    els.append(El(at(24.88), at(26.24), static(sil), x=104, y=660, anim="rise", layer=2))
    els.append(El(at(26.70), b - 0.1, counter(3, "×", at(26.70)), x=90, y=260, anim="fade", dur=0.1, layer=2))
    sub3 = rich_block([([("more likely to ", F(SANS, 52), OLIVE), ("not", F(SANS, 52), OLIVE) ], 70),
                       ([("speak up.", F(SANS, 52), OLIVE) ], 70)], bg=None, align="left", pad=(0, 0),
                      markers={(0, 1): 1.0})
    els.append(El(at(28.24), b - 0.1, static(sub3), x=104, y=630, anim="rise", layer=2))
    # B6 BUILD-ON LIST + strike-through ---------------------------------------
    items = [("01.", "ACCEPT DISCOMFORT", at(31.30)), ("02.", "MINIMIZE THEIR PLEASURE", at(33.48)),
             ("03.", "PUT THEIR PARTNER FIRST", at(35.00))]
    strike_t = at(37.48)
    def taught(lt):
        t = at(30.46) + lt
        lines = [([("many women were taught to...", F(SI, 64), OLIVE)], 84)]
        strikes = {}
        for i, (n, txt, t_in) in enumerate(items):
            if t >= t_in:
                lines.append(([(n + " ", F(SI, 62), OLIVE), (txt, F(S, 76), OLIVE)], 88))
                strikes[len(lines) - 1] = ease_io((t - strike_t - i * 0.18) / 0.3)
        return rich_block(lines, width=900, align="left", strikes=strikes)
    els.append(El(at(30.46), at(39.94), taught, y=200, anim="pop"))
    pm = rich_block([([("your pleasure", F(SI, 104), OLIVE)], 104),
                     ([("MATTERS TOO.", F(S, 170), OLIVE)], 160)], markers={(1, 0): 1.0})
    els.append(El(at(39.98), at(41.76), static(pm), y=230))
    # B7 REFRAME — "not biology" / "bad education" ------------------------------
    def reframe(lt):
        t = at(42.14) + lt
        lines = [([("THAT'S NOT ", F(S, 100), OLIVE), ("BIOLOGY.", F(S, 100), OLIVE)], 104)]
        mk = {}
        if t >= at(43.32):
            lines.append(([("THAT'S ", F(S, 100), OLIVE), ("BAD EDUCATION.", F(S, 100), OLIVE)], 104))
            mk[(1, 1)] = ease_io((t - at(43.32)) / 0.25)
        return rich_block(lines, width=960, strikes={0: 0} if t < at(43.32) else {}, markers=mk)
    els.append(El(at(42.14), at(44.46), reframe, y=230, anim="pop"))
    # B8 END CARD CTA ------------------------------------------------------------
    def endcard(lt):
        t = at(45.08) + lt
        lines = [([("if this blew your mind", F(SC, 110), OLIVE)], 104)]
        if t >= at(47.64):
            lines.append(([("SHARE IT WITH SOMEONE", F(S, 104), OLIVE)], 100))
            lines.append(([("WHO NEEDS TO HEAR IT", F(S, 104), OLIVE)], 100))
        return rich_block(lines, width=940)
    els.append(El(at(45.08), DURATION + 1, endcard, y=210, anim="pop", out=0))
    els.append(El(at(49.66), DURATION + 1, static(pill(f"FOLLOW {HANDLE}", 38)), y=640, anim="pop", out=0))
    return els

# ---- Frame compositor ----------------------------------------------------------------
class Compositor:
    def __init__(self):
        self.words = load_words()
        self.caps = caption_groups(self.words)
        self.els = sorted(build_overlays(), key=lambda e: e.layer)

    def frame(self, base, t):
        f = base.copy()
        e = split_progress(t)
        if e > 0:
            d = int(SPLIT_SHIFT * e)
            f[d:] = base[:H - d]
            ch = int(SPLIT_CARD_H * e)
            f[:ch] = CREAM
            f[max(ch - 2, 0):ch] = OLIVE
        for el in self.els:
            if el.layer == 2 and e < 0.95:
                continue
            draw_el(f, el, t)
        for t0, t1, toks in self.caps:
            if t0 <= t < t1:
                img = caption_img(toks)
                p = min((t - t0) / 0.12, 1)
                sc = 0.92 + 0.08 * ease_io(p)
                if sc < 0.999:
                    img = img.resize((int(img.width * sc), int(img.height * sc)), Image.BILINEAR)
                cy = 1400 + (1640 - 1400) * e
                blend(f, img, (W - img.width) / 2, cy - img.height / 2, min(1, p * 2))
        return f

# ---- ffmpeg plumbing ---------------------------------------------------------------
def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def cut_base(src, base, tmp):
    """Frame-accurate cuts with punch-in zoom + gentle warm grade, then concat."""
    parts = []
    for i, (s, e, z, _) in enumerate(SEGMENTS):
        cw, ch = W / z, H / z
        cx = min(max(FACE[0] * W - cw / 2, 0), W - cw)
        cy = min(max(FACE[1] * H - ch / 2, 0), H - ch)
        vf = (f"fps={FPS},crop={cw:.0f}:{ch:.0f}:{cx:.0f}:{cy:.0f},scale={W}:{H}:flags=lanczos,setsar=1,"
              "eq=contrast=1.04:saturation=0.94,colorbalance=rm=0.025:bm=-0.025:rh=0.015:bh=-0.015")
        dur = e - s
        af = f"afade=t=in:d=0.012,afade=t=out:st={dur - 0.02:.3f}:d=0.02"
        p = os.path.join(tmp, f"seg{i:02d}.mp4")
        run(["ffmpeg", "-y", "-ss", f"{s:.3f}", "-i", src, "-t", f"{dur:.3f}", "-vf", vf, "-af", af,
             "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-pix_fmt", "yuv420p",
             "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", p.replace(".mp4", ".mov")])
        parts.append(p.replace(".mp4", ".mov"))
    lst = os.path.join(tmp, "list.txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", base])

def read_frame_at(base, t):
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", base, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], check=True, capture_output=True).stdout
    return np.frombuffer(out, np.uint8).reshape(H, W, 3)

def render(base, out):
    comp = Compositor()
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", base, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", base, "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-crf", "21", "-preset", "slow", "-maxrate", "9M", "-bufsize", "18M", "-pix_fmt", "yuv420p",
                            "-af", "highpass=f=80,afftdn=nf=-25,loudnorm=I=-14:TP=-1.5:LRA=11",
                            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out],
                           stdin=subprocess.PIPE)
    n, fs = 0, W * H * 3
    while True:
        buf = dec.stdout.read(fs)
        if len(buf) < fs:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        enc.stdin.write(comp.frame(fr, n / FPS).tobytes())
        n += 1
        if n % 150 == 0:
            print(f"  {n / FPS:5.1f}s / {DURATION:.1f}s", flush=True)
    enc.stdin.close(); enc.wait(); dec.wait()
    print(f"rendered {n} frames -> {out}")

STORYBOARD_TIMES = {  # beat -> (source time to sample)
    "01_hook": 3.0, "02_sink_in": 6.3, "03_intro": 8.9, "04_get_into_it": 11.2, "05_study": 16.9,
    "06_51pct": 21.4, "07_pleasure": 25.6, "08_3x": 29.5, "09_taught_list": 36.6, "10_strike": 38.6,
    "11_pleasure_matters": 41.0, "12_not_biology": 42.7, "13_bad_education": 44.2, "14_cta": 50.5,
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out")
    ap.add_argument("--stills")
    ap.add_argument("--base", help="reuse an existing cut (skip cutting)")
    ap.add_argument("--keep-base", help="save the intermediate cut here for reuse")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="reel_")
    base = a.base or os.path.join(tmp, "base.mov")
    if not a.base:
        print("cutting segments..."); cut_base(a.src, base, tmp)
    print(f"edited duration {DURATION:.2f}s (source 52.17s)")
    if a.stills:
        os.makedirs(a.stills, exist_ok=True)
        comp = Compositor()
        for name, st in STORYBOARD_TIMES.items():
            t = at(st)
            fr = comp.frame(read_frame_at(base, t), t)
            Image.fromarray(fr).save(os.path.join(a.stills, f"{name}.jpg"), quality=88)
        print("stills ->", a.stills)
    if a.out:
        render(base, a.out)
    if a.keep_base and not a.base:
        shutil.copy(base, a.keep_base)

if __name__ == "__main__":
    main()
