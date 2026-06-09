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

    # Pad with silence to at least 0.6 seconds to work around macOS QSoundEffect silent playback issues
    min_samples = int(0.6 * SAMPLE_RATE)
    if len(signal) < min_samples:
        padding = np.zeros(min_samples - len(signal))
        signal = np.concatenate([signal, padding])

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
    """Short woody click -- piece landing on board."""
    duration = 0.15
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0.0, duration, n, endpoint=False)

    # Sharp contact transient (500 Hz + 1000 Hz) with extremely fast decay
    strike = (0.5 * np.sin(2 * math.pi * 500 * t) + 0.3 * np.sin(2 * math.pi * 1000 * t)) * np.exp(-t / 0.005)
    # Wood body resonance (180 Hz + 360 Hz)
    resonance = (0.6 * np.sin(2 * math.pi * 180 * t) + 0.4 * np.sin(2 * math.pi * 360 * t)) * np.exp(-t / 0.035)
    # Slight contact friction noise
    rng = np.random.default_rng(101)
    noise = rng.uniform(-0.3, 0.3, n) * np.exp(-t / 0.003)

    return strike + resonance + noise



def sound_capture():
    """Harder double-contact woody snap -- piece striking another and landing."""
    duration = 0.25
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0.0, duration, n, endpoint=False)

    # First strike (high-pitched contact snap at t=0)
    click1 = (0.5 * np.sin(2 * math.pi * 800 * t) + 0.3 * np.sin(2 * math.pi * 1600 * t)) * np.exp(-t / 0.008)
    # High-pass-ish noise transient at strike
    rng = np.random.default_rng(42)
    noise = rng.uniform(-1.0, 1.0, n) * np.exp(-t / 0.005)

    # Second strike (woody thunk landing at t=0.04s)
    t_delayed = np.maximum(0.0, t - 0.04)
    click2 = (0.6 * np.sin(2 * math.pi * 320 * t_delayed) + 0.4 * np.sin(2 * math.pi * 640 * t_delayed)) * np.exp(-t_delayed / 0.03)
    # Add small wood rattle/friction
    noise2 = rng.uniform(-0.5, 0.5, n) * np.exp(-t_delayed / 0.015)

    # Combine signals (and only add click2 after its delay)
    mask = t >= 0.04
    signal = click1 + 0.3 * noise
    signal[mask] += click2[mask] + 0.15 * noise2[mask]

    return signal



def sound_check():
    """Tense, buzzing threat warning alert."""
    duration = 0.35
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0.0, duration, n, endpoint=False)

    # Carrier frequencies: 160 Hz square wave + 227 Hz triangle wave
    carrier = 0.5 * np.sign(np.sin(2 * math.pi * 160.0 * t)) + \
              0.3 * np.arcsin(np.sin(2 * math.pi * 227.0 * t)) / (math.pi / 2.0)

    # Fast tremolo/buzz modulation at 35 Hz
    buzz = 1.0 + 0.8 * np.sin(2 * math.pi * 35.0 * t)

    # Combined signal with decay envelope
    env = np.exp(-t / 0.08)
    return carrier * buzz * env




def sound_castle():
    """Double-move click with a sliding/whooshing sound of pieces passing each other."""
    duration = 0.4
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0.0, duration, n, endpoint=False)

    # 1. Sliding/whooshing movement (t = 0 to 0.22s)
    # A noise band that rises/falls to simulate pieces passing
    rng = np.random.default_rng(202)
    noise_signal = rng.uniform(-1.0, 1.0, n)
    whoosh_noise = np.convolve(noise_signal, np.ones(12)/12, mode='same')

    # Envelope for the whoosh: rises and falls, peaking around t=0.08s
    whoosh_env = np.zeros_like(t)
    whoosh_mask = t < 0.22
    whoosh_env[whoosh_mask] = np.sin(math.pi * t[whoosh_mask] / 0.22) ** 2
    whoosh = 0.45 * whoosh_noise * whoosh_env

    # Add a pitch-sweeping component (one rising, one falling) for the passing effect
    sweep1 = np.sin(2 * math.pi * (500 - 1000 * t) * t) * 0.15
    sweep2 = np.sin(2 * math.pi * (150 + 800 * t) * t) * 0.15
    sweeps = (sweep1 + sweep2) * whoosh_env

    # 2. First piece landing (King) at t = 0.08s
    t_del1 = np.maximum(0.0, t - 0.08)
    click1 = (0.5 * np.sin(2 * math.pi * 220 * t_del1) + 0.3 * np.sin(2 * math.pi * 440 * t_del1)) * np.exp(-t_del1 / 0.02)

    # 3. Second piece landing (Rook) at t = 0.18s
    t_del2 = np.maximum(0.0, t - 0.18)
    click2 = (0.5 * np.sin(2 * math.pi * 260 * t_del2) + 0.3 * np.sin(2 * math.pi * 520 * t_del2)) * np.exp(-t_del2 / 0.02)

    # Combine signals
    signal = whoosh + sweeps
    mask1 = t >= 0.08
    signal[mask1] += click1[mask1]
    mask2 = t >= 0.18
    signal[mask2] += click2[mask2]

    return signal



def sound_game_start():
    """Refined cascading/arpeggiated major-9th chime."""
    duration = 0.5
    n = int(duration * SAMPLE_RATE)
    t = np.linspace(0.0, duration, n, endpoint=False)

    # Define notes and their delay offsets
    notes = [
        {"freq": 523.25,  "delay": 0.00, "amp": 0.40, "decay": 0.18},  # C5
        {"freq": 659.25,  "delay": 0.02, "amp": 0.35, "decay": 0.16},  # E5
        {"freq": 783.99,  "delay": 0.04, "amp": 0.30, "decay": 0.14},  # G5
        {"freq": 987.77,  "delay": 0.06, "amp": 0.25, "decay": 0.12},  # B5
        {"freq": 1174.66, "delay": 0.08, "amp": 0.20, "decay": 0.10},  # D6
        {"freq": 1567.98, "delay": 0.10, "amp": 0.15, "decay": 0.08},  # G6
    ]

    signal = np.zeros_like(t)
    for note in notes:
        t_delayed = np.maximum(0.0, t - note["delay"])
        note_sig = note["amp"] * np.sin(2 * math.pi * note["freq"] * t_delayed) * np.exp(-t_delayed / note["decay"])

        # Apply very fast attack (3ms) to each note at its entry point
        attack_env = np.minimum(1.0, t_delayed / 0.003)
        note_sig = note_sig * attack_env

        mask = t >= note["delay"]
        signal[mask] += note_sig[mask]

    return signal



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
