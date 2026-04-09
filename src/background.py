from __future__ import annotations
import math
import random
import numpy as np
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
    __slots__ = ('x', 'y', 'dx', 'dy', 'angle', 'spin', 'base_r', 'scale_x', 'scale_y', 'surf_cache')

    def __init__(self, x, y, dx, dy, angle, spin, base_r, scale_x, scale_y):
        self.x = x; self.y = y
        self.dx = dx; self.dy = dy
        self.angle = angle; self.spin = spin
        self.base_r = base_r
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.surf_cache: pygame.Surface | None = None


_NUM_ASTEROIDS = 28


def _make_asteroid() -> _Asteroid:
    base_r = random.uniform(14, 42)
    speed = random.uniform(12, 48)
    dir_a = random.uniform(0, 2 * math.pi)
    return _Asteroid(
        x=random.uniform(0, SCREEN_WIDTH),
        y=random.uniform(0, SCREEN_HEIGHT),
        dx=math.cos(dir_a) * speed,
        dy=math.sin(dir_a) * speed,
        angle=random.uniform(0, 2 * math.pi),
        spin=random.choice([-1, 1]) * random.uniform(0.15, 1.1),
        base_r=base_r,
        scale_x=random.uniform(0.6, 1.0),
        scale_y=random.uniform(0.55, 0.85),
    )


def _build_asteroid_surf(a: _Asteroid, rng: random.Random) -> pygame.Surface:
    """
    Render a realistic asteroid sprite into an SRCALPHA surface using numpy.
    Technique:
      1. Build a polar-coordinate mask for the irregular rocky silhouette.
      2. Fill with noisy grey-brown texture (layered octave noise).
      3. Apply radial shading (light top-left, shadow bottom-right).
      4. Stamp craters (darkened bowl + bright rim arc).
      5. Draw a 1-px anti-aliased edge outline.
    """
    R = int(a.base_r)
    pad = R + 6
    size = pad * 2
    cx = cy = pad

    # ------------------------------------------------------------------ #
    # 1. Silhouette mask — polar radii with low-freq bumps                #
    # ------------------------------------------------------------------ #
    N_ANGLES = 512  # sample resolution for the mask
    thetas = np.linspace(0, 2 * math.pi, N_ANGLES, endpoint=False)

    # Low-frequency bump function: sum of a few harmonics
    n_harmonics = rng.randint(5, 8)
    radii = np.ones(N_ANGLES) * R
    for h in range(1, n_harmonics + 1):
        amp = R * rng.uniform(0.04, 0.14) / h
        phase = rng.uniform(0, 2 * math.pi)
        radii += amp * np.cos(h * thetas + phase)
    # Elliptical squash
    radii_x = radii * a.scale_x
    radii_y = radii * a.scale_y

    # Build polygon vertices for drawing
    vx = (cx + np.cos(thetas) * radii_x).astype(int)
    vy = (cy + np.sin(thetas) * radii_y).astype(int)
    poly_pts = list(zip(vx.tolist(), vy.tolist()))

    # ------------------------------------------------------------------ #
    # 2. Texture: noisy grey-brown fill via numpy                         #
    # ------------------------------------------------------------------ #
    # Base colour palette for this asteroid (slight per-asteroid variation)
    base_v = rng.randint(58, 78)
    tint_r = rng.randint(-4, 8)   # slight warm/cool tint
    tint_b = rng.randint(-6, 2)

    # Build pixel arrays: shape (size, size, 4) RGBA
    px = np.zeros((size, size, 4), dtype=np.uint8)

    # Coordinate grids
    ys, xs = np.mgrid[0:size, 0:size]
    dx_arr = (xs - cx).astype(np.float32)
    dy_arr = (ys - cy).astype(np.float32)

    # Per-pixel angle and normalised elliptical radius
    ang = np.arctan2(dy_arr, dx_arr)            # (size,size)
    # Interpolate silhouette radius at each pixel angle
    idx = ((ang % (2 * math.pi)) / (2 * math.pi) * N_ANGLES).astype(int) % N_ANGLES
    mask_rx = radii_x[idx]
    mask_ry = radii_y[idx]
    # Ellipse-normalised distance: 1.0 = on boundary
    safe_rx = np.where(mask_rx > 0, mask_rx, 1)
    safe_ry = np.where(mask_ry > 0, mask_ry, 1)
    norm_dist = np.sqrt((dx_arr / safe_rx) ** 2 + (dy_arr / safe_ry) ** 2)
    inside = norm_dist <= 1.0   # boolean mask

    # -- Noise texture (two octaves of value noise, pure numpy) --
    seed = rng.randint(0, 2**31)
    prng = np.random.default_rng(seed)
    # Coarse grain: generate small grid, tile-repeat to full size
    grain_scale = max(2, size // 8)
    small_h = size // grain_scale + 2
    small_w = size // grain_scale + 2
    coarse_small = prng.uniform(0, 38, size=(small_h, small_w)).astype(np.float32)
    # Nearest-neighbour upsample then smooth with a simple box kernel
    coarse_up = np.repeat(np.repeat(coarse_small, grain_scale, axis=0),
                          grain_scale, axis=1)[:size, :size]
    # Cheap 5x5 box blur for smooth coarse noise
    k = 5
    for _ in range(2):
        pad_c = np.pad(coarse_up, k // 2, mode='edge')
        coarse_up = sum(pad_c[i:i+size, j:j+size]
                        for i in range(k) for j in range(k)) / (k * k)
    # Fine grain
    fine = prng.uniform(-9, 9, size=(size, size)).astype(np.float32)

    noise = (coarse_up * 0.7 + fine * 0.3).astype(np.float32)

    # -- Radial shading (light from top-left) --
    light_dir = np.array([-0.6, -0.6], dtype=np.float32)
    dist_safe = np.where(norm_dist > 0, norm_dist, 1e-6)
    nx = dx_arr / dist_safe
    ny = dy_arr / dist_safe
    diffuse = -(nx * light_dir[0] + ny * light_dir[1])   # −1..1, positive = lit
    shading = (diffuse * 10).astype(np.float32)           # ±10 brightness swing

    # Soft vignette: darken edges slightly
    vignette = np.clip((1.0 - norm_dist) * 10, -6, 0).astype(np.float32)

    # Combine
    v = base_v + noise + shading + vignette

    px[:, :, 0] = np.clip(v + tint_r, 0, 255).astype(np.uint8)
    px[:, :, 1] = np.clip(v - 2,      0, 255).astype(np.uint8)
    px[:, :, 2] = np.clip(v + tint_b, 0, 255).astype(np.uint8)
    px[:, :, 3] = np.where(inside, 255, 0).astype(np.uint8)

    surf = pygame.surfarray.make_surface(px[:, :, :3].swapaxes(0, 1))
    surf = surf.convert_alpha()
    alpha_surf = pygame.Surface((size, size), pygame.SRCALPHA)
    alpha_surf.blit(surf, (0, 0))
    # Apply alpha mask
    alpha_arr = pygame.surfarray.pixels_alpha(alpha_surf)
    alpha_arr[:] = px[:, :, 3].T
    del alpha_arr

    # ------------------------------------------------------------------ #
    # 3. Craters                                                          #
    # ------------------------------------------------------------------ #
    n_craters = rng.randint(2, max(3, R // 7))
    for _ in range(n_craters):
        # Place inside inner 65% so crater stays inside rock
        cr_angle = rng.uniform(0, 2 * math.pi)
        cr_dist = rng.uniform(0, 0.62)
        # Approximate ellipse boundary at this angle for placement
        bx = math.cos(cr_angle) * radii_x[int(cr_angle / (2*math.pi) * N_ANGLES) % N_ANGLES]
        by = math.sin(cr_angle) * radii_y[int(cr_angle / (2*math.pi) * N_ANGLES) % N_ANGLES]
        crx = int(cx + math.cos(cr_angle) * abs(bx) * cr_dist)
        cry = int(cy + math.sin(cr_angle) * abs(by) * cr_dist)
        cr = max(2, int(R * rng.uniform(0.07, 0.22)))

        # Dark bowl
        pygame.gfxdraw.filled_circle(alpha_surf, crx, cry, cr,
                                     (22, 20, 17, 200))
        # Rim — full dark ring
        pygame.gfxdraw.aacircle(alpha_surf, crx, cry, cr,
                                (18, 16, 13, 230))
        # Bright highlight arc (top-left of rim)
        if cr >= 3:
            pygame.gfxdraw.aacircle(alpha_surf, crx - 1, cry - 1, cr - 1,
                                    (105, 98, 86, 90))

    # ------------------------------------------------------------------ #
    # 4. Edge outline                                                      #
    # ------------------------------------------------------------------ #
    # Draw a slightly brighter 1-px outline along the silhouette
    pygame.draw.polygon(alpha_surf, (100, 94, 82, 220), poly_pts, 1)

    return alpha_surf


# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------

class Background:
    def __init__(self):
        self._starfield = self._render_starfield()
        rng = random.Random()   # unseeded — different each run
        self._asteroids = [_make_asteroid() for _ in range(_NUM_ASTEROIDS)]
        for a in self._asteroids:
            a.surf_cache = _build_asteroid_surf(a, rng)

    @staticmethod
    def _render_starfield() -> pygame.Surface:
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill((4, 4, 14))
        rng = random.Random(42)
        for _ in range(400):
            x = rng.randint(0, SCREEN_WIDTH)
            y = rng.randint(0, SCREEN_HEIGHT)
            kind = rng.choices(['dim', 'mid', 'bright'], weights=[50, 35, 15])[0]
            if kind == 'dim':
                r, brightness = 1, rng.randint(100, 180)
            elif kind == 'mid':
                r, brightness = 1, rng.randint(180, 225)
            else:
                r, brightness = 2, rng.randint(230, 255)
            tint = rng.choice([(10, 10, 40), (0, 0, 0), (30, 20, 0)])
            col = tuple(min(255, brightness + t) for t in tint)
            if r == 1:
                surf.set_at((x, y), col)
            else:
                _aa_circle(surf, col, (x, y), r)
            if kind == 'bright':
                dim = tuple(c // 3 for c in col)
                pygame.draw.line(surf, dim, (x - 8, y), (x + 8, y), 1)
                pygame.draw.line(surf, dim, (x, y - 8), (x, y + 8), 1)
        return surf

    def update(self, dt: float) -> None:
        margin = 50
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
            if a.surf_cache is None:
                continue
            rotated = pygame.transform.rotate(a.surf_cache, math.degrees(-a.angle))
            rect = rotated.get_rect(center=(int(a.x), int(a.y)))
            surface.blit(rotated, rect)
