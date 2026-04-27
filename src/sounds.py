"""Synthesized sound effects using numpy + pygame.mixer."""
from __future__ import annotations

import numpy as np
import pygame
from settings import SETTINGS


_RATE = 44100
_sounds: dict[str, pygame.mixer.Sound] = {}
_initialized = False


def init() -> None:
    """Initialize the mixer and generate all sounds.  Safe to call multiple times."""
    global _initialized
    if _initialized:
        return
    pygame.mixer.init(frequency=_RATE, size=-16, channels=2, buffer=512)
    _initialized = True

    _sounds["shoot"]          = _make_shoot()
    _sounds["pop"]            = _make_pop()
    for _lvl in range(1, 6):
        _sounds[f"cascade_{_lvl}"] = _make_cascade(_lvl)
    _sounds["bomb"]           = _make_bomb()
    _sounds["coin"]           = _make_coin()
    _sounds["aim"]            = _make_aim()
    _sounds["swap"]           = _make_swap()
    _sounds["slowdown"]       = _make_slowdown()
    _sounds["level_complete"] = _make_level_complete()
    _sounds["game_over"]      = _make_game_over()
    _sounds["menu_click"]     = _make_menu_click()
    _sounds["danger_beat"]    = _make_danger_beat()


def play(name: str, volume: float = 0.5) -> None:
    """Play a named sound effect.  Silently ignores unknown names."""
    snd = _sounds.get(name)
    if snd:
        snd.set_volume(volume * SETTINGS.sfx_volume)
        snd.play()


def play_cascade(level: int, volume: float = 0.5) -> None:
    """Play a cascade sound pitched higher for each combo level."""
    key = f"cascade_{min(level, 5)}"
    play(key, volume)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _envelope(n: int, attack: float = 0.01, release: float = 0.5) -> np.ndarray:
    """Generate an attack-release amplitude envelope."""
    env = np.ones(n, dtype=np.float64)
    att_samples = int(_RATE * attack)
    rel_samples = int(_RATE * release)
    if att_samples > 0:
        env[:att_samples] = np.linspace(0.0, 1.0, att_samples)
    if rel_samples > 0:
        env[-rel_samples:] = np.linspace(1.0, 0.0, rel_samples)
    return env


def _to_sound(wave: np.ndarray) -> pygame.mixer.Sound:
    """Convert a float64 wave (±1) to a 16-bit stereo pygame Sound."""
    wave = np.clip(wave, -1.0, 1.0)
    pcm = (wave * 32767).astype(np.int16)
    pcm = np.column_stack((pcm, pcm))  # mono → stereo
    return pygame.sndarray.make_sound(pcm)


def _sine(freq: float, dur: float) -> np.ndarray:
    t = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    return np.sin(2 * np.pi * freq * t)


def _noise(dur: float) -> np.ndarray:
    return np.random.uniform(-1.0, 1.0, int(_RATE * dur))


# --------------------------------------------------------------------------- #
# Individual sounds                                                            #
# --------------------------------------------------------------------------- #

def _make_shoot() -> pygame.mixer.Sound:
    """Short descending chirp."""
    dur = 0.08
    t = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    freq = np.linspace(900, 350, len(t))
    wave = np.sin(2 * np.pi * freq * t / _RATE * np.cumsum(np.ones(len(t))))
    # Simpler: use cumulative phase
    phase = np.cumsum(2 * np.pi * freq / _RATE)
    wave = np.sin(phase) * 0.6
    wave *= _envelope(len(wave), attack=0.002, release=0.04)
    return _to_sound(wave)


def _make_pop() -> pygame.mixer.Sound:
    """Punchy pop — sine burst with fast decay."""
    dur = 0.12
    t = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    freq = np.linspace(600, 200, len(t))
    phase = np.cumsum(2 * np.pi * freq / _RATE)
    wave = np.sin(phase) * 0.7
    wave += _noise(dur) * 0.15 * _envelope(len(wave), 0.001, 0.05)
    wave *= _envelope(len(wave), attack=0.001, release=0.08)
    return _to_sound(wave)


def _make_cascade(level: int = 1) -> pygame.mixer.Sound:
    """Ascending two-tone for cascades, pitched higher each combo level."""
    # Each level raises pitch by a perfect fourth (~1.33x), capped at level 5
    pitch = 1.33 ** (level - 1)
    base1, base2 = 520 * pitch, 780 * pitch
    dur = 0.18
    n = int(_RATE * dur)
    half = n // 2
    t1 = np.linspace(0, dur / 2, half, endpoint=False)
    t2 = np.linspace(0, dur / 2, n - half, endpoint=False)
    wave = np.concatenate([
        np.sin(2 * np.pi * base1 * t1) * 0.6,
        np.sin(2 * np.pi * base2 * t2) * 0.6,
    ])
    wave *= _envelope(len(wave), attack=0.002, release=0.06)
    return _to_sound(wave)


def _make_bomb() -> pygame.mixer.Sound:
    """Low rumbling boom."""
    dur = 0.25
    t = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    freq = np.linspace(180, 50, len(t))
    phase = np.cumsum(2 * np.pi * freq / _RATE)
    wave = np.sin(phase) * 0.8
    wave += _noise(dur) * 0.3
    wave *= _envelope(len(wave), attack=0.001, release=0.18)
    return _to_sound(wave)


def _make_coin() -> pygame.mixer.Sound:
    """Bright two-note chime."""
    dur = 0.15
    n = int(_RATE * dur)
    half = n // 2
    t1 = np.linspace(0, dur / 2, half, endpoint=False)
    t2 = np.linspace(0, dur / 2, n - half, endpoint=False)
    wave = np.concatenate([
        np.sin(2 * np.pi * 1200 * t1) * 0.4,
        np.sin(2 * np.pi * 1600 * t2) * 0.4,
    ])
    wave *= _envelope(len(wave), attack=0.002, release=0.06)
    return _to_sound(wave)


def _make_aim() -> pygame.mixer.Sound:
    """Quick ascending sweep for powerup."""
    dur = 0.2
    t = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    freq = np.linspace(400, 1400, len(t))
    phase = np.cumsum(2 * np.pi * freq / _RATE)
    wave = np.sin(phase) * 0.5
    wave *= _envelope(len(wave), attack=0.005, release=0.08)
    return _to_sound(wave)


def _make_swap() -> pygame.mixer.Sound:
    """Quick click for ball swap."""
    dur = 0.05
    t = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    wave = np.sin(2 * np.pi * 800 * t) * 0.4
    wave *= _envelope(len(wave), attack=0.001, release=0.03)
    return _to_sound(wave)


def _make_slowdown() -> pygame.mixer.Sound:
    """Descending sweep for slowdown activation."""
    dur = 0.3
    t = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    freq = np.linspace(800, 300, len(t))
    phase = np.cumsum(2 * np.pi * freq / _RATE)
    wave = np.sin(phase) * 0.5
    wave += np.sin(phase * 2) * 0.15  # harmonic
    wave *= _envelope(len(wave), attack=0.005, release=0.15)
    return _to_sound(wave)


def _make_level_complete() -> pygame.mixer.Sound:
    """Triumphant ascending arpeggio — C E G C'."""
    notes = [523, 659, 784, 1047]  # C5 E5 G5 C6
    note_dur = 0.12
    segments = []
    for freq in notes:
        n = int(_RATE * note_dur)
        t = np.linspace(0, note_dur, n, endpoint=False)
        seg = np.sin(2 * np.pi * freq * t) * 0.5
        seg += np.sin(2 * np.pi * freq * 2 * t) * 0.15  # octave shimmer
        seg *= _envelope(n, attack=0.003, release=0.04)
        segments.append(seg)
    wave = np.concatenate(segments)
    wave *= _envelope(len(wave), attack=0.0, release=0.1)
    return _to_sound(wave)


def _make_game_over() -> pygame.mixer.Sound:
    """Descending minor arpeggio — sad."""
    notes = [440, 370, 330, 262]  # A4 F#4 E4 C4
    note_dur = 0.18
    segments = []
    for freq in notes:
        n = int(_RATE * note_dur)
        t = np.linspace(0, note_dur, n, endpoint=False)
        seg = np.sin(2 * np.pi * freq * t) * 0.5
        seg *= _envelope(n, attack=0.005, release=0.08)
        segments.append(seg)
    wave = np.concatenate(segments)
    wave *= _envelope(len(wave), attack=0.0, release=0.15)
    return _to_sound(wave)


def _make_menu_click() -> pygame.mixer.Sound:
    """Soft UI click."""
    dur = 0.04
    t = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    wave = np.sin(2 * np.pi * 600 * t) * 0.3
    wave *= _envelope(len(wave), attack=0.001, release=0.025)
    return _to_sound(wave)


def _make_danger_beat() -> pygame.mixer.Sound:
    """Deep bass thump for danger heartbeat."""
    dur = 0.14
    t = np.linspace(0, dur, int(_RATE * dur), endpoint=False)
    freq = np.linspace(120, 55, len(t))
    phase = np.cumsum(2 * np.pi * freq / _RATE)
    wave = np.sin(phase) * 0.75
    wave += _noise(dur) * 0.08
    wave *= _envelope(len(wave), attack=0.002, release=0.09)
    return _to_sound(wave)
