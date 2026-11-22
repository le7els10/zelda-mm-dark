"""Smaller, quieter HUD for the dark mod: shrinks every HUD element towards its screen corner and mutes the
HUD colors. Edits 2ship2harkinian.json directly (HUD Editor + Cosmetic Editor settings), so run it with the
game CLOSED (the game rewrites the file when it exits). A backup is written next to the config.

Usage: python hud_style.py "D:/Games/zelda mm/2ship2harkinian.json" [--reset]
"""

import json
import shutil
import sys
from pathlib import Path

# HUD Editor modes (mm/2s2h/BenGui/HudEditor.h)
MODE_VANILLA, MODE_HIDDEN, MODE_43, MODE_LEFT, MODE_RIGHT = 0, 1, 2, 3, 4

# name in config: (default x, default y) on the 320x240 N64 screen (from HudEditor.cpp)
DEFAULTS = {
    "B": (167, 17), "CLeft": (227, 18), "CDown": (249, 34), "CRight": (271, 18), "A": (191, 18),
    "CUp": (254, 16), "DPad": (271, 55), "Minimap": (295, 220), "Start": (136, 17), "Carrots": (160, 64),
    "Clock": (160, 206), "Hearts": (30, 26), "Magic": (18, 34), "Timers": (26, 46), "SkullKidTimer": (115, 200),
    "Minigames": (20, 67), "Rupees": (26, 206), "Keys": (26, 190), "Skulltulas": (26, 190),
}

# Groups shrink towards a pivot (a screen corner) so they stay tucked into it.
GROUPS = [
    # elements, pivot, scale, mode
    (("B", "A", "CLeft", "CDown", "CRight", "CUp", "DPad", "Start"), (314, 6), 0.65, MODE_RIGHT),
    (("Hearts", "Magic", "Timers", "Minigames"), (6, 6), 0.75, MODE_LEFT),
    (("Rupees", "Keys", "Skulltulas"), (6, 236), 0.70, MODE_LEFT),
    (("Clock", "SkullKidTimer"), (160, 238), 0.65, MODE_43),
    (("Minimap",), (316, 238), 0.75, MODE_RIGHT),
    (("Carrots",), (160, 6), 0.75, MODE_43),
]

# Muted, desaturated HUD colors (R, G, B, A)
COLORS = {
    "Buttons.A": (120, 140, 150, 255),
    "Buttons.B": (120, 140, 115, 255),
    "Buttons.CLeft": (175, 160, 100, 255),
    "Buttons.CDown": (175, 160, 100, 255),
    "Buttons.CRight": (175, 160, 100, 255),
    "Buttons.DPad": (180, 180, 180, 255),
    "Buttons.Start": (150, 110, 85, 255),
    "HUD.Hearts": (165, 55, 50, 255),
    "HUD.Magic": (70, 125, 80, 255),
    "HUD.RupeeIcon": (130, 150, 100, 255),
    "HUD.Minimap": (120, 150, 150, 140),
}


def set_path(root, dotted, value):
    node = root
    keys = dotted.split(".")
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value


def del_path(root, dotted):
    node = root
    keys = dotted.split(".")
    for k in keys[:-1]:
        if k not in node:
            return
        node = node[k]
    node.pop(keys[-1], None)


def main():
    cfg_path = Path(sys.argv[1])
    reset = "--reset" in sys.argv
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    shutil.copy2(cfg_path, cfg_path.with_suffix(".json.bak-hud"))
    cvars = cfg.setdefault("CVars", {})

    for elements, (px, py), scale, mode in GROUPS:
        for name in elements:
            x, y = DEFAULTS[name]
            base = f"gHudEditor.{name}"
            if reset:
                del_path(cvars, base)
                continue
            set_path(cvars, f"{base}.Position.X", round(px + (x - px) * scale))
            set_path(cvars, f"{base}.Position.Y", round(py + (y - py) * scale))
            set_path(cvars, f"{base}.Scale", scale)
            set_path(cvars, f"{base}.Mode", mode)

    for cid, (r, g, b, a) in COLORS.items():
        base = f"gCosmetic.{cid}"
        if reset:
            del_path(cvars, base)
            continue
        set_path(cvars, f"{base}.Color", {"R": r, "G": g, "B": b, "A": a, "Type": "RGBA"})
        set_path(cvars, f"{base}.Changed", 1)

    cfg_path.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
    print("HUD reset to vanilla" if reset else "HUD style applied", "->", cfg_path)


if __name__ == "__main__":
    main()
