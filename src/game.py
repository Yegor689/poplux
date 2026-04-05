import sys
import math
import random
import pygame
from path import Path
from frog import Frog
from chain import Chain
from renderer import Renderer
from background import Background
from ball import Ball, Coin, Particle, ScorePopup, AimPowerup
import records as records_store
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE, BG_COLOR,
    BALL_RADIUS, MATCH_MINIMUM, LEVELS, BALL_COLORS,
)


class Game:
    def __init__(self):
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
        self._logical = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.renderer = Renderer(self._logical)
        self.state = "main_menu"
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

    def _init_game_state(self, level_idx: int) -> None:
        self.current_level_idx = level_idx
        cfg = LEVELS[level_idx]
        self.path = Path(cfg)
        frog_pos = cfg.get("frog_pos")
        self.frog = Frog(pos=frog_pos)
        self.chain = Chain(self.path, cfg["chain_speed"])
        self.fired_balls = []
        self.particles = []
        self.score_popups = []
        self.spawned_count = 0
        self._total_balls = cfg["total_balls"]
        self.elapsed_time = 0.0
        self.score = 0
        self.show_debug_hud = False

        pre = min(cfg["pre_placed"], self._total_balls)
        self.chain.populate(pre)
        self.spawned_count = pre

        self._endless_mode = False
        self._pre_pause_state = "playing"
        self.coins = []
        self.coin_spots = cfg.get("coin_spots", [])
        self._coin_timer = random.uniform(15.0, 25.0)
        self._slowdown_timer = 0.0
        self.aim_powerups = []
        self.aim_powerup_spots = cfg.get("aim_powerup_spots", [])
        self._aim_powerup_timer = random.uniform(20.0, 35.0)
        self._aim_timer = 0.0
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
        cfg = LEVELS[0]
        self.current_level_idx = 0
        self.path = Path(cfg)
        frog_pos = cfg.get("frog_pos")
        self.frog = Frog(pos=frog_pos, color_pool=self._COMBO_TEST_COLORS)
        self.chain = Chain(self.path, cfg["chain_speed"],
                           color_pool=self._COMBO_TEST_COLORS, pair_mode=True)
        self.fired_balls = []
        self.particles = []
        self.score_popups = []
        self.spawned_count = 0
        self._total_balls = 999_999
        self.elapsed_time = 0.0
        self.score = 0
        self.show_debug_hud = False
        pre = min(cfg["pre_placed"], self._total_balls)
        self.chain.populate(pre)
        self.spawned_count = pre
        self._endless_mode = False
        self._pre_pause_state = "combo_test"
        self.state = "combo_test"

    def _init_endless_mode(self) -> None:
        """Endless mode: Level 1 layout, infinite balls, chain speeds up over time."""
        cfg = LEVELS[0]
        self.current_level_idx = 0
        self.path = Path(cfg)
        frog_pos = cfg.get("frog_pos")
        self.frog = Frog(pos=frog_pos)
        self.chain = Chain(self.path, cfg["chain_speed"])
        self.fired_balls = []
        self.particles = []
        self.score_popups = []
        self.spawned_count = 0
        self._total_balls = 999_999
        self.elapsed_time = 0.0
        self.score = 0
        self.show_debug_hud = False
        pre = min(cfg["pre_placed"], self._total_balls)
        self.chain.populate(pre)
        self.spawned_count = pre
        self._endless_mode = True
        self._endless_base_speed = float(cfg["chain_speed"])
        self._pre_pause_state = "playing"
        self.coins = []
        self.coin_spots = cfg.get("coin_spots", [])
        self._coin_timer = random.uniform(15.0, 25.0)
        self._slowdown_timer = 0.0
        self.aim_powerups = []
        self.aim_powerup_spots = cfg.get("aim_powerup_spots", [])
        self._aim_powerup_timer = random.uniform(20.0, 35.0)
        self._aim_timer = 0.0
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
            self._cheat_message = f"{code}  [ARMED]" if code == "CLEARALL" else f"{code}  [ON]"

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            self._frame_mouse = self._logical_mouse()
            running = self._handle_events()
            self.background.update(dt)
            if self.state in ("playing", "combo_test"):
                self._update(dt)
            self._render()
        pygame.quit()
        sys.exit()

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
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "main_menu":
                        return False
                    elif self.state in ("playing", "combo_test"):
                        self._pre_pause_state = self.state
                        self.state = "paused"
                    elif self.state == "paused":
                        self.state = self._pre_pause_state
                    else:
                        self.state = "main_menu"
                if event.key == pygame.K_r and self.state == "lose":
                    if self._endless_mode:
                        self._init_endless_mode()
                    else:
                        self._init_game_state(self.current_level_idx)
                if event.key == pygame.K_r and self.state == "combo_test":
                    self._init_combo_test()
                if event.key == pygame.K_s and self.state == "playing":
                    self.show_debug_hud = not self.show_debug_hud
                elif event.key == pygame.K_s and self.state == "level_select":
                    self._init_combo_test()
                elif event.key == pygame.K_s and self.state == "main_menu":
                    self.state = "cheat_menu"
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
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.state == "main_menu":
                    btn = self.renderer.main_menu_button_at(mouse_pos)
                    if btn == 0:
                        self._init_game_state(0)
                    elif btn == 1:
                        self.state = "level_select"
                    elif btn == 2:
                        self.state = "records"
                    elif btn == 3:
                        return False
                elif self.state == "level_select":
                    idx = self.renderer.level_button_at(mouse_pos)
                    if idx is not None:
                        self._init_game_state(idx)
                elif self.state in ("playing", "combo_test"):
                    ball = self.frog.shoot()
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
                    btn = self.renderer.level_complete_button_at(mouse_pos)
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
                            self._init_endless_mode()
                        else:
                            self._init_game_state(self.current_level_idx)
                    elif btn == 2:
                        self.state = "main_menu"
                elif self.state in ("lose", "game_complete"):
                    self.state = "main_menu"
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
        total = len(self.chain.recent_pops) * cascade_level
        text = f"+{total}" if cascade_level == 1 else f"+{total}  ×{cascade_level}"
        color = self._POPUP_COLORS[min(cascade_level - 1, len(self._POPUP_COLORS) - 1)]
        life = 1.1
        self.score_popups.append(ScorePopup(cx, cy, text, color, life, life))

        for path_dist, color_name, cascade_level in self.chain.recent_pops:
            self.score += cascade_level  # 1 pt × combo multiplier per ball popped
            cx, cy = self.path.point_at(path_dist)
            base = BALL_COLORS.get(color_name, (200, 200, 200))
            light = tuple(min(255, c + 60) for c in base)
            for _ in range(self._PARTICLE_COUNT):
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(*self._PARTICLE_SPEED)
                life  = random.uniform(*self._PARTICLE_LIFE)
                color = random.choice([base, light])
                self.particles.append(Particle(
                    x=cx, y=cy,
                    dx=math.cos(angle) * speed,
                    dy=math.sin(angle) * speed,
                    lifetime=life, max_lifetime=life,
                    color=color, radius=self._PARTICLE_R,
                ))

    _COMBO_SPEED_MULTIPLIER = 4.0

    def _update(self, dt: float) -> None:
        self.elapsed_time += dt
        self.frog.tick(dt)
        if self._slowdown_timer > 0:
            self._slowdown_timer = max(0.0, self._slowdown_timer - dt)

        if self.chain.bonus_popped:
            self._slowdown_timer = 15.0
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
            if self.chain._cascade_pending:
                live_ids = {id(b) for b in self.chain.balls}
                self.chain._cascade_pending = [
                    b for b in self.chain._cascade_pending if id(b) in live_ids
                ]
            if self.chain.is_empty() and self.spawned_count < self._total_balls:
                self.chain.spawn_one()
                self.spawned_count += 1

        while self.spawned_count < self._total_balls and self.chain.needs_spawn():
            self.chain.spawn_one()
            self.spawned_count += 1

        if "MAGNET" in self.active_cheats and self.chain.balls:
            for ball in self.fired_balls:
                best_dist_sq = float('inf')
                target = None
                for cb in self.chain.balls:
                    cx, cy = self.path.point_at(cb.path_distance)
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

        to_remove = []
        for ball in self.fired_balls:
            ball.move(dt)
            if self._out_of_bounds(ball):
                to_remove.append(ball)
        for b in to_remove:
            self.fired_balls.remove(b)

        self._check_collisions()
        self._check_coin_collisions()
        self._check_aim_powerup_collisions()

        if "GODMODE" in self.active_cheats:
            while self.chain.balls and self.chain.front_distance() >= self.path.total_length:
                self.chain.balls.pop()
            if self.chain._cascade_pending:
                live_ids = {id(b) for b in self.chain.balls}
                self.chain._cascade_pending = [
                    b for b in self.chain._cascade_pending if id(b) in live_ids
                ]

        if self.state != "combo_test":
            if self.chain.is_empty() and self.spawned_count >= self._total_balls:
                level_name = LEVELS[self.current_level_idx]["name"]
                records_store.save(level_name, self.score, self.elapsed_time)
                if self.current_level_idx + 1 < len(LEVELS):
                    self.state = "level_complete"
                else:
                    self.state = "game_complete"
            elif self.chain.front_distance() >= self.path.total_length:
                if self._endless_mode:
                    records_store.save("Endless", self.score, self.elapsed_time)
                self.state = "lose"

    def _out_of_bounds(self, ball) -> bool:
        return (ball.x < -BALL_RADIUS or ball.x > SCREEN_WIDTH + BALL_RADIUS or
                ball.y < -BALL_RADIUS or ball.y > SCREEN_HEIGHT + BALL_RADIUS)

    def _check_collisions(self) -> None:
        to_remove = []
        for fired in self.fired_balls:
            hit_idx = None
            best_dist_sq = float('inf')
            for i, chain_ball in enumerate(self.chain.balls):
                cx, cy = self.path.point_at(chain_ball.path_distance)
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
                to_remove.append(fired)

        for b in to_remove:
            self.fired_balls.remove(b)

    def _explode_bomb(self, hit_idx: int) -> None:
        """Destroy up to 3 balls on each side of hit_idx, spawn particles and popup."""
        lo = max(0, hit_idx - 3)
        hi = min(len(self.chain.balls) - 1, hit_idx + 3)
        indices = list(range(lo, hi + 1))
        positions = []
        for i in indices:
            b = self.chain.balls[i]
            cx, cy = self.path.point_at(b.path_distance)
            positions.append((cx, cy))
            self.score += 5
            base = BALL_COLORS.get(b.color, (200, 200, 200))
            light = tuple(min(255, c + 60) for c in base)
            for _ in range(self._PARTICLE_COUNT):
                angle = random.uniform(0, 2 * math.pi)
                speed = random.uniform(*self._PARTICLE_SPEED) * 1.4
                life = random.uniform(*self._PARTICLE_LIFE)
                color = random.choice([base, light, (255, 140, 0), (255, 220, 60)])
                self.particles.append(Particle(
                    x=cx, y=cy,
                    dx=math.cos(angle) * speed,
                    dy=math.sin(angle) * speed,
                    lifetime=life, max_lifetime=life,
                    color=color, radius=self._PARTICLE_R,
                ))
        if positions:
            cx = sum(p[0] for p in positions) / len(positions)
            cy = sum(p[1] for p in positions) / len(positions)
            total = len(indices) * 5
            self.score_popups.append(
                ScorePopup(cx, cy, f"BOOM +{total}", (255, 140, 0), 1.4, 1.4)
            )
        self.chain.remove_balls(indices)

    def _check_coin_collisions(self) -> None:
        if not self.coins or not self.fired_balls:
            return
        coins_hit = []
        balls_used = []
        for coin in self.coins:
            for ball in self.fired_balls:
                if ball in balls_used:
                    continue
                dist_sq = (ball.x - coin.x) ** 2 + (ball.y - coin.y) ** 2
                if dist_sq <= (ball.radius + coin.radius) ** 2:
                    self.score += 10
                    self.score_popups.append(
                        ScorePopup(coin.x, coin.y, "+10", (255, 215, 0), 1.1, 1.1)
                    )
                    coins_hit.append(coin)
                    balls_used.append(ball)
                    break
        for c in coins_hit:
            self.coins.remove(c)
        for b in balls_used:
            self.fired_balls.remove(b)

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
            self.renderer.draw_level_select(mouse_pos)
        elif self.state == "records":
            self.renderer.draw_records(records_store.top())
        else:
            self.renderer.draw_path(self.path)
            self.renderer.draw_coins(self.coins)
            self.renderer.draw_aim_powerups(self.aim_powerups)
            self.renderer.draw_chain(self.chain, self.path)
            self.renderer.draw_particles(self.particles)
            self.renderer.draw_score_popups(self.score_popups)
            self.renderer.draw_fired_balls(self.fired_balls)
            self.renderer.draw_aim_line(self.frog, self._aim_timer)
            self.renderer.draw_frog(self.frog)
            self.renderer.draw_hud(
                remaining=len(self.chain.balls),
                spawned=self.spawned_count,
                total=self._total_balls,
                level_name="COMBO TEST" if self._pre_pause_state == "combo_test" else ("ENDLESS" if self._endless_mode else LEVELS[self.current_level_idx]["name"]),
                elapsed_time=self.elapsed_time,
                score=self.score,
                show_debug=self.show_debug_hud,
                aim_timer=self._aim_timer,
            )
            if self.state == "paused":
                self.renderer.draw_pause_menu(mouse_pos)
            elif self.state == "level_complete":
                next_name = LEVELS[self.current_level_idx + 1]["name"]
                self.renderer.draw_level_complete(mouse_pos, next_name)
            elif self.state == "game_complete":
                self.renderer.draw_overlay("YOU WIN!", "All levels cleared!  Click to return to menu")
            elif self.state == "lose":
                if self._endless_mode:
                    mins = int(self.elapsed_time) // 60
                    secs = int(self.elapsed_time) % 60
                    self.renderer.draw_overlay(
                        "GAME OVER",
                        f"Score: {self.score:,}  ·  {mins}:{secs:02d}  ·  R retry  ·  Click for menu",
                    )
                else:
                    self.renderer.draw_overlay("GAME OVER", "R to retry  ·  Click to return to menu")

        scale, ox, oy, scaled_w, scaled_h = self._scale_rect()
        scaled = pygame.transform.smoothscale(self._logical, (scaled_w, scaled_h))
        self.screen.fill((0, 0, 0))
        self.screen.blit(scaled, (ox, oy))
        pygame.display.flip()
