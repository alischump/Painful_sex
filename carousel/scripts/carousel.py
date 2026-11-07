#!/usr/bin/env python3
"""
"The Lube Edit": a 6-slide Instagram carousel for @floorplayunfiltered.

Clean-girl editorial look taken from the reference carousels (warm neutral paper,
cut-out products, oversized lowercase serif words layered with the product,
live-photo style ambient motion), in the Floorplay brand kit.

  python3 carousel.py --storyboard OUT_DIR   # key frames + contact sheet (no export)
  python3 carousel.py --export OUT_DIR       # PNG + MP4 per slide
  python3 carousel.py --export OUT_DIR --stills-only   # PNG stills only
"""
import argparse, math, os, random, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
FONTS = os.path.join(ROOT, "..", ".claude", "skills", "floorplay-reel-editor", "fonts")
W, H, FPS, DUR = 1080, 1350, 30, 7.0

CREAM = (250, 248, 241)
PAPER = (241, 236, 227)     # warm greige paper, like the reference flat-lay
OLIVE = (45, 43, 30)
YELLOW = (240, 233, 88)
HANDLE = "@floorplayunfiltered"

def F(name, size, _c={}):
    k = (name, size)
    if k not in _c:
        _c[k] = ImageFont.truetype(os.path.join(FONTS, name), size)
    return _c[k]
SERIF, SERIF_I, SCRIPT = "InstrumentSerif-Regular.ttf", "InstrumentSerif-Italic.ttf", "MrsSaintDelafield-Regular.ttf"
SANS, SANS_B = "Inter-Medium.otf", "Inter-SemiBold.otf"

# ---- Content (from Notion "Types of lube", tightened for slides) ------------------------------
SLIDES = [
    dict(key="water", word="water", suffix="-based", kicker="the everyday staple", tint=(219, 229, 231),
         product="slippery", brand="Slippery Stuff Gel",
         love=["Versatile and easy to wash off",
               "Works with latex condoms, dental dams and most toys",
               "A good first pick for sensitive skin",
               "Comes in thin to thicker formulas"],
         watch=["May dry out, so reapply as needed",
                "Very hyperosmolar formulas can irritate vaginal or rectal tissue"]),
    dict(key="silicone", word="silicone", suffix="-based", kicker="the long-lasting one", tint=(228, 226, 222),
         product="uberlube", brand="Überlube",
         love=["Long-lasting and super slippery",
               "Great for longer sex, anal, shower sex or significant dryness",
               "Latex condom + dental dam compatible",
               "Won't evaporate or dry quickly"],
         watch=["Can stain fabric and is harder to wash off",
                "May make some silicone toys sticky; use water-based with silicone toys"]),
    dict(key="oil", word="oil", suffix="-based", kicker="the moisturizer", tint=(236, 226, 210),
         product="coconu", brand="Coconu",
         love=["Very long-lasting and moisturizing",
               "Great for external massage or sex without latex barriers",
               "Often inexpensive and easy to find"],
         watch=["Weakens latex condoms + dental dams (breakage risk)",
                "Hard to remove from fabric",
                "Not ideal internally if you get recurrent infections"]),
    dict(key="aloe", word="aloe", suffix="-based", kicker="the gentle one", tint=(222, 227, 211),
         product="maude", brand="Maude Shine",
         love=["Moisturizing and typically non-irritating",
               "Usually water-based + condom-compatible (check the formula)"],
         watch=["Some contain alcohol, fragrance, glycerin or other irritants",
                "May dry faster than silicone lubricants"]),
    dict(key="fertility", word="fertility", suffix="-friendly", kicker="for trying to conceive", tint=(225, 226, 236),
         product="preseed", brand="Pre-Seed",
         love=["Formulated to be gentler on sperm movement + survival",
               "Helpful when trying to conceive and you need lubrication",
               "Some are designed to resemble fertile cervical mucus"],
         watch=["“Natural,” “organic” or aloe ≠ fertility-friendly",
                "Choose one labeled + tested for use while trying to conceive"]),
    dict(key="cbd", word="cbd", suffix="-infused", kicker="the wellness add-on", tint=(241, 222, 215),
         product="foria", brand="Foria Awaken Arousal Oil",
         love=["Some report more relaxation, sensation or less discomfort",
               "An option for external massage or sexual wellness"],
         watch=["Formulas vary: some are oil-based or add fragrance, warming agents or botanicals",
                "Won't treat vaginismus, pelvic-floor dysfunction or chronic pain",
                "Pregnant, breastfeeding, TTC or on meds? Ask your clinician first"],
         tip="pelvic-floor friendly pick: fragrance-free, flavor-free, non-warming, non-cooling, short ingredient list"),
]

# ---- helpers ------------------------------------------------------------------------------------------
def ease(p):
    p = min(max(p, 0.0), 1.0)
    return 1 - (1 - p) ** 3

def wrap(text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.getlength(t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines

def text_img(text, font, color=OLIVE, track=0.0):
    asc, desc = font.getmetrics()
    if track:
        w = int(sum(font.getlength(c) + track for c in text)) + 4
    else:
        w = int(font.getlength(text)) + 8
    im = Image.new("RGBA", (w, asc + desc + 6), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if track:
        x = 0
        for c in text:
            d.text((x, asc + 2), c, font=font, fill=color + (255,), anchor="ls"); x += font.getlength(c) + track
    else:
        d.text((2, asc + 2), text, font=font, fill=color + (255,), anchor="ls")
    return im

def grain(seed=3, amt=5):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amt, (H, W, 1)).astype(np.float32)
    return n

def paste(base, im, x, y, alpha=1.0):
    if alpha <= 0.01:
        return
    if alpha < 1:
        im = im.copy(); a = im.getchannel("A").point(lambda v: int(v * alpha)); im.putalpha(a)
    base.alpha_composite(im, (int(round(x)), int(round(y))))

def star(size, color=(255, 255, 255), alpha=230):
    s = size
    im = Image.new("RGBA", (s * 2, s * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = s
    pts = [(c, 0), (c + s * 0.18, c - s * 0.18), (2 * s, c), (c + s * 0.18, c + s * 0.18),
           (c, 2 * s), (c - s * 0.18, c + s * 0.18), (0, c), (c - s * 0.18, c - s * 0.18)]
    d.polygon(pts, fill=color + (alpha,))
    return im.filter(ImageFilter.GaussianBlur(0.6))

def pill(text, size=24, arrow=True, fill=CREAM, outline=OLIVE):
    f = F(SANS, size)
    track = size * 0.14
    tw = sum(f.getlength(c) + track for c in text)
    aw = 70 if arrow else 0
    w, h = int(tw + aw + 64), int(size * 2.5)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([1, 1, w - 2, h - 2], radius=h // 2, fill=fill + (255,), outline=outline + (255,), width=2)
    x = 32
    for c in text:
        d.text((x, h / 2), c, font=f, fill=OLIVE + (255,), anchor="lm"); x += f.getlength(c) + track
    if arrow:
        ax = x + 14
        d.line([ax, h / 2, ax + 46, h / 2], fill=OLIVE + (255,), width=2)
        d.line([ax + 36, h / 2 - 8, ax + 46, h / 2], fill=OLIVE + (255,), width=2)
        d.line([ax + 36, h / 2 + 8, ax + 46, h / 2], fill=OLIVE + (255,), width=2)
    return im

def marker(kind):
    s = 34
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if kind == "love":
        d.ellipse([1, 1, s - 2, s - 2], outline=OLIVE + (255,), width=2)
        d.line([10, 17, 15, 23, 25, 11], fill=OLIVE + (255,), width=3, joint="curve")
    else:
        d.ellipse([1, 1, s - 2, s - 2], fill=YELLOW + (255,))
        d.text((s / 2, s / 2 + 1), "!", font=F(SANS_B, 22), fill=OLIVE + (255,), anchor="mm")
    return im

def sticker(text1, text2, d=190):
    im = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, d - 1, d - 1], fill=YELLOW + (255,))
    dr.text((d / 2, d / 2 - 22), text1, font=F(SERIF, 70), fill=OLIVE + (255,), anchor="mm")
    dr.text((d / 2, d / 2 + 34), text2, font=F(SANS, 20), fill=OLIVE + (255,), anchor="mm")
    return im

def product_layers(name, box_w, box_h):
    p = Image.open(os.path.join(ROOT, "products_cut", f"{name}.png")).convert("RGBA")
    s = min(box_w / p.width, box_h / p.height)
    p = p.resize((int(p.width * s), int(p.height * s)), Image.LANCZOS)
    # soft cast shadow from the product's own silhouette
    a = p.getchannel("A")
    sh = Image.new("RGBA", (p.width + 120, p.height + 120), (0, 0, 0, 0))
    blk = Image.new("RGBA", p.size, OLIVE + (0,)); blk.putalpha(a.point(lambda v: int(v * 0.30)))
    sh.alpha_composite(blk, (60 + 22, 60 + 16))
    sh = sh.filter(ImageFilter.GaussianBlur(22))
    return p, sh

# ---- slide build -------------------------------------------------------------------------------------
class Slide:
    def __init__(self, idx, spec):
        self.i, self.s = idx, spec
        self.n = len(SLIDES)
        self.cover = idx == 0
        g = grain(seed=idx + 1)
        base = np.empty((H, W, 3), np.float32); base[:] = PAPER
        self.bg = Image.fromarray(np.clip(base + g, 0, 255).astype(np.uint8)).convert("RGBA")
        # arch (right side)
        self.ax0, self.ax1, self.ay0, self.ay1 = 560, 1010, 300, 1150
        aw, ah = self.ax1 - self.ax0, self.ay1 - self.ay0
        arch = Image.new("RGBA", (aw, ah), (0, 0, 0, 0))
        d = ImageDraw.Draw(arch)
        d.rounded_rectangle([0, 0, aw - 1, ah - 1], radius=aw // 2, fill=spec["tint"] + (255,))
        d.rectangle([0, ah // 2, aw - 1, ah - 1], fill=spec["tint"] + (255,))
        # faint inner light at the top of the arch
        glow = Image.new("RGBA", (aw, ah), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([aw * 0.1, -ah * 0.05, aw * 0.9, ah * 0.45], fill=(255, 255, 255, 70))
        arch.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
        arch.putalpha(Image.fromarray(np.minimum(np.asarray(arch.getchannel("A")),
                                                 np.asarray(Image.new("L", (aw, ah), 255)))))
        mask = Image.new("L", (aw, ah), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle([0, 0, aw - 1, ah - 1], radius=aw // 2, fill=255)
        md.rectangle([0, ah // 2, aw - 1, ah - 1], fill=255)
        arch.putalpha(mask)
        self.arch = arch
        # product
        self.prod, self.prod_sh = product_layers(spec["product"], aw - 110, ah - 230)
        self.px = self.ax0 + (aw - self.prod.width) / 2
        self.py = self.ay1 - 70 - self.prod.height
        # floor shadow ellipse
        fw = int(self.prod.width * 1.05)
        fl = Image.new("RGBA", (fw + 80, 90), (0, 0, 0, 0))
        ImageDraw.Draw(fl).ellipse([40, 30, fw + 40, 60], fill=OLIVE + (70,))
        self.floor = fl.filter(ImageFilter.GaussianBlur(12))
        # texts
        self.label = text_img(f"THE LUBE EDIT  ·  {idx + 1:02d}/{self.n:02d}", F(SANS, 22), track=3.2)
        self.handle = text_img(HANDLE, F(SANS, 22), track=1.0)
        wf = F(SERIF, 230 if len(spec["word"]) <= 6 else 172)
        self.word = text_img(spec["word"], wf)
        self.word_y = 168
        self.word_base = self.word_y + wf.getmetrics()[0] + 2
        sf = F(SERIF_I, 84)
        self.suffix = text_img(spec["suffix"], sf)
        self.suf_base = self.word_base + 88
        self.suf_y = self.suf_base - sf.getmetrics()[0] - 2
        self.kicker = text_img(spec["kicker"], F(SCRIPT, 66))
        self.brand = pill(f"PICTURED: {spec['brand'].upper()}", 17, arrow=False, fill=CREAM)
        self.swipe = pill("SWIPE", 22) if idx < self.n - 1 else pill("SAVE THIS", 22, arrow=False, fill=YELLOW)
        self.sticker = sticker("6", "TYPES OF LUBE") if self.cover else None
        self.blocks = self._column()
        self.stars = [(self.ax0 + 70, self.ay0 + 170, 18, 0.0), (self.ax1 - 80, self.ay0 + 260, 12, 0.9),
                      (self.ax0 + 110, self.ay0 + 420, 10, 1.7), (self.ax1 - 120, self.ay0 + 120, 9, 2.4)]
        self.tip = None
        if spec.get("tip"):
            head, body = spec["tip"].split(":", 1)
            fh, fb2 = F(SANS_B, 19), F(SANS, 19)
            lines = wrap(body.strip(), fb2, 700 - fh.getlength(head + ": "))
            im = Image.new("RGBA", (720, 28 * 2 + 8), (0, 0, 0, 0))
            dd = ImageDraw.Draw(im)
            dd.text((0, 14), head.upper() + ":", font=fh, fill=OLIVE + (255,), anchor="lm")
            hx = fh.getlength(head.upper() + ": ")
            dd.text((hx, 14), lines[0], font=fb2, fill=OLIVE + (255,), anchor="lm")
            if len(lines) > 1:
                dd.text((0, 42), " ".join(lines[1:]), font=fb2, fill=OLIVE + (255,), anchor="lm")
            self.tip = im

    def _column(self):
        """Left column: 'why we love it' / 'watch out for' lists as (y, image, delay) rows."""
        x0, maxw = 72, 462
        rows, y = [], self.suf_base + 58
        fb = F(SANS, 24 if sum(len(t) for t in self.s["love"] + self.s["watch"]) > 300 else 26)
        lh = int(fb.size * 1.34)
        t = 1.05
        for kind, head, items in [("love", "why we love it", self.s["love"]), ("watch", "watch out for", self.s["watch"])]:
            rows.append((x0, y, text_img(head, F(SERIF_I, 46)), t)); y += 60; t += 0.18
            for it in items:
                lines = wrap(it, fb, maxw - 52)
                im = Image.new("RGBA", (maxw, lh * len(lines) + 6), (0, 0, 0, 0))
                im.alpha_composite(marker(kind), (0, max(0, (lh - 34) // 2)))
                d = ImageDraw.Draw(im)
                for k, ln in enumerate(lines):
                    d.text((52, lh * k + lh / 2), ln, font=fb, fill=OLIVE + (255,), anchor="lm")
                rows.append((x0, y, im, t)); y += im.height + 10; t += 0.16
            y += 16
        self.col_bottom = y
        return rows

    def frame(self, t):
        """t in seconds. Cover slide shows everything at t=0 (it's the feed thumbnail)."""
        cv = self.cover
        def appear(t0, dur=0.45):
            return 1.0 if cv else ease((t - t0) / dur)
        im = self.bg.copy()
        # header row
        paste(im, self.label, 72, 64)
        d = ImageDraw.Draw(im)
        d.line([72, 108, 72 + self.label.width, 108], fill=OLIVE + (255,), width=2)
        paste(im, self.handle, W - 72 - self.handle.width, 64)
        # arch rises from the floor
        pa = appear(0.0, 0.6)
        if pa > 0:
            ah = int(self.arch.height * pa)
            crop = self.arch.crop((0, self.arch.height - ah, self.arch.width, self.arch.height))
            paste(im, crop, self.ax0, self.ay1 - ah)
        # big word sits BEHIND the product (layered editorial look)
        pw = appear(0.12, 0.6)
        paste(im, self.word, 60, self.word_y + 30 * (1 - pw), pw)
        # sparkles twinkle inside the arch
        for sx, sy, sz, ph in self.stars:
            tw = 0.5 + 0.5 * math.sin(2 * math.pi * (t / 2.2) + ph * 2)
            a = appear(0.9) * (0.25 + 0.75 * tw)
            st = star(sz)
            paste(im, st, sx - sz, sy - sz, a)
        # product: drops in, then floats gently
        pp = appear(0.35, 0.7)
        bob = 7 * math.sin(2 * math.pi * t / 3.5)
        dy = -70 * (1 - pp) + bob
        fl = self.floor
        sc = 1 - bob / 140
        flr = fl.resize((max(1, int(fl.width * sc)), fl.height))
        paste(im, flr, self.px + self.prod.width / 2 - flr.width / 2, self.ay1 - 98, pp * (0.85 - bob / 60))
        paste(im, self.prod_sh, self.px - 60, self.py - 60 + dy, pp)
        paste(im, self.prod, self.px, self.py + dy, pp)
        # suffix + highlighter wipe, kicker script
        ps = appear(0.3, 0.5)
        sx, sy, sb = 72, self.suf_y, self.suf_base
        hw = appear(0.8, 0.45)
        if hw > 0:
            d = ImageDraw.Draw(im)
            d.rectangle([sx - 6, sb - 30, sx - 6 + (self.suffix.width + 4) * hw, sb + 8], fill=YELLOW + (255,))
        paste(im, self.suffix, sx, sy + 14 * (1 - ps), ps)
        pk = appear(0.05, 0.5)
        paste(im, self.kicker, 78, 122 + 10 * (1 - pk), pk)
        # column rows stagger in
        for x, y, row, t0 in self.blocks:
            p = appear(t0, 0.4)
            paste(im, row, x + 0, y + 18 * (1 - p), p)
        # brand pill under the arch
        pb = appear(1.4)
        paste(im, self.brand, self.ax0 + (self.ax1 - self.ax0 - self.brand.width) / 2, self.ay1 + 22, pb)
        # tip strip (last slide)
        if self.tip is not None:
            p = appear(2.2)
            paste(im, self.tip, 72, 1236 + 10 * (1 - p), p)
        # footer
        pf = appear(1.8)
        nudge = 6 * max(0, math.sin(2 * math.pi * t / 1.6)) if self.i < self.n - 1 else 0
        paste(im, self.swipe, W - 72 - self.swipe.width + nudge, 1238, pf)
        d = ImageDraw.Draw(im)
        if self.tip is None:
            lab = text_img("PELVIC HEALTH", F(SANS, 20), track=3.0)
            paste(im, lab, 72, 1252, pf)
        # cover sticker
        if self.sticker is not None:
            rot = -12 + 3 * math.sin(2 * math.pi * t / 4)
            st = self.sticker.rotate(rot, resample=Image.BICUBIC, expand=True)
            paste(im, st, self.ax1 - st.width + 40, self.ay0 - 70)
        return im.convert("RGB")

# ---- outputs -------------------------------------------------------------------------------------------
def storyboard(out):
    os.makedirs(out, exist_ok=True)
    sheet_rows = []
    for i, spec in enumerate(SLIDES):
        sl = Slide(i, spec)
        frames = []
        for tag, t in [("a_0.4s", 0.4), ("b_1.3s", 1.3), ("c_final", DUR - 0.01)]:
            fr = sl.frame(t)
            fr.save(os.path.join(out, f"{i + 1:02d}_{spec['key']}_{tag}.jpg"), quality=90)
            frames.append(fr)
        sheet_rows.append(frames)
        print("storyboard", i + 1, spec["key"], "column ends at y", sl.col_bottom)
    tw, th = 360, 450
    sheet = Image.new("RGB", (tw * 3 + 40, th * len(SLIDES) + 10 * (len(SLIDES) - 1)), (255, 255, 255))
    for r, frames in enumerate(sheet_rows):
        for c, fr in enumerate(frames):
            sheet.paste(fr.resize((tw, th), Image.LANCZOS), (c * (tw + 20), r * (th + 10)))
    sheet.save(os.path.join(out, "contact_sheet.jpg"), quality=88)
    finals = Image.new("RGB", (tw * 6 + 50, th), (255, 255, 255))
    for c, frames in enumerate(sheet_rows):
        finals.paste(frames[2].resize((tw, th), Image.LANCZOS), (c * (tw + 10), 0))
    finals.save(os.path.join(out, "finals_strip.jpg"), quality=88)

def export(out, video=True):
    os.makedirs(out, exist_ok=True)
    for i, spec in enumerate(SLIDES):
        sl = Slide(i, spec)
        name = f"{i + 1:02d}_{spec['key']}"
        sl.frame(DUR - 0.01).save(os.path.join(out, name + ".png"))
        if not video:
            print("exported", name + ".png"); continue
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
                                "-movflags", "+faststart", os.path.join(out, name + ".mp4")], stdin=subprocess.PIPE)
        for n in range(int(DUR * FPS)):
            enc.stdin.write(np.asarray(sl.frame(n / FPS)).tobytes())
        enc.stdin.close(); enc.wait()
        print("exported", name)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--storyboard"); ap.add_argument("--export")
    ap.add_argument("--stills-only", action="store_true", help="export PNG stills, no MP4 loops")
    a = ap.parse_args()
    if a.storyboard: storyboard(a.storyboard)
    if a.export: export(a.export, video=not a.stills_only)
