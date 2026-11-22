"""Download the community mods DarkMM builds on and put them in <game-dir>/mods with the names the load order uses.

Usage:
  python tools/download_mods.py --game-dir "C:/Games/zelda-mm-dark"
  python tools/download_mods.py --game-dir ... --skip reloaded          # everything except MM Reloaded
  python tools/download_mods.py --game-dir ... --darkmm-dir "D:/Descargas/DarkMM"   # also copy the DarkMM packs

- Mods already in mods/ are skipped, so it can be re-run after a failure.
- MM Reloaded 4K is a 3-part 7z (~6.2 GB download, 24.6 GB unpacked) and needs 7-Zip (winget install 7zip.7zip).
  Leave ~40 GB free for it during the extraction.
- The DarkMM packs are not downloaded here: the project owner shares them on a Drive. Download that folder by hand
  and pass it with --darkmm-dir.
- Downloads go to <game-dir>/mods/_downloads and are deleted afterwards (unless --keep-downloads).
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# Sizes of the versions DarkMM was made with; a different size means the mod was updated upstream.
EXPECTED_SIZES = {
    "DialogosPAL.o2r": 472209, "TexPal.o2r": 339912,
    "3DS_Link_1_Models.o2r": 1260663, "3DS_Link_2_Textures.o2r": 847112,
    "3DS_Equipment_1_Models.o2r": 2806682, "3DS_Equipment_2_Textures.o2r": 61838,
    "3DS_Expressive_Human.o2r": 8378998, "3DS_Expressive_Goron.o2r": 38866612,
    "3DS_Expressive_Zora.o2r": 41949606, "3DS_Expressive_FierceDeity.o2r": 20973048,
    "1-HD Moon.otr": 1188110, "2-HD Moon Textures.otr": 11650024,
    "MM_Reloaded_v11.0.3_4K.o2r": 24651990834,
}

UA = {"User-Agent": "Mozilla/5.0 (DarkMM setup script)"}
RELOADED_BASE = "https://github.com/GhostlyDark/MM-Reloaded/releases/download/v11.0.2/"

# name: list of (url, md5 or None, {file inside the zip: name in mods/})
# (GameBanana's published md5 does not always match its download, so the check is on the extracted sizes.)
MODS = {
    "spanish": [  # Traducción Español (PAL) - https://gamebanana.com/mods/678108
        ("https://gamebanana.com/dl/1704610", None,
         {"DialogosPAL.o2r": "DialogosPAL.o2r", "TexPal.o2r": "TexPal.o2r"}),
    ],
    "3ds_link": [  # 3DS Link - https://gamebanana.com/mods/644553
        ("https://gamebanana.com/dl/1788174", None,
         {"1- 3DS Link.o2r": "3DS_Link_1_Models.o2r", "2-3DS Link Textures.o2r": "3DS_Link_2_Textures.o2r"}),
        ("https://gamebanana.com/dl/1630255", None,
         {"1-3DS Equipment.o2r": "3DS_Equipment_1_Models.o2r",
          "2-3DS Equipment Textures.o2r": "3DS_Equipment_2_Textures.o2r"}),
    ],
    "expressive": [  # Expressive Link for 3DS Link - https://gamebanana.com/mods/646581
        ("https://gamebanana.com/dl/1815712", None,
         {"The Expressive 3DS Link Collection/Expressive Human Link .o2r": "3DS_Expressive_Human.o2r",
          "The Expressive 3DS Link Collection/Expressive Goron Link .o2r": "3DS_Expressive_Goron.o2r",
          "The Expressive 3DS Link Collection/Expressive Zora Link .o2r": "3DS_Expressive_Zora.o2r",
          "The Expressive 3DS Link Collection/Expressive Fierce Deity .o2r": "3DS_Expressive_FierceDeity.o2r"}),
    ],
    "hd_moon": [  # HD Moon - https://gamebanana.com/mods/640438
        ("https://gamebanana.com/dl/1583670", None,
         {"HD Moon/1-HD Moon.otr": "1-HD Moon.otr", "HD Moon/2-HD Moon Textures.otr": "2-HD Moon Textures.otr"}),
    ],
}
RELOADED_PARTS = [f"mm-reloaded-v11.0.3-2ship-o2r-4k.7z.00{i}" for i in (1, 2, 3)]
RELOADED_NAME = "MM_Reloaded_v11.0.3_4K.o2r"
DARKMM_PACKS = ["DarkMM.o2r", "DarkMM_Scenes_AI.o2r", "DarkMM_Objects.o2r", "DarkMM_NPC_AI.o2r", "DarkMM_Items_AI.o2r",
                "DarkMM_Moon.o2r", "DarkMM_Sky.o2r", "DarkMM_SkullKid.o2r", "DarkMM_Link3DS.o2r"]


def download(url, dest, md5=None):
    if dest.exists() and (md5 is None or file_md5(dest) == md5):
        return dest
    print(f"  downloading {url}", flush=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done, step = 0, 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total and done * 10 // total > step:
                step = done * 10 // total
                print(f"    {step * 10}%", flush=True)
    if md5 and file_md5(tmp) != md5:
        tmp.unlink()
        raise RuntimeError(f"checksum mismatch for {url} (the mod may have been updated: check its page)")
    tmp.replace(dest)
    return dest


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def check_size(path):
    want = EXPECTED_SIZES.get(path.name)
    if want and path.stat().st_size != want:
        print(f"  WARNING: {path.name} is {path.stat().st_size} bytes, DarkMM was made with {want}: the mod was "
              "updated upstream. It should still work; report it if something looks wrong.")


def find_7z():
    for c in (shutil.which("7z"), "C:/Program Files/7-Zip/7z.exe", "C:/Program Files (x86)/7-Zip/7z.exe"):
        if c and Path(c).exists():
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-dir", required=True)
    ap.add_argument("--skip", nargs="*", default=[], choices=list(MODS) + ["reloaded"])
    ap.add_argument("--darkmm-dir", help="folder with the DarkMM .o2r packs downloaded from the project's Drive")
    ap.add_argument("--keep-downloads", action="store_true")
    args = ap.parse_args()

    mods = Path(args.game_dir) / "mods"
    mods.mkdir(parents=True, exist_ok=True)
    work = mods / "_downloads"
    work.mkdir(exist_ok=True)

    for name, entries in MODS.items():
        if name in args.skip:
            continue
        for url, md5, files in entries:
            if all((mods / target).exists() for target in files.values()):
                print(f"{name}: already installed")
                continue
            print(f"{name}:")
            archive = download(url, work / (url.rsplit("/", 1)[-1] + ".zip"), md5)
            with zipfile.ZipFile(archive) as z:
                for inner, target in files.items():
                    with z.open(inner) as src, open(mods / target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    print(f"  -> mods/{target}")
                    check_size(mods / target)

    if "reloaded" not in args.skip:
        if (mods / RELOADED_NAME).exists():
            print("reloaded: already installed")
        else:
            seven = find_7z()
            if not seven:
                sys.exit("MM Reloaded needs 7-Zip: winget install --id 7zip.7zip -e, then run this again.")
            print("reloaded (MM Reloaded 4K, ~6.2 GB):")
            for part in RELOADED_PARTS:
                download(RELOADED_BASE + part, work / part)
            out = work / "reloaded"
            subprocess.run([seven, "x", "-y", f"-o{out}", str(work / RELOADED_PARTS[0])], check=True)
            found = sorted(out.rglob("*.o2r"), key=lambda p: p.stat().st_size, reverse=True)
            if not found:
                sys.exit(f"No .o2r found after extracting MM Reloaded in {out}")
            shutil.move(str(found[0]), mods / RELOADED_NAME)
            shutil.rmtree(out, ignore_errors=True)
            print(f"  -> mods/{RELOADED_NAME}")
            check_size(mods / RELOADED_NAME)

    if args.darkmm_dir:
        src = Path(args.darkmm_dir)
        for pack in DARKMM_PACKS:
            if (mods / pack).exists():
                continue
            hit = next(src.rglob(pack), None)
            if hit:
                print(f"darkmm: copying {pack}", flush=True)
                shutil.copy2(hit, mods / pack)
            else:
                print(f"darkmm: {pack} not found in {src}")

    if not args.keep_downloads:
        shutil.rmtree(work, ignore_errors=True)
    missing = [p for p in DARKMM_PACKS if not (mods / p).exists()]
    if missing:
        print("Still missing (DarkMM, from the project's Drive): " + ", ".join(missing))
    print("Done. Next: python tools/configure_game.py --game-dir " + args.game_dir)


if __name__ == "__main__":
    main()
