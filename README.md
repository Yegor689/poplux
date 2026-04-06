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
| **S** | Toggle debug HUD |

---

## Features

- 6 levels with distinct paths: spiral, serpentine, winding, zigzag, double loop, vortex
- Smooth Catmull-Rom spline paths with arc-length parameterization
- Ball chain with gap-closing, cascade pops, and insertion animations
- Rolling ball visuals with synchronized rotation band effect
- Particle bursts on every pop
- Synthesized sound effects (no audio files required) + streamed background music
- Special balls: **Bonus** (slowdown), **Bomb** (blast radius), **Rainbow** (auto-match)
- Collectibles: **Coins** (+10 pts) and **Aim Line** powerups
- Per-level best score and time records
- Cheat code menu (press S on main menu)
- Fullscreen at 1280×960 logical resolution scaled to fit any screen

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
- Pygame 2.x
- NumPy (for synthesized sound)

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
poplux/
├── README.md
├── DESIGN.md
├── requirements.txt
├── ASSETS/             # music tracks (MENU, IN-GAME, FINISH, FAIL .mp3)
└── src/
    ├── main.py         # entry point
    ├── settings.py     # constants and level loader
    ├── game.py         # game loop and state machine
    ├── path.py         # spline path with arc-length parameterization
    ├── frog.py         # shooter logic
    ├── ball.py         # ball, coin, particle, and powerup data classes
    ├── chain.py        # ball chain: movement, insertion, matching, cascades
    ├── renderer.py     # all drawing code
    ├── sounds.py       # synthesized SFX and music management
    ├── records.py      # per-level score/time persistence
    ├── background.py   # starfield and asteroid background
    ├── editor.py       # interactive level editor
    └── levels/
        ├── level1.json
        ├── level2.json
        ├── level3.json
        ├── level4.json
        ├── level5.json
        └── level6.json
```

---

## License

MIT
