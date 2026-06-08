#!/usr/bin/env python3
"""
Generate CC0 sound effects for Chess_analyzer.

These sounds are synthesized from scratch and are dedicated to the public
domain (CC0 1.0). They replace the previously bundled chess.com sound files.

Dependencies: numpy (already in requirements for the engine evaluator).
No external audio samples are used.
"""
import math
import struct
import wave
import os
import numpy as np

SAMPLE_RATE = 44100
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def _envelope(n_samples, attack=0.005, decay=0.05, sustain=0.6, release=0.08):
    """ADSR envelope, returns float array in [0, 1]."""
    total = attack + decay + sustain + release
    if total > 0 and n_samples / SAMPLE_RATE < total:
        # too short: scale release down so we don't overshoot
        release = max(0.0, n_samples / SAMPLE_RATE - (attack + decay + sustain))
    t = np.linspace(0.0, n_samples / SAMPLE_RATE, n_samples, endpoint=False)
    env = np.zeros_like(t)
    # attack
    a_end = attack
    mask = t < a_end
    env[mask] = t[mask] / max(attack, 1e-9)
    # decay
    d_end = a_end + decay
    mask = (t >= a_end) & (t < d_end)
    env[mask] = 1.0 - (1.0 - sustain) * (t[mask] - a_end) / max(decay, 1e-9)
    # sustain
    s_end = d_end + sustain
    mask = (t >= d_end) & (t < s_end)
    env[mask] = sustain
    # release
    r_end = s_end + release
    mask = (t >= s_end) & (t < r_end)
    env[mask] = sustain * (1.0 - (t[mask] - s_end) / max(release, 1e-9))
    return env


def _to_int16(signal):
    """Normalize to int16 range with peak limiting."""
    peak = float(np.max(np.abs(signal))) if signal.size else 0.0
    if peak > 0:
        signal = signal / peak * 0.9
    return np.clip(signal, -1.0, 1.0)


def _write_wav(path, signal):
    signal = _to_int16(signal)
    pcm = (signal * 32767.0).astype(np.int16).tobytes()
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)


def _note(freq, duration, kind="sine", amp=0.8):
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0.0, duration, n, endpoint=False)
    if kind == "sine":
        wave_ = np.sin(2 * math.pi * freq * t)
    elif kind == "triangle":
        # bandlimited-ish triangle via additive odd harmonics
        wave_ = np.zeros_like(t)
        for k in range(1, 12, 2):
            wave_ += np.sin(2 * math.pi * freq * k * t) / (k * k)
        wave_ /= np.max(np.abs(wave_)) if wave_.size else 1
    elif kind == "square":
        wave_ = np.sign(np.sin(2 * math.pi * freq * t))
    elif kind == "noise":
        rng = np.random.default_rng(int(freq * 1000) % (2**32))
        wave_ = rng.uniform(-1.0, 1.0, n)
    else:
        wave_ = np.sin(2 * math.pi * freq * t)
    return wave_ * amp


# --------------------------------------------------------------------------- #
# Individual sound generators                                                  #
# --------------------------------------------------------------------------- #

def sound_move():
    """Short neutral click -- piece placed on board."""
    duration = 0.14
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0.0, duration, n, endpoint=False)
    body = 0.6 * np.sin(2 * math.pi * 220 * t) \
         + 0.4 * np.sin(2 * math.pi * 440 * t)
    # Two-stage envelope: fast initial attack, gentle tail so the
    # 140 ms total length is fully audible through QSoundEffect.
    env = np.exp(-t / 0.04)
    return body * env


def sound_capture():
    """Harder thunk -- piece removed and replaced."""
    duration = 0.18
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0.0, duration, n, endpoint=False)
    low = 0.8 * np.sin(2 * math.pi * 80 * t) * np.exp(-t / 0.05)
    # short noise burst at the start
    rng = np.random.default_rng(42)
    noise = rng.uniform(-1.0, 1.0, n) * np.exp(-t / 0.02)
    return low + 0.4 * noise


def sound_check():
    """Bright, attention-grabbing tone."""
    duration = 0.22
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0.0, duration, n, endpoint=False)
    vibrato = 1.0 + 0.03 * np.sin(2 * math.pi * 12 * t)
    body = 0.6 * np.sin(2 * math.pi * 880 * vibrato * t) \
         + 0.4 * np.sin(2 * math.pi * 1320 * vibrato * t)
    env = _envelope(n, attack=0.01, decay=0.04, sustain=0.12, release=0.05)
    return body * env


def sound_castle():
    """Soft, regal two-note chord (C5 + G5)."""
    duration = 0.32
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0.0, duration, n, endpoint=False)
    body = 0.5 * np.sin(2 * math.pi * 523.25 * t) \
         + 0.5 * np.sin(2 * math.pi * 783.99 * t)
    env = _envelope(n, attack=0.02, decay=0.05, sustain=0.18, release=0.07)
    return body * env


def sound_game_start():
    """Greeting ping (E5 + A5, short)."""
    duration = 0.18
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0.0, duration, n, endpoint=False)
    body = 0.5 * np.sin(2 * math.pi * 659.25 * t) \
         + 0.5 * np.sin(2 * math.pi * 880.0 * t)
    env = _envelope(n, attack=0.005, decay=0.03, sustain=0.10, release=0.05)
    return body * env


def sound_game_end():
    """Rising four-note arpeggio (C5-E5-G5-C6) to close the game."""
    notes = [523.25, 659.25, 783.99, 1046.50]
    note_len = 0.13
    gap = 0.02
    segments = []
    for f in notes:
        n = int(note_len * SAMPLE_RATE)
        t = np.linspace(0.0, note_len, n, endpoint=False)
        seg = 0.7 * np.sin(2 * math.pi * f * t)
        env = _envelope(n, attack=0.005, decay=0.03, sustain=0.07, release=0.025)
        segments.append(seg * env)
        # short silence between notes
        silence = np.zeros(int(gap * SAMPLE_RATE))
        segments.append(silence)
    return np.concatenate(segments)[:-int(gap * SAMPLE_RATE)]


# --------------------------------------------------------------------------- #
# Main                                                                          #
# --------------------------------------------------------------------------- #

GENERATORS = {
    "move.wav": sound_move,
    "capture.wav": sound_capture,
    "check.wav": sound_check,
    "castle.wav": sound_castle,
    "game_start.wav": sound_game_start,
    "game_end.wav": sound_game_end,
}


def main():
    print(f"Writing CC0 sound effects to {OUT_DIR}")
    for name, gen in GENERATORS.items():
        path = os.path.join(OUT_DIR, name)
        signal = gen()
        _write_wav(path, signal)
        size = os.path.getsize(path)
        print(f"  {name:20s}  {len(signal) / SAMPLE_RATE:5.2f}s  {size:>6d} bytes")
    print("Done.")


if __name__ == "__main__":
    main()
