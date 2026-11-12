#!/usr/bin/env python3
"""Scene 03b - Hilary's shocked reaction (5 s, 1080x1920, 30 fps).

Camera-only animation over the portal-exit still: the face pixels are never
warped, so there is no mouth stretching or morphing. The whispered line is
meant to sit as off-screen voice-over (pass --vo path/to/whisper.wav).

  python3 build_shocked_reaction.py [--src reference/03_portal_exit.png] [--vo vo.wav]
"""
import argparse, subprocess, sys, tempfile, wave
import numpy as np
from pathlib import Path
from PIL import Image

W, H, FPS, DUR = 1080, 1920, 30, 5.0
HERE = Path(__file__).resolve().parent

# Keyframes: time (s), crop centre x/y and crop width, as fractions of the source.
KEYS = [
    (0.0, 0.413, 0.222, 0.360),   # dramatic close-up on face
    (2.0, 0.412, 0.213, 0.270),   # slow push-in on the eyes
    (3.0, 0.414, 0.212, 0.258),   # near-still hold: silent observation
    (5.0, 0.575, 0.425, 0.850),   # drift up-right and pull back: skyline reveal
]

def ease(u):  # smootherstep
    return u * u * u * (u * (6 * u - 15) + 10)

def cam(t):
    for (t0, *a), (t1, *b) in zip(KEYS, KEYS[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            # linear in the push/hold so it never stalls; eased for the reveal
            u = ease(u) if t0 >= 3.0 else u
            cx, cy = (a[i] + (b[i] - a[i]) * u for i in (0, 1))
            w = a[2] * (b[2] / a[2]) ** u          # exponential zoom = constant perceived speed
            return cx, cy, w
    return KEYS[-1][1:]

def write_ambience(path, sr=48000):
    """Synthesized futuristic-city bed: low rumble, airy wash, mains hum, passing vehicle."""
    rng = np.random.default_rng(2150)
    n = int(DUR * sr)
    t = np.arange(n) / sr

    def band(lo, hi):
        spec = np.fft.rfft(rng.standard_normal(n))
        f = np.fft.rfftfreq(n, 1 / sr)
        spec[(f < lo) | (f > hi)] = 0
        x = np.fft.irfft(spec, n)
        return x / np.abs(x).max()

    rumble = band(30, 220) * 0.55
    air = band(1500, 6000) * 0.10 * (0.7 + 0.3 * np.sin(2 * np.pi * 0.4 * t))
    hum = 0.10 * np.sin(2 * np.pi * 55 * t) + 0.04 * np.sin(2 * np.pi * 110 * t)
    # hover vehicle fly-by peaking at 4.1 s, with a falling pitch
    fly_env = np.exp(-((t - 4.1) / 0.55) ** 2)
    fly = 0.16 * fly_env * np.sin(2 * np.pi * np.cumsum(190 - 45 * np.tanh((t - 4.1) * 2.5)) / sr)
    pan = np.clip((t - 3.3) / 1.6, 0, 1)
    swell = 0.22 + 0.78 * np.clip((t - 2.6) / 1.6, 0, 1)      # stays low under the whisper
    fade = np.clip(t / 0.3, 0, 1) * np.clip((DUR - t) / 0.3, 0, 1)
    bed = (rumble + air + hum) * swell * fade
    left = bed + fly * (1 - pan) * fade
    right = bed + fly * pan * fade
    st = np.stack([left, right], 1)
    st = (st / max(1.0, np.abs(st).max() / 0.89) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(st.tobytes())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(HERE / "reference/03_portal_exit_preview.webp"))
    ap.add_argument("--vo", help="whispered voice-over audio file (optional)")
    ap.add_argument("--out", default=str(HERE / "output/03b_shocked_reaction.mp4"))
    args = ap.parse_args()

    src = Image.open(args.src).convert("RGB")
    sw, sh = src.size
    n = int(DUR * FPS)

    # Audio: quiet city bed that swells after the whisper; VO (if any) starts at 0.4 s.
    amb_wav = Path(tempfile.gettempdir()) / "03b_ambience.wav"
    write_ambience(amb_wav)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(amb_wav)]
    if args.vo:
        cmd += ["-i", args.vo, "-filter_complex",
                "[2:a]adelay=400:all=1,aresample=48000,aformat=channel_layouts=stereo[vo];"
                "[1:a][vo]amix=inputs=2:normalize=0:duration=first[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-t", str(DUR), "-movflags", "+faststart", args.out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        cx, cy, w = cam(i / FPS)
        cw = w * sw
        ch = cw * H / W
        x0 = min(max(cx * sw - cw / 2, 0), sw - cw)
        y0 = min(max(cy * sh - ch / 2, 0), sh - ch)
        frame = src.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))
        p.stdin.write(frame.tobytes())
    p.stdin.close()
    sys.exit(p.wait())

if __name__ == "__main__":
    main()
