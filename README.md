# Poplux

A fast-paced 2D arcade color-matching game built with Python and Pygame.

Aim and shoot colored balls from your ship to match 3 or more in a row — clear the chain before it reaches the hole.

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
python src/editor.py                          # new level
python src/editor.py src/levels/level1.json   # edit existing
```

---

## Controls

| Input | Action |
|---|---|
| **Mouse** | Aim |
| **Left-click** | Shoot |
| **Right-click** | Swap current / next ball |
| **ESC** | Pause / back |
| **Space** | Resume from pause |
| **R** | Retry (pause, lose, or level complete) |
| **M** | Main menu (level complete screen) |
| **Enter** | Next level (level complete screen) |
| **S** (main menu) | Open cheat code menu |

---

## Gameplay

A chain of colored balls advances along a curved path toward a black hole at the end. Shoot balls from your ship to create color matches of 3 or more — matched balls pop and the chain segments catch up, potentially triggering cascades. Clear all balls to win; let the chain reach the hole and it's game over.

### Special Balls

| Ball | How to get | Effect |
|---|---|---|
| **Bonus** (pulsing blue ring) | Spawns in chain | Activates 15 s chain slowdown on pop |
| **Bomb** (fired, ~5% chance) | Ship fires it | Destroys all balls within blast radius (+25 pts each) |
| **Rainbow** (fired, ~5% chance) | Ship fires it | Auto-matches the color it hits |

### Collectibles

| Item | Effect |
|---|---|
| **Coin** (gold star) | +50 pts; fired ball passes through |
| **Aim Line powerup** (cyan crosshair) | 12 s dotted aim line + 2× shot speed |

### Scoring

| Event | Points |
|---|---|
| Ball popped (cascade level N) | N × 5 per ball |
| Bomb blast | +25 per ball destroyed |
| Coin collected | +50 |

Cascade combos build when pops chain into each other, and a **2-second cross-shot window** lets consecutive shots carry the combo multiplier forward.

### Endless Mode

Available per level from the level select screen. No ball limit; chain speed ramps up continuously up to 4× base speed. Score is saved to a separate endless leaderboard.

---

## Cheat Codes

Press **S** on the main menu, type a code, press **Enter**.

| Code | Effect |
|---|---|
| `GODMODE` | Balls reaching the hole are removed instead of causing a loss |
| `SLOWMO` | Chain runs at 25% speed |
| `MAGNET` | Fired balls home in on the nearest chain ball |
| `FASTBALL` | Fired balls travel 3× faster |
| `MULTISHOT` | Each shot fires 3 balls (±15° spread) |
| `RAINBOW` | All fired balls auto-match |
| `RESET` | Clear all active cheats |

---

## Settings

Accessible from the main menu and from the pause menu. Persisted to `config/settings.json`.

| Setting | Description |
|---|---|
| Music Volume | 0–100%, applied live |
| SFX Volume | 0–100% |
| Fullscreen | Toggle |
| Colorblind Mode | Overlays a shape on each ball color |
| Show FPS | Frame rate counter during gameplay |
| Danger Vignette | Red screen-edge pulse when chain is close to the hole |
| Particles | Ball-pop particle bursts |

---

## Project Structure

```
Zuma/
├── README.md
├── DESIGN.md               # high-level design document
├── LOW_LEVEL_DESIGN.md     # class diagrams and data-flow documentation
├── requirements.txt
├── config/
│   └── settings.json       # persisted user settings (created on first run)
├── ASSETS/                 # music tracks (MENU, IN-GAME, FINISH .mp3) + fonts
├── src/
│   ├── main.py             # entry point
│   ├── settings.py         # constants, level loader, SETTINGS singleton
│   ├── game.py             # game loop and state machine
│   ├── path.py             # Catmull-Rom spline with arc-length parameterization
│   ├── frog.py             # shooter: aim, fire, swap, ball generation
│   ├── ball.py             # Ball, Coin, Particle, ScorePopup, AimPowerup dataclasses
│   ├── chain.py            # ball chain: movement, insertion, gap closing, cascades
│   ├── renderer.py         # all Pygame drawing: game, HUD, menus, overlays
│   ├── sounds.py           # synthesized SFX (numpy) and music track management
│   ├── records.py          # per-level score persistence via platformdirs
│   ├── background.py       # procedural starfield and animated asteroid background
│   ├── editor.py           # interactive level path editor
│   └── levels/
│       ├── level1.json     # The Spiral
│       ├── level2.json     # The Snake
│       ├── level3.json     # The Scramble
│       ├── level4.json     # Zigzag
│       ├── level5.json     # Twin Coils
│       ├── level6.json     # The Vortex
│       ├── level7.json     # Infinity
│       └── level8.json     # The Labyrinth
└── tests/
    ├── test_chain_catchup.py
    ├── test_chain_insert.py
    └── test_frog.py
```

---

## License

MIT
