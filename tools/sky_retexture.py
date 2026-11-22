"""Sky pass: realistic, heavier clouds for the day skybox (d2_fine_static / d2_cloud_static).

The game tints these textures with the time-of-day sky colors, so after the AI pass every channel is matched back
to the original mean (slightly darker) and the result stays a horizontally tileable strip.

Usage: python sky_retexture.py --out D:/AI/darkmm_npc_ai/DarkMM_Sky.o2r [--preview ../previews/sky]
Needs the ComfyUI server from npc_ai_retexture.py running.
"""

import argparse
import os
import hashlib
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

import darkmm_textures as dm
import npc_ai_retexture as ai

SRC = os.environ.get("DARKMM_GAME_DIR", "D:/Games/zelda mm") + "/mods/MM_Reloaded_v11.0.3_4K.o2r"

ai.PROMPTS["sky"] = (
    "photograph of a real overcast sky, heavy layered storm clouds, dense cumulus and stratus, soft volumetric "
    "light breaking through, ominous brooding atmosphere, natural cloud detail, highly detailed, sharp focus",
    "cartoon, anime, illustration, drawing, painting, flat colors, cgi render, text, watermark, logo, birds, "
    "airplane, sun, moon, trees, buildings, ground, horizon line, people, blurry, lowres",
)


def match_colors(new, ref, darken):
    """Per-channel mean/std transfer of `new` onto `ref`, then a slight darkening and extra contrast."""
    out = np.empty_like(new, dtype=np.float32)
    for c in range(3):
        n, r = new[..., c].astype(np.float32), ref[..., c].astype(np.float32)
        out[..., c] = (n - n.mean()) / (n.std() + 1e-3) * r.std() * 1.15 + r.mean() * (1.0 - darken)
    return np.clip(out, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview")
    ap.add_argument("--denoise", type=float, default=0.55)
    ap.add_argument("--darken", type=float, default=0.08)
    ap.add_argument("--size", type=int, default=1536)
    ap.add_argument("--comfy", default="http://127.0.0.1:8188")
    ap.add_argument("--comfy-dir", default=os.environ.get("DARKMM_COMFY_DIR", "D:/AI/ComfyUI_windows_portable/ComfyUI"))
    args = ap.parse_args()

    src = zipfile.ZipFile(SRC)
    names = sorted(n for n in src.namelist() if "/d2_fine_static/" in n or "/d2_cloud_static/" in n)
    in_dir, out_dir = Path(args.comfy_dir) / "input", Path(args.comfy_dir) / "output"
    pairs = []
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_STORED) as out:
        for name in names:
            pixels, encode = dm.parse(src.read(name))
            h, w, _ = pixels.shape
            rgb, alpha = pixels[..., :3], pixels[..., 3]
            # Wrap left/right (the strip goes around the horizon), mirror top/bottom.
            pad = max(8, min(w, h) // 8)
            padded = np.pad(rgb, ((0, 0), (pad, pad), (0, 0)), mode="wrap")
            padded = np.pad(padded, ((pad, pad), (0, 0), (0, 0)), mode="reflect")
            key = hashlib.md5(name.encode()).hexdigest()[:12]
            in_name = f"sky_{key}.png"
            Image.fromarray(padded, "RGB").save(in_dir / in_name)
            pw, ph = ai.work_size(w + 2 * pad, h + 2 * pad, args.size)
            fname, sub = ai.comfy_run(args.comfy, ai.workflow(in_name, pw, ph, args.denoise, 0.7, int(key[:8], 16),
                                                              f"darkmm/sky_{key}", "sky"))
            img = Image.open(out_dir / sub / fname).convert("RGB").resize((w + 2 * pad, h + 2 * pad), Image.LANCZOS)
            ai_rgb = np.asarray(img)[pad:pad + h, pad:pad + w]
            new_rgb = match_colors(ai_rgb, rgb, args.darken)
            # Blend the wrapped seam back to the original edge columns so the strip still tiles.
            ramp = np.clip(np.minimum(np.arange(w), w - 1 - np.arange(w)) / max(pad, 1), 0, 1)[None, :, None]
            new_rgb = (new_rgb * ramp + rgb * (1 - ramp)).astype(np.uint8)
            new = np.concatenate([new_rgb, alpha[..., None]], axis=-1)
            out.writestr(name, encode(new))
            (in_dir / in_name).unlink(missing_ok=True)
            (out_dir / sub / fname).unlink(missing_ok=True)
            pairs.append((pixels, new))
            print(name.split("/")[-1], flush=True)
    if args.preview:
        Path(args.preview).mkdir(parents=True, exist_ok=True)
        dm.preview_sheet(pairs, Path(args.preview) / "sky.png")


if __name__ == "__main__":
    main()
