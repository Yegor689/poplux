import sys
import math
import os
import random
import pygame
from path import Path, _PATH_SCALE_X, _PATH_SCALE_Y, _PATH_X_OFFSET
from frog import Frog
from chain import Chain
from renderer import Renderer
from background import Background
from ball import Ball, Coin, Particle, ScorePopup, AimPowerup
import records as records_store
import sounds
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE, BG_COLOR,
    BALL_RADIUS, MATCH_MINIMUM, LEVELS, BALL_COLORS, SETTINGS,
)


class Game:
    def __init__(self):
        sounds.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
        self._logical = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.renderer = Renderer(self._logical)
        self.state = "main_menu"
        self._records_scroll = 0
        self._records_tab = 0  # 0 = per-level grid, 1 = all runs
        self._level_complete_new_best = False
        self._level_select_idx = 0
        self._ls_scroll = 0
        self._ls_hover_suppressed = False
        self._all_unlocked: bool = False  # F9 in level_select: unlock all levels
        self.current_level_idx = 0
        self.path = None
        self.frog = None
        self.chain = None
        self.fired_balls = []
        self.particles: list[Particle] = []
        self.score_popups: list[ScorePopup] = []
        self.spawned_count = 0
        self._total_balls = 0
        self._cached_scale_rect = None
        self._cached_screen_size = None
        self._frame_mouse = (0, 0)
        self.background = Background()
        self._pre_pause_state = "playing"  # state to restore when unpausing
        self._overlay_t: float = 1.0        # 0→1 fade-in for overlays; 1.0 = fully faded in
        self.active_cheats: set = set()
        self._cheat_input: str = ""
        self._cheat_message: str = ""
        self._endless_mode: bool = False
        self._endless_base_speed: float = 0.0
        self._slowdown_timer: float = 0.0
        self.coins: list[Coin] = []
        self.coin_spots: list = []
        self._coin_timer: float = 20.0
        self.aim_powerups: list[AimPowerup] = []
        self.aim_powerup_spots: list = []
        self._aim_powerup_timer: float = 30.0
        self._aim_timer: float = 0.0
        self._spawn_hold: float = 0.0   # pause spawning briefly after bomb removal
        self._display_score: float = 0.0  # animated score counter
        self._danger_beat_timer: float = 0.0
        self._shake: float = 0.0   # current shake magnitude in logical px
        self._frame_chain_positions: list = []
        self._current_music: str = ""
        _assets = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ASSETS")
        self._music_menu    = os.path.join(_assets, "MENU.mp3")
        self._music_ingame  = os.path.join(_assets, "IN-GAME.mp3")
        self._music_finish  = os.path.join(_assets, "FINISH.mp3")

    @staticmethod
    def _scale_pos(raw, sx, ox, sy):
        """Scale a raw authored position to logical screen space."""
        return [raw[0] * sx + ox, raw[1] * sy]

    def _reset_session(self, level_idx: int, total_balls: int,
                       frog_kwargs: dict | None = None,
                       chain_kwargs: dict | None = None) -> None:
        """Reset all per-session state shared by normal, endless, and combo-test modes."""
        self._current_music = ""
        cfg = LEVELS[level_idx]
        self.current_level_idx = level_idx
        self.path = Path(cfg)
        raw_frog = cfg.get("frog_pos")
        frog_pos = self._scale_pos(raw_frog, _PATH_SCALE_X, _PATH_X_OFFSET, _PATH_SCALE_Y) if raw_frog else None
        self.frog = Frog(pos=frog_pos, **(frog_kwargs or {}))
        self.chain = Chain(self.path, cfg["chain_speed"], **(chain_kwargs or {}))
        self.fired_balls = []
        self.particles = []
        self.score_popups = []
        self.spawned_count = 0
        self._total_balls = total_balls
        self.elapsed_time = 0.0
        self.score = 0
        self._display_score = 0.0
        self._spawn_hold = 0.0
        self._slowdown_timer = 0.0
        self._danger_beat_timer = 0.0
        self._aim_timer = 0.0
        self.coins = []
        self.coin_spots = [
            self._scale_pos(s, _PATH_SCALE_X, _PATH_X_OFFSET, _PATH_SCALE_Y)
            for s in cfg.get("coin_spots", [])
        ]
        self._coin_timer = random.uniform(15.0, 25.0)
        self.aim_powerups = []
        self.aim_powerup_spots = [
            self._scale_pos(s, _PATH_SCALE_X, _PATH_X_OFFSET, _PATH_SCALE_Y)
            for s in cfg.get("aim_powerup_spots", [])
        ]
        self._aim_powerup_timer = random.uniform(20.0, 35.0)
        pre = min(cfg["pre_placed"], self._total_balls)
        self.chain.populate(pre)
        self.spawned_count = pre

    def _init_game_state(self, level_idx: int) -> None:
        self._level_select_idx = level_idx  # remember last played level
        self._reset_session(level_idx, LEVELS[level_idx]["total_balls"])
        self._endless_mode = False
        self._pre_pause_state = "playing"
        self.state = "playing"

    _COMBO_TEST_COLORS = list(BALL_COLORS.keys())[:2]  # first two colours only

    _CHEAT_CODES = {
        "GODMODE":   "No lose condition",
        "SLOWMO":    "Chain at 25% speed",
        "MAGNET":    "Fired balls home in on chain",
        "FASTBALL":  "Balls travel 3x faster",
        "MULTISHOT": "Every shot fires 3 balls",
        "RAINBOW":   "Fired balls auto-match color",
        "RESET":     "Clear all active cheats",
    }

    def _init_combo_test(self) -> None:
        """Secret combo-tester: two ball colours, infinite supply, no win/lose."""
        self._reset_session(0, 999_999,
                            frog_kwargs={"color_pool": self._COMBO_TEST_COLORS},
                            chain_kwargs={"color_pool": self._COMBO_TEST_COLORS, "pair_mode": True})
        self._endless_mode = False
        self._pre_pause_state = "combo_test"
        self.state = "combo_test"

    def _init_endless_mode(self, level_idx: int = 0) -> None:
        """Endless mode: use any level's path, infinite balls, chain speeds up over time."""
        self._reset_session(level_idx, 999_999)
        self._endless_mode = True
        self._endless_base_speed = float(LEVELS[level_idx]["chain_speed"])
        self._pre_pause_state = "playing"
        self.state = "playing"

    def _submit_cheat(self) -> None:
        code = self._cheat_input.strip()
        self._cheat_input = ""
        if not code:
            return
        if code not in self._CHEAT_CODES:
            self._cheat_message = "UNKNOWN CODE"
            return
        if code == "RESET":
            self.active_cheats.clear()
            self._cheat_message = "ALL CHEATS CLEARED"
            return
        if code in self.active_cheats:
            self.active_cheats.discard(code)
            self._cheat_message = f"{code}  [OFF]"
        else:
            self.active_cheats.add(code)
            self._cheat_message = f"{code}  [ON]"

    def _ls_scroll_to(self, idx: int) -> None:
        """Ensure the selected level row is visible in the list."""
        row_h   = self.renderer._LS_ROW_H + self.renderer._LS_ROW_GAP
        list_h  = self.renderer.screen.get_height() - self.renderer._LS_LIST_TOP - 20
        top     = idx * row_h
        bottom  = top + self.renderer._LS_ROW_H
        if top < self._ls_scroll:
            self._ls_scroll = top
        elif bottom > self._ls_scroll + list_h:
            self._ls_scroll = bottom - list_h

    def _update_music(self) -> None:
        if self.state in ("level_complete", "game_complete"):
            track = self._music_finish
        elif self.state in ("playing", "combo_test", "lose"):
            track = self._music_ingame
        else:
            track = self._music_menu

        if track != self._current_music:
            self._current_music = track
            pygame.mixer.music.load(track)
            pygame.mixer.music.set_volume(SETTINGS.music_volume)
            loops = 0 if track == self._music_finish else -1
            pygame.mixer.music.play(loops)

    _OVERLAY_STATES = {"paused", "lose", "level_complete", "game_complete"}
    _OVERLAY_FADE_DUR = 0.25   # seconds for full fade-in

    def _set_state(self, new_state: str) -> None:
        """Transition to a new state, resetting the overlay fade when needed."""
        if new_state in self._OVERLAY_STATES and self.state not in self._OVERLAY_STATES:
            self._overlay_t = 0.0
        if new_state not in ("playing", "combo_test"):
            self._shake = 0.0
        self.state = new_state

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            self._frame_mouse = self._logical_mouse()
            running = self._handle_events()
            self.background.update(dt)
            if self._overlay_t < 1.0:
                self._overlay_t = min(1.0, self._overlay_t + dt / self._OVERLAY_FADE_DUR)
            if self.state in ("playing", "combo_test"):
                self._update(dt)
            self._update_music()
            self._render()
        pygame.quit()
        sys.exit()

    def _max_unlocked(self) -> int:
        """Highest level index the player can access this session."""
        if self._all_unlocked:
            return len(LEVELS) - 1
        return records_store.max_unlocked(LEVELS)

    def _scale_rect(self) -> tuple:
        """Return (scale, offset_x, offset_y, scaled_w, scaled_h) preserving aspect ratio."""
        size = self.screen.get_size()
        if size != self._cached_screen_size:
            sw, sh = size
            scale = min(sw / SCREEN_WIDTH, sh / SCREEN_HEIGHT)
            scaled_w = int(SCREEN_WIDTH * scale)
            scaled_h = int(SCREEN_HEIGHT * scale)
            ox = (sw - scaled_w) // 2
            oy = (sh - scaled_h) // 2
            self._cached_scale_rect = (scale, ox, oy, scaled_w, scaled_h)
            self._cached_screen_size = size
        return self._cached_scale_rect

    def _logical_mouse(self) -> tuple:
        mx, my = pygame.mouse.get_pos()
        scale, ox, oy, _, _ = self._scale_rect()
        lx = int((mx - ox) / scale)
        ly = int((my - oy) / scale)
        return (max(0, min(SCREEN_WIDTH, lx)), max(0, min(SCREEN_HEIGHT, ly)))

    def _handle_events(self) -> bool:
        mouse_pos = self._frame_mouse
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.MOUSEWHEEL and self.state == "records":
                if self._records_tab == 2:
                    all_records = records_store.top()
                    max_rows = self.renderer.records_max_rows()
                    self._records_scroll = max(0, min(
                        self._records_scroll - event.y,
                        max(0, len(all_records) - max_rows)
                    ))
            if event.type == pygame.MOUSEMOTION and self.state == "settings":
                if event.buttons[0]:  # left button held — drag slider
                    action = self.renderer.settings_interact(mouse_pos, SETTINGS)
                    if action == "volume_changed":
                        pygame.mixer.music.set_volume(SETTINGS.music_volume)
                        SETTINGS.save()
                    elif action == "sfx_changed":
                        SETTINGS.save()
            if event.type == pygame.MOUSEMOTION and self.state == "level_select":
                self._ls_hover_suppressed = False
            if event.type == pygame.MOUSEWHEEL and self.state == "level_select":
                self._level_select_idx = max(0, min(
                    self._level_select_idx - event.y,
                    len(LEVELS) - 1
                ))
                self._ls_scroll_to(self._level_select_idx)
                self._ls_hover_suppressed = True
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "main_menu":
                        return False
                    elif self.state in ("playing", "combo_test"):
                        self._pre_pause_state = self.state
                        self._set_state("paused")
                    elif self.state == "paused":
                        self.state = self._pre_pause_state
                    else:
                        self.state = "main_menu"
                # Space resumes from pause (item 1)
                if event.key == pygame.K_SPACE and self.state == "paused":
                    self.state = self._pre_pause_state
                if self.state == "records":
                    if event.key == pygame.K_LEFT:
                        self._records_tab = max(0, self._records_tab - 1)
                        self._records_scroll = 0
                    elif event.key == pygame.K_RIGHT:
                        self._records_tab = min(2, self._records_tab + 1)
                        self._records_scroll = 0
                    elif self._records_tab == 2:
                        all_records = records_store.top()
                        max_rows = self.renderer.records_max_rows()
                        if event.key == pygame.K_DOWN:
                            self._records_scroll = min(self._records_scroll + 1, max(0, len(all_records) - max_rows))
                        elif event.key == pygame.K_UP:
                            self._records_scroll = max(0, self._records_scroll - 1)
                if self.state == "level_select":
                    if event.key == pygame.K_DOWN:
                        self._level_select_idx = min(self._level_select_idx + 1, len(LEVELS) - 1)
                        self._ls_scroll_to(self._level_select_idx)
                        self._ls_hover_suppressed = True
                    elif event.key == pygame.K_UP:
                        self._level_select_idx = max(0, self._level_select_idx - 1)
                        self._ls_scroll_to(self._level_select_idx)
                        self._ls_hover_suppressed = True
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if self._level_select_idx <= self._max_unlocked():
                            self._init_game_state(self._level_select_idx)
                # R and Enter on level_complete (items 2, 3)
                if self.state == "level_complete":
                    if event.key == pygame.K_r:
                        self._init_game_state(self.current_level_idx)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        if self.current_level_idx + 1 < len(LEVELS):
                            self._init_game_state(self.current_level_idx + 1)
                        else:
                            self.state = "game_complete"
                if event.key == pygame.K_r and self.state == "lose":
                    if self._endless_mode:
                        self._init_endless_mode(self.current_level_idx)
                    else:
                        self._init_game_state(self.current_level_idx)
                if event.key == pygame.K_r and self.state == "combo_test":
                    self._init_combo_test()
                if event.key == pygame.K_s and self.state == "level_select":
                    self._init_combo_test()
                elif event.key == pygame.K_s and self.state == "main_menu":
                    self.state = "cheat_menu"
                elif event.key == pygame.K_F9 and self.state == "level_select":
                    self._all_unlocked = not self._all_unlocked
                elif event.key == pygame.K_F9 and self.state in ("playing", "combo_test"):
                    self.state = "game_complete"
                elif self.state == "cheat_menu":
                    if event.key == pygame.K_BACKSPACE:
                        self._cheat_input = self._cheat_input[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self._submit_cheat()
                    elif event.unicode and event.unicode.isalpha():
                        self._cheat_message = ""
                        self._cheat_input += event.unicode.upper()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if self.state in ("playing", "combo_test"):
                    self.frog.swap()
                    sounds.play("swap", 0.3)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.state == "main_menu":
                    btn = self.renderer.main_menu_button_at(mouse_pos)
                    if btn is not None:
                        sounds.play("menu_click", 0.4)
                    if btn == 0:
                        self._init_game_state(0)
                    elif btn == 1:
                        self.state = "level_select"
                        self._ls_scroll = 0
                        self._ls_scroll_to(self._level_select_idx)
                    elif btn == 2:
                        self.state = "records"
                        self._records_scroll = 0
                        self._records_tab = 0
                    elif btn == 3:
                        self.state = "settings"
                    elif btn == 4:
                        return False
                elif self.state == "level_select":
                    action = self.renderer.level_select_interact(mouse_pos, self._level_select_idx, self._ls_scroll)
                    _locked = self._level_select_idx > self._max_unlocked()
                    if action == "play" and not _locked:
                        sounds.play("menu_click", 0.4)
                        self._init_game_state(self._level_select_idx)
                    elif action == "endless" and not _locked:
                        sounds.play("menu_click", 0.4)
                        self._init_endless_mode(self._level_select_idx)
                    elif isinstance(action, int):
                        sounds.play("menu_click", 0.4)
                        self._level_select_idx = action
                elif self.state == "records":
                    tab = self.renderer.records_tab_at(mouse_pos)
                    if tab is not None and tab != self._records_tab:
                        self._records_tab = tab
                        self._records_scroll = 0
                elif self.state in ("playing", "combo_test"):
                    if self.frog.can_shoot:
                        ball = self.frog.shoot()
                        sounds.play("shoot", 0.35)
                        if self._aim_timer > 0:
                            ball.dx *= 2.0   # aim powerup: 2× shoot speed
                            ball.dy *= 2.0
                        if "FASTBALL" in self.active_cheats:
                            ball.dx *= 3.0
                            ball.dy *= 3.0
                        self.fired_balls.append(ball)
                        if "MULTISHOT" in self.active_cheats:
                            for offset in (-0.26, 0.26):  # ±15°
                                co, so = math.cos(offset), math.sin(offset)
                                extra = Ball(color=ball.color, radius=ball.radius)
                                extra.x, extra.y = ball.x, ball.y
                                extra.dx = ball.dx * co - ball.dy * so
                                extra.dy = ball.dx * so + ball.dy * co
                                extra.active = True
                                self.fired_balls.append(extra)
                elif self.state == "level_complete":
                    btn = self.renderer.level_complete_button_at(mouse_pos, self._level_complete_new_best)
                    if btn == 0:
                        self._init_game_state(self.current_level_idx + 1)
                    elif btn == 1:
                        self.state = "main_menu"
                elif self.state == "paused":
                    btn = self.renderer.pause_button_at(mouse_pos)
                    if btn == 0:
                        self.state = self._pre_pause_state
                    elif btn == 1:
                        if self._pre_pause_state == "combo_test":
                            self._init_combo_test()
                        elif self._endless_mode:
                            self._init_endless_mode(self.current_level_idx)
                        else:
                            self._init_game_state(self.current_level_idx)
                    elif btn == 2:
                        self.state = "main_menu"
                elif self.state == "lose":
                    btn = self.renderer.lose_button_at(mouse_pos)
                    if btn == 0:  # retry
                        if self._endless_mode:
                            self._init_endless_mode(self.current_level_idx)
                        else:
                            self._init_game_state(self.current_level_idx)
                    else:  # menu or anywhere else
                        self.state = "main_menu"
                elif self.state == "game_complete":
                    self.state = "main_menu"
                elif self.state == "settings":
                    action = self.renderer.settings_interact(mouse_pos, SETTINGS)
                    if action == "volume_changed":
                        pygame.mixer.music.set_volume(SETTINGS.music_volume)
                        SETTINGS.save()
                    elif action == "fullscreen_toggled":
                        flags = pygame.FULLSCREEN if SETTINGS.fullscreen else 0
                        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), flags)
                        SETTINGS.save()
                    elif action == "setting_toggled":
                        SETTINGS.save()
        if self.state in ("playing", "combo_test"):
            self.frog.update(self._frame_mouse)
        return True

    _PARTICLE_COUNT = 10   # particles per popped ball
    _PARTICLE_SPEED = (80, 200)
    _PARTICLE_LIFE  = (0.3, 0.55)
    _PARTICLE_R     = 5

    _POPUP_COLORS = [
        (255, 240,  55),   # cascade 1 — yellow
        (255, 170,  30),   # cascade 2 — orange
        (255,  90,  60),   # cascade 3+ — coral
    ]

    def _spawn_particles(self) -> None:
        if not self.chain.recent_pops:
            return

        # One score popup per group, centred on the popped balls
        positions = [self.path.point_at(d) for d, _, _ in self.chain.recent_pops]
        cx = sum(p[0] for p in positions) / len(positions)
        cy = sum(p[1] for p in positions) / len(positions)
        cascade_level = self.chain.recent_pops[0][2]
        n_balls = len(self.chain.recent_pops)
        total = n_balls * cascade_level * 5
        text = f"+{total:,}" if cascade_level == 1 else f"+{n_balls * 5:,}  x{cascade_level}"
        color = self._POPUP_COLORS[min(cascade_level - 1, len(self._POPUP_COLORS) - 1)]
        if cascade_level > 1:
            sounds.play_cascade(cascade_level, 0.5)
            self._shake = max(self._shake, min(cascade_level * 2.5, 8.0))
        else:
            sounds.play("pop", 0.45)
        life = 1.1
        self.score_popups.append(ScorePopup(cx, cy, text, color, life, life, cascade_level=cascade_level))

        for (_, color_name, cascade_level), (pcx, pcy) in zip(
                self.chain.recent_pops, positions):
            self.score += cascade_level * 5  # 5 pts × combo multiplier per ball popped
            base = BALL_COLORS.get(color_name, (200, 200, 200))
            light = tuple(min(255, c + 60) for c in base)
            for _ in range(self._PARTICLE_COUNT):
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(*self._PARTICLE_SPEED)
                life  = random.uniform(*self._PARTICLE_LIFE)
                color = random.choice([base, light])
                self.particles.append(Particle(
                    x=pcx, y=pcy,
                    dx=math.cos(angle) * speed,
                    dy=math.sin(angle) * speed,
                    lifetime=life, max_lifetime=life,
                    color=color, radius=self._PARTICLE_R,
                ))

    _COMBO_SPEED_MULTIPLIER = 4.0

    def _cleanup_cascade_pending(self) -> None:
        """Remove stale _cascade_pending refs after balls are forcibly removed."""
        if self.chain._cascade_pending:
            live_ids = {id(b) for b in self.chain.balls}
            self.chain._cascade_pending = [
                b for b in self.chain._cascade_pending if id(b) in live_ids
            ]

    def _update(self, dt: float) -> None:
        self.elapsed_time += dt
        if self._shake > 0:
            self._shake = max(0.0, self._shake - self._shake * 12.0 * dt - 30.0 * dt)
        # Animate score counter: close gap in ~0.3s, minimum 50 pts/s so it always arrives
        if self._display_score < self.score:
            step = max(50.0, (self.score - self._display_score) / 0.3) * dt
            self._display_score = min(float(self.score), self._display_score + step)
        if self._overlay_t < 1.0:
            self._overlay_t = min(1.0, self._overlay_t + dt / self._OVERLAY_FADE_DUR)
        self.frog.tick(dt)
        if self._slowdown_timer > 0:
            self._slowdown_timer = max(0.0, self._slowdown_timer - dt)

        if self.chain.bonus_popped:
            self._slowdown_timer = 15.0
            sounds.play("slowdown", 0.4)
            cx, cy = self.path.point_at(self.chain.bonus_pop_dist)
            self.score_popups.append(
                ScorePopup(cx, cy, "SLOW!", (120, 220, 255), 1.6, 1.6)
            )

        self.chain.movement_mult = 0.35 if self._slowdown_timer > 0 else 1.0
        if self.state == "combo_test" and pygame.key.get_pressed()[pygame.K_s]:
            self.chain.advance(dt * self._COMBO_SPEED_MULTIPLIER)
        elif "SLOWMO" in self.active_cheats:
            self.chain.advance(dt * 0.25)
        else:
            self.chain.advance(dt)

        if self._endless_mode:
            # Speed ramps up continuously: +50% per minute, capped at 4× base
            scale = 1.0 + self.elapsed_time / 120.0
            self.chain.speed = min(self._endless_base_speed * scale,
                                   self._endless_base_speed * 4.0)

        self._spawn_particles()

        # Remove exhausted colors from the frog's generation pool
        active = {b.color for b in self.chain.balls}
        active |= {b.color for b in self.fired_balls if b.active}
        self.frog.update_available_colors(active)

        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

        for c in self.coins:
            c.update(dt)
        self.coins = [c for c in self.coins if c.alive]

        if self.coin_spots:
            self._coin_timer -= dt
            if self._coin_timer <= 0:
                occupied = {(c.x, c.y) for c in self.coins}
                available = [s for s in self.coin_spots if tuple(s) not in occupied]
                if available:
                    spot = random.choice(available)
                    self.coins.append(Coin(x=float(spot[0]), y=float(spot[1])))
                self._coin_timer = random.uniform(15.0, 25.0)

        for p in self.aim_powerups:
            p.update(dt)
        self.aim_powerups = [p for p in self.aim_powerups if p.alive]

        if self.aim_powerup_spots:
            self._aim_powerup_timer -= dt
            if self._aim_powerup_timer <= 0:
                occupied = {(p.x, p.y) for p in self.aim_powerups}
                available = [s for s in self.aim_powerup_spots if tuple(s) not in occupied]
                if available:
                    spot = random.choice(available)
                    self.aim_powerups.append(AimPowerup(x=float(spot[0]), y=float(spot[1])))
                self._aim_powerup_timer = random.uniform(20.0, 35.0)

        if self._aim_timer > 0:
            self._aim_timer = max(0.0, self._aim_timer - dt)

        # Danger heartbeat — beats faster as chain approaches hole
        _front = self.chain.front_distance() if self.chain.balls else 0.0
        _path_len = self.path.total_length if self.path else 1.0
        _danger_frac = _front / _path_len if _path_len else 0.0
        _DANGER_START = 0.82
        if _danger_frac > _DANGER_START:
            intensity = min(1.0, (_danger_frac - _DANGER_START) / (0.96 - _DANGER_START))
            beat_interval = 1.2 - intensity * 0.8   # 1.2s → 0.4s
            self._danger_beat_timer -= dt
            if self._danger_beat_timer <= 0:
                sounds.play("danger_beat", 0.28 + intensity * 0.22)
                self._danger_beat_timer = beat_interval
        else:
            self._danger_beat_timer = 0.0

        for p in self.score_popups:
            p.update(dt)
        self.score_popups = [p for p in self.score_popups if p.alive]

        # Combo-test: remove balls that exit the path so they don't pile up at
        # the hole and corrupt collisions.  Re-seed the chain if it fully empties
        # so spawning can continue.
        if self.state == "combo_test":
            while self.chain.balls and self.chain.front_distance() >= self.path.total_length:
                self.chain.balls.pop()
            # If we popped balls that were cascade-pending, clear the stale refs
            self._cleanup_cascade_pending()
            if self.chain.is_empty() and self.spawned_count < self._total_balls:
                self.chain.spawn_one()
                self.spawned_count += 1

        if self._spawn_hold > 0:
            self._spawn_hold = max(0.0, self._spawn_hold - dt)
        elif self.spawned_count < self._total_balls and self.chain.needs_spawn():
            while self.spawned_count < self._total_balls and self.chain.needs_spawn():
                self.chain.spawn_one()
                self.spawned_count += 1

        # Build chain positions once per frame — shared by MAGNET and _check_collisions
        self._frame_chain_positions = [
            self.path.point_at(b.path_distance) for b in self.chain.balls
        ]

        if "MAGNET" in self.active_cheats and self.chain.balls:
            for ball in self.fired_balls:
                best_dist_sq = float('inf')
                target = None
                for (cx, cy) in self._frame_chain_positions:
                    dsq = (ball.x - cx) ** 2 + (ball.y - cy) ** 2
                    if dsq < best_dist_sq:
                        best_dist_sq = dsq
                        target = (cx, cy)
                if target:
                    speed = math.sqrt(ball.dx ** 2 + ball.dy ** 2)
                    if speed > 0:
                        cur_angle = math.atan2(ball.dy, ball.dx)
                        tgt_angle = math.atan2(target[1] - ball.y, target[0] - ball.x)
                        diff = (tgt_angle - cur_angle + math.pi) % (2 * math.pi) - math.pi
                        turn = max(-4.0 * dt, min(4.0 * dt, diff))
                        new_angle = cur_angle + turn
                        ball.dx = math.cos(new_angle) * speed
                        ball.dy = math.sin(new_angle) * speed

        for ball in self.fired_balls:
            ball.move(dt)
        self.fired_balls = [b for b in self.fired_balls if not self._out_of_bounds(b)]

        self._check_collisions()
        self._check_coin_collisions()
        self._check_aim_powerup_collisions()

        if "GODMODE" in self.active_cheats:
            while self.chain.balls and self.chain.front_distance() >= self.path.total_length:
                self.chain.balls.pop()
            self._cleanup_cascade_pending()

        if self.state != "combo_test":
            if self.chain.is_empty() and self.spawned_count >= self._total_balls:
                level_name = LEVELS[self.current_level_idx]["name"]
                self._level_complete_new_best = records_store.is_new_best(level_name, self.score)
                records_store.save(level_name, self.score, self.elapsed_time)
                if self.current_level_idx + 1 < len(LEVELS):
                    sounds.play("level_complete", 0.6)
                    self._set_state("level_complete")
                else:
                    sounds.play("level_complete", 0.6)
                    self._set_state("game_complete")
            elif self.chain.front_distance() >= self.path.total_length:
                if self._endless_mode:
                    endless_key = f"Endless (Lvl {self.current_level_idx + 1})"
                    records_store.save(endless_key, self.score, self.elapsed_time)
                sounds.play("game_over", 0.5)
                self._set_state("lose")

    def _out_of_bounds(self, ball) -> bool:
        return (ball.x < -BALL_RADIUS or ball.x > SCREEN_WIDTH + BALL_RADIUS or
                ball.y < -BALL_RADIUS or ball.y > SCREEN_HEIGHT + BALL_RADIUS)

    def _check_collisions(self) -> None:
        chain_positions = self._frame_chain_positions
        surviving = []
        for fired in self.fired_balls:
            hit_idx = None
            best_dist_sq = float('inf')
            for i, (chain_ball, (cx, cy)) in enumerate(
                    zip(self.chain.balls, chain_positions)):
                dist_sq = (fired.x - cx) ** 2 + (fired.y - cy) ** 2
                threshold = (fired.radius + chain_ball.radius) ** 2
                if dist_sq <= threshold and dist_sq < best_dist_sq:
                    best_dist_sq = dist_sq
                    hit_idx = i

            if hit_idx is not None:
                if fired.is_bomb:
                    self._explode_bomb(hit_idx)
                else:
                    if fired.is_rainbow or "RAINBOW" in self.active_cheats:
                        fired.color = self.chain.balls[hit_idx].color
                    path_dist = self.chain.balls[hit_idx].path_distance
                    idx = self.chain.insert(fired, path_dist)
                    matches = self.chain.check_matches(idx)
                    if len(matches) >= MATCH_MINIMUM:
                        self.chain.queue_match(matches)
            else:
                surviving.append(fired)
        self.fired_balls = surviving

    _BOMB_RADIUS = BALL_RADIUS * 6  # physical blast radius in screen pixels

    def _explode_bomb(self, hit_idx: int) -> None:
        """Destroy balls within physical blast radius of hit_idx, spawn particles and popup."""
        sounds.play("bomb", 0.6)
        self._shake = max(self._shake, 14.0)
        hx, hy = self.path.point_at(self.chain.balls[hit_idx].path_distance)
        indices = []
        positions = []
        for i, b in enumerate(self.chain.balls):
            bx, by = self.path.point_at(b.path_distance)  # computed once per ball
            if math.hypot(bx - hx, by - hy) <= self._BOMB_RADIUS:
                indices.append(i)
                positions.append((bx, by))
                self.score += 25
                base = BALL_COLORS.get(b.color, (200, 200, 200))
                light = tuple(min(255, c + 60) for c in base)
                for _ in range(self._PARTICLE_COUNT):
                    angle = random.uniform(0, 2 * math.pi)
                    speed = random.uniform(*self._PARTICLE_SPEED) * 1.4
                    life = random.uniform(*self._PARTICLE_LIFE)
                    color = random.choice([base, light, (255, 140, 0), (255, 220, 60)])
                    self.particles.append(Particle(
                        x=bx, y=by,
                        dx=math.cos(angle) * speed,
                        dy=math.sin(angle) * speed,
                        lifetime=life, max_lifetime=life,
                        color=color, radius=self._PARTICLE_R,
                    ))
        if positions:
            cx = sum(p[0] for p in positions) / len(positions)
            cy = sum(p[1] for p in positions) / len(positions)
            total = len(indices) * 25
            self.score_popups.append(
                ScorePopup(cx, cy, f"BOOM +{total}", (255, 140, 0), 1.4, 1.4)
            )
        self.chain.remove_balls(indices)
        self._spawn_hold = 1.2  # hold off spawning for 1.2 s after bomb

    def _check_coin_collisions(self) -> None:
        if not self.coins or not self.fired_balls:
            return
        hit_coin_ids: set[int] = set()
        hit_ball_ids: set[int] = set()
        for coin in self.coins:
            for ball in self.fired_balls:
                if id(ball) in hit_ball_ids:
                    continue
                dist_sq = (ball.x - coin.x) ** 2 + (ball.y - coin.y) ** 2
                if dist_sq <= (ball.radius + coin.radius) ** 2:
                    self.score += 50
                    sounds.play("coin", 0.4)
                    self.score_popups.append(
                        ScorePopup(coin.x, coin.y, "+50", (255, 215, 0), 1.1, 1.1)
                    )
                    hit_coin_ids.add(id(coin))
                    hit_ball_ids.add(id(ball))
                    break
        if hit_coin_ids:
            self.coins = [c for c in self.coins if id(c) not in hit_coin_ids]
            self.fired_balls = [b for b in self.fired_balls if id(b) not in hit_ball_ids]

    def _check_aim_powerup_collisions(self) -> None:
        """Fired balls collect aim powerups without being consumed."""
        if not self.aim_powerups or not self.fired_balls:
            return
        collected = []
        for powerup in self.aim_powerups:
            for ball in self.fired_balls:
                if not ball.active:
                    continue
                dist_sq = (ball.x - powerup.x) ** 2 + (ball.y - powerup.y) ** 2
                if dist_sq <= (ball.radius + powerup.radius) ** 2:
                    self._aim_timer = 12.0
                    sounds.play("aim", 0.45)
                    self.score_popups.append(
                        ScorePopup(powerup.x, powerup.y, "AIM LINE!", (0, 220, 255), 1.3, 1.3)
                    )
                    collected.append(powerup)
                    break
        for p in collected:
            self.aim_powerups.remove(p)

    def _render(self) -> None:
        mouse_pos = self._frame_mouse
        self.background.draw(self._logical)

        if self.state == "main_menu":
            self.renderer.draw_main_menu(mouse_pos)
        elif self.state == "cheat_menu":
            self.renderer.draw_cheat_menu(self.active_cheats, self._cheat_input, self._cheat_message)
        elif self.state == "level_select":
            _ls_mouse = (-1, -1) if self._ls_hover_suppressed else mouse_pos
            self.renderer.draw_level_select(_ls_mouse, self._level_select_idx, records_store.best_by_level(), self._ls_scroll, self._max_unlocked(), self._all_unlocked)
        elif self.state == "records":
            self.renderer.draw_records(records_store.top(), self._records_scroll,
                                       tab=self._records_tab,
                                       best_by_level=records_store.best_by_level(),
                                       endless_records=records_store.top_endless(),
                                       best_by_endless=records_store.best_by_endless())
        elif self.state == "settings":
            self.renderer.draw_settings(mouse_pos, SETTINGS)
        else:
            self.renderer.draw_path(self.path)
            self.renderer.draw_coins(self.coins)
            self.renderer.draw_aim_powerups(self.aim_powerups)
            self.renderer.draw_chain(self.chain, self.path)
            if SETTINGS.particles:
                self.renderer.draw_particles(self.particles)
            self.renderer.draw_score_popups(self.score_popups)
            self.renderer.draw_fired_balls(self.fired_balls)
            self.renderer.draw_aim_line(self.frog, self._aim_timer, self._frame_chain_positions)
            self.renderer.draw_frog(self.frog)
            _front = self.chain.front_distance() if self.chain.balls else 0.0
            _path_len = self.path.total_length if self.path else 1.0
            self.renderer.draw_hud(
                remaining=len(self.chain.balls),
                spawned=self.spawned_count,
                total=self._total_balls,
                elapsed_time=self.elapsed_time,
                score=int(self._display_score),
                aim_timer=self._aim_timer,
                slowdown_timer=self._slowdown_timer,
                danger_frac=_front / _path_len if SETTINGS.danger_vignette else 0.0,
                fps=self.clock.get_fps(),
            )
            _ov_alpha = int(self._overlay_t * 255)
            if self.state == "paused":
                _pause_name = "COMBO TEST" if self._pre_pause_state == "combo_test" else (f"ENDLESS  {LEVELS[self.current_level_idx]['name']}" if self._endless_mode else LEVELS[self.current_level_idx]["name"])
                self.renderer.draw_pause_menu(mouse_pos, level_name=_pause_name, score=self.score, overlay_alpha=_ov_alpha)
            elif self.state == "level_complete":
                next_idx = self.current_level_idx + 1
                next_name = LEVELS[next_idx]["name"] if next_idx < len(LEVELS) else ""
                self.renderer.draw_level_complete(mouse_pos, next_name, score=self.score, new_best=self._level_complete_new_best, overlay_alpha=_ov_alpha)
            elif self.state == "game_complete":
                self.renderer.draw_game_complete(mouse_pos, self.score, self.elapsed_time, overlay_alpha=_ov_alpha)
            elif self.state == "lose":
                self.renderer.draw_lose(mouse_pos, self.score, self.elapsed_time,
                                        is_endless=self._endless_mode, overlay_alpha=_ov_alpha)

        scale, ox, oy, scaled_w, scaled_h = self._scale_rect()
        scaled = pygame.transform.smoothscale(self._logical, (scaled_w, scaled_h))
        self.screen.fill((0, 0, 0))
        if self.state not in ("playing", "combo_test"):
            self._shake = 0.0
        if self._shake > 0.5:
            sx = int(random.uniform(-self._shake, self._shake) * scale)
            sy = int(random.uniform(-self._shake, self._shake) * scale)
        else:
            sx, sy = 0, 0
        self.screen.blit(scaled, (ox + sx, oy + sy))
        pygame.display.flip()
