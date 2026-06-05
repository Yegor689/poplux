# Poplux — Low-Level Design

Companion to [DESIGN.md](DESIGN.md). Covers internal structure: classes, data flow, runtime collaboration, and per-frame execution order.

---

## 1. Module Dependency Graph

Arrow means "imports from".

```mermaid
graph TD
    main["main.py"] --> game["game.py"]
    editor["editor.py"] --> renderer & path

    game --> chain & frog & renderer
    game --> background & records & sounds
    game --> path & ball

    chain --> ball
    frog --> ball

    chain & frog & renderer & path & ball & sounds & background & editor & records & game --> settings["settings.py"]

    classDef entry fill:#f8d7da,stroke:#c0392b,stroke-width:2px,color:#000
    classDef core  fill:#d6eaf8,stroke:#2980b9,stroke-width:2px,color:#000
    classDef data  fill:#d5f5e3,stroke:#27ae60,stroke-width:1px,color:#000
    classDef ext   fill:#fef9e7,stroke:#f39c12,stroke-width:1px,color:#000

    class main entry
    class game,chain,frog,path,renderer core
    class ball,settings,records data
    class sounds,background,editor ext
```

`settings.py` is a leaf — imported by all, imports nothing. All modules use it for constants (`BALL_RADIUS`, `FPS`, level configs) and the `SETTINGS` singleton.

---

## 2. Class Diagrams

### 2a. Core Simulation

```mermaid
classDiagram
    direction TB

    class Game {
        +state : str
        +path : Path
        +frog : Frog
        +chain : Chain
        +renderer : Renderer
        +score : int
        +elapsed_time : float
        +fired_balls : list
        +coins / aim_powerups / particles / score_popups : list
        -_logical : Surface
        -_combo_window : float
        -_combo_level : int
        -_endless_mode : bool
        -_slowdown_timer : float
        -_aim_timer : float
        -_shake : float
        +run()
        -_update(dt)
        -_handle_events() bool
        -_render()
        -_reset_session(idx, total)
        -_check_collisions()
        -_spawn_particles()
    }

    class Chain {
        +speed : float
        +balls : list
        +movement_mult : float
        +recent_pops : list
        -_cascade_pending : list
        -_cascade_timer : float
        -_cascade_level : int
        +advance(dt)
        +insert(ball, d) int
        +check_matches(idx) list
        +queue_match(indices, inherited_level)
        +remove_balls(indices)
        +spawn_one() Ball
        -_fire_cascade()
    }

    class Frog {
        +x / y : float
        +angle : float
        +current_ball : Ball
        +next_ball : Ball
        +available_colors : list
        -_recoil_t : float
        -_cooldown_t : float
        +can_shoot : bool
        +tick(dt)
        +update(mouse_pos)
        +shoot() Ball
        +swap()
    }

    class Path {
        +waypoints : list
        +total_length : float
        -_arc_lengths : list
        +point_at(d) tuple
        +direction_at(d) float
        +nearest_distance(x, y) float
    }

    class Ball {
        +color : str
        +radius : int
        +is_bomb / is_rainbow / is_bonus : bool
        +path_distance : float
        +path_offset : float
        +entry_t : float
        +entry_x / entry_y : float
        -_gap_remaining : float
        +x / y / dx / dy : float
        +active : bool
        +move(dt)
    }

    Game *-- Path
    Game *-- Frog
    Game *-- Chain
    Game o-- "*" Ball : fired_balls
    Chain o-- "*" Ball : balls
    Frog *-- "2" Ball : current + next
    Chain --> Path : point_at / direction_at
```

> **Ball dual-role:** `path_distance / path_offset / entry_t / _gap_remaining` are chain-role fields; `x / y / dx / dy / active` are fired-role fields. The same object transitions from fired → chain on `Chain.insert()`. `entry_t` goes 0→1 during insertion animation (`< 1` = still animating in); `path_offset` is a visual displacement animated to 0 after insertion.

### 2b. Visual & Ephemeral

```mermaid
classDiagram
    direction LR

    class Renderer {
        +screen : Surface
        -_palettes : dict
        -_aim_line_surf : Surface
        -_overlay_surf : Surface
        -_vign_surf : Surface
        +draw_chain(chain, path, match_color)
        +draw_frog(frog)
        +draw_fired_balls(balls)
        +draw_hud(remaining, score, ...)
        +draw_aim_line(frog, timer, positions)
        +draw_path(path)
        +draw_coins(coins)
        +draw_particles(particles)
        +draw_score_popups(popups)
    }

    class Background {
        -_starfield : Surface
        -_asteroids : list
        +update(dt)
        +draw(surface)
    }

    class Settings {
        +music_volume : float
        +sfx_volume : float
        +fullscreen : bool
        +colorblind_mode : bool
        +show_fps : bool
        +danger_vignette : bool
        +particles : bool
        +save()
    }

    class Coin {
        +x / y : float
        +lifetime : float
        +alive : bool
        +update(dt)
    }

    class AimPowerup {
        +x / y : float
        +lifetime : float
        +alive : bool
        +update(dt)
    }

    class Particle {
        +x / y / dx / dy : float
        +color : tuple
        +lifetime : float
        +alive : bool
        +update(dt)
    }

    class ScorePopup {
        +text : str
        +color : tuple
        +cascade_level : int
        +lifetime : float
        +alive : bool
        +update(dt)
    }

    Coin --|> AimPowerup : same shape
    Particle --* ScorePopup : both ephemeral
```

> `Renderer` and `Background` never mutate game entities. Ephemeral lists are pruned each frame via `[x for x in xs if x.alive]`.

---

## 3. State Machine

`Game.state` is a string. `_set_state()` drives overlay-fade transitions; direct assignment is used for instant transitions.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> main_menu

    main_menu --> playing       : Play (level 1)
    main_menu --> level_select  : Level Select
    main_menu --> records       : Records
    main_menu --> settings      : Settings
    main_menu --> cheat_menu    : S key
    main_menu --> [*]           : Quit

    level_select --> playing    : Play / Endless
    level_select --> combo_test : S key
    level_select --> main_menu  : Esc

    cheat_menu --> main_menu    : Esc

    playing --> paused          : Esc
    playing --> level_complete  : chain cleared
    playing --> game_complete   : final level cleared
    playing --> lose            : chain reached hole

    paused --> playing          : Resume / Space
    paused --> playing          : Restart R
    paused --> settings         : Settings
    paused --> main_menu        : Main Menu

    level_complete --> playing  : Next Level / Enter
    level_complete --> playing  : Retry R
    level_complete --> main_menu: M key

    lose --> playing            : Retry R
    lose --> main_menu          : Main Menu

    game_complete --> main_menu : any click

    combo_test --> paused       : Esc
    combo_test --> combo_test   : Retry R

    records --> main_menu       : Esc
    settings --> main_menu      : Esc (from menu)
    settings --> paused         : Esc (from pause)
```

`_settings_return_state` stores where settings was opened from. `_pre_pause_state` stores `"playing"` or `"combo_test"` so restart works from either.

---

## 4. Per-Frame Update Order

Single tick at 60 Hz. All work runs on the main thread in this order:

```mermaid
flowchart TD
    subgraph frame["Each frame"]
        A([clock.tick<br/>dt = elapsed / 1000]) --> C[_handle_events<br/>poll input]
        C --> D[Background.update<br/>asteroid drift]
        D --> E{playing or<br/>combo_test?}
    end

    subgraph sim["Simulation step (if active)"]
        F[decay shake · lerp score<br/>tick frog recoil + cooldown<br/>tick slowdown / combo / aim timers]
        F --> H[Chain.advance<br/>gap logic, cascade queue]
        H --> I[endless speed ramp<br/>SPEED UP popup on tier cross]
        I --> J[_spawn_particles<br/>from chain.recent_pops]
        J --> K[update colors · tick ephemerals<br/>spawn collectibles · danger beat]
        K --> L[move + cull fired_balls<br/>_check_collisions<br/>coin + powerup pickups]
        L --> M[spawn next chain ball<br/>check win / lose]
    end

    subgraph present["Present"]
        R[_update_music<br/>swap track if state changed]
        R --> S["_render<br/>BG → path → chain → particles<br/>→ fired → frog → HUD → overlay"]
        S --> T[smoothscale + shake offset<br/>blit to screen]
    end

    E -->|yes| F
    E -->|no| R
    M --> R
```

**Invariants:** `Chain.advance()` runs before `_check_collisions` (uses current-frame positions). `recent_pops` is cleared at the top of `advance()`, so `_spawn_particles` always reads current-frame pops.

---

## 5. Chain Internals

### 5.1 Ball Array Layout

```
Index:   [0]     [1]     [2]     [3]     [4]     [5]
         rear ◄────────────────────────────► front
         (spawn)                             (hole)

dist:     0     dia    2·dia   2·dia   3·dia   4·dia
                                ↑
                        _gap_remaining > 0 (just inserted)
```

`balls[0]` = smallest path_distance (spawn side). `balls[-1]` = largest (hole side, triggers lose).

### 5.2 Gap State Machine

```mermaid
stateDiagram-v2
    direction TB
    [*]          --> Closed

    Closed       --> Open        : ball removed by pop or bomb
    Closed       --> Opening     : ball inserted
    Opening      --> Open        : _gap_remaining fully drained

    Open         --> Open        : colors differ — front segment frozen
    Open         --> Closing     : colors match — front catches up

    Closing      --> Matched     : gap closes, colors match
    Closing      --> Rejoined    : gap closes, colors differ

    Matched      --> [*]         : cascade queued, balls pop
    Rejoined     --> Closed      : rear segment snapped flush
```

### 5.3 advance(dt) Flow

```mermaid
flowchart TD
    A([advance dt]) --> B[clear recent_pops]
    B --> C{cascade<br/>pending?}
    C -->|yes| D[tick cascade_timer]
    D --> E{expired?}
    E -->|yes| F[_fire_cascade<br/>remove balls<br/>set recent_pops]
    E -->|no| G[snapshot prev_gaps]
    C -->|no| G
    F --> G

    G --> H[move all balls forward by delta<br/>push balls ahead per _gap_remaining<br/>advance entry_t animations]
    H --> J[recompute cur_gaps<br/>tag match / no-match]
    J --> K[freeze no-match front segments<br/>pull match segments back]
    K --> L{cascade<br/>pending?}

    L -->|yes| Z([return])
    L -->|no| M{newly-closed<br/>gaps?}
    M -->|no| Z
    M -->|match colors| O[pack merged segment<br/>check_matches → queue cascade]
    M -->|differ| P[snap rear ball flush<br/>pack rear segment back]
    O & P --> Z
```

### 5.4 Insertion + Cross-Shot Combo

```mermaid
sequenceDiagram
    participant FB as fired Ball
    participant G  as Game
    participant CH as Chain

    FB ->> G  : collision detected
    G  ->> CH : insert(ball, target_dist)
    Note over CH: _gap_remaining=BALL_DIAMETER, entry_t=0
    G  ->> CH : check_matches(idx)

    alt 3+ color match
        Note over G: inherited = combo_level if combo_window > 0 else 1
        G  ->> CH : queue_match(matches, inherited_level)
        Note over CH: timer = ~0.17s (entry anim) for shot-triggered<br/>timer = 0.5s (_CASCADE_DELAY) for gap-close cascade
        CH ->> CH : _fire_cascade after timer
        CH -->> G : recent_pops available
        Note over G: score += cascade_level x 5 x n_balls
        Note over G: combo_window = 2.0s, combo_level = cascade_level+1
    end
```

If the next shot lands within 2 s, `inherited_level` carries the bumped level forward.

---

## 6. Path — Spline Pipeline

```mermaid
flowchart TD
    A["level.json\n5–20 waypoints"]
    A --> B["_catmull_rom_chain\ncentripetal alpha=0.5\n20 samples / seg"]
    B --> C["dense polyline  ~400–1000 pts"]
    C --> D["_resample → 500 pts uniform"]
    D --> E["scale to 1920×1080 canvas"]
    E --> F["_compute_arc_lengths\ncumulative distance array"]
    F --> G{{"Path ready"}}

    G --> H["point_at(d)\nO(log n) bisect"]
    G --> I["direction_at(d)\nlocal tangent angle"]
    G --> J["nearest_distance(x,y)\nO(n) segment scan\neditor only"]
```

Centripetal CR (alpha=0.5) avoids cusps. Phantom endpoint duplication forces the curve through all authored waypoints.

---

## 7. Frog — Shot Pipeline

```mermaid
flowchart TD
    subgraph mm["Mouse motion"]
        A([MOUSEMOTION]) --> B["Frog.update mouse_pos<br/>angle = atan2 dy, dx"]
    end

    subgraph rc["Right click"]
        L([MOUSEBUTTONDOWN right]) --> M["Frog.swap<br/>current ⇄ next"]
    end

    subgraph lc["Left click"]
        C([MOUSEBUTTONDOWN left]) --> D{can_shoot?}
        D -->|no| E([ignore])
        D -->|yes| F["Frog.shoot<br/>muzzle x/y · dx/dy = SHOOT_SPEED·dir<br/>recoil_t=1.0 · cooldown=0.18s<br/>current=next · next=_new_ball"]
        F --> G[Game appends to fired_balls]
        G --> H{active modifiers}
        H -->|aim_timer| I[speed × 2]
        H -->|FASTBALL| J[speed × 3]
        H -->|MULTISHOT| K[2 extra balls at ±15°]
        H -->|none| Z([fly])
        I & J & K --> Z
    end
```

**`_new_ball()` draw:**  `r < 0.05` → bomb · `r < 0.10` → rainbow · else → random color from `available_colors`.

---

## 8. Rendering Pipeline

```mermaid
flowchart TD
    A([_render]) --> B["Background<br/>starfield + asteroids"]
    B --> C{game state}
    C -->|"menu / records / settings"| D["draw appropriate screen"]
    C -->|gameplay| E["draw_path<br/>tube + pulsing hole"]

    E --> F["draw_coins · draw_aim_powerups"]
    F --> G["draw_chain<br/>bonus ring · match ring · ball layers"]
    G --> H["draw_particles · draw_score_popups"]
    H --> I["draw_fired_balls"]
    I --> J["draw_aim_line  (if aim_timer > 0)"]
    J --> K["draw_frog"]
    K --> L["draw_hud<br/>vignette · score · timer · endless speed · bars"]
    L --> N{overlay?}

    OUT(["smoothscale + shake offset + blit"])

    N -->|paused| P1["draw_pause_menu"] --> OUT
    N -->|level_complete| P2["draw_level_complete"] --> OUT
    N -->|game_complete| P3["draw_game_complete"] --> OUT
    N -->|lose| P4["draw_lose"] --> OUT
    N -->|none| OUT
    D --> OUT
```

**Surface inventory:**

| Surface | Purpose | Lifetime |
|---|---|---|
| `_logical` | 1920×1080 draw canvas | Per session |
| `_aim_line_surf` | SRCALPHA, cleared each frame | Allocated once |
| `_overlay_surf` | SRCALPHA for menu backdrops | Allocated once |
| `_vign_surf` | SRCALPHA red vignette, alpha re-scaled per frame | Allocated once |

---

## 9. Persistence

```mermaid
flowchart LR
    subgraph disk["On-disk"]
        SF["settings.json\nnext to src/"]
        RF["records.json\nplatformdirs user_data_dir"]
    end

    subgraph runtime["Runtime"]
        ST["Settings singleton\nloaded on import"]
        RC["records module\n_cache list"]
        G["Game"]
    end

    ST -. load on import .-> SF
    ST -. save on change .-> SF
    G --> RC
    RC -. cached load .-> RF
    RC -. write-through .-> RF
```

**Record schema:** `{ "level": "The Spiral", "score": 1840, "time": 87.4, "date": "2026-05-21" }`

Endless runs use key prefix `"Endless (Lvl N)"`. `top()` vs `top_endless()` split them at query time.

---

## 10. Sound System

```mermaid
flowchart TD
    subgraph sfx["SFX (synthesized)"]
        direction TB
        A(["startup"]) --> B["pygame.mixer.init<br/>44100 Hz stereo"]
        B --> C["synthesize all SFX<br/>numpy waveforms → Sound objects"]
        C --> D[["_sounds dict<br/>name → Sound"]]
        D --> F["snd.set_volume<br/>vol × sfx_volume"]
        F --> G(["snd.play"])

        H(["play_cascade(level)"]) -->|clamp 1–5| E(["sounds.play(name, vol)"])
        E --> D
    end

    subgraph music["Music (pygame.mixer.music)"]
        direction TB
        J(["_update_music<br/>each frame"]) --> K{state}
        K -->|"menu / records / settings"| L1["MENU.mp3"]
        K -->|"playing / paused / lose"| L2["IN-GAME.mp3"]
        K -->|"level_complete / game_complete"| L3["FINISH.mp3"]
        L1 & L2 & L3 --> M1["load + set_volume + play"]
    end
```

`cascade_1`–`cascade_5` are pre-generated at startup, each a perfect fourth higher than the last.

---

## 11. Coordinate Spaces

```mermaid
flowchart TD
    A["Mouse<br/>physical px"]      -->|"scale + offset"| L
    B["Level JSON<br/>1280×960 authored"] -->|"PATH_SCALE + X_OFFSET<br/>at Path init"| L
    C["Arc-length d<br/>0..total_length"] -->|"point_at(d)"| L
    L{{"Logical canvas<br/>1920×1080"}} -->|"smoothscale + letterbox"| D["Physical screen<br/>any resolution"]
```

| Space | Range | Where used |
|---|---|---|
| Authored | 0–1280 × 0–960 | Level JSON, editor |
| Logical | 0–1920 × 0–1080 | All game math, rendering, collision |
| Arc-length | 0–total_length | Chain ball positions |
| Physical | display resolution | Final blit only |

---

## 12. Cheat & Powerup Hooks

| Effect | Source | Hook point | What changes |
|---|---|---|---|
| GODMODE | cheat menu | `_update` end of frame | Balls past path end removed instead of loss |
| SLOWMO | cheat menu | `chain.advance` call | `advance(dt * 0.25)` |
| MAGNET | cheat menu | before fired ball move | `dx/dy` steered toward nearest chain ball |
| FASTBALL | cheat menu | shoot in event loop | `ball.dx/dy *= 3` |
| MULTISHOT | cheat menu | shoot in event loop | 2 extra balls at ±15° |
| RAINBOW | cheat menu | `_check_collisions` on hit | `fired.color = chain_ball.color` before insert |
| Aim powerup | pickup collision | shoot in event loop | `ball.dx/dy *= 2` while `_aim_timer > 0` |
| Slowdown | bonus ball pop | `_update` each frame | `chain.movement_mult = 0.35` while `_slowdown_timer > 0` |
| Cross-shot combo | any pop | `queue_match` call | `inherited_level = combo_level` if window open |

Cheats are `set[str]` in `Game.active_cheats`; each hook does a simple `"CHEAT" in self.active_cheats` check.

---

## 13. Test Layout

```
tests/
├── test_chain_catchup.py    gap closing, freeze/catch-up, match-on-close
├── test_chain_insert.py     insertion ordering, _gap_remaining animation
└── test_frog.py             cooldown, recoil, swap, color pool refresh
```

Tests run headless — `Path` uses a straight two-point waypoint list; `Chain` and `Frog` need no display surface. Tests assert `path_distance` invariants after sequences of `insert()` and `advance()` calls.

---

## 14. Threading Model

Single-threaded. `pygame.mixer` manages its own audio thread; all simulation, rendering, input, and file I/O run synchronously on the main thread.

At 60 Hz the frame budget is 16.7 ms. The heaviest per-frame operations (chain advance, collision scan, `smoothscale`) each take well under 1 ms on typical hardware. Records write to disk only at level end or loss — no I/O in the hot path.
