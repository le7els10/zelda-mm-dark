"""Write the DarkMM settings and the mod load order into the game's config (2ship2harkinian.json).

Usage: python tools/configure_game.py --game-dir "C:/Games/zelda-mm-dark"

- Merges config/darkmm_settings.json (graphics, HUD, enhancements) into the existing config, or creates one.
- Sets gSettings.EnabledMods to MOD_ORDER, keeping only the mods present in <game-dir>/mods. Any other mod found
  there is appended at the end. Missing mods are listed so you know what is still to be downloaded.
- The game rewrites this file when it closes: run this with the game CLOSED.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Load order: the LAST archive wins when two mods replace the same file.
MOD_ORDER = [
    "DialogosPAL",            # Spanish PAL text            (GameBanana 678108)
    "TexPal",                 # Spanish PAL textures        (GameBanana 678108)
    "MM_Reloaded_v11.0.3_4K", # HD textures                 (GameBanana 555331)
    "DarkMM",                 # DarkMM: regional scenery grade (shared by the project owner)
    "DarkMM_Scenes_AI",       # DarkMM: AI scenery
    "DarkMM_Objects",         # DarkMM: objects grade
    "DarkMM_NPC_AI",          # DarkMM: AI characters
    "DarkMM_Items_AI",        # DarkMM: AI shared objects and inventory
    "DarkMM_Moon",            # DarkMM: moon textures
    "1-HD Moon",              # HD Moon model               (GameBanana 640438)
    "2-HD Moon Textures",     # HD Moon textures            (GameBanana 640438)
    "DarkMM_Sky",             # DarkMM: storm sky
    "DarkMM_SkullKid",        # DarkMM: Skull Kid, Majora's Mask, Majora
    "3DS_Link_1_Models",      # 3DS Link                    (GameBanana 644553)
    "3DS_Equipment_1_Models",
    "3DS_Link_2_Textures",
    "3DS_Equipment_2_Textures",
    "3DS_Expressive_Human",   # Expressive Link             (GameBanana 646581)
    "3DS_Expressive_Goron",
    "3DS_Expressive_Zora",
    "3DS_Expressive_FierceDeity",
    "DarkMM_Link3DS",         # DarkMM: grade for the 3DS Link
]


def deep_merge(dst, src):
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            deep_merge(dst[key], value)
        else:
            dst[key] = value


def game_running():
    if sys.platform != "win32":
        return False
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq 2ship.exe"], capture_output=True, text=True).stdout
    return "2ship.exe" in out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-dir", required=True)
    ap.add_argument("--no-settings", action="store_true", help="only write the mod order")
    args = ap.parse_args()

    game = Path(args.game_dir)
    if game_running():
        sys.exit("2ship.exe is running: close the game first (it overwrites the config when it exits).")
    if not (game / "2ship.exe").exists():
        sys.exit(f"2ship.exe not found in {game}: run tools/install_game.ps1 first.")

    cfg_path = game / "2ship2harkinian.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {"ConfigVersion": 2}
    cfg.setdefault("CVars", {})
    if cfg_path.exists():
        cfg_path.with_suffix(".json.bak").write_text(cfg_path.read_text(encoding="utf-8"), encoding="utf-8")
    if not args.no_settings:
        preset = json.loads((REPO / "config" / "darkmm_settings.json").read_text(encoding="utf-8"))
        deep_merge(cfg, preset)

    mods_dir = game / "mods"
    present = {p.stem for p in mods_dir.rglob("*") if p.suffix.lower() in (".o2r", ".otr")} if mods_dir.exists() else set()
    order = [m for m in MOD_ORDER if m in present] + sorted(present - set(MOD_ORDER))
    cfg["CVars"].setdefault("gSettings", {})["EnabledMods"] = "|".join(order)
    cfg_path.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")

    print(f"Config written: {cfg_path}")
    print(f"Enabled mods ({len(order)}): " + ", ".join(order))
    missing = [m for m in MOD_ORDER if m not in present]
    if missing:
        print("Missing from mods/ (see README, section 'Mods'): " + ", ".join(missing))


if __name__ == "__main__":
    main()
