#!/usr/bin/env python3
"""Cut a product out of a photo or screenshot for the carousel.

  python3 cutout.py IN.jpg OUT.png [--crop L,T,R,B] [--mode model|white|rect] [--trim-top N]

  --crop      crop to the product first (drop screenshot UI, captions, borders)
  --mode      model : rembg isnet-general-use (default; best for bottles/tubes on colored bgs)
              white : flood-fill pure-white background from the edges (white products on white,
                      pale boxes the model loses, e.g. Coconu's pale-blue box)
              rect  : keep the crop as-is (flat boxes/cartons, e.g. Pre-Seed)
  --trim-top  shave N px off the top of the result (a ragged edge where the product ran out of frame)

The model needs `pip install "rembg[cpu]"`; its weights download from github.com release assets.
Always look at the cut-outs on a tan background before using them.
"""
import argparse
import numpy as np
from PIL import Image, ImageFilter

def white_bg_cut(im, thresh=250, erode=1):
    from scipy import ndimage
    a = np.asarray(im).astype(int)
    lab, _ = ndimage.label(a.min(2) >= thresh)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    fg = ndimage.binary_fill_holes(~np.isin(lab, list(border)))
    fg = ndimage.binary_opening(fg, iterations=2)
    if erode:
        fg = ndimage.binary_erosion(fg, iterations=erode)
    alpha = Image.fromarray((fg * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    out = im.convert("RGBA"); out.putalpha(alpha)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--crop"); ap.add_argument("--mode", default="model", choices=["model", "white", "rect"])
    ap.add_argument("--trim-top", type=int, default=0)
    a = ap.parse_args()
    im = Image.open(a.src).convert("RGB")
    if a.crop:
        im = im.crop(tuple(int(v) for v in a.crop.split(",")))
    if a.mode == "model":
        from rembg import remove, new_session
        out = remove(im, session=new_session("isnet-general-use"), post_process_mask=True)
    elif a.mode == "white":
        out = white_bg_cut(im)
    else:
        out = im.convert("RGBA")
    bbox = out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    out = out.crop(bbox)
    if a.trim_top:
        out = out.crop((0, a.trim_top, out.width, out.height))
    out.save(a.out)
    print(a.out, out.size)

if __name__ == "__main__":
    main()
