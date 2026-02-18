from __future__ import annotations
import math
import random
import pygame
import pygame.gfxdraw
from settings import SCREEN_WIDTH, SCREEN_HEIGHT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _aa_circle(surf: pygame.Surface, color: tuple, pos: tuple, radius: int) -> None:
    x, y, r = int(pos[0]), int(pos[1]), max(0, int(radius))
    pygame.gfxdraw.filled_circle(surf, x, y, r, color)
    pygame.gfxdraw.aacircle(surf, x, y, r, color)


# ---------------------------------------------------------------------------
# Asteroid
# ---------------------------------------------------------------------------

class _Asteroid:
    __slots__ = ('x', 'y', 'dx', 'dy', 'angle', 'spin', 'verts')

    def __init__(self, x, y, dx, dy, angle, spin, verts):
        self.x = x; self.y = y
        self.dx = dx; self.dy = dy
        self.angle = angle; self.spin = spin
        self.verts = verts


_NUM_ASTEROIDS = 20


def _make_asteroid() -> _Asteroid:
    n = random.randint(6, 9)
    base_r = random.uniform(4, 12)
    verts = []
    for i in range(n):
        theta = 2 * math.pi * i / n + random.uniform(-0.28, 0.28)
        r = base_r * random.uniform(0.55, 1.35)
        verts.append((math.cos(theta) * r, math.sin(theta) * r))
    speed = random.uniform(10, 35)
    dir_a = random.uniform(0, 2 * math.pi)
    return _Asteroid(
        x=random.uniform(0, SCREEN_WIDTH),
        y=random.uniform(0, SCREEN_HEIGHT),
        dx=math.cos(dir_a) * speed,
        dy=math.sin(dir_a) * speed,
        angle=random.uniform(0, 2 * math.pi),
        spin=random.choice([-1, 1]) * random.uniform(0.3, 1.4),
        verts=verts,
    )


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------

class Background:
    def __init__(self):
        self._starfield = self._render_starfield()
        self._asteroids = [_make_asteroid() for _ in range(_NUM_ASTEROIDS)]

    @staticmethod
    def _render_starfield() -> pygame.Surface:
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill((4, 4, 14))
        rng = random.Random(42)
        for _ in range(260):
            x = rng.randint(0, SCREEN_WIDTH)
            y = rng.randint(0, SCREEN_HEIGHT)
            kind = rng.choices(['dim', 'mid', 'bright'], weights=[55, 35, 10])[0]
            if kind == 'dim':
                r, brightness = 1, rng.randint(80, 160)
            elif kind == 'mid':
                r, brightness = 1, rng.randint(160, 210)
            else:
                r, brightness = 2, rng.randint(220, 255)
            tint = rng.choice([(10, 10, 40), (0, 0, 0), (30, 20, 0)])
            col = tuple(min(255, brightness + t) for t in tint)
            if r == 1:
                surf.set_at((x, y), col)
            else:
                _aa_circle(surf, col, (x, y), r)
            if kind == 'bright':
                dim = tuple(c // 3 for c in col)
                pygame.draw.line(surf, dim, (x - 6, y), (x + 6, y), 1)
                pygame.draw.line(surf, dim, (x, y - 6), (x, y + 6), 1)
        return surf

    def update(self, dt: float) -> None:
        margin = 15
        for a in self._asteroids:
            a.x += a.dx * dt
            a.y += a.dy * dt
            a.angle += a.spin * dt
            if a.x < -margin:
                a.x = SCREEN_WIDTH + margin
            elif a.x > SCREEN_WIDTH + margin:
                a.x = -margin
            if a.y < -margin:
                a.y = SCREEN_HEIGHT + margin
            elif a.y > SCREEN_HEIGHT + margin:
                a.y = -margin

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self._starfield, (0, 0))
        for a in self._asteroids:
            ca, sa = math.cos(a.angle), math.sin(a.angle)
            pts = [
                (int(a.x + vx * ca - vy * sa),
                 int(a.y + vx * sa + vy * ca))
                for vx, vy in a.verts
            ]
            pygame.draw.polygon(surface, (48, 45, 41), pts)
            pygame.draw.polygon(surface, (78, 73, 66), pts, 1)
