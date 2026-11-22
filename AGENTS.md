# Instrucciones para agentes

Proyecto: Majora's Mask oscuro y realista sobre 2Ship2Harkinian. Para instalar el juego, sigue
[README.md, sección "Instalación automática"](README.md#instalación-automática-para-agentes) paso a paso.

## Reglas

- **Nunca** subas a git la ROM (`*.z64`, `*.n64`, `*.v64`), `mm.o2r`, `2ship.o2r`, ningún `*.o2r`, `*.otr` o `*.zip`,
  ni texturas o capturas sacadas del juego. Son assets con copyright o archivos de varios GB. El `.gitignore` los
  excluye; no lo saltes con `git add -f`.
- Los mods de la comunidad se descargan con `tools/download_mods.py` (enlaces directos en el README). La ROM y los
  packs DarkMM (Drive del proyecto) los aporta la persona: nunca busques la ROM en internet.
- El juego reescribe `2ship2harkinian.json` al cerrarse, y Windows bloquea `2ship.exe` y los `.o2r` mientras el juego
  está abierto. Antes de tocar la carpeta del juego, comprueba que el juego está cerrado
  (`Get-Process 2ship -ErrorAction SilentlyContinue`) y, si está abierto, pide a la persona que lo cierre.
- Los cambios del motor solo funcionan con **DirectX 11** (`Window.Backend.Name = "DirectX 11"`).
- Si cambias `engine/libultraship/src/fast/shaders/directx/default.shader.hlsl`, cópialo a
  `engine/mm/assets/custom/shaders/directx/` y compila el objetivo `Generate2ShipOtr`.
- Cada opción nueva del motor va detrás de un CVar `gEnhancements.Graphics.*`, con su control en
  `engine/mm/2s2h/BenGui/BenMenu.cpp` (texto en español) y un valor por defecto en `config/darkmm_settings.json`.
- No toques `engine/` para estilo ni formato fuera de lo que cambias: es código de terceros y luego hay que fusionar
  sus actualizaciones.
- Actualiza [PLAN.md](PLAN.md) (tabla de estado) cuando termines una parte.
- Trabaja en una rama y abre un Pull Request; no hagas push a `main`.

## Comprobación rápida

- Compila: `cmake --build engine/build/x64 --config Release` sin errores.
- Instala: `tools\install_game.ps1` y luego `python tools\configure_game.py --game-dir <carpeta>`.
- La prueba visual la hace la persona en el juego: pídele que lo pruebe y que te cuente qué ve.
