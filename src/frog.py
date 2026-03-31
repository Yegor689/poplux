import math
import random
from ball import Ball
from settings import (
    PATH_CENTER, BALL_RADIUS, SHOOT_SPEED, BALL_COLORS,
)

COLOR_NAMES = list(BALL_COLORS.keys())


_RECOIL_MAX   = 9.0          # pixels of kick-back
_RECOIL_DECAY = 1.0 / 0.14  # recoil-to-rest in ~0.14 s
_BOMB_CHANCE    = 0.05  # probability any new ball is a bomb
_RAINBOW_CHANCE = 0.05  # probability any new ball is a rainbow


class Frog:
    def __init__(self, pos=None, color_pool: list[str] | None = None):
        self.x, self.y = pos if pos is not None else PATH_CENTER
        self.angle: float = 0.0  # radians, aim direction
        self.available_colors: list[str] = list(color_pool) if color_pool is not None else list(COLOR_NAMES)
        self.current_ball: Ball = self._new_ball()
        self.next_ball: Ball = self._new_ball()
        self._recoil_t: float = 0.0  # 1 → 0 over the recoil duration

    @property
    def recoil(self) -> float:
        """Current displacement (px) opposite the aim direction."""
        return self._recoil_t * _RECOIL_MAX

    def tick(self, dt: float) -> None:
        """Decay recoil animation each frame."""
        if self._recoil_t > 0:
            self._recoil_t = max(0.0, self._recoil_t - _RECOIL_DECAY * dt)

    def _new_ball(self) -> Ball:
        pool = self.available_colors if self.available_colors else COLOR_NAMES
        r = random.random()
        is_bomb    = r < _BOMB_CHANCE
        is_rainbow = not is_bomb and r < _BOMB_CHANCE + _RAINBOW_CHANCE
        return Ball(color=random.choice(pool), is_bomb=is_bomb, is_rainbow=is_rainbow)

    def update_available_colors(self, active_colors: set[str]) -> None:
        """Remove exhausted colors from the generation pool. Never empties it mid-game.
        Also refreshes pre-loaded balls whose color is no longer active so a ghost
        color can't be fired after the last chain ball of that color pops."""
        updated = [c for c in COLOR_NAMES if c in active_colors]
        if not updated:
            return
        self.available_colors = updated
        if self.next_ball.color not in active_colors and not (self.next_ball.is_bomb or self.next_ball.is_rainbow):
            self.next_ball = self._new_ball()
        if self.current_ball.color not in active_colors and not (self.current_ball.is_bomb or self.current_ball.is_rainbow):
            self.current_ball = self._new_ball()

    def update(self, mouse_pos: tuple[float, float]) -> None:
        """Rotate frog to face mouse cursor."""
        dx = mouse_pos[0] - self.x
        dy = mouse_pos[1] - self.y
        self.angle = math.atan2(dy, dx)

    def swap(self) -> None:
        """Swap current and next ball."""
        self.current_ball, self.next_ball = self.next_ball, self.current_ball

    def shoot(self) -> Ball:
        """Fire the current ball; cycle next -> current, generate new next."""
        ball = self.current_ball
        # Position at the frog's mouth (edge in the aim direction)
        mouth_dist = BALL_RADIUS * 3 + BALL_RADIUS
        ball.x = self.x + math.cos(self.angle) * mouth_dist
        ball.y = self.y + math.sin(self.angle) * mouth_dist
        ball.dx = math.cos(self.angle) * SHOOT_SPEED
        ball.dy = math.sin(self.angle) * SHOOT_SPEED
        ball.active = True

        self._recoil_t = 1.0
        self.current_ball = self.next_ball
        self.next_ball = self._new_ball()
        return ball

