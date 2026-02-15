# Poplux

A fast-paced 2D arcade color-matching game built with Python and Pygame.

Aim and shoot colored balls from your frog to match 3 or more in a row — clear the chain before it reaches the hole.

---

## Gameplay

- **Left-click** — shoot
- **Right-click** — swap current and next ball
- **ESC** — pause / back
- **S** — toggle debug info

### Scoring
Each ball popped is worth **1 point × combo multiplier**. Chain reactions multiply your score — the longer the cascade, the higher the multiplier.

---

## Features

- Smooth Catmull-Rom spline paths defined per level
- Ball chain with gap-closing, cascade pops, and insertion animations
- Rolling ball visuals with a synchronized rotation band effect
- Particle burst on every pop
- Frog recoil animation on shoot
- Exhausted color removal — once a color is cleared from the chain, the frog stops generating it
- Pause menu with Resume / Restart / Main Menu
- Score display with combo multiplier
- On-screen timer
- Fullscreen by default

---

## Requirements

- Python 3.10+
- Pygame 2.x

```bash
pip install -r requirements.txt
```

---

## Running

```bash
python src/main.py
```

---

## Project Structure

```
poplux/
├── README.md
├── DESIGN.md
├── requirements.txt
└── src/
    ├── main.py         # entry point
    ├── settings.py     # constants and config
    ├── game.py         # game loop and state machine
    ├── path.py         # spline path with arc-length parameterization
    ├── frog.py         # shooter logic
    ├── ball.py         # ball and particle data classes
    ├── chain.py        # ball chain: movement, insertion, matching, cascades
    ├── renderer.py     # all drawing code
    └── levels/
        ├── level1.json
        └── level2.json
```

---

## License

MIT
