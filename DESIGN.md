# Poplux — Design Document

## 1. Game Overview

A single-player 2D arcade color-matching game. A ship sits at a fixed position on screen, surrounded by a curved path along which a chain of colored balls advances. The player aims and shoots colored balls from the ship to match three or more of the same color, removing them from the chain. The goal is to eliminate all balls before they reach the endpoint hole.

**Framework:** Pygame 2.6+  
**Language:** Python 3.10+  
**Display:** Fullscreen (logical canvas 1920×1080, 16:9), letterboxed to any physical resolution. Level paths are authored at 1280×960 and scaled uniformly to fit the canvas height, centered horizontally.  
**Ball Colors:** Red, Green, Blue, Yellow  
**Levels:** 8 levels defined as JSON files in `src/levels/`

---

## 2. Core Mechanics

### 2.1 The Path
- Each level defines a curve as a sequence of control waypoints, smoothed via centripetal Catmull-Rom splines and resampled to a uniform arc-length parameterization.
- Has a **spawn point** (start) where new balls enter and an **endpoint hole** (end) where balls must not reach.
- Balls move along this path at a constant speed toward the endpoint.

### 2.2 The Ship (Shooter)
- Positioned at a level-defined position (default: screen center).
- Rotates to face the mouse cursor.
- Visually rendered as a gunmetal hull with swept wings, a cannon barrel, an amber-accented visor slit, and twin engine glows.
- Holds a **current ball** (at the cannon tip) and a **next ball** (recessed in the magazine bay behind the hull).
- **Left-click:** fires the current ball; next becomes current, a new random ball is generated.
- **Right-click:** swaps current and next ball.

### 2.3 Ball Chain
- An ordered sequence of colored balls advancing along the path.
- Each ball's position is expressed as a distance along the path.
- New balls spawn at the rear when the chain advances far enough to create space.
- When a gap opens (e.g. after a pop), the front segment reverses at high speed to close it.
- Gaps between segments are tracked with `_GAP_THRESHOLD`; each open gap bounds a segment so that freeze/catch-up and insertion push effects never cross segment boundaries.
- If a bomb wipes the entire chain, spawning resumes from the path origin.

### 2.4 Shooting & Insertion
- Fired balls travel in a straight line from the ship at high speed.
- On collision with a chain ball, the fired ball inserts into the chain at the appropriate position.
- Balls ahead of the insertion point animate outward to make room (`_gap_remaining`, animated by `advance()`).
- The inserted ball plays an entry animation (`entry_t`), sliding from its fired position into its chain slot over ~0.17 s.

### 2.5 Match Detection & Removal
- After insertion, the contiguous same-color group around the new ball is checked.
- If the group is **3 or more**, it is queued to pop after a short delay (entry animation completes).
- After a pop, if the newly adjacent balls form another match, a **cascade** follows with a brief inter-pop delay (0.5 s).
- Cascades continue until no new matches form. Each cascade level increments the combo multiplier.

### 2.6 Special Balls
- **Bonus ball:** Appears randomly in the chain; popping it activates a 15-second slowdown (chain at 35% speed). Rendered with a pulsing blue ring.
- **Bomb ball:** Fired by the ship (~5% chance); destroys all balls within a fixed blast radius on impact.
- **Rainbow ball:** Fired by the ship (~5% chance); auto-matches the color of the ball it hits.

### 2.7 Collectibles & Powerups
- **Coins:** Appear at level-defined spots on a random timer (15–25 s). Shooting a coin scores +10 points.
- **Aim Line powerup:** Appears at level-defined spots on a random timer (20–35 s). A fired ball passing through it activates a 12-second dotted aim-line trajectory indicator. Does not consume the fired ball.

### 2.8 Catch-Up & Freeze Mechanics
- Gaps are evaluated per-segment after every `advance()` tick.
- When a gap opens between two balls of **different** colors, the front segment freezes (its forward advance is reversed each tick).
- When a gap opens between two balls of the **same** color, the front segment accelerates backward to close the gap (`_CATCH_UP_MULTIPLIER = 10×`).
- When a gap closes on a **matching** join, both segments are snapped flush and the merged segment is packed outward from the join point. A match check fires immediately.
- When a gap closes on a **non-matching** join, the rear ball is snapped behind the front ball and the rear segment is packed backward.

### 2.9 Scoring
- Each popped ball scores `cascade_level × 5` points.
- Score is displayed via an animated counter that closes the gap in ~0.3 s.
- A floating popup shows the score delta; cascade pops show `+N × multiplier`.
- Coins score +10 each.

### 2.10 Endless Mode
- Available for every level from the level select screen.
- No ball limit; the chain spawns indefinitely.
- Chain speed ramps up continuously: `speed = base_speed × (1 + elapsed / 120)`, capped at 4× base.
- Loss condition is the same (chain reaches the hole). Score is saved to a separate endless leaderboard.

### 2.11 Win / Loss Conditions
- **Win (normal):** All balls are removed and no more balls remain to spawn.
- **Loss:** The leading ball reaches the endpoint hole.
- In endless mode there is no win; only loss (chain reached the hole).

### 2.12 Pause
- **ESC while playing** pauses the game; the simulation freezes and a pause menu appears.
- The pause menu offers: Resume, Restart (current level), Settings, and Main Menu.
- **Space** also resumes from pause.

---

## 3. Architecture

```
┌──────────────────────────────────────────────────┐
│                      Game                         │
│   (main loop, state machine, event handling)      │
├──────────┬──────────┬───────────┬────────────────┤
│  Path    │  Frog    │  Chain    │  Renderer      │
│          │          │           │                │
│ waypoints│ position │ balls[]   │ draw all       │
│ sample() │ angle    │ advance() │ menus/HUD      │
│ tangent()│ shoot()  │ insert()  │                │
│          │ swap()   │ match()   │                │
└──────────┴──────────┴───────────┴────────────────┘
         Background              Records
         (starfield +            (JSON persistence
          asteroids)              via platformdirs)
                    Sounds
                    (synthesized SFX
                     + streamed music)
```

### Module Breakdown

| Module | Responsibility |
|---|---|
| `main.py` | Entry point. Initializes Pygame and starts the game loop. |
| `game.py` | Owns game state, orchestrates updates, handles all input and state transitions. Manages music track switching. |
| `path.py` | Catmull-Rom spline path with arc-length parameterization. Provides position, tangent, and nearest-point queries. |
| `frog.py` | Ship rotation, current/next ball management, firing and swapping. Refreshes ball color pool when colors are exhausted from the chain. |
| `chain.py` | Ordered ball list: advance, insertion, segment-isolated gap closing, match detection, cascade pop logic. |
| `ball.py` | Ball data: color, path position, spin angle, insertion animation state, fired-ball velocity. Also defines `Coin`, `Particle`, `ScorePopup`, and `AimPowerup` dataclasses. |
| `renderer.py` | All Pygame drawing: path, chain, ship, fired balls, coins, aim powerups, aim line, HUD, all menus and overlays. |
| `sounds.py` | Synthesized sound effects (numpy waveforms) and streamed music track management. |
| `settings.py` | Constants and tuning values (sizes, speeds, colors, FPS). Loads level JSON files. Hosts the `SETTINGS` singleton (volumes, fullscreen, colorblind mode, etc.), persisted to `settings.json`. |
| `records.py` | Saves and loads per-level score records as JSON via `platformdirs`. Provides `best_by_level()`, `best_by_endless()`, `top()`, `top_endless()`, and `is_new_best()`. |
| `background.py` | Procedural starfield (rendered once, seeded) and animated asteroids (numpy-rendered silhouettes with noise texture and distance-based craters). |
| `editor.py` | Interactive level editor for creating and modifying level waypoints. |
| `levels/*.json` | Level definitions: path waypoints, frog position, chain speed, ball count, coin spots, aim powerup spots. |

---

## 4. Game States

| State | Description | Music |
|---|---|---|
| `main_menu` | Title screen with Play, Select Level, Records, Settings, Quit. | MENU.mp3 (loop) |
| `level_select` | Scrollable level list with detail panel; shows normal best and endless best per level. | MENU.mp3 (loop) |
| `playing` | Active gameplay (normal or endless mode). | IN-GAME.mp3 (loop) |
| `paused` | Game frozen; pause menu overlay shown (Resume / Restart / Settings / Main Menu). | IN-GAME.mp3 (loop) |
| `level_complete` | Level cleared; shows score, NEW BEST banner if applicable, Next Level / Main Menu. | FINISH.mp3 (once) |
| `game_complete` | All levels cleared. | FINISH.mp3 (once) |
| `lose` | Chain reached the hole; shows score and NEW BEST banner (endless only) if applicable. | IN-GAME.mp3 (loop) |
| `records` | Three-tab records screen: Best by Level / Best Endless / All Runs. | MENU.mp3 (loop) |
| `settings` | Settings screen. Reachable from main menu and pause menu; ESC returns to the originating state. | MENU.mp3 (loop) |
| `cheat_menu` | Cheat code entry screen. | MENU.mp3 (loop) |
| `combo_test` | Developer mode: two colors, pair-mode chain, infinite balls, no win/lose. | IN-GAME.mp3 (loop) |

---

## 5. Sound Design

### 5.1 Music
Streamed via `pygame.mixer.music`. Tracks located in `ASSETS/`:

| File | Used for |
|---|---|
| `MENU.mp3` | All menu and non-gameplay states |
| `IN-GAME.mp3` | Active gameplay and lose screen |
| `FINISH.mp3` | Level/game complete (plays once) |

### 5.2 Sound Effects
Synthesized at startup using numpy waveforms (no audio files required):

| Sound | Trigger |
|---|---|
| `shoot` | Ball fired |
| `pop` | Match cleared (cascade level 1) |
| `cascade_N` | Cascade cleared at level N (pitch rises each level, up to level 5) |
| `bomb` | Bomb ball explodes |
| `coin` | Coin collected |
| `aim` | Aim line powerup collected |
| `swap` | Current/next ball swapped |
| `slowdown` | Bonus ball popped (slowdown activated) |
| `level_complete` | Level won (ascending C–E–G–C arpeggio) |
| `game_over` | Level lost (descending minor arpeggio) |
| `menu_click` | Menu button pressed |
| `danger_beat` | Heartbeat pulse when chain is near the hole (rate increases with proximity) |

---

## 6. Visual Details

| Element | Description |
|---|---|
| **Background** | Dark blue-black sky with a seeded starfield of 400 procedural stars (dim, mid, bright tiers) with diffraction spikes on the brightest. 14 animated asteroids drift across the field; each is numpy-rendered with a polar silhouette mask, layered noise texture, edge vignette, and distance-based craters. Drawn at 60% opacity. |
| **Path** | Dark gray tube drawn along waypoints. A pulsing purple/magenta black-hole at the endpoint with accretion disk rings. |
| **Chain balls** | Layered circles: base color, dark rim, inner glow, sheen, and specular highlight. A rotating seam stripe is drawn perpendicular to the travel direction. Bonus balls have a pulsing blue ring. Colorblind mode overlays a distinct symbol on each color. |
| **Ship** | Gunmetal hull with swept two-part wings, amber leading-edge trim, a cannon barrel, a flat visor slit with cyan scan-line, a nose cone, twin engine glows, and hull accent rings. Rotates to face mouse. Current ball shown at cannon tip; next ball shown smaller in the rear magazine bay. |
| **Fired ball** | Same appearance as chain balls. Travels in a straight line until chain collision or out-of-bounds. |
| **Coins** | Pulsing gold circles with a spinning star icon and glow rings. |
| **Aim powerup** | Pulsing cyan crosshair with glow rings. |
| **Aim line** | Animated scrolling dotted line from ship to first collision point, on a per-frame SRCALPHA surface. |
| **HUD** | Score box (top-left, animated counter), timer (top-center), balls-remaining box (top-right), slowdown and aim line progress bars (bottom-right when active), FPS counter (optional). |
| **Danger vignette** | Red pulsing edge vignette baked as a numpy gradient, applied when the chain front exceeds 82% of path length. Intensity and pulse rate increase with proximity. |
| **Score popups** | Floating text with cascade-level-scaled font; yellow for level 1, orange for level 2, coral for level 3+. |
| **Level select** | Scrollable list on the left; detail panel on the right shows level name, subtitle, stats, and best normal run + best endless run side by side. |
| **Records screen** | Three tabs: Best by Level (grid), Best Endless (grid), All Runs (paginated list). |
| **Pause menu** | Semi-transparent overlay with RESUME / RESTART / SETTINGS / MAIN MENU buttons. |
| **Level complete** | Shows score, optional NEW BEST banner, Next Level and Main Menu buttons. Keyboard hints: Enter/Space, R, M. |
| **Lose screen** | Shows score, optional NEW BEST banner (endless only), RETRY and MAIN MENU buttons. |

---

## 7. Project File Structure

```
Zuma/
├── DESIGN.md
├── README.md
├── requirements.txt
├── settings.json               # persisted user settings (created on first run)
├── ASSETS/
│   ├── MENU.mp3
│   ├── IN-GAME.mp3
│   ├── FINISH.mp3
│   ├── Orbitron-VariableFont_wght.ttf
│   ├── Exo2-VariableFont_wght.ttf
│   └── NotoSansSymbols2-Regular.ttf
├── src/
│   ├── main.py
│   ├── settings.py
│   ├── game.py
│   ├── path.py
│   ├── frog.py
│   ├── ball.py
│   ├── chain.py
│   ├── renderer.py
│   ├── sounds.py
│   ├── records.py
│   ├── background.py
│   ├── editor.py
│   └── levels/
│       ├── level1.json         # The Spiral
│       ├── level2.json         # The Snake
│       ├── level3.json         # The Scramble
│       ├── level4.json         # Zigzag
│       ├── level5.json         # Twin Coils
│       ├── level6.json         # The Vortex
│       ├── level7.json         # Infinity
│       └── level8.json         # The Labyrinth
└── tests/
    ├── test_chain_catchup.py
    ├── test_chain_insert.py
    └── test_frog.py
```

---

## 8. Cheat Codes

Accessible from the main menu (press S). Enter code and press Enter to toggle.

| Code | Effect |
|---|---|
| `GODMODE` | Chain balls that reach the hole are removed instead of triggering a loss |
| `SLOWMO` | Chain advances at 25% speed |
| `MAGNET` | Fired balls home in on the nearest chain ball |
| `FASTBALL` | Fired balls travel 3× faster |
| `MULTISHOT` | Each shot fires 3 balls (±15° spread) |
| `RAINBOW` | All fired balls auto-match the color they hit |
| `RESET` | Clear all active cheats |

---

## 9. Settings

Accessible from the main menu and from the pause menu. Persisted to `settings.json` next to `src/`.

| Setting | Description |
|---|---|
| Music Volume | Slider, 0–100%. Applied live via `pygame.mixer.music.set_volume()`. |
| SFX Volume | Slider, 0–100%. Applied to all synthesized sound effects. |
| Fullscreen | Toggle. Switches between `pygame.FULLSCREEN` and windowed mode. |
| Colorblind Mode | Overlays a distinct symbol on each ball color: ring (red), triangle (green), square (blue), diamond (yellow). |
| Show FPS | Displays frame rate in the top-right corner during gameplay. |
| Danger Vignette | Toggles the red screen-edge pulse when the chain approaches the hole. |
| Particles | Toggles particle bursts on ball pops. |

---

## 10. Records

Records are persisted as JSON via `platformdirs.user_data_dir("Poplux")`. Each record stores level name, score, elapsed time (seconds), and date.

The records screen has three tabs:
- **Best by Level** — one row per level, showing highest score run.
- **Best Endless** — one row per endless slot, showing highest score endless run.
- **All Runs** — full paginated list of every run, newest first.

`is_new_best()` is called before `save()` so the comparison is against the pre-save state.
