"""DarkMM texture retouch: reads textures from an .o2r (e.g. MM Reloaded 4K), regrades them to a darker,
less cartoon look with added material detail, and writes them into a separate .o2r that overrides the original.

Usage:
  python darkmm_textures.py --src "D:/Games/zelda mm/mods/MM_Reloaded_v11.0.3_4K.o2r" \
      --out "D:/Games/zelda mm/mods/DarkMM.o2r" --objects object_link_child --preview previews/link

Texture resources (LUS "OTEX" v1): 64-byte resource header, then
  u32 type, u32 width, u32 height, u32 flags, f32 hByteScale, f32 vPixelScale, u32 dataSize, data.
Reloaded stores decoded RGBA8 pixels with flags & 1 (TEX_FLAG_LOAD_AS_RAW); anything else is skipped.
"""

import argparse
import hashlib
import multiprocessing
from collections import deque
import struct
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HEADER_SIZE = 64
FIELDS = struct.Struct("<IIIIffI")
TEX_FLAG_LOAD_AS_RAW = 1

# Textures that carry facial features: only color-graded, no grain, so faces stay readable.
FEATURE_KEYWORDS = ("Eye", "Mouth", "Pupil", "Iris")


FIELDS_V0 = struct.Struct("<IIII")  # version 0: type, width, height, dataSize (no flags/scales)
TEX_TYPE_RGBA16 = 2


def decode_rgba16(data, w, h):
    """N64 RGBA5551, big-endian."""
    v = np.frombuffer(data, dtype=">u2", count=w * h).reshape(h, w).astype(np.uint32)
    r, g, b = (v >> 11) & 31, (v >> 6) & 31, (v >> 1) & 31
    a = (v & 1) * 255
    rgb = np.stack([r, g, b], axis=-1) * 255 // 31
    return np.concatenate([rgb, a[..., None]], axis=-1).astype(np.uint8)


def encode_rgba16(pixels):
    p = pixels.astype(np.uint32)
    r, g, b = ((p[..., c] * 31 + 127) // 255 for c in range(3))
    a = (p[..., 3] >= 128).astype(np.uint32)
    return ((r << 11) | (g << 6) | (b << 1) | a).astype(">u2").tobytes()


def parse(blob):
    """Returns (RGBA8 pixels, encode(pixels) -> resource bytes) or None for unsupported resources.
    Supports decoded RGBA8 textures (flags & 1) and native N64 RGBA16 textures, versions 0 and 1."""
    if len(blob) < HEADER_SIZE + FIELDS_V0.size or blob[4:8] != b"XETO":
        return None
    version = blob[8]
    if version == 1 and len(blob) >= HEADER_SIZE + FIELDS.size:
        tex_type, w, h, flags, hscale, vscale, size = FIELDS.unpack_from(blob, HEADER_SIZE)
        start = HEADER_SIZE + FIELDS.size
    elif version == 0:
        tex_type, w, h, size = FIELDS_V0.unpack_from(blob, HEADER_SIZE)
        flags = 0
        start = HEADER_SIZE + FIELDS_V0.size
    else:
        return None
    header = blob[:start]
    if len(blob) < start + size or w == 0 or h == 0:
        return None
    if (flags & TEX_FLAG_LOAD_AS_RAW) and size == w * h * 4:
        pixels = np.frombuffer(blob, dtype=np.uint8, count=size, offset=start).reshape(h, w, 4)
        return pixels, lambda px: header + px.tobytes()
    if not (flags & TEX_FLAG_LOAD_AS_RAW) and tex_type == TEX_TYPE_RGBA16 and size == w * h * 2:
        pixels = decode_rgba16(blob[start : start + size], w, h)
        return pixels, lambda px: header + encode_rgba16(px)
    return None


def decode_native(blob):
    """Decode a native N64 texture resource (as extracted into mm.o2r) to RGBA8, for comparison only.
    Supports RGBA32/RGBA16 and the grayscale formats; palette (CI) textures return None."""
    if len(blob) < HEADER_SIZE + FIELDS_V0.size or blob[4:8] != b"XETO":
        return None
    if blob[8] == 1:
        tex_type, w, h, flags, _, _, size = FIELDS.unpack_from(blob, HEADER_SIZE)
        start = HEADER_SIZE + FIELDS.size
        if flags & TEX_FLAG_LOAD_AS_RAW:
            return None
    else:
        tex_type, w, h, size = FIELDS_V0.unpack_from(blob, HEADER_SIZE)
        start = HEADER_SIZE + FIELDS_V0.size
    data = np.frombuffer(blob, dtype=np.uint8, count=min(size, len(blob) - start), offset=start)
    n = w * h
    try:
        if tex_type == 1:
            return data[: n * 4].reshape(h, w, 4).copy()
        if tex_type == 2:
            return decode_rgba16(data[: n * 2].tobytes(), w, h)
        if tex_type in (5, 7):  # I4 / IA4: two pixels per byte
            nib = np.stack([data[: n // 2] >> 4, data[: n // 2] & 15], axis=-1).reshape(h, w)
            if tex_type == 5:
                i, a = nib * 17, np.full_like(nib, 255)
            else:
                i, a = (nib >> 1) * 36, (nib & 1) * 255
        elif tex_type == 6:  # I8
            i, a = data[:n].reshape(h, w), np.full((h, w), 255)
        elif tex_type == 8:  # IA8
            px = data[:n].reshape(h, w)
            i, a = (px >> 4) * 17, (px & 15) * 17
        elif tex_type == 9:  # IA16
            px = data[: n * 2].reshape(h, w, 2)
            i, a = px[..., 0], px[..., 1]
        else:
            return None
    except ValueError:
        return None
    i = i.astype(np.uint8)
    return np.stack([i, i, i, a.astype(np.uint8)], axis=-1)


def find_aliases(base_zip, hd_owner, objects=None, max_diff=28.0):
    """MM Reloaded names some textures by ROM offset (object_xx_Tex_00C520) while current 2Ship asks for
    symbol names (gBomberEyeOpenTex), so those HD textures are never used. For every game texture without an
    HD version, find the unused HD texture of the same object that looks most alike.
    Returns {hd_path: [game_alt_path, ...]}."""
    base = zipfile.ZipFile(base_zip) if isinstance(base_zip, (str, Path)) else base_zip
    by_obj_base, by_obj_hd = {}, {}
    for n in base.namelist():
        parts = n.split("/")
        if len(parts) == 3 and parts[0] == "objects" and (not objects or parts[1] in objects):
            by_obj_base.setdefault(parts[1], []).append(n)
    for n in hd_owner:
        parts = n.split("/")
        if len(parts) == 4 and parts[0] == "alt" and parts[1] == "objects" and (not objects or parts[2] in objects):
            by_obj_hd.setdefault(parts[2], []).append(n)

    aliases = {}
    for obj, hd_names in by_obj_hd.items():
        base_names = set(by_obj_base.get(obj, []))
        orphans = [n for n in hd_names if n[len("alt/"):] not in base_names]
        missing = [n for n in base_names if "alt/" + n not in hd_owner]
        if not orphans or not missing:
            continue
        orphan_px = {}
        for n in orphans:
            p = parse(hd_owner[n].read(n))
            if p is not None:
                orphan_px[n] = p[0]
        for m in missing:
            low = decode_native(base.read(m))
            if low is None:
                continue
            lh, lw, _ = low.shape
            best, best_diff = None, max_diff
            for n, hd in orphan_px.items():
                hh, hw, _ = hd.shape
                if abs(hw / hh - lw / lh) > 0.01:
                    continue
                small = np.asarray(Image.fromarray(hd, "RGBA").resize((lw, lh), Image.BOX), dtype=np.float32)
                diff = np.abs(small[..., :3] - low[..., :3].astype(np.float32)).mean()
                if diff < best_diff:
                    best, best_diff = n, diff
            if best:
                aliases.setdefault(best, []).append("alt/" + m)
    return aliases


def tileable_noise(w, h, cells, rng, cells_y=None):
    """Smooth value noise with `cells` features across the texture, seamless when the texture wraps.
    cells_y (optional) sets a different feature count vertically, for stretched fibers."""
    cw = max(2, int(cells))
    ch = max(2, int(cells_y if cells_y is not None else cells * h / w))
    base = rng.random((ch, cw)).astype(np.float32)
    tiled = np.tile(base, (3, 3))
    img = Image.fromarray((tiled * 255).astype(np.uint8)).resize((w * 3, h * 3), Image.BICUBIC)
    arr = np.asarray(img, dtype=np.float32)[h : 2 * h, w : 2 * w] / 255.0
    return arr - 0.5


def wrap_blur(rgb, radius):
    """Gaussian blur that wraps around the edges (textures tile)."""
    h, w, _ = rgb.shape
    pad = int(radius * 3) + 1
    padded = np.pad(rgb, ((pad, pad), (pad, pad), (0, 0)), mode="wrap")
    img = Image.fromarray((np.clip(padded, 0, 1) * 255).astype(np.uint8))
    blurred = np.asarray(img.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255.0
    return blurred[pad : pad + h, pad : pad + w]


def leaf_material(pixels, name, rng):
    """Replaces a flat painted green with a mossy leaf: dark green, fibers and veins along the leaf,
    keeping the light/dark folds painted in the original texture."""
    h, w, _ = pixels.shape
    rgba = pixels.astype(np.float32) / 255.0
    lum = rgba[..., :3] @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    shading = np.clip(lum / max(lum.mean(), 1e-3), 0.45, 1.6) ** 1.3

    dark = np.array([0.10, 0.17, 0.06], dtype=np.float32)
    light = np.array([0.30, 0.40, 0.13], dtype=np.float32)
    patches = np.clip(tileable_noise(w, h, 4, rng) * 1.6 + 0.5, 0, 1)
    color = dark + (light - dark) * patches[..., None]

    # Fibers: noise stretched along the leaf (vertical), several scales.
    fibers = tileable_noise(w, h, w / 6, rng, cells_y=3) + tileable_noise(w, h, w / 20, rng, cells_y=6) * 0.5
    # Veins: thin dark lines where a stretched noise crosses zero.
    # Veins: parallel wavy lines running along the leaf (an integer count so the texture still tiles).
    xs = np.arange(w, dtype=np.float32)[None, :] / w
    warp = tileable_noise(w, h, 3, rng, cells_y=3) * 0.35
    vein_field = np.sin(np.pi * (xs * 9.0 + warp))
    veins = np.clip(1.0 - np.abs(vein_field) * 9.0, 0, 1) ** 2

    rgb = color * shading[..., None]
    rgb = rgb * (1.0 + fibers[..., None] * 0.35) * (1.0 - veins[..., None] * 0.45)
    rgb = rgb + veins[..., None] * np.array([0.03, 0.05, 0.0], dtype=np.float32)  # veins catch a little light
    out = np.concatenate([np.clip(rgb, 0, 1), rgba[..., 3:]], axis=-1)
    return (out * 255.0 + 0.5).astype(np.uint8)


# Per-texture recipes, matched on the end of the resource path.
# "material" replaces the texture; "params" overrides the generic retouch settings.
SPECIAL = {
    "object_link_nuts_Tex_0043B0": {"material": leaf_material},  # Deku hood
    "object_link_nuts_Tex_009068": {"material": leaf_material},  # Deku body leaves
    "object_link_nuts_Tex_0044B0": {"params": {"saturation": 0.5, "tint": (0.80, 0.90, 0.55)}},  # leaf fringe
}


# Scene (environment) textures: realistic and gloomy. Less color, colder, damp grime, stronger detail.
SCENE_PARAMS = {
    "saturation": 0.6,
    "tint": (0.93, 0.95, 0.92),
    "gamma": 1.18,
    "detail": 0.75,
    "grain": 0.12,
    "grime": 0.32,
    "streaks": 0.28,
}


# Regional moods on top of SCENE_PARAMS, matched on the start of the scene folder (alt/scenes/nonmq/<scene>/...).
REGIONS = {
    "swamp": {  # sick green, poisoned water, dead vegetation
        "scenes": ("Z2_20SICHITAI", "Z2_21MITURINMAE", "Z2_22DEKUCITY", "Z2_24KEMONOMITI", "Z2_26SARUNOMORI",
                   "Z2_MITURIN", "Z2_DEKUTES", "Z2_DEKU_KING", "Z2_KINSTA1", "Z2_WITCH_SHOP", "Z2_SYATEKI_MORI"),
        "params": {"saturation": 0.55, "tint": (0.86, 0.97, 0.78)},
    },
    "snow": {  # frozen, blue-grey, dirty ice
        "scenes": ("Z2_10YUKIYAMANOMURA", "Z2_11GORONNOSATO", "Z2_12HAKUGINMAE", "Z2_13HUBUKINOMITI",
                   "Z2_14YUKIDAMANOMITI", "Z2_16GORON_HOUSE", "Z2_17SETUGEN", "Z2_HAKUGIN", "Z2_GORONRACE",
                   "Z2_GORONSHOP", "Z2_GORON_HAKA"),
        "params": {"saturation": 0.5, "tint": (0.86, 0.94, 1.06)},
    },
    "sea": {  # murky teal, rust and salt
        "scenes": ("Z2_30GYOSON", "Z2_31MISAKI", "Z2_33ZORACITY", "Z2_35TAKI", "Z2_SEA", "Z2_PIRATE", "Z2_KAIZOKU",
                   "Z2_TORIDE", "Z2_LABO", "Z2_FISHERMAN", "Z2_KINDAN2", "Z2_SINKAI", "Z2_KONPEKI_ENT"),
        "params": {"saturation": 0.55, "tint": (0.84, 0.96, 0.95)},
    },
    "ikana": {  # dry bone, sepia, almost colorless, heavy grime
        "scenes": ("Z2_IKANA", "Z2_IKNINSIDE", "Z2_CASTLE", "Z2_INISIE", "Z2_HAKASHITA", "Z2_BOTI", "Z2_SECOM",
                   "Z2_REDEAD", "Z2_RANDOM", "Z2_TOUGITES", "Z2_F40", "Z2_F41", "Z2_DANPEI", "Z2_MUSICHOUSE"),
        "params": {"saturation": 0.42, "tint": (1.0, 0.92, 0.80), "grime": 0.38},
    },
    "moon": {  # near monochrome, cold
        "scenes": ("Z2_SOUGEN", "Z2_LAST_"),
        "params": {"saturation": 0.3, "tint": (0.95, 0.95, 1.0)},
    },
}


def scene_params(name):
    """SCENE_PARAMS plus the regional mood for scene textures; {} for anything that is not a scene."""
    parts = name.split("/")
    if "/scenes/" not in name or len(parts) < 4:
        return {}
    scene = parts[3]
    for region in REGIONS.values():
        if scene.startswith(region["scenes"]):
            return {**SCENE_PARAMS, **region["params"]}
    return dict(SCENE_PARAMS)


def process(job):
    """Worker: (name, blob, base args dict) -> (name, new resource bytes or None, preview pair or None)."""
    name, blob, base, want_preview = job
    parsed = parse(blob)
    if parsed is None:
        return name, None, None
    pixels, encode = parsed
    recipe = next((r for key, r in SPECIAL.items() if name.endswith(key)), {})
    if "material" in recipe:
        seed = int.from_bytes(hashlib.md5(name.encode()).digest()[:4], "little")
        new = recipe["material"](pixels, name, np.random.default_rng(seed))
    else:
        local = argparse.Namespace(**{**base, **scene_params(name), **recipe.get("params", {})})
        new = retouch(pixels, name, local)
    return name, encode(new), ((pixels, new) if want_preview else None)


def retouch(pixels, name, args):
    h, w, _ = pixels.shape
    rgba = pixels.astype(np.float32) / 255.0
    rgb, alpha = rgba[..., :3], rgba[..., 3:]
    seed = int.from_bytes(hashlib.md5(name.encode()).digest()[:4], "little")
    rng = np.random.default_rng(seed)

    # 1. Color grade: less saturated, earthier, slightly darker midtones.
    lum = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    rgb = lum[..., None] + (rgb - lum[..., None]) * args.saturation
    rgb = rgb * np.array(args.tint, dtype=np.float32)
    rgb = np.clip(rgb, 0, 1) ** args.gamma

    if not any(k in name for k in FEATURE_KEYWORDS) and min(w, h) >= 16:
        # 2. Local detail: unsharp mask brings out folds, seams and wear painted in the texture.
        radius = max(1.0, w / 256.0 * 1.5)
        rgb = rgb + (rgb - wrap_blur(rgb, radius)) * args.detail

        # 3. Material grain: fine multi-scale noise, strongest in the midtones.
        grain = (
            tileable_noise(w, h, w / 4, rng) * 0.5
            + tileable_noise(w, h, w / 16, rng) * 0.3
            + tileable_noise(w, h, w / 64, rng) * 0.2
        )
        mid = 1.0 - np.abs(lum - 0.5) * 1.2
        rgb = rgb * (1.0 + grain[..., None] * args.grain * np.clip(mid, 0.2, 1.0)[..., None])

        # 4. Grime: broad, soft dark patches so surfaces look used rather than freshly painted.
        grime = np.clip(tileable_noise(w, h, 3, rng) + tileable_noise(w, h, 8, rng) * 0.5, 0, None)
        rgb = rgb * (1.0 - grime[..., None] * args.grime)

        # 5. Damp streaks: thin vertical runs of darker, slightly greenish water stains.
        streaks = getattr(args, "streaks", 0.0)
        if streaks > 0:
            runs = tileable_noise(w, h, w / 24, rng, cells_y=2) + tileable_noise(w, h, w / 8, rng, cells_y=3) * 0.5
            mask = np.clip(runs * 2.5, 0, 1) * np.clip(tileable_noise(w, h, 2, rng) * 2 + 0.6, 0, 1)
            damp = np.array([0.80, 0.86, 0.80], dtype=np.float32)
            rgb = rgb * (1.0 - mask[..., None] * streaks * (1.0 - damp))

    out = np.concatenate([np.clip(rgb, 0, 1), alpha], axis=-1)
    return (out * 255.0 + 0.5).astype(np.uint8)


def preview_sheet(pairs, path, cell=192):
    cols = 2
    rows = len(pairs)
    sheet = Image.new("RGB", (cell * cols, cell * rows), (40, 40, 40))
    for r, (before, after) in enumerate(pairs):
        for c, arr in enumerate((before, after)):
            img = Image.fromarray(arr, "RGBA")
            img.thumbnail((cell, cell))
            bg = Image.new("RGB", img.size, (40, 40, 40))
            bg.paste(img, mask=img.split()[3])
            sheet.paste(bg, (c * cell, r * cell))
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="+", required=True,
                    help="one or more .o2r in load order; when several contain a file, the last one wins")
    ap.add_argument("--out", required=True)
    ap.add_argument("--objects", nargs="+", help="object/scene folder names, e.g. object_link_child (default: all)")
    ap.add_argument("--exclude", nargs="+", default=[],
                    help="folder name prefixes to leave untouched, e.g. object_link_ gameplay_")
    ap.add_argument("--exclude-from", nargs="+", default=[],
                    help=".o2r files whose paths must be left untouched (e.g. model mods loaded later)")
    ap.add_argument("--preview", help="folder for before/after sheets")
    ap.add_argument("--saturation", type=float, default=0.72)
    ap.add_argument("--tint", type=float, nargs=3, default=(1.0, 0.95, 0.88))
    ap.add_argument("--gamma", type=float, default=1.12)
    ap.add_argument("--detail", type=float, default=0.6)
    ap.add_argument("--grain", type=float, default=0.10)
    ap.add_argument("--grime", type=float, default=0.18)
    ap.add_argument("--jobs", type=int, default=1, help="worker processes (each can use ~1-2 GB on 4K textures)")
    args = ap.parse_args()

    # Effective file per path, like the game's archive manager: later archives override earlier ones.
    owner = {}
    for path in args.src:
        z = zipfile.ZipFile(path)
        for n in z.namelist():
            if not n.endswith("/"):
                owner[n] = z
    blocked = set()
    for path in args.exclude_from:
        blocked |= set(zipfile.ZipFile(path).namelist())

    def excluded(n):
        parts = n.split("/")
        folder = parts[2] if len(parts) > 2 and parts[1] == "objects" else (parts[3] if len(parts) > 3 else "")
        return n in blocked or (bool(args.exclude) and folder.startswith(tuple(args.exclude)))

    wanted = [n for n in owner
              if (not args.objects or any(f"/{o}/" in n for o in args.objects)) and not excluded(n)]
    print(f"{len(wanted)} files in {', '.join(args.objects) if args.objects else 'all folders'}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pairs, done, skipped = [], 0, 0
    base = {k: v for k, v in vars(args).items()
            if k not in ("src", "out", "objects", "preview", "jobs", "exclude", "exclude_from")}

    def handle(result):
        nonlocal done, skipped
        name, data, pair = result
        if data is None:
            skipped += 1
            return
        out.writestr(name, data)
        done += 1
        if pair is not None and len(pairs) < 24:
            pairs.append(pair)
        if done % 100 == 0:
            print(f"  {done} retouched...", flush=True)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED, allowZip64=True) as out:
        if args.jobs <= 1:
            for name in wanted:
                handle(process((name, owner[name].read(name), base, bool(args.preview))))
        else:
            # Bounded window of in-flight jobs so multi-GB packs are never fully loaded in memory.
            with multiprocessing.Pool(args.jobs) as pool:
                pending = deque()
                for name in wanted:
                    job = (name, owner[name].read(name), base, bool(args.preview) and len(pairs) < 24)
                    pending.append(pool.apply_async(process, (job,)))
                    while len(pending) >= args.jobs * 2:
                        handle(pending.popleft().get())
                while pending:
                    handle(pending.popleft().get())

    if args.preview and pairs:
        Path(args.preview).mkdir(parents=True, exist_ok=True)
        for i in range(0, len(pairs), 8):
            preview_sheet(pairs[i : i + 8], Path(args.preview) / f"sheet_{i // 8 + 1}.png")
    print(f"retouched {done}, skipped {skipped} -> {out_path}")


if __name__ == "__main__":
    main()
