from dataclasses import dataclass, field
from settings import BALL_RADIUS


@dataclass
class Coin:
    x: float
    y: float
    radius: int = 14
    lifetime: float = 12.0
    max_lifetime: float = 12.0
    pulse: float = 0.0

    def update(self, dt: float) -> None:
        self.lifetime -= dt
        self.pulse += dt * 3.0

    @property
    def alive(self) -> bool:
        return self.lifetime > 0

    @property
    def alpha(self) -> int:
        t = self.lifetime / self.max_lifetime
        if t < 0.15:
            return int(255 * t / 0.15)
        return 255


@dataclass
class Particle:
    x: float
    y: float
    dx: float
    dy: float
    lifetime: float      # remaining seconds
    max_lifetime: float  # initial lifetime (for lerp)
    color: tuple         # RGB
    radius: float        # initial radius

    def update(self, dt: float) -> None:
        self.x += self.dx * dt
        self.y += self.dy * dt
        self.lifetime -= dt

    @property
    def alive(self) -> bool:
        return self.lifetime > 0

    @property
    def t(self) -> float:
        """Progress 1→0 as particle dies."""
        return max(0.0, self.lifetime / self.max_lifetime)


@dataclass
class ScorePopup:
    x: float
    y: float
    text: str
    color: tuple
    lifetime: float
    max_lifetime: float
    vy: float = -110.0  # pixels per second upward

    def update(self, dt: float) -> None:
        self.y += self.vy * dt
        self.lifetime -= dt

    @property
    def alive(self) -> bool:
        return self.lifetime > 0

    @property
    def alpha(self) -> int:
        return int(255 * max(0.0, self.lifetime / self.max_lifetime))


@dataclass
class Ball:
    color: str
    radius: int = BALL_RADIUS

    # For chain balls
    path_distance: float = 0.0
    path_offset: float = 0.0   # temporary visual displacement; animated to 0 after insertion
    entry_t: float = 1.0       # 0 → 1 entry animation; <1 means still animating in
    entry_x: float = 0.0       # screen x where ball was when it joined the chain
    entry_y: float = 0.0       # screen y where ball was when it joined the chain
    spin_angle: float = 0.0    # cumulative rotation angle (radians) for the rolling seam

    # For fired balls
    x: float = 0.0
    y: float = 0.0
    dx: float = 0.0
    dy: float = 0.0
    active: bool = False

    def move(self, dt: float) -> None:
        """Move the ball along its velocity vector."""
        self.x += self.dx * dt
        self.y += self.dy * dt
