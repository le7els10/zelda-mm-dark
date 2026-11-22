# Plan: Majora's Mask, versión moderna y oscura

## Progreso (16-nov-2026)

Todo está en Esc → Enhancements → Graphics:

| Función | Estado | Ajuste actual |
|---|---|---|
| MM Reloaded 4K (`mods/`) | ✅ Instalado | — |
| Atmósfera oscura (niebla, luz fría, empeora por días) | ✅ Aprobado | Por defecto |
| Suavizar modelos (personajes y objetos curvados) | ✅ Aprobado | Nivel 4 (máx. 6) |
| Luz recalculada sobre la superficie curva | ✅ Aprobado | Automático con el suavizado |
| Relieve por píxel (DirectX 11) | ✅ Funciona | 50 |
| Modelo de Link: 3DS Link + 3DS Equipment + Expressive Link (GameBanana) | ✅ Aprobado (reemplaza al Link original) | `mods/3DS_*.o2r` |
| Texturas DarkMM: escenarios de Clock Town (5 barrios) | ✅ Instalado | DarkMM.o2r (después de Reloaded) |
| Relieve en escenarios (con el sol de la escena) | ✅ Instalado | Relieve 50 |
| Tono lúgubre para las texturas del Link 3DS | ✅ Aprobado | `DarkMM_Link3DS.o2r` (último mod) |
| Todas las zonas (100 escenas) con matiz por región: pantano verde, nieve azul, mar turbio, Ikana sepia, Luna monocromo | ✅ Aprobado | DarkMM.o2r (14.6 GB) |
| NPC, enemigos y objetos (357 objetos, 3 419 texturas) | ✅ Instalado | DarkMM_Objects.o2r (antes de los mods 3DS) |
| Postproceso: viñeta, grano, contraste, tono frío, aberración, tensión del día 3 (Fase 3) | ✅ Aprobado | 2ship.exe (menú Gráficos > Filtro de imagen) |
| Oclusión ambiental (SSAO) entre el mundo 3D y el HUD, con MSAA; se apaga con distancia y en pausa | 🧪 En prueba | 2ship.exe (Gráficos > Oclusion ambiental) |
| Luna N64 mejorada (roca y dientes; ojos del pack IA). Existe HD Moon de la comunidad (ver fila siguiente) | ✅ Aprobado | DarkMM_Moon.o2r |
| Luna HD de la comunidad (HD Moon, GameBanana 640438): modelo N64 con más polígonos; no brillan los ojos en la escena de "consumir" | ✅ Aprobado | 1-HD Moon.otr + 2-HD Moon Textures.otr (después de DarkMM_Moon) |
| Cielo: nubes realistas y más densas (10 texturas, colores originales para el tinte horario) | ✅ Aprobado | DarkMM_Sky.o2r |
| Skull Kid, máscara de Majora y Majora: madera lacada agrietada, púas de hueso, piel de corteza, tela rasgada | ✅ Aprobado | DarkMM_SkullKid.o2r |
| IA en escenarios: todas las zonas, 2743 texturas (13 GB); agua, brillos y degradados sin tocar | ✅ Aprobado | DarkMM_Scenes_AI.o2r (después de DarkMM) |
| IA en objetos compartidos e inventario: 366 texturas (sin efectos; grises sin tinte sepia) | ✅ Aprobado | DarkMM_Items_AI.o2r |
| IA en NPC: 3 267 texturas, 602 caras/pieles con arrugas y facciones | ✅ Instalado | DarkMM_NPC_AI.o2r (5.3 GB) |
| Repaso: ninguna cara quedó con el ajuste viejo. Excluidos sin IA: gameplay_ (328), object_gi_ (181), object_mag (27), efectos (22); Link (154) lo cubre el modelo 3DS | ✅ Hecho (DarkMM_Items_AI.o2r) | — |

Objetivo: que el juego se vea más actual (menos "poligonal") y llevar más lejos el tono oscuro y de terror, sin romper la jugabilidad.

---

## 0. Diagnóstico (estado actual, 16-nov-2026)

| Hallazgo | Impacto |
|---|---|
| `D:\Games\zelda mm\mods` solo tiene `DialogosPAL.o2r` y `TexPal.o2r` (traducción al español). **MM Reloaded no está instalado.** | Ahora mismo juegas con texturas originales. |
| `MM-Reloaded-11.0.2` es la versión para **GLideN64 / Zelda64Recomp (rt64)**: 14 055 PNG con nombres por hash, 5.3 GB. | **2Ship no puede leer este formato.** Hace falta la versión **MM-Reloaded-2S2H** (`.o2r`) de GhostlyDark, o convertir los PNG. |
| El código fuente de 2Ship (v5.0.1+126) ya trae ganchos útiles: `Enhancements/Graphics` (MotionBlur, RainEverywhere, FlatShading), `framebuffer_effects.c`, `GfxPatcher` y el sistema `GameInteractor`. | Podemos añadir efectos de ambiente como "enhancements" propios, con su interruptor en el menú. |
| El submódulo `libultraship` está **vacío** (no se inicializó). | Hay que hacer `git submodule update --init --recursive` antes de compilar. |
| 2Ship admite música personalizada (`docs/CUSTOM_SEQUENCED_MUSIC.md`, `CUSTOM_STREAMED_MUSIC.md`). | El audio también se puede cambiar sin tocar código. |

**Ojo:** las texturas en HD **no quitan el aspecto poligonal**. Eso viene de la geometría (pocos polígonos) y de la iluminación plana. Para arreglarlo hay que actuar en tres frentes: texturas, iluminación/postproceso y, de forma selectiva, modelos.

---

## Fase 1: Base estable (sin programar)

1. Una sola instalación (`D:\Games\zelda mm`). No hace falta que el juego sea jugable durante el desarrollo; solo se jugará al terminar.
2. Descarga **MM Reloaded v11.0.3 para 2Ship** (`.o2r`) desde evilgames.eu. Hay dos versiones: `mm-reloaded-v11.0.3-2ship-o2r-hd.7z` y `mm-reloaded-v11.0.3-2ship-o2r-4k.7z`. Extráela en `mods/`, activa *Use Alternate Assets* en el menú (Esc) y alterna las texturas con Tab. En el Mod Menu, ordénala **por debajo** de `TexPal.o2r` para que las texturas en español no se pierdan (comprobar en el juego).
3. Ajustes gráficos de 2Ship: resolución interna 2x-4x, MSAA 4x-8x, 60 FPS (interpolación), filtro de texturas.
4. Prepara la compilación desde el código: VS 2022 + CMake según `docs/BUILDING.md`, inicializa los submódulos y comprueba que el `2ship.exe` compilado arranca sin cambios.

**Entregable:** el juego con texturas HD y un ejecutable propio que arranca.

## Fase 2: Ambiente oscuro por código (lo que más cambia, con menos esfuerzo)

Un enhancement nuevo, `Enhancements/Atmosphere/`, con interruptores (CVars) en el menú:

- **Niebla e iluminación:** niebla más cercana y densa, luz ambiente más fría y apagada, noches más oscuras. Se aplica sobre `envCtx` / los lighting settings de cada escena.
- **Escalada por día:** día 1 casi normal → día 3 desaturado, rojizo, con niebla espesa. Ligado a `gSaveContext.save.day` y a la hora.
- **Luna:** más grande, más roja y con temblores más frecuentes en las últimas horas.
- **Clima:** reutilizar `RainEverywhere` como tormenta en el día 3 y añadir más relámpagos.
- **Zonas clave:** perfiles propios para Ikana, Stone Tower, Pantano y Clock Town de noche.

**Entregable:** un preset "Terror" que se activa y desactiva en el menú.

## Fase 3: Postproceso (shader)

Requiere tocar el renderizador de `libultraship` (DX11/OpenGL). Dificultad media-alta.

- Viñeta, grano de película, desaturación y corrección de color (LUT).
- Aberración cromática ligera en momentos de tensión (la luna, Majora, poca vida).
- Opcional: oclusión ambiental o sombreado suave para disimular lo plano de los polígonos.

**Entregable:** un pase de postproceso configurable, empezando por la viñeta y el LUT.

## Fase 4: Dirección artística de texturas

Sobre la base de Reloaded. Un `.o2r` es un ZIP con los PNG organizados por ruta del asset, así que se puede abrir, retocar y volver a empaquetar.

**4a. Personajes y objetos clave:** cara de la Luna, Skull Kid, la Máscara de Majora, el Vendedor de Máscaras.

**4b. Escenarios** (`Areas`), por regiones y en este orden:
1. Clock Town (versión día 1/2/3 y noche): piedra húmeda, madera podrida, grietas, cielo enfermo.
2. Termina Field y cielo/nubes.
3. Pantano del Sur / Woodfall: agua envenenada, vegetación muerta.
4. Montañas / Snowhead: hielo sucio, niebla.
5. Gran Bahía / Great Bay: agua turbia, óxido.
6. Ikana / Stone Tower: huesos, ruinas, sangre seca.
7. Interiores de templos y la Luna.

**Proceso por región:**
1. Extraer los PNG de la región desde el `.o2r` de Reloaded con un script.
2. Retocarlos en lote con un script (Python: desaturar, oscurecer, ajustar el color y añadir mugre y suciedad) para dar una base uniforme.
3. Retocar a mano o con IA las texturas protagonistas.
4. Empaquetar en `mods/DarkMM.o2r`, que se carga encima de Reloaded, y revisar en el juego.

**Entregable:** un pack propio, separado de Reloaded, que se completa región por región.

## Fase 5: Modelos (selectivo)

2Ship permite reemplazar skeletons y display lists desde un `.o2r`. Pipeline: Blender + **Fast64** → exportar → empaquetar.

- Prioridad: Link, Skull Kid, la Luna, el Vendedor de Máscaras y los jefes.
- **No** remodelar el mundo entero: es un trabajo enorme y rompe las colisiones.
- Requiere saber modelar en 3D o usar modelos ya hechos por la comunidad.

---

## Reglas del proyecto

- Todo el código nuevo va aislado en `mm/2s2h/Enhancements/Atmosphere/` con CVars, para poder actualizar 2Ship sin conflictos.
- Hacer una copia de seguridad de `D:\Games\zelda mm` (sobre todo de las partidas guardadas) antes de reemplazar el ejecutable.
- Assets propios en un `.o2r` aparte, nunca editando `mm.o2r` ni el pack de Reloaded.
- Uso personal: no redistribuir la ROM ni los assets extraídos.

## Orden recomendado

Fase 1 → Fase 2 → Fase 3 (viñeta/LUT) → Fase 4 (escenarios, región por región) → Fase 5.
Las fases 2 y 3 son las que más cambian la sensación de terror; los modelos son lo más caro y van al final. El audio queda fuera del alcance.

## Decisiones pendientes (tuyas)

1. ¿Hasta dónde llegar con los modelos? (nada / solo Link y personajes clave / más)
2. ¿El tono oscuro siempre activo, o como preset que se puede activar y desactivar?
3. ¿Tienes experiencia con Blender o con la edición de texturas, o lo hacemos más por código?
