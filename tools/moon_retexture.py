"""Moon pass: keeps the N64 Moon design (same layout, colors and shapes) but gives each part its own realistic
prompt: cracked rock for the face, a wet bloodshot eye, yellowed teeth with gums.

Usage: python moon_retexture.py --out D:/AI/darkmm_npc_ai/DarkMM_Moon.o2r [--preview ../previews/moon]
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
NEG = ("cartoon, anime, illustration, drawing, flat colors, plastic, toy, cgi render, text, watermark, logo, "
       "blurry, lowres, human face, person")

ai.PROMPTS["moon_rock"] = (
    "macro photograph of ancient cracked grey-brown moon rock, deep craters, fine fractures and pits, dust in "
    "the crevices, harsh raking light, ominous, highly detailed, sharp focus",
    NEG,
)
ai.PROMPTS["moon_eye"] = (
    "extreme macro photograph of a monstrous glowing orange-red eye iris, wet glossy surface, fibrous iris "
    "detail, thin red veins, glowing amber center, black pupil, ominous, highly detailed, sharp focus",
    NEG,
)
ai.PROMPTS["moon_teeth"] = (
    "macro photograph of a row of large old yellowed teeth with cracks and stains, wet dark red gums, "
    "grotesque, ominous, highly detailed, sharp focus",
    NEG,
)

# texture name suffix -> (prompt kind, denoise)
TARGETS = {
    "gMoonFaceTex": ("moon_rock", 0.5),
    "gMoonFarSideTex": ("moon_rock", 0.5),
    "gOpenMouthMoonFaceTex": ("moon_rock", 0.5),
    "gOpenMouthMoonFarSideTex": ("moon_rock", 0.5),
    "gMoonEyeTex": ("moon_eye", 0.45),
    "gOpenMouthMoonEyesTex": ("moon_eye", 0.45),
    "gMoonTeethTex": ("moon_teeth", 0.45),
    "gOpenMouthMoonTeethTex": ("moon_teeth", 0.45),
}
GRADE = dict(saturation=0.85, tint=(1.0, 0.96, 0.92), gamma=1.05, detail=0.35, grain=0.03, grime=0.1, streaks=0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview")
    ap.add_argument("--comfy", default="http://127.0.0.1:8188")
    ap.add_argument("--comfy-dir", default=os.environ.get("DARKMM_COMFY_DIR", "D:/AI/ComfyUI_windows_portable/ComfyUI"))
    args = ap.parse_args()

    src = zipfile.ZipFile(SRC)
    names = [n for n in src.namelist() if n.split("/")[-1] in TARGETS and "/object_fall" in n]
    in_dir, out_dir = Path(args.comfy_dir) / "input", Path(args.comfy_dir) / "output"
    grade = argparse.Namespace(**GRADE)
    pairs = []
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_STORED) as out:
        for name in names:
            kind, denoise = TARGETS[name.split("/")[-1]]
            pixels, encode = dm.parse(src.read(name))
            h, w, _ = pixels.shape
            rgb, alpha = pixels[..., :3], pixels[..., 3]
            pad = max(4, min(w, h) // 8)
            f = rgb.astype(np.float32)
            tiles = (np.abs(f[:, 0] - f[:, -1]).mean() < 12) and (np.abs(f[0] - f[-1]).mean() < 12)
            padded = np.pad(rgb, ((pad, pad), (pad, pad), (0, 0)), mode="wrap" if tiles else "reflect")
            key = hashlib.md5(name.encode()).hexdigest()[:12]
            in_name = f"moon_{key}.png"
            Image.fromarray(padded, "RGB").save(in_dir / in_name)
            pw, ph = ai.work_size(w + 2 * pad, h + 2 * pad, 1024)
            fname, sub = ai.comfy_run(args.comfy, ai.workflow(in_name, pw, ph, denoise, 0.8, int(key[:8], 16),
                                                              f"darkmm/moon_{key}", kind))
            img = Image.open(out_dir / sub / fname).convert("RGB").resize((w + 2 * pad, h + 2 * pad), Image.LANCZOS)
            new_rgb = np.asarray(img)[pad:pad + h, pad:pad + w]
            new = dm.retouch(np.concatenate([new_rgb, alpha[..., None]], axis=-1), name, grade)
            out.writestr(name, encode(new))
            (in_dir / in_name).unlink(missing_ok=True)
            (out_dir / sub / fname).unlink(missing_ok=True)
            pairs.append((pixels, new))
            print(name.split("/")[-1], kind, flush=True)
    if args.preview:
        Path(args.preview).mkdir(parents=True, exist_ok=True)
        dm.preview_sheet(pairs, Path(args.preview) / "moon.png")


if __name__ == "__main__":
    main()
