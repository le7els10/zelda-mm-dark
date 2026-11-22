"""AI pass for scene (environment) textures: walls, floors, rocks, wood. Same ComfyUI img2img + ControlNet Tile setup
as npc_ai_retexture.py, then the regional DarkMM grade (darkmm_textures.scene_params) so each area keeps its mood.

The AI works at ~768 px while Reloaded scenes are up to 4K, so the original's fine detail above the AI resolution is
added back on top of the upscaled result. Water, sky-like gradients and tiny textures are left alone.

Usage:
  python scene_ai_retexture.py --scenes Z2_TOWN Z2_BACKTOWN --cache D:/AI/darkmm_npc_ai/cache_scenes \
      --out D:/AI/darkmm_npc_ai/DarkMM_Scenes_AI.o2r [--preview ../previews/scenes] [--assemble-only]
Needs the ComfyUI server from npc_ai_retexture.py running. Load the pack after DarkMM.o2r.
"""

import argparse
import os
import colorsys
import hashlib
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

import darkmm_textures as dm
import npc_ai_retexture as ai

SRC = os.environ.get("DARKMM_GAME_DIR", "D:/Games/zelda mm") + "/mods/MM_Reloaded_v11.0.3_4K.o2r"

ai.PROMPTS["scene"] = (
    "photograph of a real weathered surface up close, old stone, brick, plaster, wooden planks, roof tiles, "
    "packed dirt and rock as the image shows, cracks, chipped edges, moss and dirt in the crevices, natural "
    "wear and stains, muted natural colors, soft diffuse light, highly detailed, sharp focus",
    "cartoon, anime, illustration, drawing, painting, cel shading, flat colors, plastic, toy, cgi render, face, "
    "faces, eyes, person, people, animal, text, letters, watermark, logo, blurry, lowres, oversaturated",
)
DENOISE = 0.45
# The AI already adds detail and grain: keep the regional color grade, go lighter on the synthetic noise.
GRADE_OVERRIDE = {"detail": 0.25, "grain": 0.05}


def skip_reason(rgb, alpha):
    h, w, _ = rgb.shape
    if min(w, h) < 32:
        return "tiny"
    if (alpha < 128).mean() > 0.7:
        return "mostly transparent"
    f = rgb.astype(np.float32)
    tiles = np.abs(f[:, 0] - f[:, -1]).mean() < 14 and np.abs(f[0] - f[-1]).mean() < 14
    m = f.reshape(-1, 3).mean(0) / 255
    hue, sat, _ = colorsys.rgb_to_hsv(*m)
    if tiles and 0.42 < hue < 0.66 and sat > 0.2:
        return "water"
    # Glows, light shafts and gradients: almost no local change over the opaque part.
    gray = np.asarray(Image.fromarray(rgb).convert("L").resize((128, 128)), np.float32)
    opaque = np.asarray(Image.fromarray(alpha).resize((128, 128)))[:-1, :-1] > 128
    d = np.abs(np.diff(gray, axis=1))[:-1] + np.abs(np.diff(gray, axis=0))[:, :-1]
    if not opaque.any() or np.median(d[opaque]) <= 3.0:
        return "smooth"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", nargs="+", help="scene folder prefixes (default: all scenes)")
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview")
    ap.add_argument("--assemble-only", action="store_true")
    ap.add_argument("--size", type=int, default=768)
    ap.add_argument("--control", type=float, default=0.75)
    ap.add_argument("--keep-detail", type=float, default=0.6, help="how much original fine detail to add back")
    ap.add_argument("--comfy", default="http://127.0.0.1:8188")
    ap.add_argument("--comfy-dir", default=os.environ.get("DARKMM_COMFY_DIR", "D:/AI/ComfyUI_windows_portable/ComfyUI"))
    args = ap.parse_args()

    src = zipfile.ZipFile(SRC)
    names = [n for n in src.namelist() if n.startswith("alt/scenes/") and len(n.split("/")) == 5
             and (not args.scenes or n.split("/")[3].startswith(tuple(args.scenes)))]
    print(f"{len(names)} scene textures", flush=True)
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    in_dir, out_dir = Path(args.comfy_dir) / "input", Path(args.comfy_dir) / "output"
    pairs, done, skipped = [], 0, {}
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_STORED, allowZip64=True) as out:
        for name in names:
            key = hashlib.md5(name.encode()).hexdigest()[:12]
            cached = cache / f"{key}.bin"
            if cached.exists():
                out.writestr(name, cached.read_bytes())
                done += 1
                continue
            if args.assemble_only:
                continue
            parsed = dm.parse(src.read(name))
            if parsed is None:
                continue
            pixels, encode = parsed
            h, w, _ = pixels.shape
            rgb, alpha = pixels[..., :3], pixels[..., 3]
            reason = skip_reason(rgb, alpha)
            if reason:
                skipped[reason] = skipped.get(reason, 0) + 1
                continue

            pad = max(4, min(w, h) // 8)
            f = rgb.astype(np.float32)
            tiles = (np.abs(f[:, 0] - f[:, -1]).mean() < 12) and (np.abs(f[0] - f[-1]).mean() < 12)
            padded = np.pad(rgb, ((pad, pad), (pad, pad), (0, 0)), mode="wrap" if tiles else "reflect")
            in_name = f"scene_{key}.png"
            Image.fromarray(padded, "RGB").save(in_dir / in_name)
            pw, ph = ai.work_size(w + 2 * pad, h + 2 * pad, args.size)
            fname, sub = ai.comfy_run(args.comfy, ai.workflow(in_name, pw, ph, DENOISE, args.control,
                                                              int(key[:8], 16), f"darkmm/scene_{key}", "scene"))
            img = Image.open(out_dir / sub / fname).convert("RGB").resize((w + 2 * pad, h + 2 * pad), Image.LANCZOS)
            new_rgb = np.asarray(img, np.float32)[pad:pad + h, pad:pad + w]

            # Add back the original detail finer than the AI resolution (only matters for big textures).
            scale = w / (pw * w / (w + 2 * pad))
            if scale > 1.5:
                blurred = np.asarray(Image.fromarray(rgb).filter(ImageFilter.GaussianBlur(scale * 0.6)), np.float32)
                new_rgb += (f - blurred) * args.keep_detail
            new_rgb = np.clip(new_rgb, 0, 255).astype(np.uint8)

            grade = argparse.Namespace(**{**dm.SCENE_PARAMS, **dm.scene_params(name), **GRADE_OVERRIDE})
            new = dm.retouch(np.concatenate([new_rgb, alpha[..., None]], axis=-1), name, grade)
            data = encode(new)
            cached.write_bytes(data)
            out.writestr(name, data)
            (in_dir / in_name).unlink(missing_ok=True)
            (out_dir / sub / fname).unlink(missing_ok=True)
            done += 1
            print(f"  [{done}] {name.split('/')[-1]} {w}x{h}", flush=True)
            if args.preview and len(pairs) < 32:
                pairs.append((pixels, new))
    if args.preview and pairs:
        Path(args.preview).mkdir(parents=True, exist_ok=True)
        for i in range(0, len(pairs), 8):
            dm.preview_sheet(pairs[i:i + 8], Path(args.preview) / f"sheet_{i // 8 + 1}.png")
    print(f"done {done}, skipped {skipped} -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
