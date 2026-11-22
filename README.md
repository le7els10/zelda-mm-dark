# Zelda: Majora's Mask — Dark

Versión más realista y oscura, casi de terror, de *The Legend of Zelda: Majora's Mask* para PC, construida sobre
[2 Ship 2 Harkinian](https://github.com/HarbourMasters/2ship2harkinian) (2Ship).

- **Motor:** ambiente oscuro (niebla, luz y noches), modelos suavizados y relieve con la luz del sol. Además, filtro de imagen
  (viñeta, grano, contraste, tono frío, tensión del día 3) y oclusión ambiental. Todo se ajusta en el menú
  **Gráficos** del juego. Solo con DirectX 11.
- **Texturas:** escenarios, personajes, objetos, cielo, Luna y Skull Kid retocados y pasados por IA (Stable Diffusion +
  ControlNet Tile) sobre el pack HD *MM Reloaded*, con un matiz por región.

El estado de cada parte está en [PLAN.md](PLAN.md).

> **Este repositorio no contiene la ROM ni ningún asset de Nintendo**, ni los packs de texturas generados (~35 GB).
> Cada persona usa su propia copia del juego. Los packs DarkMM se comparten por Drive (ver [Mods](#4-mods)).

---

## Instalación automática (para agentes)

Si eres un agente de IA ayudando a instalar el juego, sigue estos pasos en orden. Lee también [AGENTS.md](AGENTS.md).
Los pasos marcados con **[humano]** los tiene que hacer la persona; pídeselo y espera su confirmación.

Plataforma: **Windows 10/11 x64**, PowerShell. La carpeta del juego de ejemplo es `C:\Games\zelda-mm-dark`
(pregunta a la persona si quiere otra).

### 1. Requisitos

```powershell
winget install --id Git.Git -e
winget install --id Kitware.CMake -e
winget install --id Python.Python.3.12 -e
winget install --id Microsoft.VisualStudio.2022.BuildTools -e --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
```

Hace falta al menos 8 GB de RAM para compilar. Abre una terminal nueva después de instalar, para que se actualice el PATH.

### 2. Compilar

Desde la raíz del repo:

```powershell
cmake -S engine -B engine/build/x64 -G "Visual Studio 17 2022" -T v143 -A x64
cmake --build engine/build/x64 --target Generate2ShipOtr --config Release
cmake --build engine/build/x64 --config Release
```

Salida: `engine\x64\Release\2ship.exe` y `engine\build\x64\mm\2ship.o2r`. La primera compilación tarda de 10 a 30
minutos.

La primera configuración descarga dependencias con vcpkg. Si termina con `Configuring incomplete, errors occurred`,
vuelve a ejecutar el primer comando: la segunda vez suele completarse.

### 3. Instalar en la carpeta del juego

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_game.ps1 -GameDir "C:\Games\zelda-mm-dark"
```

Copia el ejecutable, `assets\`, `2ship.o2r` y `gamecontrollerdb.txt`, y crea `mods\`. Si ya había partidas, mods o
configuración, los conserva.

**[humano]** Pon tu propia ROM de *Majora's Mask (USA)* (`.z64`) en la carpeta del juego y abre `2ship.exe` una
vez. El juego pide confirmar la ROM y genera `mm.o2r`, lo que tarda unos minutos. Después cierra el juego. Puedes
verificar la ROM en <https://2ship.equipment/>.

### 4. Mods

Todos van en `<carpeta del juego>\mods\`, con los nombres de la tabla: el orden de carga se configura por nombre.
Espacio necesario: unos 75 GB, más 40 GB temporales mientras se descomprime MM Reloaded.

**a) Mods de la comunidad (automático).** El script los descarga, extrae solo los archivos necesarios, les pone el
nombre correcto y comprueba que son las mismas versiones con las que se hizo DarkMM:

```powershell
winget install --id 7zip.7zip -e
python tools\download_mods.py --game-dir "C:\Games\zelda-mm-dark"
```

Descarga unos 6,4 GB (casi todo es MM Reloaded) y se puede volver a ejecutar si se corta: salta lo que ya está.
`--skip reloaded` omite MM Reloaded.

**b) Packs DarkMM (manual).** **[humano]** Descarga la carpeta completa del Drive del proyecto:
**DARKMM_DRIVE_URL** (el dueño del proyecto la comparte aparte; si aquí aún pone `DARKMM_DRIVE_URL`, pídele el
enlace). Después cópialos con:

```powershell
python tools\download_mods.py --game-dir "C:\Games\zelda-mm-dark" --darkmm-dir "<carpeta descargada del Drive>"
```

| Archivo(s) en `mods\` | Fuente | Descarga directa |
| --- | --- | --- |
| `DialogosPAL.o2r`, `TexPal.o2r` | [Traducción Español (PAL)](https://gamebanana.com/mods/678108) | <https://gamebanana.com/dl/1704610> |
| `MM_Reloaded_v11.0.3_4K.o2r` (en el 7z se llama distinto; renómbralo) | [MM Reloaded](https://github.com/GhostlyDark/MM-Reloaded/releases/tag/v11.0.2), *2ship o2r 4k* v11.0.3 | [parte 1](https://github.com/GhostlyDark/MM-Reloaded/releases/download/v11.0.2/mm-reloaded-v11.0.3-2ship-o2r-4k.7z.001), [parte 2](https://github.com/GhostlyDark/MM-Reloaded/releases/download/v11.0.2/mm-reloaded-v11.0.3-2ship-o2r-4k.7z.002), [parte 3](https://github.com/GhostlyDark/MM-Reloaded/releases/download/v11.0.2/mm-reloaded-v11.0.3-2ship-o2r-4k.7z.003) |
| `3DS_Link_1_Models.o2r` ← `1- 3DS Link.o2r`, `3DS_Link_2_Textures.o2r` ← `2-3DS Link Textures.o2r` | [3DS Link](https://gamebanana.com/mods/644553), *standard* | <https://gamebanana.com/dl/1788174> |
| `3DS_Equipment_1_Models.o2r` ← `1-3DS Equipment.o2r`, `3DS_Equipment_2_Textures.o2r` ← `2-3DS Equipment Textures.o2r` | [3DS Link](https://gamebanana.com/mods/644553), *equipment* | <https://gamebanana.com/dl/1630255> |
| `3DS_Expressive_Human/Goron/Zora/FierceDeity.o2r` ← `Expressive Human/Goron/Zora/Fierce Deity Link .o2r` | [Expressive Link for 3DS Link](https://gamebanana.com/mods/646581), *collection* | <https://gamebanana.com/dl/1815712> |
| `1-HD Moon.otr`, `2-HD Moon Textures.otr` | [HD Moon](https://gamebanana.com/mods/640438) | <https://gamebanana.com/dl/1583670> |
| `DarkMM.o2r`, `DarkMM_Scenes_AI.o2r`, `DarkMM_Objects.o2r`, `DarkMM_NPC_AI.o2r`, `DarkMM_Items_AI.o2r`, `DarkMM_Moon.o2r`, `DarkMM_Sky.o2r`, `DarkMM_SkullKid.o2r`, `DarkMM_Link3DS.o2r` | Drive del proyecto | **DARKMM_DRIVE_URL** |

Los packs DarkMM se pueden regenerar con `tools\` (ver [Generar texturas](#generar-texturas)), pero tarda días.

### 5. Configurar

Con el juego **cerrado** (al salir, el juego sobrescribe su configuración):

```powershell
python tools\configure_game.py --game-dir "C:\Games\zelda-mm-dark"
```

Aplica los ajustes de [config/darkmm_settings.json](config/darkmm_settings.json): DirectX 11, MSAA 4x, el ambiente
oscuro, el filtro de imagen, la oclusión ambiental, los colores del HUD y las mejoras. También fija el orden de
carga de los mods (el último gana) y lista los que falten. Antes guarda una copia en `2ship2harkinian.json.bak`.

### 6. Jugar

Abre `2ship.exe`. F1 muestra u oculta el menú, y Tab activa o desactiva los assets alternativos (los mods de
texturas deben estar activos). Los ajustes DarkMM están en **Gráficos**: *Ambiente oscuro*, *Filtro de imagen* y
*Oclusión ambiental*.

---

## Estructura

```
engine/   2Ship2Harkinian completo con los cambios DarkMM (incluye libultraship, ZAPDTR y OTRExporter, sin submódulos)
tools/    scripts de texturas (Python) e instalación
config/   ajustes recomendados y base de datos de mandos
PLAN.md   plan del proyecto y estado de cada parte
```

### Dónde están los cambios del motor

| Qué | Archivos |
| --- | --- |
| Ambiente oscuro (niebla, luz, noches, tensión del día 3) | `engine/mm/2s2h/Enhancements/Graphics/DarkAtmosphere.cpp`, `engine/mm/src/code/z_kankyo.c` |
| Menú (opciones en español) | `engine/mm/2s2h/BenGui/BenMenu.cpp` |
| Modelos suavizados y relieve | `engine/libultraship/src/fast/interpreter.cpp`, `engine/libultraship/src/fast/shaders/directx/default.shader.hlsl` (copiado en `engine/mm/assets/custom/shaders/`) |
| Filtro de imagen | `GfxRenderingAPIDX11::PostProcess` en `engine/libultraship/src/fast/backends/gfx_direct3d11.cpp` |
| Oclusión ambiental | Comando `G_AMBIENTOCC` (0x4b) emitido en `Play_DrawMain` (`engine/mm/src/code/z_play.c`) → `Interpreter::ApplyAmbientOcclusion` → `GfxRenderingAPIDX11::AmbientOcclusion` |

Si cambias `default.shader.hlsl`, cópialo también a `engine/mm/assets/custom/shaders/directx/` y vuelve a
compilar el objetivo `Generate2ShipOtr`: el juego lee los shaders de `2ship.o2r`.

Base: 2Ship `develop` en el commit `7f2d4ad22`, libultraship `7f9b86a5`, ZAPDTR `ee3397a3` y OTRExporter
`32e088e2`. Actualizar 2Ship implica fusionar a mano sus cambios en `engine/`.

---

## Generar texturas

Los scripts de `tools\` crean los packs DarkMM a partir de *MM Reloaded*. Necesitan Python con `numpy` y `pillow`
(`pip install -r tools\requirements.txt`). Las rutas se configuran con variables de entorno:

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `DARKMM_GAME_DIR` | `D:/Games/zelda mm` | Carpeta del juego (lee `mods/MM_Reloaded_v11.0.3_4K.o2r` y `mm.o2r`) |
| `DARKMM_COMFY_DIR` | `D:/AI/ComfyUI_windows_portable/ComfyUI` | ComfyUI para los scripts con IA |

- `darkmm_textures.py`: retoque sin IA (color por región, detalle, grano, suciedad). Genera `DarkMM.o2r`,
  `DarkMM_Objects.o2r` y `DarkMM_Link3DS.o2r`.
- `npc_ai_retexture.py`, `scene_ai_retexture.py`, `special_retexture.py`, `moon_retexture.py` y `sky_retexture.py`:
  pasadas con IA. Usan [ComfyUI](https://github.com/comfyanonymous/ComfyUI) en `http://127.0.0.1:8188` con
  *Realistic Vision V6.0 B1* (fp16), *control_v11f1e_sd15_tile* (fp16) y *vae-ft-mse-840000-ema-pruned*. Hace falta
  una GPU NVIDIA. Tienen caché y se pueden reanudar (`--cache`).
- `hud_style.py`: colores del HUD (ya incluidos en `config/darkmm_settings.json`).

Cada script explica su uso en la cabecera.

---

## Cómo colaborar

1. Crea una rama por cambio (`git checkout -b motor/agua-reflejos`) y abre un Pull Request.
2. Prueba en el juego con DirectX 11 antes de pedir revisión, y cuenta qué probaste y dónde.
3. Las opciones nuevas del motor van detrás de un CVar `gEnhancements.Graphics.*`, con su control en `BenMenu.cpp`,
   para poder apagarlas.
4. Nunca subas la ROM, `mm.o2r`, ningún `.o2r`, `.otr` o `.zip`, capturas con texturas, ni carpetas `build/`. El
   `.gitignore` ya los excluye.

## Créditos y licencias

- [2 Ship 2 Harkinian](https://github.com/HarbourMasters/2ship2harkinian) (Harbour Masters), CC0. Incluye
  [libultraship](https://github.com/Kenix3/libultraship), [ZAPDTR](https://github.com/HarbourMasters/ZAPDTR) y
  [OTRExporter](https://github.com/HarbourMasters/OTRExporter). Sus licencias están en cada carpeta de `engine/`.
- Mods de la comunidad: MM Reloaded (GhostlyDark), 3DS Link, Expressive Link, HD Moon y la traducción PAL, de sus
  autores en GameBanana. No se redistribuyen aquí.
- *The Legend of Zelda: Majora's Mask* es de Nintendo. Este proyecto no incluye assets del juego.
