#include "audio.h"

#include "raylib.h"

#include <cmath>

namespace {

Sound sfxShoot;
Sound sfxHit;
Sound sfxWave;

Wave genTone(float freq, float duration, float volume, bool square) {
    Wave wave = { 0 };
    wave.sampleRate = 44100;
    wave.sampleSize = 16;
    wave.channels = 1;
    wave.frameCount = (unsigned int)(44100.0f * duration);
    short* samples = (short*)MemAlloc(wave.frameCount * sizeof(short));
    if (!samples) return wave;
    for (unsigned int i = 0; i < wave.frameCount; i++) {
        float t = (float)i / (float)wave.sampleRate;
        float env = 1.0f - (float)i / (float)wave.frameCount;
        env *= env;
        float v = 0.0f;
        if (square) v = (sinf(2.0f * PI * freq * t) >= 0.0f) ? 1.0f : -1.0f;
        else v = sinf(2.0f * PI * freq * t);
        samples[i] = (short)(v * env * volume * 32767.0f);
    }
    wave.data = samples;
    return wave;
}

} // namespace

void initAudioSfx(float shootFreq, float hitFreq, float waveFreq) {
    Wave w = genTone(shootFreq, 0.08f, 0.25f, true);
    sfxShoot = LoadSoundFromWave(w);
    UnloadWave(w);

    w = genTone(hitFreq, 0.15f, 0.4f, false);
    sfxHit = LoadSoundFromWave(w);
    UnloadWave(w);

    w = genTone(waveFreq, 0.3f, 0.3f, false);
    sfxWave = LoadSoundFromWave(w);
    UnloadWave(w);
}

void playShoot() { PlaySound(sfxShoot); }
void playHit() { PlaySound(sfxHit); }
void playWave() { PlaySound(sfxWave); }

void closeAudioSfx() {
    UnloadSound(sfxShoot);
    UnloadSound(sfxHit);
    UnloadSound(sfxWave);
}
