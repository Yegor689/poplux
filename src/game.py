import sys
import math
import random
import pygame
from path import Path
from frog import Frog
from chain import Chain
from renderer import Renderer
from background import Background
from ball import Particle
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
        self.spawned_count = 0
        self._total_balls = 0
        self._cached_scale_rect = None
        self._cached_screen_size = None
        self._frame_mouse = (0, 0)
        self.background = Background()

    def _init_game_state(self, level_idx: int) -> None:
        self.current_level_idx = level_idx
        cfg = LEVELS[level_idx]
        self.path = Path(cfg)
        frog_pos = cfg.get("frog_pos")
        self.frog = Frog(pos=frog_pos)
        self.chain = Chain(self.path, cfg["chain_speed"])
        self.fired_balls = []
        self.particles = []
        self.spawned_count = 0
        self._total_balls = cfg["total_balls"]
        self.elapsed_time = 0.0
        self.score = 0
        self.show_debug_hud = False

        pre = min(cfg["pre_placed"], self._total_balls)
        self.chain.populate(pre)
        self.spawned_count = pre

        self.state = "playing"

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            self._frame_mouse = self._logical_mouse()
            running = self._handle_events()
            self.background.update(dt)
            if self.state in ("playing",):
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
                    elif self.state == "playing":
                        self.state = "paused"
                    elif self.state == "paused":
                        self.state = "playing"
                    else:
                        self.state = "main_menu"
                if event.key == pygame.K_r and self.state == "lose":
                    self._init_game_state(self.current_level_idx)
                if event.key == pygame.K_s and self.state == "playing":
                    self.show_debug_hud = not self.show_debug_hud
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if self.state == "playing":
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
                elif self.state == "playing":
                    ball = self.frog.shoot()
                    self.fired_balls.append(ball)
                elif self.state == "level_complete":
                    btn = self.renderer.level_complete_button_at(mouse_pos)
                    if btn == 0:
                        self._init_game_state(self.current_level_idx + 1)
                    elif btn == 1:
                        self.state = "main_menu"
                elif self.state == "paused":
                    btn = self.renderer.pause_button_at(mouse_pos)
                    if btn == 0:
                        self.state = "playing"
                    elif btn == 1:
                        self._init_game_state(self.current_level_idx)
                    elif btn == 2:
                        self.state = "main_menu"
                elif self.state in ("lose", "game_complete"):
                    self.state = "main_menu"
        if self.state == "playing":
            self.frog.update(self._frame_mouse)
        return True

    _PARTICLE_COUNT = 10   # particles per popped ball
    _PARTICLE_SPEED = (80, 200)
    _PARTICLE_LIFE  = (0.3, 0.55)
    _PARTICLE_R     = 5

    def _spawn_particles(self) -> None:
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

    def _update(self, dt: float) -> None:
        self.elapsed_time += dt
        self.frog.tick(dt)
        self.chain.advance(dt)
        self._spawn_particles()

        # Remove exhausted colors from the frog's generation pool
        active = {b.color for b in self.chain.balls}
        active |= {b.color for b in self.fired_balls if b.active}
        self.frog.update_available_colors(active)

        self.particles = [p for p in self.particles if p.alive]
        for p in self.particles:
            p.update(dt)

        while self.spawned_count < self._total_balls and self.chain.needs_spawn():
            self.chain.spawn_one()
            self.spawned_count += 1

        to_remove = []
        for ball in self.fired_balls:
            ball.move(dt)
            if self._out_of_bounds(ball):
                to_remove.append(ball)
        for b in to_remove:
            self.fired_balls.remove(b)

        self._check_collisions()

        if self.chain.is_empty() and self.spawned_count >= self._total_balls:
            level_name = LEVELS[self.current_level_idx]["name"]
            records_store.save(level_name, self.score, self.elapsed_time)
            if self.current_level_idx + 1 < len(LEVELS):
                self.state = "level_complete"
            else:
                self.state = "game_complete"
        elif self.chain.front_distance() >= self.path.total_length:
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
                path_dist = self.chain.balls[hit_idx].path_distance
                idx = self.chain.insert(fired, path_dist)
                matches = self.chain.check_matches(idx)
                if len(matches) >= MATCH_MINIMUM:
                    self.chain.queue_match(matches)
                to_remove.append(fired)

        for b in to_remove:
            self.fired_balls.remove(b)

    def _render(self) -> None:
        mouse_pos = self._frame_mouse
        self.background.draw(self._logical)

        if self.state == "main_menu":
            self.renderer.draw_main_menu(mouse_pos)
        elif self.state == "level_select":
            self.renderer.draw_level_select(mouse_pos)
        elif self.state == "records":
            self.renderer.draw_records(records_store.top())
        else:
            self.renderer.draw_path(self.path)
            self.renderer.draw_chain(self.chain, self.path)
            self.renderer.draw_particles(self.particles)
            self.renderer.draw_fired_balls(self.fired_balls)
            self.renderer.draw_frog(self.frog)
            self.renderer.draw_hud(
                remaining=len(self.chain.balls),
                spawned=self.spawned_count,
                total=self._total_balls,
                level_name=LEVELS[self.current_level_idx]["name"],
                elapsed_time=self.elapsed_time,
                score=self.score,
                show_debug=self.show_debug_hud,
            )
            if self.state == "paused":
                self.renderer.draw_pause_menu(mouse_pos)
            elif self.state == "level_complete":
                next_name = LEVELS[self.current_level_idx + 1]["name"]
                self.renderer.draw_level_complete(mouse_pos, next_name)
            elif self.state == "game_complete":
                self.renderer.draw_overlay("YOU WIN!", "All levels cleared!  Click to return to menu")
            elif self.state == "lose":
                self.renderer.draw_overlay("GAME OVER", "R to retry  ·  Click to return to menu")

        scale, ox, oy, scaled_w, scaled_h = self._scale_rect()
        scaled = pygame.transform.smoothscale(self._logical, (scaled_w, scaled_h))
        self.screen.fill((0, 0, 0))
        self.screen.blit(scaled, (ox, oy))
        pygame.display.flip()
