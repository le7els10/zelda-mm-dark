"""Repaint NPC/object textures with a local Stable Diffusion (ComfyUI) so they look realistic instead of drawn.

Per texture: optional skin-tone fix (cartoon yellow -> natural skin), img2img with ControlNet Tile so the layout
stays exactly where the model's UVs expect it, alpha restored, then the DarkMM gloomy grade. Text/number glyph
textures (mostly pure black/white) are left alone.

Needs ComfyUI running locally (default http://127.0.0.1:8188) with:
  checkpoints/Realistic_Vision_V6.0_NV_B1_fp16.safetensors
  controlnet/control_v11f1e_sd15_tile_fp16.safetensors
  vae/vae-ft-mse-840000-ema-pruned.safetensors

Usage:
  python npc_ai_retexture.py --src "D:/Games/zelda mm/mods/MM_Reloaded_v11.0.3_4K.o2r" \
      --objects object_cs --out "D:/Games/zelda mm/mods/DarkMM_NPC_AI.o2r" --preview previews/ai_cs
"""

import argparse
import os
import re
import hashlib
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import darkmm_textures as dm  # noqa: E402

CKPT = "Realistic_Vision_V6.0_NV_B1_fp16.safetensors"
CONTROLNET = "control_v11f1e_sd15_tile_fp16.safetensors"
VAE = "vae-ft-mse-840000-ema-pruned.safetensors"

# Two prompt families: skin (faces, ears, hands) and other materials (cloth, leather, hair, wood, metal).
# Mixing them in one prompt makes the model put scales on ears and eyes inside hair.
PROMPTS = {
    "skin": (
        "photorealistic close-up of natural human skin, fine pores, subtle redness and imperfections, soft "
        "matte skin, realistic eyelid and eyebrow hairs where present, muted natural tones, soft diffuse light, "
        "highly detailed, sharp focus",
        "cartoon, anime, illustration, drawing, painting, cel shading, flat colors, plastic, doll, cgi render, "
        "scales, reptile skin, snake skin, fish scales, mesh, net pattern, text, watermark, blurry, lowres",
    ),
    "material": (
        "photorealistic texture of a real material photographed up close, woven fabric with visible threads, "
        "worn leather, real hair strands, weathered wood, used and slightly dirty, muted natural colors, soft "
        "diffuse light, highly detailed, sharp focus",
        "cartoon, anime, illustration, drawing, painting, cel shading, flat colors, plastic, toy, cgi render, "
        "face, faces, eyes, person, people, animal, scales, reptile skin, text, letters, watermark, logo, "
        "blurry, lowres, oversaturated",
    ),
}
PROMPTS["face"] = (
    "photorealistic close-up of a real human face, natural skin with fine pores, subtle fine wrinkles and "
    "creases, faint crow's feet and laugh lines, slight under-eye shadows, realistic eyes with detailed iris, "
    "wet highlight and individual eyelashes, natural lips with fine lines, defined eyebrows with hair strands, "
    "muted natural tones, soft diffuse light, highly detailed, sharp focus",
    "cartoon, anime, illustration, drawing, painting, cel shading, flat colors, plastic, doll, cgi render, "
    "smooth airbrushed skin, scales, reptile skin, fish scales, mesh, extra eyes, deformed, text, watermark, "
    "blurry, lowres",
)
PROMPTS["skin"] = (
    PROMPTS["skin"][0] + ", fine wrinkles and skin creases, knuckle and joint folds, faint veins",
    PROMPTS["skin"][1],
)
DENOISE = {"skin": 0.45, "face": 0.45, "material": 0.5}

# Texture names that point at a body part; still checked against the colors so armor and wood are not "skin".
BODY_NAME = re.compile(r"(Eye|Mouth|Face|Nose|Brow|Lip|Cheek|Forehead|Skin|Ear(?!th|ring)|Hand|Arm(?!or|let)|Leg"
                       r"|Head|Chin|Neck|Finger|Foot|Feet|Knee|Thigh)")
NOT_SKIN_OBJECTS = ("object_um_Tex_",)  # Cremia's cart: olive paint and the ranch logo
FACE_NAME = re.compile(r"(Eye|Mouth|Face|Nose|Brow|Lip|Cheek|Forehead|Chin)")
NOT_BODY_NAME = re.compile(r"(Leaf|Leaves|Tree|Sword|Hilt|Fuse|Teeth|Wood|Armor|Cloth|Hair|Jewel|Emblem|Decal"
                           r"|Rivet|Mask|Moon|Beamos|Broom|Stalchild|Skull|Bone|Guay|Deku|Dodongo|Wolfos)")

# Character profile for the DarkMM grade applied after the AI pass (same as Link 3DS / NPC packs).
GRADE = dict(saturation=0.75, tint=(1.0, 0.96, 0.9), gamma=1.08, detail=0.3, grain=0.04, grime=0.12, streaks=0.0)


def natural_skin_weight(rgb):
    """0..1 per pixel: natural (peach/tan/brown) or cartoon-yellow skin colors."""
    img = Image.fromarray(rgb, "RGB").convert("HSV")
    h, s, v = [np.asarray(c, dtype=np.float32) for c in img.split()]
    hue = h / 255.0 * 360.0
    sat, val = s / 255.0, v / 255.0
    return (np.clip(1.0 - np.abs(hue - 30.0) / 45.0, 0, 1) * np.clip((sat - 0.08) / 0.12, 0, 1)
            * np.clip((0.97 - sat) / 0.2, 0, 1) * np.clip((val - 0.25) / 0.25, 0, 1))


def classify(name, rgb, alpha):
    base = name.split("/")[-1]
    opaque = alpha > 128
    if not opaque.any():
        return "material"
    if NOT_BODY_NAME.search(base):
        return "material"
    if BODY_NAME.search(base):
        if natural_skin_weight(rgb)[opaque].mean() > 0.1:
            return "face" if FACE_NAME.search(base) else "skin"
        return "material"
    if base.startswith(NOT_SKIN_OBJECTS):  # yellow paint/cloth that the color test mistakes for cartoon skin
        return "material"
    return "skin" if skin_weight(rgb)[opaque].mean() > 0.35 else "material"


def is_glyph(rgb):
    """Numbers, letters and logos: almost every pixel is near black or near white."""
    lum = rgb.astype(np.float32).mean(axis=-1)
    extreme = ((lum < 40) | (lum > 215)).mean()
    sat = (rgb.max(axis=-1).astype(np.float32) - rgb.min(axis=-1)) / 255.0
    return extreme > 0.85 and sat.mean() < 0.12


def skin_weight(rgb):
    """0..1 per pixel: how much it looks like cartoon yellow skin (bright, saturated, yellow hue)."""
    img = Image.fromarray(rgb, "RGB").convert("HSV")
    h, s, v = [np.asarray(c, dtype=np.float32) for c in img.split()]
    hue = h / 255.0 * 360.0
    sat, val = s / 255.0, v / 255.0
    return np.clip(1.0 - np.abs(hue - 62.0) / 22.0, 0, 1) * np.clip((sat - 0.15) / 0.2, 0, 1) * np.clip(
        (val - 0.35) / 0.3, 0, 1)


def fix_skin(rgb):
    """Move cartoon yellow skin (high-value, yellow/yellow-green hue) towards a natural skin tone,
    keeping the painted light and shadow."""
    img = Image.fromarray(rgb, "RGB").convert("HSV")
    h, s, v = [np.asarray(c, dtype=np.float32) for c in img.split()]
    hue = h / 255.0 * 360.0
    sat, val = s / 255.0, v / 255.0
    # Yellow skin sits around 55-70 degrees, saturated and bright.
    weight = np.clip(1.0 - np.abs(hue - 62.0) / 22.0, 0, 1) * np.clip((sat - 0.15) / 0.2, 0, 1) * np.clip(
        (val - 0.35) / 0.3, 0, 1)
    skin = np.array([0.80, 0.62, 0.52], dtype=np.float32)
    lum = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32) / 255.0
    target = skin[None, None, :] * (lum / 0.85)[..., None]
    out = rgb.astype(np.float32) / 255.0 * (1 - weight[..., None]) + target * weight[..., None]
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def workflow(image_name, width, height, denoise, control, seed, prefix, kind):
    positive, negative = PROMPTS[kind]
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["1", 1]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "5": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "6": {"class_type": "ImageScale", "inputs": {"image": ["5", 0], "upscale_method": "lanczos",
                                                      "width": width, "height": height, "crop": "disabled"}},
        "7": {"class_type": "VAEEncode", "inputs": {"pixels": ["6", 0], "vae": ["2", 0]}},
        "8": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET}},
        "9": {"class_type": "ControlNetApplyAdvanced",
              "inputs": {"positive": ["3", 0], "negative": ["4", 0], "control_net": ["8", 0], "image": ["6", 0],
                         "strength": control, "start_percent": 0.0, "end_percent": 1.0, "vae": ["2", 0]}},
        "10": {"class_type": "KSampler",
               "inputs": {"model": ["1", 0], "seed": seed, "steps": 28, "cfg": 6.0, "sampler_name": "dpmpp_2m",
                          "scheduler": "karras", "positive": ["9", 0], "negative": ["9", 1],
                          "latent_image": ["7", 0], "denoise": denoise}},
        "11": {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["2", 0]}},
        "12": {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": prefix}},
    }


def comfy_run(url, wf, timeout=600):
    req = urllib.request.Request(f"{url}/prompt", data=json.dumps({"prompt": wf}).encode(),
                                 headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req).read())
    if resp.get("node_errors"):
        raise RuntimeError(json.dumps(resp["node_errors"])[:800])
    pid = resp["prompt_id"]
    start = time.time()
    while time.time() - start < timeout:
        hist = json.loads(urllib.request.urlopen(f"{url}/history/{pid}").read())
        if pid in hist:
            entry = hist[pid]
            if entry.get("status", {}).get("status_str") == "error":
                raise RuntimeError(json.dumps(entry["status"])[:800])
            for node in entry.get("outputs", {}).values():
                for img in node.get("images", []):
                    return img["filename"], img.get("subfolder", "")
        time.sleep(0.5)
    raise TimeoutError(pid)


def work_size(w, h, target):
    """Size for SD 1.5: longest side `target`, both sides multiples of 64, at least 256."""
    s = target / max(w, h)
    return max(256, int(round(w * s / 64)) * 64), max(256, int(round(h * s / 64)) * 64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="+", required=True, help=".o2r files in load order (last wins)")
    ap.add_argument("--objects", nargs="+", help="object folders to process (default: every object)")
    ap.add_argument("--exclude", nargs="+", default=[], help="object folder prefixes to skip")
    ap.add_argument("--cache", help="folder for per-texture results; a rerun resumes instead of starting over")
    ap.add_argument("--out", required=True)
    ap.add_argument("--comfy", default="http://127.0.0.1:8188")
    ap.add_argument("--comfy-dir", default=os.environ.get("DARKMM_COMFY_DIR", "D:/AI/ComfyUI_windows_portable/ComfyUI"))
    ap.add_argument("--denoise", type=float, default=None, help="override the per-kind default (skin 0.4)")
    ap.add_argument("--control", type=float, default=0.75, help="ControlNet Tile strength (higher = closer layout)")
    ap.add_argument("--size", type=int, default=768, help="longest side used for the AI pass")
    ap.add_argument("--no-skin-fix", action="store_true")
    ap.add_argument("--no-grade", action="store_true")
    ap.add_argument("--base", default=os.environ.get("DARKMM_GAME_DIR", "D:/Games/zelda mm") + "/mm.o2r",
                    help="game assets extracted from the ROM, used to fix Reloaded textures saved under old names")
    ap.add_argument("--assemble-only", action="store_true",
                    help="only pack what the cache already holds (no AI calls), e.g. a partial pack mid-run")
    ap.add_argument("--redo-kinds", nargs="+", default=[], choices=["face", "skin", "material"],
                    help="recompute cached results of these kinds (e.g. after changing their prompt)")
    ap.add_argument("--exclude-names", help="regex: skip textures whose name matches (e.g. effects)")
    ap.add_argument("--preview")
    args = ap.parse_args()

    owner = {}
    for path in args.src:
        z = zipfile.ZipFile(path)
        for n in z.namelist():
            owner[n] = z
    def obj_of(n):
        parts = n.split("/")
        return parts[2] if len(parts) == 4 and parts[0] == "alt" and parts[1] == "objects" else None

    if not args.objects:
        args.objects = sorted({o for o in map(obj_of, owner) if o and not o.startswith(tuple(args.exclude))})
    wanted = [n for n in owner if obj_of(n) in set(args.objects)]
    if args.exclude_names:
        skip = re.compile(args.exclude_names, re.I)
        wanted = [n for n in wanted if not skip.search(n.split("/")[-1])]
    print(f"{len(wanted)} files in {len(args.objects)} objects", flush=True)
    cache = Path(args.cache) if args.cache else None
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
    in_dir = Path(args.comfy_dir) / "input"
    out_dir = Path(args.comfy_dir) / "output"
    in_dir.mkdir(parents=True, exist_ok=True)
    pairs, done, skipped = [], 0, 0
    grade = argparse.Namespace(**GRADE)
    aliases = dm.find_aliases(args.base, owner, args.objects) if args.base else {}
    print(f"{sum(len(v) for v in aliases.values())} textures recovered under their current game names")

    def write(name, data):
        out.writestr(name, data)
        for alias in aliases.get(name, []):
            out.writestr(alias, data)

    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_STORED, allowZip64=True) as out:
        for name in wanted:
            key = hashlib.md5(name.encode()).hexdigest()[:12]
            cached = cache / f"{key}.bin" if cache else None
            redone = cached.with_suffix(".redone") if cached else None
            if cached and cached.exists() and args.redo_kinds and not redone.exists():
                p = dm.parse(owner[name].read(name))
                if p is not None and classify(name, p[0][..., :3], p[0][..., 3]) in args.redo_kinds:
                    cached.unlink()
            if cached and cached.exists():
                write(name, cached.read_bytes())
                done += 1
                continue
            if args.assemble_only:
                if name in aliases:  # glyphs etc. never go through the AI: ship the HD original under its alias
                    p = dm.parse(owner[name].read(name))
                    if p is not None and is_glyph(p[0][..., :3]):
                        write(name, owner[name].read(name))
                continue
            parsed = dm.parse(owner[name].read(name))
            if parsed is None:
                continue
            pixels, encode = parsed
            h, w, _ = pixels.shape
            rgb, alpha = pixels[..., :3], pixels[..., 3]
            if is_glyph(rgb) or min(w, h) < 16:
                skipped += 1
                if name in aliases:  # keep the HD original, just make the game find it
                    write(name, owner[name].read(name))
                continue
            kind = classify(name, rgb, alpha)
            src = rgb if args.no_skin_fix else fix_skin(rgb)
            denoise = args.denoise if args.denoise is not None else DENOISE[kind]

            # Wrap padding so tiling textures stay seamless after the AI pass.
            pad = max(4, min(w, h) // 8)
            # Tileable textures (matching opposite edges) wrap; the rest mirror, so no fake seam appears.
            f = src.astype(np.float32)
            tiles = (np.abs(f[:, 0] - f[:, -1]).mean() < 12) and (np.abs(f[0] - f[-1]).mean() < 12)
            padded = np.pad(src, ((pad, pad), (pad, pad), (0, 0)), mode="wrap" if tiles else "reflect")
            in_name = f"darkmm_{key}.png"
            Image.fromarray(padded, "RGB").save(in_dir / in_name)
            pw, ph = work_size(w + 2 * pad, h + 2 * pad, args.size)
            seed = int(key[:8], 16)
            fname, sub = comfy_run(args.comfy, workflow(in_name, pw, ph, denoise, args.control, seed,
                                                        f"darkmm/{key}", kind))
            ai = Image.open(out_dir / sub / fname).convert("RGB").resize((w + 2 * pad, h + 2 * pad), Image.LANCZOS)
            ai = np.asarray(ai)[pad:pad + h, pad:pad + w]

            new = np.concatenate([ai, alpha[..., None]], axis=-1)
            if not args.no_grade:
                new = dm.retouch(new, name, grade)
            data = encode(new)
            if cached:
                cached.write_bytes(data)
                if args.redo_kinds:
                    redone.touch()  # a resumed --redo-kinds run keeps this result
            write(name, data)
            (in_dir / in_name).unlink(missing_ok=True)
            (out_dir / sub / fname).unlink(missing_ok=True)
            done += 1
            print(f"  [{done}] {name.split('/')[-1]} {w}x{h} {kind}", flush=True)
            if args.preview and len(pairs) < 24:
                pairs.append((pixels, new))

    if args.preview and pairs:
        Path(args.preview).mkdir(parents=True, exist_ok=True)
        for i in range(0, len(pairs), 8):
            dm.preview_sheet(pairs[i:i + 8], Path(args.preview) / f"sheet_{i // 8 + 1}.png")
    print(f"AI retextured {done}, skipped {skipped} glyph/tiny -> {args.out}")


if __name__ == "__main__":
    main()
