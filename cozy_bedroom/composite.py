#!/usr/bin/env python3
"""Composite the two rendered layers into the final plate.

Background gets a lens (disc) blur for shallow depth of field, then bloom, haze,
vignette and grain are applied; the desk foreground stays sharp.

  python3 composite.py [--dir output] [--name cozy_bedroom_night]
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument('--dir', default=str(Path(__file__).resolve().parent / 'output'))
ap.add_argument('--name', default='cozy_bedroom_night')
a = ap.parse_args()
d = Path(a.dir)

def lin(img):   # sRGB 8-bit -> linear float
    return (np.asarray(img, np.float32) / 255.0) ** 2.2

def srgb(x):
    return Image.fromarray((np.clip(x, 0, 1) ** (1 / 2.2) * 255 + 0.5).astype(np.uint8))

def disc_blur(x, radius):
    """Convolve with a flat disc (bokeh-shaped kernel) via FFT."""
    h, w, _ = x.shape
    r = int(np.ceil(radius))
    pad = np.pad(x, ((r, r), (r, r), (0, 0)), mode='edge')
    H, W = pad.shape[:2]
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    k = np.clip(radius + 0.5 - np.hypot(xx, yy), 0, 1).astype(np.float32)
    k /= k.sum()
    K = np.zeros((H, W), np.float32)
    K[:2 * r + 1, :2 * r + 1] = k
    K = np.roll(K, (-r, -r), (0, 1))
    Kf = np.fft.rfft2(K)
    out = np.empty_like(pad)
    for c in range(3):
        out[..., c] = np.fft.irfft2(np.fft.rfft2(pad[..., c]) * Kf, s=(H, W))
    return np.clip(out[r:r + h, r:r + w], 0, None)

def gauss(x, radius):
    out = np.empty_like(x)
    for c in range(x.shape[2]):
        im = Image.fromarray(np.clip(x[..., c] * 255, 0, 255).astype(np.uint8))
        out[..., c] = np.asarray(im.filter(ImageFilter.GaussianBlur(radius)), np.float32) / 255
    return out

bg_img = Image.open(d / '_layer_bg.png').convert('RGB')
fg_img = Image.open(d / '_layer_fg.png').convert('RGBA')
W, H = bg_img.size
s = W / 1920.0

bg = lin(bg_img)
# boost highlights before the lens blur so lights open up into bright bokeh discs
lum = bg.max(axis=2, keepdims=True)
bg = bg * (1 + 3.0 * np.clip((lum - 0.8) / 0.2, 0, 1) ** 2)
bg = disc_blur(bg, 6.5 * s)
bg = bg / (1 + 0.18 * bg)            # soft roll-off

# haze: purple/magenta atmosphere, denser toward the neon wall and low in the room
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
u, v = xx / W, yy / H
haze = (0.012 + 0.035 * np.exp(-((u - 0.25) ** 2) / 0.08) + 0.03 * np.exp(-((u - 0.78) ** 2) / 0.05))[..., None]
haze = haze * np.array([0.75, 0.28, 1.0], np.float32)
bg = bg + haze * (1 - bg)

fg = np.asarray(fg_img, np.float32) / 255.0
alpha = fg[..., 3:4]
# very slight softening at the far edge of the desk and near the lens for depth
comp = bg * (1 - alpha) + (fg[..., :3] ** 2.2) * alpha

# bloom
bright = np.clip(comp - 0.75, 0, None)
comp = comp + 0.7 * gauss(bright, 12 * s) + 0.45 * gauss(bright, 44 * s)
glow = gauss(np.clip(comp, 0, 1), 90 * s)
comp = comp + 0.05 * glow

# grade: lift purple in shadows, warm highlights, vignette
l = comp.mean(axis=2, keepdims=True)
comp = comp + (1 - np.clip(l * 4, 0, 1)) * np.array([0.012, 0.0, 0.03], np.float32)
comp = comp * (1 + np.clip(l - 0.5, 0, 1) * np.array([0.10, 0.03, -0.06], np.float32))
vig = 1 - 0.42 * np.clip(np.hypot((u - 0.5) * 1.15, (v - 0.48) * 1.25) / 0.75, 0, 1.3) ** 2.2
comp = comp * vig[..., None]
comp = comp / (1 + 0.06 * comp)

out = np.clip(comp, 0, 1) ** (1 / 2.2)
rng = np.random.default_rng(3)
out = out + rng.normal(0, 0.006, (H, W, 1)).astype(np.float32)
final = Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8))
final.save(d / f'{a.name}.png', optimize=True)
final.resize((1920, 1080), Image.LANCZOS).save(d / f'{a.name}_1080p.jpg', quality=93)
print('wrote', d / f'{a.name}.png', final.size)
