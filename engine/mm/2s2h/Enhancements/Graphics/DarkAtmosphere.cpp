// Dark Atmosphere: makes Termina darker, colder and foggier as the three days pass.
// Runs right after Environment_UpdateLights() has computed the final light and fog values for the frame,
// so nothing accumulates: the game recomputes them from the scene's light settings every frame.

#include <libultraship/bridge/consolevariablebridge.h>
#include "2s2h/GameInteractor/GameInteractor.h"
#include "2s2h/ShipInit.hpp"
#include <algorithm>

extern "C" {
#include "functions.h"
#include "variables.h"
extern PlayState* gPlayState;
}

#define CVAR_NAME "gEnhancements.Graphics.DarkAtmosphere.Enabled"
#define CVAR CVarGetInteger(CVAR_NAME, 0)
#define CVAR_DARKNESS "gEnhancements.Graphics.DarkAtmosphere.Darkness"
#define CVAR_FOG "gEnhancements.Graphics.DarkAtmosphere.Fog"
#define CVAR_DESAT "gEnhancements.Graphics.DarkAtmosphere.Desaturation"
#define CVAR_DAY_SCALING "gEnhancements.Graphics.DarkAtmosphere.DayScaling"

namespace {

float Lerp(float a, float b, float t) {
    return a + (b - a) * t;
}

u8 ToU8(float v) {
    return (u8)std::clamp(v, 0.0f, 255.0f);
}

// Desaturate, darken and tint one RGB color in place.
// tint multiplies each channel after darkening (1.0 = unchanged).
void Grade(u8* color, float desat, float darken, const float tint[3]) {
    float r = color[0], g = color[1], b = color[2];
    float luma = 0.299f * r + 0.587f * g + 0.114f * b;
    float scale = 1.0f - darken;

    color[0] = ToU8(Lerp(r, luma, desat) * scale * tint[0]);
    color[1] = ToU8(Lerp(g, luma, desat) * scale * tint[1]);
    color[2] = ToU8(Lerp(b, luma, desat) * scale * tint[2]);
}

// 0.55 on the first day, rising to 1.0 on the final day, plus extra at night.
float DayFactor() {
    if (!CVarGetInteger(CVAR_DAY_SCALING, 1)) {
        return 1.0f;
    }

    float factor;
    switch (CURRENT_DAY) {
        case 0:
        case 1:
            factor = 0.55f;
            break;
        case 2:
            factor = 0.75f;
            break;
        default:
            factor = 1.0f;
            break;
    }

    if (gSaveContext.save.isNight) {
        factor += 0.15f;
    }

    return std::min(factor, 1.0f);
}

// How much the blood-red "the moon is falling" tint is applied: day 3 only, maxing out in the final hours.
float DoomFactor() {
    if (CURRENT_DAY < 3) {
        return 0.0f;
    }

    if (TIME_UNTIL_MOON_CRASH < CLOCK_TIME_HOUR * 6) {
        return 1.0f;
    }

    return 0.5f;
}

void ApplyDarkAtmosphere() {
    if (gPlayState == nullptr) {
        return;
    }

    LightContext* lightCtx = &gPlayState->lightCtx;
    EnvironmentContext* envCtx = &gPlayState->envCtx;

    float day = DayFactor();
    float darkness = (CVarGetInteger(CVAR_DARKNESS, 60) / 100.0f) * day;
    float fog = (CVarGetInteger(CVAR_FOG, 50) / 100.0f) * day;
    float desat = (CVarGetInteger(CVAR_DESAT, 50) / 100.0f) * day;
    float doom = DoomFactor() * darkness;

    // Cold blue-ish tint for the lights; the fog turns red as the moon gets closer.
    const float coldTint[3] = { 1.0f - 0.10f * darkness, 1.0f - 0.03f * darkness, 1.0f + 0.08f * darkness };
    const float fogTint[3] = { Lerp(coldTint[0], 1.35f, doom), Lerp(coldTint[1], 0.75f, doom),
                               Lerp(coldTint[2], 0.70f, doom) };

    Grade(lightCtx->ambientColor, desat, 0.45f * darkness, coldTint);
    Grade(envCtx->dirLight1.params.dir.color, desat, 0.35f * darkness, coldTint);
    Grade(envCtx->dirLight2.params.dir.color, desat, 0.35f * darkness, coldTint);
    Grade(lightCtx->fogColor, desat, 0.55f * darkness, fogTint);

    // fogNear is 0-996: the lower it is, the closer to the camera the fog starts.
    const s16 denseFogNear = 920;
    if (lightCtx->fogNear > denseFogNear) {
        lightCtx->fogNear = (s16)Lerp(lightCtx->fogNear, denseFogNear, fog);
    }
}

} // namespace

void RegisterDarkAtmosphere() {
    COND_HOOK(OnEnvironmentLightsUpdate, CVAR, ApplyDarkAtmosphere);
}

static RegisterShipInitFunc initFunc(RegisterDarkAtmosphere, { CVAR_NAME });

// Relief on scenery: the renderer has no light info for unlit room geometry, so publish the scene's main
// directional light (the sun) every frame. Same convention as the RSP lights: points towards the light.
#define CVAR_RELIEF "gEnhancements.Graphics.Relief.Strength"

void PublishSunDirection() {
    if (gPlayState == nullptr) {
        return;
    }
    const LightDirectional& sun = gPlayState->envCtx.dirLight1.params.dir;
    CVarSetFloat("gEnhancements.Graphics.Relief.SunX", sun.x / 127.0f);
    CVarSetFloat("gEnhancements.Graphics.Relief.SunY", sun.y / 127.0f);
    CVarSetFloat("gEnhancements.Graphics.Relief.SunZ", sun.z / 127.0f);
}

void RegisterReliefSun() {
    COND_HOOK(OnEnvironmentLightsUpdate, CVarGetInteger(CVAR_RELIEF, 0) > 0, PublishSunDirection);
}

static RegisterShipInitFunc initSunFunc(RegisterReliefSun, { CVAR_RELIEF });

// Post-processing "tension": 0 until day 3, then rises towards 1 as the moon is about to fall.
// The renderer reads it to push the image redder, darker and grainier.
#define CVAR_POST "gEnhancements.Graphics.Post.Enabled"
#define CVAR_POST_TENSION "gEnhancements.Graphics.Post.Tension"

void PublishPostTension() {
    float tension = 0.0f;
    if (gPlayState != nullptr && CURRENT_DAY >= 3) {
        const float dayLength = (float)CLOCK_TIME_HOUR * 24.0f;
        float left = std::clamp((float)TIME_UNTIL_MOON_CRASH / dayLength, 0.0f, 1.0f);
        tension = 0.35f + 0.65f * (1.0f - left) * (1.0f - left);
    }
    CVarSetFloat("gEnhancements.Graphics.Post.TensionNow", tension);
}

void RegisterPostTension() {
    if (!(CVarGetInteger(CVAR_POST, 1) && CVarGetInteger(CVAR_POST_TENSION, 1))) {
        CVarSetFloat("gEnhancements.Graphics.Post.TensionNow", 0.0f);
    }
    COND_HOOK(OnEnvironmentLightsUpdate, CVarGetInteger(CVAR_POST, 1) && CVarGetInteger(CVAR_POST_TENSION, 1),
              PublishPostTension);
}

static RegisterShipInitFunc initPostFunc(RegisterPostTension, { CVAR_POST, CVAR_POST_TENSION });
