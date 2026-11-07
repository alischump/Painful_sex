#!/usr/bin/env python3
"""Crop each brand photo to the product and remove its background (rembg / isnet)."""
import os
from PIL import Image
from rembg import remove, new_session
HERE = os.path.dirname(os.path.abspath(__file__)) + "/.."
CROPS = {  # (left, top, right, bottom) in source px - drops UI cards / captions from screenshots
    "coconu": (45, 45, 790, 1165), "foria": (30, 30, 1095, 1090), "uberlube": (20, 60, 1020, 1075),
    "preseed": (60, 55, 445, 785), "slippery": (90, 45, 565, 1245), "maude": (90, 40, 645, 1405),
}
sess = new_session("isnet-general-use")
for name, box in CROPS.items():
    im = Image.open(f"{HERE}/products_src/{name}.jpg").convert("RGB").crop(box)
    out = remove(im, session=sess, post_process_mask=True)
    out = out.crop(out.getchannel("A").point(lambda a: 255 if a > 20 else 0).getbbox())
    out.save(f"{HERE}/products_cut/{name}.png"); print(name, out.size)

# --- Overrides: products on pure-white backgrounds that the model mis-segments -------------
import numpy as np
from scipy import ndimage
from PIL import ImageFilter

def white_bg_cut(im, thresh=250, erode=1):
    a = np.asarray(im).astype(int)
    cand = a.min(2) >= thresh                     # near-white pixels
    lab, _ = ndimage.label(cand)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(border))
    fg = ndimage.binary_fill_holes(~bg)
    fg = ndimage.binary_opening(fg, iterations=2)
    if erode: fg = ndimage.binary_erosion(fg, iterations=erode)
    alpha = Image.fromarray((fg * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    out = im.convert("RGBA"); out.putalpha(alpha)
    return out.crop(alpha.point(lambda v: 255 if v > 20 else 0).getbbox())

OVERRIDES = {"coconu": (45, 45, 790, 1165), "preseed": (70, 84, 386, 779)}
for name, box in OVERRIDES.items():
    im = Image.open(f"{HERE}/products_src/{name}.jpg").convert("RGB").crop(box)
    out = white_bg_cut(im) if name == "coconu" else im.convert("RGBA")
    out.save(f"{HERE}/products_cut/{name}.png"); print("override", name, out.size)

# Final trims: Coconu's tube top runs out of the source frame (ragged) -> straight seal edge;
# Pre-Seed's lid flap strip removed.
for name, top in {"coconu": 175, "preseed": 20}.items():
    im = Image.open(f"{HERE}/products_cut/{name}.png"); im.crop((0, top, im.width, im.height)).save(f"{HERE}/products_cut/{name}.png")
