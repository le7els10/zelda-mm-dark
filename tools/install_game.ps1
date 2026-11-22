# Copies the built game into a play folder.
# Usage (from the repo root, after building): powershell -File tools\install_game.ps1 -GameDir "C:\Games\zelda-mm-dark"
# The game must be closed. Saves, mods, the ROM and the config already in GameDir are kept.
param(
    [Parameter(Mandatory = $true)][string]$GameDir
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$release = Join-Path $repo "engine\x64\Release"
$o2r = Join-Path $repo "engine\build\x64\mm\2ship.o2r"

if (Get-Process -Name 2ship -ErrorAction SilentlyContinue) {
    throw "2ship.exe is running: close the game first."
}
foreach ($p in @((Join-Path $release "2ship.exe"), (Join-Path $release "assets"), $o2r)) {
    if (-not (Test-Path $p)) { throw "Missing $p - build first (README, section 'Compilar')." }
}

New-Item -ItemType Directory -Force -Path $GameDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $GameDir "mods") | Out-Null
$exe = Join-Path $GameDir "2ship.exe"
if (Test-Path $exe) { Copy-Item $exe "$exe.bak" -Force }
Copy-Item (Join-Path $release "2ship.exe") $GameDir -Force
Copy-Item (Join-Path $release "assets") $GameDir -Recurse -Force
Copy-Item $o2r $GameDir -Force
Copy-Item (Join-Path $repo "config\gamecontrollerdb.txt") $GameDir -Force

Write-Host "Installed in $GameDir"
if (-not (Get-ChildItem $GameDir -Filter *.z64 -ErrorAction SilentlyContinue) -and -not (Test-Path (Join-Path $GameDir "mm.o2r"))) {
    Write-Host "Next: put your own Majora's Mask (USA) ROM (.z64) in $GameDir and launch 2ship.exe once to extract mm.o2r."
}
