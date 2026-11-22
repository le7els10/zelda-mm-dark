"""Hand-tuned AI pass for key characters (Skull Kid, Majora's Mask and Majora): each texture group gets its own
prompt instead of the generic skin/material ones. The layout and colors are kept (ControlNet Tile), only the
material changes: cursed lacquered wood for the mask, bone spikes, bark skin, ragged cloth, sinewy flesh.

Usage: python special_retexture.py --out D:/AI/darkmm_npc_ai/DarkMM_SkullKid.o2r [--preview ../previews/skullkid]
Needs the ComfyUI server from npc_ai_retexture.py running.
"""

import argparse
import os
import hashlib
import re
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

import darkmm_textures as dm
import npc_ai_retexture as ai

SRC = os.environ.get("DARKMM_GAME_DIR", "D:/Games/zelda mm") + "/mods/MM_Reloaded_v11.0.3_4K.o2r"
OBJECTS = ("object_stk", "object_osn", "object_ob", "object_boss07")
NEG = ("cartoon, anime, illustration, drawing, painting, cel shading, flat colors, plastic, toy, cgi render, text, "
       "letters, watermark, logo, blurry, lowres, oversaturated")

PROMPTS = {
    "mask": ("photograph of an ancient carved wooden ritual mask surface, cracked old lacquer paint, faded colors, "
             "chipped edges with bare aged wood grain showing through, dark stains in the cracks, cursed relic, eerie, "
             "soft diffuse light, highly detailed, sharp focus", NEG + ", human face, person"),
    "mask_eye": ("macro photograph of a glowing sickly yellow-orange eye painted on an old cursed mask, glossy wet "
                 "surface, thin red bloodshot veins, deep black pupil, menacing, highly detailed, sharp focus",
                 NEG + ", person, eyelashes"),
    "bone": ("macro photograph of old yellowed bone horn, cracked ivory surface, dark stains and pits, aged, eerie, "
             "highly detailed, sharp focus", NEG + ", face, eyes, person"),
    "bark": ("macro photograph of dark weathered tree bark used as skin, cracked dry old wood, deep fissures, "
             "faint moss in the crevices, eerie, highly detailed, sharp focus", NEG + ", face, eyes, person, leaves"),
    "cloth": ("photograph of torn ragged old fabric, frayed threads, moth-eaten holes, dirt and stains, faded dye, "
              "highly detailed, sharp focus", NEG + ", face, eyes, person, animal"),
    "flesh": ("macro photograph of dark sinewy organic flesh, taut veins and tendons, wet glistening surface, "
              "grotesque, highly detailed, sharp focus", NEG + ", face, person, scales"),
}

# (regex on texture name, prompt kind, denoise). First match wins; no match = keep the current version.
RULES = [
    (r"TitleCard|Beam|Fire|Electricity|Overlay|Unused|Ocarina|Flute|Ring|Beak|BossMask|Whip|Goht|Gyorg|Twinmold"
     r"|SalesmanEye", None, 0),
    (r"MajorasMaskWith|MajorasIncarnationMask", "mask", 0.5),
    (r"MajorasMaskTentacle|MajoraBody|MajoraHand|MajoraStripes|MajorasWrathEar", "flesh", 0.5),
    (r"Eye", "mask_eye", 0.45),
    (r"Spike", "bone", 0.55),
    (r"MajorasMask", "mask", 0.55),
    (r"SkullKid(Head)?Skin|SkullKidHand", "bark", 0.5),
    (r"Shawl|Fringe|PantsAndWrists|SkullKidShoe|LinkMaskHat|LinkMaskHair", "cloth", 0.5),
]
GRADE = dict(saturation=0.8, tint=(1.0, 0.95, 0.9), gamma=1.08, detail=0.35, grain=0.04, grime=0.15, streaks=0.0)


def rule_for(base):
    for pattern, kind, denoise in RULES:
        if re.search(pattern, base):
            return kind, denoise
    return None, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview")
    ap.add_argument("--comfy", default="http://127.0.0.1:8188")
    ap.add_argument("--comfy-dir", default=os.environ.get("DARKMM_COMFY_DIR", "D:/AI/ComfyUI_windows_portable/ComfyUI"))
    args = ap.parse_args()
    for kind, prompt in PROMPTS.items():
        ai.PROMPTS["sp_" + kind] = prompt

    src = zipfile.ZipFile(SRC)
    names = [n for n in src.namelist() if n.startswith("alt/objects/") and n.split("/")[2] in OBJECTS]
    in_dir, out_dir = Path(args.comfy_dir) / "input", Path(args.comfy_dir) / "output"
    grade = argparse.Namespace(**GRADE)
    pairs = []
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_STORED) as out:
        for name in names:
            base = name.split("/")[-1]
            kind, denoise = rule_for(base)
            if kind is None:
                continue
            parsed = dm.parse(src.read(name))
            if parsed is None:
                continue
            pixels, encode = parsed
            h, w, _ = pixels.shape
            if min(w, h) < 16:
                continue
            rgb, alpha = pixels[..., :3], pixels[..., 3]
            pad = max(4, min(w, h) // 8)
            f = rgb.astype(np.float32)
            tiles = (np.abs(f[:, 0] - f[:, -1]).mean() < 12) and (np.abs(f[0] - f[-1]).mean() < 12)
            padded = np.pad(rgb, ((pad, pad), (pad, pad), (0, 0)), mode="wrap" if tiles else "reflect")
            key = hashlib.md5(name.encode()).hexdigest()[:12]
            in_name = f"sp_{key}.png"
            Image.fromarray(padded, "RGB").save(in_dir / in_name)
            pw, ph = ai.work_size(w + 2 * pad, h + 2 * pad, 768)
            fname, sub = ai.comfy_run(args.comfy, ai.workflow(in_name, pw, ph, denoise, 0.75, int(key[:8], 16),
                                                              f"darkmm/sp_{key}", "sp_" + kind))
            img = Image.open(out_dir / sub / fname).convert("RGB").resize((w + 2 * pad, h + 2 * pad), Image.LANCZOS)
            new_rgb = np.asarray(img)[pad:pad + h, pad:pad + w]
            if kind == "bone":  # the spikes are colored per mask: keep each one's hue, take only the AI detail
                opaque = alpha > 128
                fixed = np.empty(new_rgb.shape, np.float32)
                for c in range(3):
                    o, m = rgb[..., c][opaque].astype(np.float32), new_rgb[..., c][opaque].astype(np.float32)
                    fixed[..., c] = (new_rgb[..., c] - m.mean()) / (m.std() + 1e-3) * o.std() * 1.1 + o.mean() * 0.95
                new_rgb = np.clip(fixed, 0, 255).astype(np.uint8)
            new = dm.retouch(np.concatenate([new_rgb, alpha[..., None]], axis=-1), name, grade)
            out.writestr(name, encode(new))
            (in_dir / in_name).unlink(missing_ok=True)
            (out_dir / sub / fname).unlink(missing_ok=True)
            if len(pairs) < 32:
                pairs.append((pixels, new))
            print(base, kind, flush=True)
    if args.preview:
        Path(args.preview).mkdir(parents=True, exist_ok=True)
        for i in range(0, len(pairs), 8):
            dm.preview_sheet(pairs[i:i + 8], Path(args.preview) / f"sheet_{i // 8 + 1}.png")


if __name__ == "__main__":
    main()
