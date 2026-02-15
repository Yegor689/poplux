# Poplux — Design Document

## 1. Game Overview

A single-player 2D arcade color-matching game. A frog sits at the center of the screen, surrounded by a curved path along which a chain of colored balls advances. The player aims and shoots colored balls from the frog to match three or more of the same color, removing them from the chain. The goal is to eliminate all balls before they reach the endpoint hole.

**Framework:** Pygame
**Language:** Python 3.10+
**Display:** Fullscreen (logical canvas 800×600, scaled to fill screen)
**Ball Colors:** Red, Green, Blue, Yellow
**Levels:** Multiple levels defined as JSON files in `src/levels/`

---

## 2. Core Mechanics

### 2.1 The Path
- Each level defines a curve as a sequence of control waypoints, smoothed via centripetal Catmull-Rom splines and resampled to a uniform arc-length parameterization.
- Has a **spawn point** (start) where new balls enter and an **endpoint hole** (end) where balls must not reach.
- Balls move along this path at a constant speed toward the endpoint.

### 2.2 The Frog (Shooter)
- Positioned at a level-defined position (default: screen center).
- Rotates to face the mouse cursor.
- Holds a **current ball** (at its mouth) and a **next ball** (behind the body).
- **Left-click:** fires the current ball; next becomes current, a new random ball is generated.
- **Right-click:** swaps current and next ball.

### 2.3 Ball Chain
- An ordered sequence of colored balls advancing along the path.
- Each ball's position is expressed as a distance along the path.
- New balls spawn at the rear when the chain advances far enough to create space.
- When a gap opens (e.g. after a pop), the front segment reverses at high speed to close it.

### 2.4 Shooting & Insertion
- Fired balls travel in a straight line from the frog at high speed.
- On collision with a chain ball, the fired ball inserts into the chain at the appropriate position.
- Neighboring balls animate outward to make room, then settle.
- The inserted ball plays an entry animation, sliding from its fired position into its chain slot.

### 2.5 Match Detection & Removal
- After insertion, the contiguous same-color group around the new ball is checked.
- If the group is **3 or more**, it is queued to pop after a short delay.
- After a pop, if the newly adjacent balls form another match, a **cascade** follows with a brief inter-pop delay.
- Cascades continue until no new matches form.

### 2.6 Win / Loss Conditions
- **Win:** All balls are removed and no more balls remain to spawn.
- **Loss:** The leading ball reaches the endpoint hole.

### 2.7 Pause
- **ESC while playing** pauses the game; the simulation freezes and a pause menu appears.
- The pause menu offers: Resume, Restart (current level), and Main Menu.

---

## 3. Architecture

```
┌──────────────────────────────────────────────┐
│                    Game                       │
│   (main loop, state machine, event handling)  │
├──────────┬──────────┬───────────┬────────────┤
│  Path    │  Frog    │  Chain    │  Renderer  │
│          │          │           │            │
│ waypoints│ position │ balls[]   │ draw all   │
│ sample() │ angle    │ advance() │ menus/HUD  │
│ tangent()│ shoot()  │ insert()  │            │
│          │ swap()   │ match()   │            │
└──────────┴──────────┴───────────┴────────────┘
```

### Module Breakdown

| Module | Responsibility |
|---|---|
| `main.py` | Entry point. Initializes Pygame and starts the game loop. |
| `game.py` | Owns game state, orchestrates updates, handles all input and state transitions. |
| `path.py` | Catmull-Rom spline path with arc-length parameterization. Provides position, tangent, and nearest-point queries. |
| `frog.py` | Frog rotation, current/next ball management, firing and swapping. |
| `chain.py` | Ordered ball list: advance, insertion, gap closing, match detection, cascade pop logic. |
| `ball.py` | Ball data: color, path position, spin angle, insertion animation state, and fired-ball velocity. |
| `renderer.py` | All Pygame drawing: path, chain, frog, fired balls, HUD, all menus and overlays. |
| `settings.py` | Constants and tuning values (sizes, speeds, colors, FPS). |
| `levels/*.json` | Level definitions: path waypoints, frog position, chain speed, ball count, etc. |

---

## 4. Game States

| State | Description |
|---|---|
| `main_menu` | Title screen with Play, Select Level, Quit. |
| `level_select` | Grid of level buttons. |
| `playing` | Active gameplay. |
| `paused` | Game frozen; pause menu overlay shown. |
| `level_complete` | Level cleared; shows Next Level / Main Menu. |
| `game_complete` | All levels cleared. |
| `lose` | Chain reached the hole. |

---

## 5. Visual Details

| Element | Description |
|---|---|
| **Path** | Dark gray tube drawn along waypoints with a filled endpoint hole. |
| **Chain balls** | Layered circles with rim, base color, inner glow, sheen, and specular highlight. A rotating seam stripe is drawn perpendicular to the travel direction, spinning forward as the ball rolls (top-forward rolling physics). |
| **Frog** | Multi-layer green circle body with bulging eyes, nostrils, and feet. Rotates to face mouse. Current ball shown at mouth; next ball shown smaller behind the body. |
| **Fired ball** | Same appearance as chain balls (no spin stripe). |
| **HUD** | Level name, balls remaining on path, and balls left to spawn — top-left corner. |
| **Menus / overlays** | Semi-transparent dark overlays with styled rounded-rect buttons (main menu, level select, pause, level complete). |

---

## 6. Project File Structure

```
Zuma/
├── DESIGN.md
├── requirements.txt
└── src/
    ├── main.py
    ├── settings.py
    ├── game.py
    ├── path.py
    ├── frog.py
    ├── ball.py
    ├── chain.py
    ├── renderer.py
    └── levels/
        ├── level1.json
        └── level2.json
```

---

## 7. Future Considerations

- Score system and combo multipliers
- Power-up balls (bomb, slow, wildcard)
- Sound effects and music
- Animated background / themed art per level
- Difficulty scaling (chain speed increases over time)
- Additional ball colors and larger levels
