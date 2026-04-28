# Poplux

A fast-paced 2D arcade color-matching game built with Python and Pygame.

Aim and shoot colored balls from your ship to match 3 or more in a row — clear the chain before it reaches the hole.

---

## Controls

| Input | Action |
|---|---|
| **Left-click** | Shoot |
| **Right-click** | Swap current / next ball |
| **ESC** | Pause / back |
| **Space** | Resume from pause |
| **R** | Retry (on pause, lose, or level complete screens) |
| **M** | Main menu (on level complete screen) |
| **S** (main menu) | Open cheat code menu |

---

## Features

- 8 levels with distinct paths: spiral, serpentine, scramble, zigzag, twin coils, vortex, infinity, labyrinth
- Endless mode per level — chain speed ramps up over time, no ball limit
- Smooth Catmull-Rom spline paths with arc-length parameterization
- Ball chain with gap-closing, cascade pops, and insertion animations
- Rolling ball visuals with synchronized rotation band effect
- Particle bursts on every pop, screen shake on cascades
- Synthesized sound effects (no audio files required) + streamed background music
- Special balls: **Bonus** (slowdown), **Bomb** (blast radius), **Rainbow** (auto-match)
- Collectibles: **Coins** (+10 pts) and **Aim Line** powerups
- Records screen with three tabs: Best by Level / Best Endless / All Runs
- "NEW BEST!" banner on level complete and endless game over when a record is beaten
- Settings: music volume, SFX volume, fullscreen toggle, colorblind mode, FPS display, danger vignette, particles
- Settings accessible from both main menu and pause menu
- Danger heartbeat sound and red vignette pulse as the chain approaches the hole
- Animated score counter with combo multiplier popups
- Cheat code menu (press S on main menu)
- Procedural animated asteroid background
- Fullscreen at 1920×1080 logical resolution, letterboxed to any display size

---

## Special Balls

| Ball | Effect |
|---|---|
| Bonus (pulsing blue ring) | Activates 15s chain slowdown |
| Bomb (fired) | Destroys all balls within blast radius |
| Rainbow (fired) | Auto-matches the color it hits |

---

## Cheat Codes

Access from the main menu (press S), then type a code and press Enter.

| Code | Effect |
|---|---|
| `GODMODE` | Balls reaching the hole are removed instead of causing a loss |
| `SLOWMO` | Chain runs at 25% speed |
| `MAGNET` | Fired balls home in on the nearest chain ball |
| `FASTBALL` | Fired balls travel 3× faster |
| `MULTISHOT` | Each shot fires 3 balls |
| `RAINBOW` | All fired balls auto-match |
| `RESET` | Clear all active cheats |

---

## Requirements

- Python 3.10+
- Pygame 2.6+
- NumPy 2.0+
- platformdirs 4.0+

```bash
pip install -r requirements.txt
```

---

## Running

```bash
python src/main.py
```

### Level Editor

```bash
python src/editor.py
python src/editor.py src/levels/level1.json   # load existing level
```

---

## Project Structure

```
Zuma/
├── README.md
├── DESIGN.md
├── requirements.txt
├── settings.json           # persisted user settings (created on first run)
├── ASSETS/                 # music tracks (MENU, IN-GAME, FINISH .mp3) + fonts
└── src/
    ├── main.py             # entry point
    ├── settings.py         # constants, level loader, SETTINGS singleton
    ├── game.py             # game loop and state machine
    ├── path.py             # spline path with arc-length parameterization
    ├── frog.py             # shooter logic
    ├── ball.py             # ball, coin, particle, and powerup data classes
    ├── chain.py            # ball chain: movement, insertion, matching, cascades
    ├── renderer.py         # all drawing code
    ├── sounds.py           # synthesized SFX and music management
    ├── records.py          # per-level score/time persistence (platformdirs)
    ├── background.py       # procedural starfield and asteroid background
    ├── editor.py           # interactive level editor
    └── levels/
        ├── level1.json     # The Spiral
        ├── level2.json     # The Snake
        ├── level3.json     # The Scramble
        ├── level4.json     # Zigzag
        ├── level5.json     # Twin Coils
        ├── level6.json     # The Vortex
        ├── level7.json     # Infinity
        └── level8.json     # The Labyrinth
```

---

## License

MIT
