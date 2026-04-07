# Poplux — Design Document

## 1. Game Overview

A single-player 2D arcade color-matching game. A ship sits at a fixed position on screen, surrounded by a curved path along which a chain of colored balls advances. The player aims and shoots colored balls from the ship to match three or more of the same color, removing them from the chain. The goal is to eliminate all balls before they reach the endpoint hole.

**Framework:** Pygame  
**Language:** Python 3.10+  
**Display:** Fullscreen (logical canvas 1920×1080, 16:9). Level paths are authored at 1280×960 and scaled uniformly to fit the canvas height, centered horizontally.  
**Ball Colors:** Red, Green, Blue, Yellow  
**Levels:** Multiple levels defined as JSON files in `src/levels/`

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
- If a bomb wipes the entire chain, spawning resumes from the path origin.

### 2.4 Shooting & Insertion
- Fired balls travel in a straight line from the ship at high speed.
- On collision with a chain ball, the fired ball inserts into the chain at the appropriate position.
- Neighboring balls animate outward to make room, then settle.
- The inserted ball plays an entry animation, sliding from its fired position into its chain slot.

### 2.5 Match Detection & Removal
- After insertion, the contiguous same-color group around the new ball is checked.
- If the group is **3 or more**, it is queued to pop after a short delay.
- After a pop, if the newly adjacent balls form another match, a **cascade** follows with a brief inter-pop delay.
- Cascades continue until no new matches form.

### 2.6 Special Balls
- **Bonus ball:** Appears randomly in the chain; popping it activates a 15-second slowdown. Rendered with a pulsing blue ring.
- **Bomb ball:** Fired by the ship; destroys up to 3 balls on each side of the impact point.
- **Rainbow ball:** Fired by the ship; auto-matches the color of the ball it hits.

### 2.7 Collectibles & Powerups
- **Coins:** Appear at fixed spots per level on a timer. Shooting a coin scores +10 points and removes it.
- **Aim Line powerup:** Appears at fixed spots per level on a timer. A fired ball passing through it activates a 12-second dotted aim-line trajectory indicator (like the original Zuma). Does not consume the fired ball.

### 2.8 Catch-Up & Freeze Mechanics
- When a gap opens between two balls of **different** colors, all balls ahead of the gap freeze.
- When a gap opens between two balls of the **same** color, the rear segment accelerates toward the front to close the gap.
- `frozen_by` dict tracks the nearest (rightmost) non-matching gap per ball, allowing catch-up to occur correctly within frozen segments when a matching gap is closer than the freeze source.

### 2.9 Win / Loss Conditions
- **Win:** All balls are removed and no more balls remain to spawn.
- **Loss:** The leading ball reaches the endpoint hole.

### 2.10 Pause
- **ESC while playing** pauses the game; the simulation freezes and a pause menu appears.
- The pause menu offers: Resume, Restart (current level), and Main Menu.

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
                                   sounds
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
| `chain.py` | Ordered ball list: advance, insertion, gap closing, match detection, cascade pop logic. |
| `ball.py` | Ball data: color, path position, spin angle, insertion animation state, fired-ball velocity. Also defines `Coin`, `Particle`, `ScorePopup`, and `AimPowerup` dataclasses. |
| `renderer.py` | All Pygame drawing: path, chain, ship, fired balls, coins, aim powerups, aim line, HUD, all menus and overlays. Caches the starfield background and path surface to avoid redundant per-frame draw calls. |
| `sounds.py` | Synthesized sound effects (numpy waveforms) and streamed music track management. |
| `settings.py` | Constants and tuning values (sizes, speeds, colors, FPS). Loads level JSON files. Hosts the `SETTINGS` singleton (music volume, colorblind mode). |
| `records.py` | Saves and loads per-level score records as JSON. Provides `best_by_level()` for the level select screen. |
| `editor.py` | Interactive level editor for creating and modifying level waypoints. |
| `levels/*.json` | Level definitions: path waypoints, frog position, chain speed, ball count, coin spots, aim powerup spots. |

---

## 4. Game States

| State | Description | Music |
|---|---|---|
| `main_menu` | Title screen with Play, Select Level, Records, Settings, Quit. | MENU.mp3 (loop) |
| `level_select` | Grid of level cards with best score per level. | MENU.mp3 (loop) |
| `playing` | Active gameplay. | IN-GAME.mp3 (loop) |
| `paused` | Game frozen; pause menu overlay shown. | MENU.mp3 (loop) |
| `level_complete` | Level cleared; shows Next Level / Main Menu. | FINISH.mp3 (once) |
| `game_complete` | All levels cleared. | FINISH.mp3 (once) |
| `lose` | Chain reached the hole. | IN-GAME.mp3 (loop) |
| `records` | High score table. | MENU.mp3 (loop) |
| `cheat_menu` | Cheat code entry screen. | MENU.mp3 (loop) |
| `settings` | Settings screen (music volume, colorblind mode). | MENU.mp3 (loop) |
| `combo_test` | Developer mode for testing chain combos. | IN-GAME.mp3 (loop) |

---

## 5. Sound Design

### 5.1 Music
Streamed via `pygame.mixer.music`. Tracks located in `ASSETS/`:

| File | Used for |
|---|---|
| `MENU.mp3` | All menu and non-gameplay states |
| `IN-GAME.mp3` | Active gameplay |
| `FINISH.mp3` | Level/game complete (plays once) |

### 5.2 Sound Effects
Synthesized at startup using numpy waveforms (no audio files required):

| Sound | Trigger |
|---|---|
| `shoot` | Ball fired |
| `pop` | Match cleared (cascade level 1) |
| `cascade_N` | Cascade cleared at level N (pitch rises with each level, up to level 5) |
| `bomb` | Bomb ball explodes |
| `coin` | Coin collected |
| `aim` | Aim line powerup collected |
| `swap` | Current/next ball swapped |
| `slowdown` | Bonus ball popped (slowdown activated) |
| `level_complete` | Level won (ascending C–E–G–C arpeggio) |
| `game_over` | Level lost (descending minor arpeggio) |
| `menu_click` | Menu button pressed |

---

## 6. Visual Details

| Element | Description |
|---|---|
| **Background** | Dark blue-black sky with a cached starfield of 260 procedural stars (dim, mid, bright) with diffraction spikes on the brightest ones. Rendered once and blitted each frame. Animated asteroids drift across the field. |
| **Path** | Dark gray tube drawn along waypoints with a filled endpoint hole. Cached to an off-screen surface and invalidated when the level changes. |
| **Chain balls** | Layered circles with rim, base color, inner glow, sheen, and specular highlight. A rotating seam stripe is drawn perpendicular to the travel direction, spinning forward as the ball rolls. Bonus balls have a pulsing blue ring. |
| **Ship** | Gunmetal hull with swept two-part wings, amber leading-edge trim, a cannon barrel, a flat visor slit with cyan scan-line, a nose cone, twin engine glows, and hull accent rings. Rotates to face mouse. Current ball shown at cannon tip; next ball shown smaller in the rear magazine bay. |
| **Fired ball** | Same appearance as chain balls. |
| **Coins** | Pulsing gold circles with a spinning star icon and glow rings. |
| **Aim powerup** | Pulsing cyan crosshair with glow rings. |
| **Aim line** | Animated scrolling dotted line from ship to first collision point, drawn on a per-frame SRCALPHA surface. |
| **HUD** | Score display (top-left), timer (top-center), slowdown bar and aim line progress bar (bottom-right when active), optional debug info (top-right, toggle with S in-game). |
| **Level select** | Cards showing level name, subtitle, ball count, and best score + time (or "No record yet"). |
| **Menus / overlays** | Semi-transparent dark overlays with styled rounded-rect buttons. |

---

## 7. Project File Structure

```
Zuma/
├── DESIGN.md
├── README.md
├── requirements.txt
├── ASSETS/
│   ├── MENU.mp3
│   ├── IN-GAME.mp3
│   ├── FINISH.mp3
│   ├── Orbitron-VariableFont_wght.ttf
│   ├── Exo2-VariableFont_wght.ttf
│   ├── red_sprite_fixed.png
│   ├── green_sprite_fixed.png
│   ├── blue_sprite_fixed.png
│   └── yellow_sprite_fixed.png
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
│       ├── level1.json
│       ├── level2.json
│       ├── level3.json
│       ├── level4.json
│       ├── level5.json
│       └── level6.json
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

Accessible from the main menu via the Settings button.

| Setting | Description |
|---|---|
| Music Volume | Slider controlling `pygame.mixer.music` volume (0–100%). Applied live. |
| Colorblind Mode | Overlays a distinct white symbol on each ball color: ring (red), triangle (green), square (blue), diamond (yellow). |

---

## 10. Future Considerations

- Ball sprite textures (sprite strips ready in `ASSETS/`, integration pending)
- Difficulty scaling (chain speed increases over time within a level)
- Additional ball colors
- Star ratings per level (1–3 stars based on time or score)
- Screen shake on bomb explosion
- Chain speed warning when front ball is near the hole
