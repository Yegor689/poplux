import math
import os
import pygame
import pygame.gfxdraw
from settings import (
    BALL_COLORS, HOLE_COLOR, HUD_COLOR, BALL_RADIUS, LEVELS,
    SCREEN_WIDTH, SCREEN_HEIGHT, SETTINGS,
)

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ASSETS")
_FONT_ORBITRON  = os.path.join(_ASSETS, "Orbitron-VariableFont_wght.ttf")
_FONT_EXO2      = os.path.join(_ASSETS, "Exo2-VariableFont_wght.ttf")
_FONT_SYMBOLS   = os.path.join(_ASSETS, "NotoSansSymbols2-Regular.ttf")


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_large    = pygame.font.Font(_FONT_ORBITRON, 112)
        self.font_med      = pygame.font.Font(_FONT_EXO2, 58)
        self.font_small    = pygame.font.Font(_FONT_EXO2, 42)
        self.font_score    = pygame.font.Font(_FONT_ORBITRON, 76)
        self.font_icon_lg  = pygame.font.Font(_FONT_SYMBOLS, 72)
        self.font_icon_sm  = pygame.font.Font(_FONT_SYMBOLS, 44)
        # Score popup fonts scaled by cascade level (1=base, 5=largest)
        # Use Exo2 for full glyph coverage (Orbitron missing some punctuation)
        _popup_sizes = [76, 92, 108, 124, 140]
        self._popup_fonts = [pygame.font.Font(_FONT_EXO2, s) for s in _popup_sizes]
        self._palettes = self._build_palettes()
        # Cached surfaces — allocated once, cleared and reused each frame
        self._aim_line_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._overlay_surf  = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._vign_surf     = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._vign_base_alpha: "np.ndarray | None" = None  # baked once on first use

    @staticmethod
    def _build_palettes() -> dict:
        """Pre-compute colour palettes for each ball colour."""
        palettes = {}
        for name, color in BALL_COLORS.items():
            palettes[name] = (
                color,
                tuple(max(0,   c - 70) for c in color),
                tuple(min(255, c + 30) for c in color),
                tuple(min(255, c + 80) for c in color),
                tuple(max(0,   c - 55) for c in color),
            )
        # fallback for unknown colours
        fallback = (200, 200, 200)
        palettes[None] = (
            fallback,
            tuple(max(0,   c - 70) for c in fallback),
            tuple(min(255, c + 30) for c in fallback),
            tuple(min(255, c + 80) for c in fallback),
            tuple(max(0,   c - 55) for c in fallback),
        )
        return palettes

    @staticmethod
    def _aa_circle(surface: pygame.Surface, color: tuple, pos: tuple, radius: int) -> None:
        """Filled anti-aliased circle."""
        x, y, r = int(pos[0]), int(pos[1]), max(0, int(radius))
        pygame.gfxdraw.filled_circle(surface, x, y, r, color)
        pygame.gfxdraw.aacircle(surface, x, y, r, color)

    def draw_path(self, path) -> None:
        if len(path.waypoints) < 2:
            return
        pts = [(int(x), int(y)) for x, y in path.waypoints]
        color = (55, 55, 55)
        pygame.draw.lines(self.screen, color, False, pts, BALL_RADIUS * 2)
        for x, y in pts:
            self._aa_circle(self.screen, color, (x, y), BALL_RADIUS)

        # Black hole at the end
        hole_x, hole_y = path.waypoints[-1]
        hx, hy = int(hole_x), int(hole_y)
        t = pygame.time.get_ticks() / 1000.0

        # Outer gravitational rings — pulsing alpha via SRCALPHA surface
        for ring_r, base_alpha in ((BALL_RADIUS + 28, 35), (BALL_RADIUS + 18, 55), (BALL_RADIUS + 10, 80)):
            pulse = int(base_alpha + 20 * math.sin(t * 3.0 + ring_r * 0.1))
            sz = (ring_r + 2) * 2
            rs = pygame.Surface((sz, sz), pygame.SRCALPHA)
            pygame.gfxdraw.aacircle(rs, ring_r, ring_r, ring_r, (180, 60, 255, pulse))
            self.screen.blit(rs, (hx - ring_r, hy - ring_r))

        # Accretion disk — bright inner ring
        pygame.gfxdraw.aacircle(self.screen, hx, hy, BALL_RADIUS + 6, (220, 100, 255))
        pygame.gfxdraw.aacircle(self.screen, hx, hy, BALL_RADIUS + 5, (255, 140, 255))

        # Black hole core
        self._aa_circle(self.screen, (4, 0, 8),   (hx, hy), BALL_RADIUS + 4)
        self._aa_circle(self.screen, (0, 0, 0),   (hx, hy), BALL_RADIUS + 2)

    def _draw_ball(self, surface: pygame.Surface, color_name: str, cx: int, cy: int, radius: int,
                   spin_angle: float = 0.0, tangent: float = 0.0) -> None:
        palette = self._palettes.get(color_name) or self._palettes[None]
        color, dark, mid, light, seam = palette

        self._aa_circle(surface, dark,  (cx, cy), radius)                                             # dark rim
        self._aa_circle(surface, color, (cx, cy), int(radius * 0.88))                                 # base colour

        # Rolling-band effect: two bands 90° apart, each only drawn when
        # facing the viewer.  They wrap continuously around the ball,
        # giving a full-rotation illusion rather than an oscillation.
        r88 = int(radius * 0.88)
        t_cos, t_sin = math.cos(tangent), math.sin(tangent)
        p_cos, p_sin = -t_sin, t_cos
        for phase in (0, math.pi / 2):
            angle = spin_angle + phase
            facing = math.cos(angle)
            if facing < 0.05:
                continue
            band_offset = math.sin(angle) * r88 * 0.7
            chord_sq = r88 * r88 - band_offset * band_offset
            if chord_sq <= 0:
                continue
            chord_half = math.sqrt(chord_sq)
            bcx = cx + t_cos * band_offset
            bcy = cy + t_sin * band_offset
            x1 = int(bcx + p_cos * chord_half)
            y1 = int(bcy + p_sin * chord_half)
            x2 = int(bcx - p_cos * chord_half)
            y2 = int(bcy - p_sin * chord_half)
            w = max(1, int(facing * radius * 0.22))
            pygame.draw.line(surface, seam, (x1, y1), (x2, y2), w)

        self._aa_circle(surface, mid,   (cx, cy), int(radius * 0.62))                                 # inner glow
        self._aa_circle(surface, light, (cx - radius // 5, cy - radius // 5), int(radius * 0.38))    # soft sheen
        self._aa_circle(surface, (255, 255, 255),                                                      # specular dot
                        (cx - radius // 3, cy - radius // 3), max(2, radius // 4))
        pygame.gfxdraw.aacircle(surface, cx, cy, radius, (0, 0, 0))                                   # outline

        if SETTINGS.colorblind_mode and color_name in self._CB_SYMBOLS:
            self._draw_cb_symbol(surface, color_name, cx, cy, radius)

    # Colorblind symbols: one distinct shape per ball color
    _CB_SYMBOLS = {
        "red":    "circle",    # filled ring
        "green":  "triangle",  # upward triangle
        "blue":   "square",    # square
        "yellow": "diamond",   # diamond
    }

    def _draw_cb_symbol(self, surface: pygame.Surface, color_name: str, cx: int, cy: int, radius: int) -> None:
        symbol = self._CB_SYMBOLS.get(color_name)
        s = max(7, int(radius * 0.48))
        fill = (20, 20, 20)
        outline = (255, 255, 255)
        if symbol == "circle":
            # Filled dark ring with white border, hole in the middle
            self._aa_circle(surface, outline, (cx, cy), s)
            self._aa_circle(surface, fill,    (cx, cy), s - 3)
            self._aa_circle(surface, outline, (cx, cy), max(1, s - 6))
            self._aa_circle(surface, fill,    (cx, cy), max(1, s - 9))
        elif symbol == "triangle":
            pts = [(cx, cy - s), (cx - s, cy + s), (cx + s, cy + s)]
            pygame.gfxdraw.filled_polygon(surface, pts, fill)
            pygame.gfxdraw.aapolygon(surface, pts, outline)
        elif symbol == "square":
            r = pygame.Rect(cx - s, cy - s, s * 2, s * 2)
            pygame.draw.rect(surface, fill, r)
            pygame.draw.rect(surface, outline, r, 2)
        elif symbol == "diamond":
            pts = [(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)]
            pygame.gfxdraw.filled_polygon(surface, pts, fill)
            pygame.gfxdraw.aapolygon(surface, pts, outline)

    _AIM_LINE_DURATION = 12.0   # must match game.py

    def draw_aim_powerups(self, powerups: list) -> None:
        for p in powerups:
            cx, cy = int(p.x), int(p.y)
            alpha = p.alpha
            r = p.radius + int(math.sin(p.pulse) * 3)
            glow = 20
            size = (r + glow) * 2
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            sc = r + glow
            # Wide soft glow
            pygame.gfxdraw.filled_circle(surf, sc, sc, r + glow - 2, (0, 220, 255, alpha // 8))
            pygame.gfxdraw.filled_circle(surf, sc, sc, r + 12,       (0, 220, 255, alpha // 5))
            pygame.gfxdraw.filled_circle(surf, sc, sc, r + 6,        (0, 220, 255, alpha // 3))
            # Dark fill with cyan border
            pygame.gfxdraw.filled_circle(surf, sc, sc, r, (8, 18, 38, alpha))
            pygame.gfxdraw.aacircle(surf, sc, sc, r,     (0, 220, 255, alpha))
            pygame.gfxdraw.aacircle(surf, sc, sc, r - 2, (0, 180, 220, alpha // 2))
            # Crosshair lines (broken at centre), thicker
            gap = r // 3
            lc = (0, 230, 255, alpha)
            pygame.draw.line(surf, lc, (sc - r + 3, sc), (sc - gap, sc), 2)
            pygame.draw.line(surf, lc, (sc + gap, sc), (sc + r - 3, sc), 2)
            pygame.draw.line(surf, lc, (sc, sc - r + 3), (sc, sc - gap), 2)
            pygame.draw.line(surf, lc, (sc, sc + gap), (sc, sc + r - 3), 2)
            # Centre dot
            pygame.gfxdraw.filled_circle(surf, sc, sc, 4, (0, 255, 255, alpha))
            self.screen.blit(surf, (cx - sc, cy - sc))

    def draw_aim_line(self, frog, aim_timer: float, chain_positions: list | None = None) -> None:
        if aim_timer <= 0:
            return
        base_alpha = int(220 * min(aim_timer / 2.0, 1.0))  # fade in over 2 s
        mouth_dist = BALL_RADIUS * 4
        sx = frog.x + math.cos(frog.angle) * mouth_dist
        sy = frog.y + math.sin(frog.angle) * mouth_dist
        adx = math.cos(frog.angle)
        ady = math.sin(frog.angle)

        if chain_positions is None:
            chain_positions = []
        # Compute proximity factor: how close the frog is to the chain
        # Closer chain = brighter, thicker, more opaque line
        if chain_positions:
            fx, fy = frog.x, frog.y
            min_dist_sq = min((fx - cx) ** 2 + (fy - cy) ** 2 for cx, cy in chain_positions)
            min_dist = min_dist_sq ** 0.5
            # Fully bright within 200px, fades to 30% at 700px+
            prox = max(0.3, 1.0 - (min_dist - 200) / 500)
        else:
            prox = 0.5

        # Animate dots scrolling toward the target
        phase = (pygame.time.get_ticks() / 120) % 22
        line_surf = self._aim_line_surf
        line_surf.fill((0, 0, 0, 0))
        dot_r = max(2, int(3 + prox * 3))   # 2–6 px radius based on proximity
        t = phase
        while True:
            x = sx + adx * t
            y = sy + ady * t
            if not (0 <= x < SCREEN_WIDTH and 0 <= y < SCREEN_HEIGHT):
                break
            # Distance fade along the line, boosted by proximity
            fade = max(0.2, prox * (1.0 - t / 800))
            dot_alpha = int(base_alpha * fade)
            if dot_alpha > 5:
                pygame.gfxdraw.filled_circle(line_surf, int(x), int(y), dot_r,
                                             (120, 220, 255, dot_alpha))
                # Bright core
                pygame.gfxdraw.filled_circle(line_surf, int(x), int(y), max(1, dot_r - 2),
                                             (255, 255, 255, min(255, dot_alpha + 60)))
            t += 22
        self.screen.blit(line_surf, (0, 0))

    def draw_coins(self, coins: list) -> None:
        for coin in coins:
            cx, cy = int(coin.x), int(coin.y)
            r = max(8, int(coin.radius + math.sin(coin.pulse) * 3))
            alpha = coin.alpha
            glow = 18
            size = (r + glow) * 2
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            sc = r + glow
            # Wide soft glow
            pygame.gfxdraw.filled_circle(surf, sc, sc, r + glow - 2, (255, 200, 0, alpha // 8))
            pygame.gfxdraw.filled_circle(surf, sc, sc, r + 10,       (255, 215, 0, alpha // 5))
            pygame.gfxdraw.filled_circle(surf, sc, sc, r + 5,        (255, 215, 0, alpha // 3))
            pygame.gfxdraw.filled_circle(surf, sc, sc, r,            (255, 215, 0, alpha))
            pygame.gfxdraw.aacircle(surf, sc, sc, r,                 (180, 140, 0, alpha))
            # Highlight
            pygame.gfxdraw.filled_circle(surf, sc - r // 4, sc - r // 4, r // 3,
                                         (255, 245, 140, alpha))
            self.screen.blit(surf, (cx - sc, cy - sc))

    _RAINBOW_BANDS = [
        (255, 60,  60),   # red
        (255, 165,  0),   # orange
        (255, 230,  0),   # yellow
        (60,  210, 60),   # green
        (60,  130, 255),  # blue
        (180,  60, 255),  # violet
    ]

    def _draw_rainbow_ball(self, surface: pygame.Surface, cx: int, cy: int, radius: int) -> None:
        bands = self._RAINBOW_BANDS
        step = max(1, radius // len(bands))
        for i, color in enumerate(reversed(bands)):
            r = radius - i * step
            if r > 0:
                self._aa_circle(surface, color, (cx, cy), r)
        # white specular
        self._aa_circle(surface, (255, 255, 255),
                        (cx - radius // 3, cy - radius // 3), max(2, radius // 4))
        pygame.gfxdraw.aacircle(surface, cx, cy, radius, (255, 255, 255))

    def _draw_bomb_ball(self, surface: pygame.Surface, cx: int, cy: int, radius: int) -> None:
        self._aa_circle(surface, (255, 90, 0),   (cx, cy), radius + 3)          # orange glow halo
        self._aa_circle(surface, (18, 18, 18),   (cx, cy), radius)              # near-black body
        self._aa_circle(surface, (70, 35, 0),    (cx, cy), int(radius * 0.72))  # dark amber mid
        self._aa_circle(surface, (255, 130, 0),  (cx, cy), int(radius * 0.44))  # bright core
        self._aa_circle(surface, (255, 230, 120),(cx, cy), int(radius * 0.22))  # white-hot centre
        pygame.gfxdraw.aacircle(surface, cx, cy, radius, (255, 60, 0))          # orange rim
        r2 = max(2, radius // 3)
        pygame.draw.line(surface, (255, 200, 0), (cx - r2, cy), (cx + r2, cy), 2)
        pygame.draw.line(surface, (255, 200, 0), (cx, cy - r2), (cx, cy + r2), 2)

    def draw_chain(self, chain, path) -> None:
        t_pulse = pygame.time.get_ticks() / 1000.0
        for ball in chain.balls:
            cx, cy = path.point_at(ball.path_distance + ball.path_offset)
            if ball.entry_t < 1.0:
                # ease-out: decelerate into the chain position
                t = 1.0 - (1.0 - ball.entry_t) ** 2
                cx = ball.entry_x + (cx - ball.entry_x) * t
                cy = ball.entry_y + (cy - ball.entry_y) * t
            tangent = path.direction_at(ball.path_distance)
            spin = ball.path_distance / ball.radius
            if ball.is_bonus:
                ring_r = ball.radius + 5 + int(math.sin(t_pulse * 5) * 2)
                brightness = int(abs(math.sin(t_pulse * 4)) * 80 + 175)
                pygame.gfxdraw.aacircle(self.screen, int(cx), int(cy), ring_r,
                                        (brightness, brightness, 255))
                pygame.gfxdraw.aacircle(self.screen, int(cx), int(cy), ring_r + 2,
                                        (brightness, brightness, 255, 80))
            self._draw_ball(self.screen, ball.color, int(cx), int(cy), ball.radius,
                            spin, tangent)

    def draw_particles(self, particles: list) -> None:
        for p in particles:
            r = max(1, int(p.radius * p.t))
            self._aa_circle(self.screen, p.color, (int(p.x), int(p.y)), r)

    def draw_score_popups(self, popups: list) -> None:
        for p in popups:
            font = self._popup_fonts[min(p.cascade_level - 1, len(self._popup_fonts) - 1)]
            # antialias=False uses colorkey transparency — no opaque black tofu rects
            surf = font.render(p.text, False, p.color)
            surf.set_colorkey((0, 0, 0))
            surf.set_alpha(p.alpha)
            self.screen.blit(surf, surf.get_rect(center=(int(p.x), int(p.y))))

    def draw_fired_balls(self, fired_balls: list) -> None:
        for ball in fired_balls:
            if ball.active:
                if ball.is_bomb:
                    self._draw_bomb_ball(self.screen, int(ball.x), int(ball.y), ball.radius)
                elif ball.is_rainbow:
                    self._draw_rainbow_ball(self.screen, int(ball.x), int(ball.y), ball.radius)
                else:
                    self._draw_ball(self.screen, ball.color, int(ball.x), int(ball.y), ball.radius)

    def draw_frog(self, frog) -> None:
        cx = int(frog.x - math.cos(frog.angle) * frog.recoil)
        cy = int(frog.y - math.sin(frog.angle) * frog.recoil)
        angle = frog.angle
        R = BALL_RADIUS

        fc, fs = math.cos(angle), math.sin(angle)
        pc, ps = -math.sin(angle), math.cos(angle)

        def pt(fwd, perp):
            return (int(cx + fc * fwd + pc * perp),
                    int(cy + fs * fwd + ps * perp))

        HULL  = (32, 36, 44)    # dark gunmetal
        PANEL = (44, 50, 62)    # lighter panel
        SPINE = (58, 66, 82)    # spine highlight
        AMBER = (220, 155, 25)  # amber accent
        AMBER2= (140,  95, 10)  # dark amber
        EDGE  = (80,  92, 115)  # hull edge aa

        # --- Engine glow ---
        for perp_off in (-R * 0.42, R * 0.42):
            ex, ey = pt(-R * 1.1, perp_off)
            self._aa_circle(self.screen, (255,  70,   5), (ex, ey), int(R * 0.62))
            self._aa_circle(self.screen, (255, 170,  40), (ex, ey), int(R * 0.38))
            self._aa_circle(self.screen, (255, 240, 180), (ex, ey), int(R * 0.18))

        # --- Swept wings (two-part: inner strake + outer panel) ---
        for sign in (-1, 1):
            strake = [pt(R * 0.5,  sign * R * 0.5),
                      pt(-R * 0.2, sign * R * 0.9),
                      pt(-R * 1.0, sign * R * 0.48)]
            outer  = [pt(R * 0.1,  sign * R * 0.85),
                      pt(-R * 0.4, sign * R * 1.7),
                      pt(-R * 1.0, sign * R * 0.85),
                      pt(-R * 0.2, sign * R * 0.9)]
            pygame.draw.polygon(self.screen, PANEL,  strake)
            pygame.draw.polygon(self.screen, HULL,   outer)
            pygame.gfxdraw.aapolygon(self.screen, strake, EDGE)
            pygame.gfxdraw.aapolygon(self.screen, outer,  EDGE)
            # amber leading-edge trim
            pygame.draw.aaline(self.screen, AMBER,
                               pt(R * 0.5, sign * R * 0.5),
                               pt(-R * 0.35, sign * R * 1.62))
            # panel rib
            pygame.draw.aaline(self.screen, AMBER2,
                               pt(R * 0.0, sign * R * 0.72),
                               pt(-R * 0.85, sign * R * 0.65))

        # --- Rounded hull body ---
        self._aa_circle(self.screen, HULL,  pt( R * 0.65, 0), int(R * 0.92))
        self._aa_circle(self.screen, PANEL, pt( 0,         0), int(R * 1.06))
        self._aa_circle(self.screen, HULL,  pt(-R * 0.65, 0), int(R * 0.86))
        pygame.gfxdraw.aacircle(self.screen, *pt(0, 0), int(R * 1.06), EDGE)

        # Spine stripe
        spine_pts = [pt(R * 1.6,  R * 0.1), pt(-R * 0.8,  R * 0.1),
                     pt(-R * 0.8, -R * 0.1), pt(R * 1.6,  -R * 0.1)]
        pygame.draw.polygon(self.screen, SPINE, spine_pts)

        # Hull panel seam lines
        pygame.draw.aaline(self.screen, AMBER2, pt(R * 0.3,  R * 0.85), pt(-R * 0.55, R * 0.70))
        pygame.draw.aaline(self.screen, AMBER2, pt(R * 0.3, -R * 0.85), pt(-R * 0.55, -R * 0.70))

        # --- Nose cone ---
        self._aa_circle(self.screen, SPINE,           pt(R * 1.5, 0), int(R * 0.42))
        self._aa_circle(self.screen, (100, 115, 145), pt(R * 1.82, 0), int(R * 0.20))
        # amber nose ring
        pygame.gfxdraw.aacircle(self.screen, *pt(R * 1.5, 0), int(R * 0.42), AMBER)

        # --- Cannon barrel ---
        barrel = [pt(R * 1.22,  R * 0.13), pt(R * 2.5,  R * 0.09),
                  pt(R * 2.5,  -R * 0.09), pt(R * 1.22, -R * 0.13)]
        pygame.draw.polygon(self.screen, PANEL, barrel)
        pygame.gfxdraw.aapolygon(self.screen, barrel, AMBER)

        # --- Visor (flat viewport slit, NOT ball-shaped) ---
        visor = [pt(R * 0.9,  R * 0.28), pt(R * 0.3,  R * 0.28),
                 pt(R * 0.3, -R * 0.28), pt(R * 0.9, -R * 0.28)]
        pygame.draw.polygon(self.screen, (8, 12, 22), visor)
        # amber visor frame
        pygame.gfxdraw.aapolygon(self.screen, visor, AMBER)
        # cyan scan-line inside
        pygame.draw.aaline(self.screen, (0, 200, 230),
                           pt(R * 0.85, R * 0.05), pt(R * 0.35, R * 0.05))

        # --- Amber hull accent rings ---
        pygame.gfxdraw.aacircle(self.screen, *pt(-R * 0.3, 0), int(R * 0.3), AMBER2)

        # --- Magazine bay — next ball recessed in hull ---
        bx, by = pt(-R * 0.65, 0)
        self._aa_circle(self.screen, (12, 14, 20), (bx, by), int(BALL_RADIUS * 0.75))
        pygame.gfxdraw.aacircle(self.screen, bx, by, int(BALL_RADIUS * 0.75), AMBER2)
        if frog.next_ball.is_bomb:
            self._draw_bomb_ball(self.screen, bx, by, int(BALL_RADIUS * 0.58))
        elif frog.next_ball.is_rainbow:
            self._draw_rainbow_ball(self.screen, bx, by, int(BALL_RADIUS * 0.58))
        else:
            self._draw_ball(self.screen, frog.next_ball.color, bx, by, int(BALL_RADIUS * 0.58))

        # --- Current ball at cannon tip ---
        mx, my = pt(R * 2.5 + BALL_RADIUS + 3, 0)
        if frog.current_ball.is_bomb:
            self._draw_bomb_ball(self.screen, mx, my, frog.current_ball.radius)
        elif frog.current_ball.is_rainbow:
            self._draw_rainbow_ball(self.screen, mx, my, frog.current_ball.radius)
        else:
            self._draw_ball(self.screen, frog.current_ball.color, mx, my, frog.current_ball.radius)

    _SLOWDOWN_DURATION = 15.0   # must match game.py
    _DANGER_START = 0.82        # fraction of path at which danger begins
    _DANGER_PEAK  = 0.96        # fraction at which vignette is at full intensity

    def draw_hud(self, remaining: int, spawned: int, total: int, elapsed_time: float = 0.0, score: int = 0, aim_timer: float = 0.0, slowdown_timer: float = 0.0, danger_frac: float = 0.0, fps: float = 0.0) -> None:
        # --- Danger vignette — red screen-edge pulse when chain is close to hole ---
        if danger_frac > self._DANGER_START:
            import numpy as np
            t = pygame.time.get_ticks() / 1000.0
            raw = (danger_frac - self._DANGER_START) / (self._DANGER_PEAK - self._DANGER_START)
            intensity = min(1.0, raw)
            pulse_speed = 2.0 + intensity * 4.0
            pulse = 0.55 + 0.45 * math.sin(t * pulse_speed * math.pi)
            max_alpha = int(intensity * pulse * 160)
            if max_alpha > 4:
                # Bake the normalised gradient shape once (values 0–255 at full intensity).
                # Every frame we just scale the pre-baked alpha by max_alpha/255.
                if self._vign_base_alpha is None:
                    ys, xs = np.mgrid[0:SCREEN_HEIGHT, 0:SCREEN_WIDTH]
                    dist_x = np.minimum(xs, SCREEN_WIDTH  - 1 - xs).astype(np.float32)
                    dist_y = np.minimum(ys, SCREEN_HEIGHT - 1 - ys).astype(np.float32)
                    dist   = np.minimum(dist_x, dist_y)
                    fade_px = SCREEN_HEIGHT * 0.22
                    base = np.clip(1.0 - dist / fade_px, 0.0, 1.0) ** 1.8
                    self._vign_base_alpha = (base * 255).astype(np.uint8)  # shape (H, W)
                    # Pre-fill the RGB channels once — they never change
                    rgb = pygame.surfarray.pixels3d(self._vign_surf)
                    rgb[:, :, 0] = 220
                    rgb[:, :, 1] = 30
                    rgb[:, :, 2] = 30
                    del rgb

                # Scale the baked gradient by current max_alpha (cheap per-frame op)
                alpha_arr = (self._vign_base_alpha * (max_alpha / 255.0)).astype(np.uint8)
                pix = pygame.surfarray.pixels_alpha(self._vign_surf)
                pix[:] = alpha_arr.T
                del pix
                self.screen.blit(self._vign_surf, (0, 0))

        # --- Score — top-left, prominent ---
        label_surf = self.font_small.render("SCORE", True, (180, 180, 100))
        value_surf = self.font_score.render(f"{score:,}", True, (255, 240, 80))
        pad_x, pad_y = 23, 16
        box_w = max(label_surf.get_width(), value_surf.get_width()) + pad_x * 2
        box_h = label_surf.get_height() + value_surf.get_height() + pad_y * 2 + 4
        box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(box_surf, (0, 0, 0, 140), box_surf.get_rect(), border_radius=10)
        pygame.draw.rect(box_surf, (180, 160, 40, 80), box_surf.get_rect(), width=1, border_radius=10)
        self.screen.blit(box_surf, (23, 23))
        self.screen.blit(label_surf, label_surf.get_rect(centerx=23 + box_w // 2, top=23 + pad_y))
        self.screen.blit(value_surf, value_surf.get_rect(centerx=23 + box_w // 2, top=23 + pad_y + label_surf.get_height() + 4))

        # --- Timer — top-center ---
        mins = int(elapsed_time) // 60
        secs = int(elapsed_time) % 60
        timer_text = self.font_med.render(f"{mins}:{secs:02d}", True, HUD_COLOR)
        self.screen.blit(timer_text, timer_text.get_rect(center=(SCREEN_WIDTH // 2, 48)))

        # --- Slowdown indicator — bottom-right when active ---
        if slowdown_timer > 0:
            bar_h = 29
            by = SCREEN_HEIGHT - bar_h - 14
            secs_left = math.ceil(slowdown_timer)
            label = self.font_small.render(f"SLOWDOWN  {secs_left}s", True, (80, 180, 255))
            bar_w = max(220, label.get_width())
            right_edge = SCREEN_WIDTH - 14
            if aim_timer > 0:
                right_edge -= max(220, self.font_small.size(f"AIM LINE  {math.ceil(aim_timer)}s")[0]) + 18
            bx = right_edge - bar_w
            fill_w = int(bar_w * slowdown_timer / self._SLOWDOWN_DURATION)
            backing = pygame.Surface((bar_w + 8, bar_h + 35), pygame.SRCALPHA)
            pygame.draw.rect(backing, (0, 0, 0, 140), backing.get_rect(), border_radius=6)
            self.screen.blit(backing, (bx - 4, by - 18))
            self.screen.blit(label, label.get_rect(centerx=bx + bar_w // 2, bottom=by - 1))
            pygame.draw.rect(self.screen, (10, 20, 50), (bx, by, bar_w, bar_h), border_radius=4)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (60, 140, 255), (bx, by, fill_w, bar_h), border_radius=4)
            pygame.draw.rect(self.screen, (40, 100, 200), (bx, by, bar_w, bar_h), 1, border_radius=4)

        # --- Aim line indicator — bottom-right when active ---
        if aim_timer > 0:
            bar_h = 29
            by = SCREEN_HEIGHT - bar_h - 14
            secs_left = math.ceil(aim_timer)
            label = self.font_small.render(f"AIM LINE  {secs_left}s", True, (0, 220, 255))
            bar_w = max(220, label.get_width())
            bx = SCREEN_WIDTH - 14 - bar_w
            fill_w = int(bar_w * aim_timer / self._AIM_LINE_DURATION)
            backing = pygame.Surface((bar_w + 8, bar_h + 35), pygame.SRCALPHA)
            pygame.draw.rect(backing, (0, 0, 0, 140), backing.get_rect(), border_radius=6)
            self.screen.blit(backing, (bx - 4, by - 18))
            self.screen.blit(label, label.get_rect(centerx=bx + bar_w // 2, bottom=by - 1))
            pygame.draw.rect(self.screen, (20, 40, 60), (bx, by, bar_w, bar_h), border_radius=4)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (0, 200, 255), (bx, by, fill_w, bar_h), border_radius=4)
            pygame.draw.rect(self.screen, (0, 150, 200), (bx, by, bar_w, bar_h), 1, border_radius=4)

        # --- FPS counter — top-right corner ---
        if SETTINGS.show_fps:
            fps_surf = self.font_small.render(f"{int(fps)} FPS", True, (100, 100, 100))
            self.screen.blit(fps_surf, fps_surf.get_rect(topright=(SCREEN_WIDTH - 23, 23)))

        # --- Balls remaining — top-right ---
        to_go = max(0, total - spawned) + remaining
        if total < 999_999:  # don't show in endless/combo-test
            balls_label = self.font_small.render("BALLS LEFT", True, (140, 140, 160))
            balls_value = self.font_score.render(str(to_go), True, HUD_COLOR)
            pad_x, pad_y = 23, 16
            box_w = max(balls_label.get_width(), balls_value.get_width()) + pad_x * 2
            box_h = balls_label.get_height() + balls_value.get_height() + pad_y * 2 + 4
            bx = SCREEN_WIDTH - 23 - box_w
            fps_offset = (self.font_small.get_height() + 8) if SETTINGS.show_fps else 0
            by = 23 + fps_offset
            box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            pygame.draw.rect(box_surf, (0, 0, 0, 140), box_surf.get_rect(), border_radius=10)
            pygame.draw.rect(box_surf, (80, 80, 120, 80), box_surf.get_rect(), width=1, border_radius=10)
            self.screen.blit(box_surf, (bx, by))
            self.screen.blit(balls_label, balls_label.get_rect(centerx=bx + box_w // 2, top=by + pad_y))
            self.screen.blit(balls_value, balls_value.get_rect(centerx=bx + box_w // 2, top=by + pad_y + balls_label.get_height() + 4))

    def _lose_button_rects(self) -> list:
        """Retry and Main Menu button rects — must match draw_lose geometry."""
        GAP_S, GAP_L = 18, 36
        btn_w, btn_h = 340, 78
        btns_w = btn_w * 2 + GAP_L
        # Approximate total_h (same calc as draw_lose, using font metrics)
        stats_h = max(
            self.font_small.get_height() + GAP_S + self.font_score.get_height(),
            self.font_small.get_height() + GAP_S + self.font_score.get_height(),
        )
        total_h = (self.font_large.get_height() + GAP_L
                   + self.font_med.get_height()   + GAP_L
                   + 1 + GAP_L + stats_h + GAP_L
                   + 1 + GAP_L + btn_h + GAP_S
                   + self.font_small.get_height())
        cx = SCREEN_WIDTH // 2
        btn_y = (SCREEN_HEIGHT // 2 - total_h // 2
                 + self.font_large.get_height() + GAP_L
                 + self.font_med.get_height()   + GAP_L
                 + 1 + GAP_L + stats_h + GAP_L + 1 + GAP_L)
        return [
            pygame.Rect(cx - btns_w // 2, btn_y, btn_w, btn_h),
            pygame.Rect(cx - btns_w // 2 + btn_w + GAP_L, btn_y, btn_w, btn_h),
        ]

    def lose_button_at(self, pos) -> "int | None":
        for i, rect in enumerate(self._lose_button_rects()):
            if rect.collidepoint(pos):
                return i
        return None

    def draw_lose(self, mouse_pos, score: int, elapsed_time: float,
                  is_endless: bool = False, overlay_alpha: int = 200) -> None:
        overlay = self._overlay_surf
        overlay.fill((0, 0, 0, min(overlay_alpha, 200)))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        GAP_S = 18
        GAP_L = 36
        DIV_W = 480

        title_surf = self.font_large.render("GAME OVER", True, (220, 60, 60))
        sub_text   = "Endless run ended" if is_endless else "The chain reached the hole"
        sub_surf   = self.font_med.render(sub_text, True, (180, 120, 120))

        mins, secs = int(elapsed_time) // 60, int(elapsed_time) % 60
        score_label = self.font_small.render("SCORE",    True, (150, 150, 150))
        score_value = self.font_score.render(f"{score:,}", True, (220, 80, 80))
        time_label  = self.font_small.render("TIME",     True, (150, 150, 150))
        time_value  = self.font_score.render(f"{mins}:{secs:02d}", True, (200, 160, 160))

        btn_w, btn_h = 340, 78
        retry_txt = self.font_med.render("RETRY", True, HUD_COLOR)
        menu_txt  = self.font_med.render("MAIN MENU", True, HUD_COLOR)
        hint_surf = self.font_small.render("R to retry", True, (90, 90, 90))

        stats_h = max(score_label.get_height() + GAP_S + score_value.get_height(),
                      time_label.get_height()  + GAP_S + time_value.get_height())
        btns_w  = btn_w * 2 + GAP_L
        total_h = (title_surf.get_height() + GAP_L
                   + sub_surf.get_height()  + GAP_L
                   + 1 + GAP_L
                   + stats_h               + GAP_L
                   + 1 + GAP_L
                   + btn_h                 + GAP_S
                   + hint_surf.get_height())
        y = SCREEN_HEIGHT // 2 - total_h // 2

        self.screen.blit(title_surf, title_surf.get_rect(centerx=cx, top=y))
        y += title_surf.get_height() + GAP_L

        self.screen.blit(sub_surf, sub_surf.get_rect(centerx=cx, top=y))
        y += sub_surf.get_height() + GAP_L

        pygame.draw.line(self.screen, (80, 40, 40), (cx - DIV_W // 2, y), (cx + DIV_W // 2, y), 1)
        y += 1 + GAP_L

        col_x = DIV_W // 4
        for label, value, color_x in (
            (score_label, score_value, cx - col_x),
            (time_label,  time_value,  cx + col_x),
        ):
            self.screen.blit(label, label.get_rect(centerx=color_x, top=y))
            self.screen.blit(value, value.get_rect(centerx=color_x, top=y + label.get_height() + GAP_S))
        y += stats_h + GAP_L

        pygame.draw.line(self.screen, (80, 40, 40), (cx - DIV_W // 2, y), (cx + DIV_W // 2, y), 1)
        y += 1 + GAP_L

        # Two buttons side by side
        retry_rect = pygame.Rect(cx - btns_w // 2, y, btn_w, btn_h)
        menu_rect  = pygame.Rect(cx - btns_w // 2 + btn_w + GAP_L, y, btn_w, btn_h)
        for rect, txt, hcol, col in (
            (retry_rect, retry_txt, (130, 40, 40), (90, 25, 25)),
            (menu_rect,  menu_txt,  (55, 55, 75),  (35, 35, 52)),
        ):
            hovered = rect.collidepoint(mouse_pos)
            pygame.draw.rect(self.screen, hcol if hovered else col, rect, border_radius=10)
            pygame.draw.rect(self.screen, (200, 100, 100) if hovered else (130, 70, 70),
                             rect, 2, border_radius=10)
            self.screen.blit(txt, txt.get_rect(center=rect.center))
        y += btn_h + GAP_S

        self.screen.blit(hint_surf, hint_surf.get_rect(centerx=cx, top=y))

    def draw_overlay(self, title: str, subtitle: str = "") -> None:
        overlay = self._overlay_surf
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        t = self.font_large.render(title, True, HUD_COLOR)
        self.screen.blit(t, t.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 64)))
        if subtitle:
            s = self.font_med.render(subtitle, True, HUD_COLOR)
            self.screen.blit(s, s.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 48)))

    # ------------------------------------------------------------------ #
    # Level-select screen                                                  #
    # ------------------------------------------------------------------ #

    # Left panel: scrollable level list
    _LS_LIST_X     = 80
    _LS_LIST_W     = 560
    _LS_LIST_TOP   = 170
    _LS_ROW_H      = 130
    _LS_ROW_GAP    = 8
    # Right panel: detail area
    _LS_DETAIL_X   = 720
    _LS_DETAIL_W   = SCREEN_WIDTH - 720 - 80
    # Play / Endless buttons
    _LS_BTN_W      = 260
    _LS_BTN_H      = 90
    _LS_BTN_GAP    = 20

    def _ls_row_rects(self, scroll: int = 0) -> list[pygame.Rect]:
        rects = []
        y = self._LS_LIST_TOP - scroll
        for _ in LEVELS:
            rects.append(pygame.Rect(self._LS_LIST_X, y, self._LS_LIST_W, self._LS_ROW_H))
            y += self._LS_ROW_H + self._LS_ROW_GAP
        return rects

    def _ls_play_rect(self) -> pygame.Rect:
        cx = self._LS_DETAIL_X + self._LS_DETAIL_W // 2
        total = self._LS_BTN_W * 2 + self._LS_BTN_GAP
        left = cx - total // 2
        return pygame.Rect(left, SCREEN_HEIGHT - self._LS_BTN_H - 60,
                           self._LS_BTN_W, self._LS_BTN_H)

    def _ls_endless_rect(self) -> pygame.Rect:
        cx = self._LS_DETAIL_X + self._LS_DETAIL_W // 2
        total = self._LS_BTN_W * 2 + self._LS_BTN_GAP
        left = cx - total // 2
        return pygame.Rect(left + self._LS_BTN_W + self._LS_BTN_GAP,
                           SCREEN_HEIGHT - self._LS_BTN_H - 60,
                           self._LS_BTN_W, self._LS_BTN_H)

    def level_select_interact(self, pos, selected_idx: int, scroll: int = 0) -> "int | str | None":
        """Returns level index if a list row clicked, 'play'/'endless' if buttons clicked."""
        if self._ls_play_rect().collidepoint(pos):
            return "play"
        if self._ls_endless_rect().collidepoint(pos):
            return "endless"
        for i, rect in enumerate(self._ls_row_rects(scroll)):
            if rect.collidepoint(pos):
                return i
        return None

    def draw_level_select(self, mouse_pos, selected_idx: int = 0,
                          best_scores: dict | None = None, scroll: int = 0,
                          max_unlocked: int = 0, all_unlocked: bool = False) -> None:
        title = self.font_large.render("SELECT LEVEL", True, HUD_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 96)))

        # Divider between panels
        pygame.draw.line(self.screen, (60, 60, 80),
                         (self._LS_DETAIL_X - 30, self._LS_LIST_TOP),
                         (self._LS_DETAIL_X - 30, SCREEN_HEIGHT - 40), 1)

        # --- Left panel: level list ---
        list_clip = pygame.Rect(self._LS_LIST_X, self._LS_LIST_TOP,
                                self._LS_LIST_W, SCREEN_HEIGHT - self._LS_LIST_TOP - 20)
        self.screen.set_clip(list_clip)
        for i, (rect, cfg) in enumerate(zip(self._ls_row_rects(scroll), LEVELS)):
            locked   = i > max_unlocked
            selected = i == selected_idx
            hovered  = rect.collidepoint(mouse_pos) and not locked

            if locked:
                fill   = (22, 22, 30)
                border = (40, 40, 55)
            elif selected:
                fill   = (50, 60, 90)
                border = (140, 160, 255)
            elif hovered:
                fill   = (45, 45, 65)
                border = (100, 100, 150)
            else:
                fill   = (30, 30, 44)
                border = (55, 55, 75)

            pygame.draw.rect(self.screen, fill,   rect, border_radius=8)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=8)

            # Level number badge
            num_col = (60, 60, 80) if locked else ((140, 160, 255) if selected else (80, 80, 110))
            num_surf = self.font_med.render(f"{i + 1:02d}", True, num_col)
            self.screen.blit(num_surf, num_surf.get_rect(midleft=(rect.x + 16, rect.centery)))

            if locked:
                # Lock icon + "LOCKED" text
                lock_surf = self.font_small.render("LOCKED", True, (55, 55, 70))
                self.screen.blit(lock_surf, lock_surf.get_rect(midleft=(rect.x + 90, rect.centery)))
            else:
                # Best score on the right
                best = (best_scores or {}).get(cfg["name"])
                score_x = rect.right - 16
                if best:
                    sc_surf = self.font_small.render(f"{best['score']:,}", True, (220, 190, 50))
                    self.screen.blit(sc_surf, sc_surf.get_rect(midright=(score_x, rect.centery)))
                    score_x = rect.right - sc_surf.get_width() - 24

                text_right = score_x - 12
                text_x = rect.x + 90
                max_text_w = text_right - text_x

                name_surf = self.font_med.render(cfg["name"], True, HUD_COLOR)
                self.screen.blit(name_surf, name_surf.get_rect(
                    midleft=(text_x, rect.centery - name_surf.get_height() // 2 - 1)))
                sub = cfg.get("subtitle", "")
                if sub:
                    sub_surf = self.font_small.render(sub, True, (130, 130, 150))
                    if sub_surf.get_width() > max_text_w:
                        sub_surf = pygame.transform.smoothscale(sub_surf, (max_text_w, sub_surf.get_height()))
                    self.screen.blit(sub_surf, sub_surf.get_rect(
                        midleft=(text_x, rect.centery + name_surf.get_height() // 2 + 1)))

        self.screen.set_clip(None)

        # --- Right panel: selected level detail ---
        cfg    = LEVELS[selected_idx]
        locked = selected_idx > max_unlocked
        best   = (best_scores or {}).get(cfg["name"])
        dx     = self._LS_DETAIL_X
        dw     = self._LS_DETAIL_W
        dcx    = dx + dw // 2

        name_col  = (90, 90, 110) if locked else HUD_COLOR
        name_surf = self.font_large.render(cfg["name"], True, name_col)
        self.screen.blit(name_surf, name_surf.get_rect(center=(dcx, 220)))

        sub = cfg.get("subtitle", "")
        if sub and not locked:
            sub_surf = self.font_med.render(sub, True, (160, 160, 180))
            max_w = dw - 40
            if sub_surf.get_width() > max_w:
                sub_surf = pygame.transform.smoothscale(sub_surf, (max_w, sub_surf.get_height()))
            self.screen.blit(sub_surf, sub_surf.get_rect(center=(dcx, 300)))

        pygame.draw.line(self.screen, (60, 60, 80), (dx + 20, 340), (dx + dw - 20, 340), 1)

        if locked:
            lock_big = self.font_large.render("LOCKED", True, (60, 60, 80))
            self.screen.blit(lock_big, lock_big.get_rect(center=(dcx, 500)))
            hint2 = self.font_small.render("Complete the previous level to unlock", True, (70, 70, 90))
            self.screen.blit(hint2, hint2.get_rect(center=(dcx, 580)))
        else:
            stats = [
                ("BALLS",  f"{cfg['total_balls']}",           (160, 200, 160)),
                ("SPEED",  f"{int(cfg['chain_speed'])} px/s", (180, 150, 210)),
            ]
            sy = 380
            for label, value, col in stats:
                lbl = self.font_small.render(label, True, (100, 100, 120))
                val = self.font_med.render(value, True, col)
                self.screen.blit(lbl, lbl.get_rect(center=(dcx, sy)))
                self.screen.blit(val, val.get_rect(center=(dcx, sy + lbl.get_height() + 4)))
                sy += lbl.get_height() + val.get_height() + 24

            pygame.draw.line(self.screen, (60, 60, 80), (dx + 20, sy), (dx + dw - 20, sy), 1)
            sy += 20

            if best:
                mins, secs = divmod(int(best["time"]), 60)
                rec_label = self.font_small.render("BEST RUN", True, (100, 100, 120))
                rec_score = self.font_med.render(f"{best['score']:,}", True, (255, 215, 50))
                rec_time  = self.font_small.render(f"{mins}:{secs:02d}", True, (180, 200, 180))
                self.screen.blit(rec_label, rec_label.get_rect(center=(dcx, sy)))
                self.screen.blit(rec_score, rec_score.get_rect(center=(dcx, sy + rec_label.get_height() + 4)))
                self.screen.blit(rec_time,  rec_time.get_rect(center=(dcx, sy + rec_label.get_height() + rec_score.get_height() + 8)))
            else:
                no_surf = self.font_small.render("No record yet", True, (80, 80, 100))
                self.screen.blit(no_surf, no_surf.get_rect(center=(dcx, sy + 20)))

            # Play button
            play_rect = self._ls_play_rect()
            hovered   = play_rect.collidepoint(mouse_pos)
            pygame.draw.rect(self.screen, (40, 110, 40) if hovered else (25, 75, 25),
                             play_rect, border_radius=10)
            pygame.draw.rect(self.screen, (100, 230, 100) if hovered else (60, 170, 60),
                             play_rect, 2, border_radius=10)
            play_txt = self.font_med.render("PLAY", True, HUD_COLOR)
            self.screen.blit(play_txt, play_txt.get_rect(center=play_rect.center))

            # Endless button
            end_rect = self._ls_endless_rect()
            end_hov  = end_rect.collidepoint(mouse_pos)
            pygame.draw.rect(self.screen, (80, 40, 110) if end_hov else (50, 25, 75),
                             end_rect, border_radius=10)
            pygame.draw.rect(self.screen, (200, 100, 255) if end_hov else (130, 60, 180),
                             end_rect, 2, border_radius=10)
            end_txt = self.font_med.render("ENDLESS", True, HUD_COLOR)
            self.screen.blit(end_txt, end_txt.get_rect(center=end_rect.center))

        dbg = "  ·  F9: unlock all [ON]" if all_unlocked else "  ·  F9: unlock all"
        hint = self.font_small.render(
            f"up/down or click to select  ·  Enter to play  ·  ESC back{dbg}",
            True, (90, 90, 100))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18)))

    # ------------------------------------------------------------------ #
    # Main menu                                                            #
    # ------------------------------------------------------------------ #

    _MENU_BTN_W      = 700
    _MENU_BTN_H      = 90
    _MENU_BTN_H_PLAY = 130
    _MENU_BTN_GAP    = 36
    # (label, icon, fill, fill_hover, border, border_hover)
    _MENU_BTNS = [
        ("PLAY",         "▶",  (20,  65,  20),  (35,  95,  35),  (80,  210, 80),  (120, 245, 120)),
        ("SELECT LEVEL", "▦",  (18,  38,  75),  (28,  58,  110), (60,  130, 220), (90,  170, 255)),
        ("RECORDS",      "◈",  (70,  60,  10),  (100, 85,  15),  (210, 175, 45),  (250, 215, 75)),
        ("SETTINGS",     "⌘",  (35,  35,  52),  (52,  52,  75),  (110, 110, 160), (160, 160, 210)),
        ("QUIT",         "✕",  (65,  18,  18),  (95,  28,  28),  (190, 65,  65),  (240, 95,  95)),
    ]

    def _main_menu_button_rects(self) -> list:
        n = len(self._MENU_BTNS)
        total_h = (self._MENU_BTN_H_PLAY + (n - 1) * self._MENU_BTN_H
                   + (n - 1) * self._MENU_BTN_GAP)
        start_y = SCREEN_HEIGHT // 2 - total_h // 2 + 120
        x = (SCREEN_WIDTH - self._MENU_BTN_W) // 2
        rects = []
        y = start_y
        for i in range(n):
            h = self._MENU_BTN_H_PLAY if i == 0 else self._MENU_BTN_H
            rects.append(pygame.Rect(x, y, self._MENU_BTN_W, h))
            y += h + self._MENU_BTN_GAP
        return rects

    def main_menu_button_at(self, pos) -> "int | None":
        for i, rect in enumerate(self._main_menu_button_rects()):
            if rect.collidepoint(pos):
                return i
        return None

    # One ball color per letter of POPLUX
    _LOGO_COLORS = ["red", "blue", "green", "red", "yellow", "blue"]
    _LOGO_LETTERS = list("POPLUX")

    def draw_main_menu(self, mouse_pos) -> None:
        cx = SCREEN_WIDTH // 2
        t = pygame.time.get_ticks() / 1000.0

        # --- Logo glow — neutral white pulse ---
        glow_alpha = int(30 + 20 * math.sin(t * 2.0))
        glow_w, glow_h = 860, 130
        glow_surf = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
        for r, a in ((glow_h // 2, glow_alpha // 3), (glow_h // 3, glow_alpha // 2), (glow_h // 4, glow_alpha)):
            pygame.gfxdraw.filled_ellipse(glow_surf, glow_w // 2, glow_h // 2, glow_w // 2, r, (200, 200, 220, a))
        self.screen.blit(glow_surf, glow_surf.get_rect(center=(cx, 110)))

        # --- Letter-by-letter title with bob ---
        letter_surfs = []
        letter_colors = [
            tuple(min(255, c + 60) for c in BALL_COLORS[col])
            for col in self._LOGO_COLORS
        ]
        for letter, color in zip(self._LOGO_LETTERS, letter_colors):
            letter_surfs.append(self.font_large.render(letter, True, color))

        total_w = sum(s.get_width() for s in letter_surfs) + 8 * (len(letter_surfs) - 1)
        lx = cx - total_w // 2
        logo_y = 42
        for i, surf in enumerate(letter_surfs):
            bob = math.sin(t * 2.5 + i * 0.55) * 6
            self.screen.blit(surf, (lx, logo_y + bob))
            lx += surf.get_width() + 8

        # --- Tagline — short spaced-out style ---
        tagline = self.font_small.render("M A T C H  ·  P O P  ·  S U R V I V E", True, (110, 110, 130))
        self.screen.blit(tagline, tagline.get_rect(center=(cx, 196)))

        # --- Buttons ---
        rects = self._main_menu_button_rects()
        for i, (rect, (label, icon, fill, fill_h, border, border_h)) in enumerate(
                zip(rects, self._MENU_BTNS)):
            hovered    = rect.collidepoint(mouse_pos)
            col_fill   = fill_h   if hovered else fill
            col_border = border_h if hovered else border
            pygame.draw.rect(self.screen, col_fill,   rect, border_radius=10)
            pygame.draw.rect(self.screen, col_border, rect, 2, border_radius=10)

            # Icon + label centered together — secondary buttons use smaller font
            font      = self.font_large  if i == 0 else self.font_med
            icon_font = self.font_icon_lg if i == 0 else self.font_icon_sm
            icon_surf = icon_font.render(icon, True, col_border)
            txt_surf  = font.render(label, True, HUD_COLOR)
            gap       = 20
            total_w   = icon_surf.get_width() + gap + txt_surf.get_width()
            ix        = rect.centerx - total_w // 2
            txt_top     = rect.centery - txt_surf.get_height() // 2
            txt_cap_mid = txt_top + font.get_ascent() // 2
            icon_y      = txt_cap_mid - icon_font.get_ascent() // 2
            self.screen.blit(icon_surf, (ix, icon_y))
            self.screen.blit(txt_surf,  (ix + icon_surf.get_width() + gap, txt_top))

        hint = self.font_small.render("ESC to quit", True, (100, 100, 110))
        self.screen.blit(hint, hint.get_rect(center=(cx, SCREEN_HEIGHT - 18)))

    # ------------------------------------------------------------------ #
    # Pause menu                                                           #
    # ------------------------------------------------------------------ #

    _PAUSE_BTN_W = 640
    _PAUSE_BTN_H = 108
    _PAUSE_BTN_GAP = 28
    _PAUSE_LABELS = ["RESUME", "RESTART", "MAIN MENU"]

    def _pause_button_rects(self) -> list:
        n = len(self._PAUSE_LABELS)
        total_h = n * self._PAUSE_BTN_H + (n - 1) * self._PAUSE_BTN_GAP
        start_y = SCREEN_HEIGHT // 2 - total_h // 2 + 20
        x = (SCREEN_WIDTH - self._PAUSE_BTN_W) // 2
        return [
            pygame.Rect(x, start_y + i * (self._PAUSE_BTN_H + self._PAUSE_BTN_GAP),
                        self._PAUSE_BTN_W, self._PAUSE_BTN_H)
            for i in range(n)
        ]

    def pause_button_at(self, pos) -> "int | None":
        for i, rect in enumerate(self._pause_button_rects()):
            if rect.collidepoint(pos):
                return i
        return None

    def draw_pause_menu(self, mouse_pos, level_name: str = "", score: int = 0, overlay_alpha: int = 255) -> None:
        overlay = self._overlay_surf
        overlay.fill((0, 0, 0, int(160 * overlay_alpha / 255)))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        title = self.font_large.render("PAUSED", True, HUD_COLOR)
        self.screen.blit(title, title.get_rect(center=(cx, SCREEN_HEIGHT // 2 - 280)))

        if level_name:
            name_surf = self.font_small.render(level_name, True, (140, 140, 160))
            self.screen.blit(name_surf, name_surf.get_rect(center=(cx, SCREEN_HEIGHT // 2 - 200)))
        score_surf = self.font_med.render(f"Score  {score:,}", True, (200, 190, 80))
        self.screen.blit(score_surf, score_surf.get_rect(center=(cx, SCREEN_HEIGHT // 2 - 160)))

        colors      = [(35, 80, 35), (80, 60, 25), (80, 30, 30)]
        hover_colors = [(55, 130, 55), (130, 100, 40), (130, 50, 50)]
        for i, (rect, label) in enumerate(zip(self._pause_button_rects(), self._PAUSE_LABELS)):
            hovered = rect.collidepoint(mouse_pos)
            fill   = hover_colors[i] if hovered else colors[i]
            border = (180, 220, 180) if hovered else (100, 140, 100)
            pygame.draw.rect(self.screen, fill, rect, border_radius=10)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=10)
            txt = self.font_med.render(label, True, HUD_COLOR)
            self.screen.blit(txt, txt.get_rect(center=rect.center))

        hint = self.font_small.render("Space / ESC to resume", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 256)))

    # ------------------------------------------------------------------ #
    # Level-complete overlay                                               #
    # ------------------------------------------------------------------ #

    _LC_BTN_W = 384
    _LC_BTN_H = 83
    _LC_BTN_GAP = 32
    _LC_TITLE_BTN_GAP = 48   # gap between title bottom and buttons top

    def _level_complete_button_rects(self, new_best: bool = False) -> list:
        GAP = 22
        title_h = self.font_large.get_height()
        score_block_h = self.font_small.get_height() + 6 + self.font_score.get_height()
        if new_best:
            score_block_h += 10 + self.font_small.get_height()
        total_h = title_h + GAP + score_block_h + self._LC_TITLE_BTN_GAP + self._LC_BTN_H
        top = SCREEN_HEIGHT // 2 - total_h // 2
        btn_y = top + title_h + GAP + score_block_h + self._LC_TITLE_BTN_GAP
        total_w = 2 * self._LC_BTN_W + self._LC_BTN_GAP
        x = (SCREEN_WIDTH - total_w) // 2
        return [
            pygame.Rect(x, btn_y, self._LC_BTN_W, self._LC_BTN_H),
            pygame.Rect(x + self._LC_BTN_W + self._LC_BTN_GAP, btn_y, self._LC_BTN_W, self._LC_BTN_H),
        ]

    def level_complete_button_at(self, pos, new_best: bool = False) -> "int | None":
        for i, rect in enumerate(self._level_complete_button_rects(new_best)):
            if rect.collidepoint(pos):
                return i
        return None

    def draw_level_complete(self, mouse_pos, next_level_name: str, score: int = 0, new_best: bool = False, overlay_alpha: int = 255) -> None:
        overlay = self._overlay_surf
        overlay.fill((0, 0, 0, int(170 * overlay_alpha / 255)))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        GAP = 22

        title_surf  = self.font_large.render("LEVEL COMPLETE!", True, (100, 240, 100))
        score_label = self.font_small.render("SCORE", True, (140, 200, 140))
        score_surf  = self.font_score.render(f"{score:,}", True, (160, 255, 160))
        best_surf   = self.font_small.render("NEW BEST!", True, (255, 220, 50)) if new_best else None

        score_block_h = score_label.get_height() + 6 + score_surf.get_height()
        if best_surf:
            score_block_h += 10 + best_surf.get_height()
        total_h = title_surf.get_height() + GAP + score_block_h + self._LC_TITLE_BTN_GAP + self._LC_BTN_H
        title_y = SCREEN_HEIGHT // 2 - total_h // 2

        self.screen.blit(title_surf, title_surf.get_rect(centerx=cx, top=title_y))
        sy = title_y + title_surf.get_height() + GAP
        self.screen.blit(score_label, score_label.get_rect(centerx=cx, top=sy))
        sy += score_label.get_height() + 6
        self.screen.blit(score_surf, score_surf.get_rect(centerx=cx, top=sy))
        sy += score_surf.get_height()
        if best_surf:
            sy += 10
            self.screen.blit(best_surf, best_surf.get_rect(centerx=cx, top=sy))
            sy += best_surf.get_height()

        # Recompute button y to sit below score block
        btn_y = title_y + title_surf.get_height() + GAP + score_block_h + self._LC_TITLE_BTN_GAP
        total_w = 2 * self._LC_BTN_W + self._LC_BTN_GAP
        x = (SCREEN_WIDTH - total_w) // 2
        rects = [
            pygame.Rect(x, btn_y, self._LC_BTN_W, self._LC_BTN_H),
            pygame.Rect(x + self._LC_BTN_W + self._LC_BTN_GAP, btn_y, self._LC_BTN_W, self._LC_BTN_H),
        ]

        labels = [f"Next: {next_level_name}", "Main Menu"]
        colors = [(55, 130, 55), (130, 55, 55)]
        hover_colors = [(80, 170, 80), (170, 80, 80)]
        for i, (rect, label) in enumerate(zip(rects, labels)):
            hovered = rect.collidepoint(mouse_pos)
            fill = hover_colors[i] if hovered else colors[i]
            pygame.draw.rect(self.screen, fill, rect, border_radius=10)
            pygame.draw.rect(self.screen, (200, 200, 200), rect, 2, border_radius=10)
            txt = self.font_small.render(label, True, HUD_COLOR)
            self.screen.blit(txt, txt.get_rect(center=rect.center))

        hint = self.font_small.render("Enter / Space — next level    R — restart", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(centerx=SCREEN_WIDTH // 2, top=rects[0].bottom + 24))

    # ------------------------------------------------------------------ #
    # Game-complete screen                                                 #
    # ------------------------------------------------------------------ #

    def draw_game_complete(self, mouse_pos, score: int, elapsed_time: float, overlay_alpha: int = 255) -> None:
        overlay = self._overlay_surf
        overlay.fill((0, 0, 0, int(200 * overlay_alpha / 255)))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        GAP_S = 18   # small gap between label and value
        GAP_L = 36   # large gap between sections
        DIV_W = 560

        # Render all surfaces first
        title_surf = self.font_large.render("YOU WIN!", True, (255, 220, 60))
        sub_surf   = self.font_med.render("All levels cleared!", True, (200, 200, 200))

        mins, secs = int(elapsed_time) // 60, int(elapsed_time) % 60
        score_label = self.font_small.render("FINAL SCORE", True, (150, 150, 150))
        score_value = self.font_score.render(f"{score:,}", True, (255, 215, 60))
        time_label  = self.font_small.render("TIME", True, (150, 150, 150))
        time_value  = self.font_score.render(f"{mins}:{secs:02d}", True, (120, 200, 255))

        btn_w, btn_h = 360, 78
        btn_txt = self.font_med.render("MAIN MENU", True, HUD_COLOR)
        hint_surf = self.font_small.render("or click anywhere", True, (90, 90, 90))

        # Measure total block height to centre the whole card
        stats_h = max(score_label.get_height() + GAP_S + score_value.get_height(),
                      time_label.get_height()  + GAP_S + time_value.get_height())
        total_h = (title_surf.get_height() + GAP_L
                   + sub_surf.get_height()  + GAP_L
                   + 1                      + GAP_L   # divider
                   + stats_h                + GAP_L
                   + 1                      + GAP_L   # divider
                   + btn_h                  + GAP_S
                   + hint_surf.get_height())
        y = SCREEN_HEIGHT // 2 - total_h // 2

        # Title
        self.screen.blit(title_surf, title_surf.get_rect(centerx=cx, top=y))
        y += title_surf.get_height() + GAP_L

        # Subtitle
        self.screen.blit(sub_surf, sub_surf.get_rect(centerx=cx, top=y))
        y += sub_surf.get_height() + GAP_L

        # Divider
        pygame.draw.line(self.screen, (80, 80, 80), (cx - DIV_W // 2, y), (cx + DIV_W // 2, y), 1)
        y += 1 + GAP_L

        # Stats row — score left, time right
        col_x = DIV_W // 4
        for label, value, color_x in (
            (score_label, score_value, cx - col_x),
            (time_label,  time_value,  cx + col_x),
        ):
            self.screen.blit(label, label.get_rect(centerx=color_x, top=y))
            self.screen.blit(value, value.get_rect(centerx=color_x, top=y + label.get_height() + GAP_S))
        y += stats_h + GAP_L

        # Divider
        pygame.draw.line(self.screen, (80, 80, 80), (cx - DIV_W // 2, y), (cx + DIV_W // 2, y), 1)
        y += 1 + GAP_L

        # Button
        btn_rect = pygame.Rect(cx - btn_w // 2, y, btn_w, btn_h)
        hovered = btn_rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, (80, 55, 130) if hovered else (55, 35, 100), btn_rect, border_radius=10)
        pygame.draw.rect(self.screen, (180, 150, 255) if hovered else (120, 90, 200), btn_rect, 2, border_radius=10)
        self.screen.blit(btn_txt, btn_txt.get_rect(center=btn_rect.center))
        y += btn_h + GAP_S

        # Hint
        self.screen.blit(hint_surf, hint_surf.get_rect(centerx=cx, top=y))

    # ------------------------------------------------------------------ #
    # Cheat-code menu                                                      #
    # ------------------------------------------------------------------ #

    _CHEAT_INPUT_W = 576
    _CHEAT_INPUT_H = 83

    _CHEAT_DESCRIPTIONS = {
        "GODMODE":   "No lose condition",
        "SLOWMO":    "Chain at 25% speed",
        "MAGNET":    "Fired balls home in on chain",
        "FASTBALL":  "Balls travel 3x faster",
        "MULTISHOT": "Every shot fires 3 balls",
        "RAINBOW":   "Fired balls auto-match color",
        "RESET":     "Clear all active cheats",
    }

    def draw_cheat_menu(self, active_cheats: set, input_text: str, message: str) -> None:
        title = self.font_large.render("CHEAT CODES", True, (210, 80, 80))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 144)))

        # Input box
        box_x = (SCREEN_WIDTH - self._CHEAT_INPUT_W) // 2
        box_y = 232
        box_rect = pygame.Rect(box_x, box_y, self._CHEAT_INPUT_W, self._CHEAT_INPUT_H)
        pygame.draw.rect(self.screen, (20, 20, 30), box_rect, border_radius=8)
        pygame.draw.rect(self.screen, (180, 80, 80), box_rect, 2, border_radius=8)
        cursor = "|" if (pygame.time.get_ticks() // 530) % 2 == 0 else " "
        input_surf = self.font_med.render(input_text + cursor, True, (220, 220, 220))
        self.screen.blit(input_surf, input_surf.get_rect(center=box_rect.center))

        # Feedback message
        if message:
            is_on  = message.endswith("[ON]") or message == "ALL CHEATS CLEARED"
            is_err = message == "UNKNOWN CODE"
            color  = (100, 220, 100) if is_on else (220, 100, 100) if is_err else (180, 180, 100)
            msg_surf = self.font_small.render(message, True, color)
            self.screen.blit(msg_surf, msg_surf.get_rect(center=(SCREEN_WIDTH // 2, box_y + self._CHEAT_INPUT_H + 20)))

        # Unified code list — always visible; active codes are highlighted
        y = box_y + self._CHEAT_INPUT_H + 46
        for code, desc in self._CHEAT_DESCRIPTIONS.items():
            is_active = code in active_cheats
            if is_active:
                prefix     = "ON  "
                code_color = (230, 100, 100)
                desc_color = (170, 65, 65)
            else:
                prefix     = "        "
                code_color = (95, 95, 95)
                desc_color = (65, 65, 65)
            code_surf = self.font_small.render(f"{prefix}{code}", True, code_color)
            desc_surf = self.font_small.render(f"  —  {desc}", True, desc_color)
            total_w   = code_surf.get_width() + desc_surf.get_width()
            x0        = (SCREEN_WIDTH - total_w) // 2
            self.screen.blit(code_surf, (x0, y))
            self.screen.blit(desc_surf, (x0 + code_surf.get_width(), y))
            y += code_surf.get_height() + 5

        hint = self.font_small.render("type code  +  ENTER  to toggle     ESC  ·  back", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18)))

    # ------------------------------------------------------------------ #
    # Records screen                                                       #
    # ------------------------------------------------------------------ #

    # Column right-edges (for "r") or left-edges (for "l") — used by all-runs tab
    _COL_X      = (120, 220, 820, 1200, 1520, 1860)
    _ROW_H      = 62
    _TABLE_TOP  = 230   # below tabs
    # Tab bar geometry
    _TAB_Y      = 140
    _TAB_H      = 52
    _TAB_W      = 340
    _TAB_GAP    = 16

    def _tab_rects(self) -> list[pygame.Rect]:
        cx = SCREEN_WIDTH // 2
        total_w = 3 * self._TAB_W + 2 * self._TAB_GAP
        x0 = cx - total_w // 2
        return [
            pygame.Rect(x0,                              self._TAB_Y, self._TAB_W, self._TAB_H),
            pygame.Rect(x0 + self._TAB_W + self._TAB_GAP, self._TAB_Y, self._TAB_W, self._TAB_H),
            pygame.Rect(x0 + 2 * (self._TAB_W + self._TAB_GAP), self._TAB_Y, self._TAB_W, self._TAB_H),
        ]

    def records_tab_at(self, pos) -> "int | None":
        for i, rect in enumerate(self._tab_rects()):
            if rect.collidepoint(pos):
                return i
        return None

    def records_max_rows(self) -> int:
        div_y = self._TABLE_TOP + self.font_small.get_height() + 6
        hint_h = self.font_small.get_height() + 28
        return (SCREEN_HEIGHT - div_y - hint_h) // self._ROW_H

    def _draw_records_tabs(self, active_tab: int) -> None:
        tab_labels = ["BEST BY LEVEL", "ENDLESS", "ALL RUNS"]
        rects = self._tab_rects()
        for i, (rect, label) in enumerate(zip(rects, tab_labels)):
            active = i == active_tab
            bg     = (38, 38, 58) if active else (20, 20, 30)
            border = HUD_COLOR if active else (60, 60, 80)
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=8)
            txt = self.font_small.render(label, True, HUD_COLOR if active else (120, 120, 140))
            self.screen.blit(txt, txt.get_rect(center=rect.center))

    def _draw_records_grid(self, best_by_level: dict) -> None:
        """Tab 0: one row per level, best score + best time."""
        header_y = self._TABLE_TOP
        div_y    = header_y + self.font_small.get_height() + 6

        # Column layout: Level | Best Score | Best Time | Date
        COL_LEVEL = 200
        COL_SCORE = 1100
        COL_TIME  = 1560
        COL_DATE  = 1870

        for label, x, align in (
            ("LEVEL", COL_LEVEL, "l"),
            ("BEST SCORE", COL_SCORE, "r"),
            ("BEST TIME", COL_TIME, "r"),
            ("DATE", COL_DATE, "r"),
        ):
            surf = self.font_small.render(label, True, (180, 180, 100))
            rect = surf.get_rect(y=header_y)
            rect.right = x if align == "r" else rect.right
            rect.left  = x if align == "l" else rect.left
            self.screen.blit(surf, rect)

        pygame.draw.line(self.screen, (80, 80, 80), (40, div_y), (SCREEN_WIDTH - 40, div_y), 1)

        for row_i, cfg in enumerate(LEVELS):
            y = div_y + 4 + row_i * self._ROW_H
            shade = (22, 22, 30) if row_i % 2 == 0 else (0, 0, 0, 0)
            pygame.draw.rect(self.screen, shade,
                             pygame.Rect(40, y, SCREEN_WIDTH - 80, self._ROW_H - 2))
            cy = y + (self._ROW_H - self.font_small.get_height()) // 2

            best = best_by_level.get(cfg["name"])
            color = HUD_COLOR if best else (80, 80, 100)

            name_surf = self.font_small.render(cfg["name"], True, color)
            self.screen.blit(name_surf, name_surf.get_rect(left=COL_LEVEL, y=cy))

            if best:
                score_surf = self.font_small.render(f"{best['score']:,}", True, (220, 190, 50))
                self.screen.blit(score_surf, score_surf.get_rect(right=COL_SCORE, y=cy))

                mins, secs = divmod(int(best["time"]), 60)
                time_surf = self.font_small.render(f"{mins}:{secs:02d}", True, (120, 200, 255))
                self.screen.blit(time_surf, time_surf.get_rect(right=COL_TIME, y=cy))

                date_surf = self.font_small.render(best["date"], True, (140, 140, 140))
                self.screen.blit(date_surf, date_surf.get_rect(right=COL_DATE, y=cy))
            else:
                no_surf = self.font_small.render("—", True, (60, 60, 80))
                self.screen.blit(no_surf, no_surf.get_rect(right=COL_SCORE, y=cy))

    def _draw_records_endless(self, best_by_endless: dict) -> None:
        """Tab 1: one row per level slot, best endless score + time."""
        header_y = self._TABLE_TOP
        div_y    = header_y + self.font_small.get_height() + 6

        COL_LEVEL = 200
        COL_SCORE = 1100
        COL_TIME  = 1560
        COL_DATE  = 1870

        for label, x, align in (
            ("LEVEL", COL_LEVEL, "l"),
            ("BEST SCORE", COL_SCORE, "r"),
            ("BEST TIME", COL_TIME, "r"),
            ("DATE", COL_DATE, "r"),
        ):
            surf = self.font_small.render(label, True, (180, 180, 100))
            rect = surf.get_rect(y=header_y)
            rect.right = x if align == "r" else rect.right
            rect.left  = x if align == "l" else rect.left
            self.screen.blit(surf, rect)

        pygame.draw.line(self.screen, (80, 80, 80), (40, div_y), (SCREEN_WIDTH - 40, div_y), 1)

        for row_i, cfg in enumerate(LEVELS):
            endless_key = f"Endless (Lvl {row_i + 1})"
            y = div_y + 4 + row_i * self._ROW_H
            shade = (22, 22, 30) if row_i % 2 == 0 else (0, 0, 0, 0)
            pygame.draw.rect(self.screen, shade,
                             pygame.Rect(40, y, SCREEN_WIDTH - 80, self._ROW_H - 2))
            cy = y + (self._ROW_H - self.font_small.get_height()) // 2

            best = best_by_endless.get(endless_key)
            color = HUD_COLOR if best else (80, 80, 100)

            name_surf = self.font_small.render(cfg["name"], True, color)
            self.screen.blit(name_surf, name_surf.get_rect(left=COL_LEVEL, y=cy))

            if best:
                score_surf = self.font_small.render(f"{best['score']:,}", True, (220, 190, 50))
                self.screen.blit(score_surf, score_surf.get_rect(right=COL_SCORE, y=cy))

                mins, secs = divmod(int(best["time"]), 60)
                time_surf = self.font_small.render(f"{mins}:{secs:02d}", True, (120, 200, 255))
                self.screen.blit(time_surf, time_surf.get_rect(right=COL_TIME, y=cy))

                date_surf = self.font_small.render(best["date"], True, (140, 140, 140))
                self.screen.blit(date_surf, date_surf.get_rect(right=COL_DATE, y=cy))
            else:
                no_surf = self.font_small.render("—", True, (60, 60, 80))
                self.screen.blit(no_surf, no_surf.get_rect(right=COL_SCORE, y=cy))

    def _draw_records_all(self, records: list, scroll: int) -> None:
        """Tab 1: paginated list of all runs sorted by score."""
        max_rows = self.records_max_rows()
        scroll   = max(0, min(scroll, max(0, len(records) - max_rows)))
        shown    = records[scroll:scroll + max_rows]

        header_y = self._TABLE_TOP
        div_y    = header_y + self.font_small.get_height() + 6

        col_labels = ("#", "LEVEL", "SCORE", "TIME", "DATE")
        col_x      = (self._COL_X[0], self._COL_X[2], self._COL_X[3], self._COL_X[4], self._COL_X[5])
        col_align  = ("r", "l", "r", "r", "r")
        for label, x, align in zip(col_labels, col_x, col_align):
            surf = self.font_small.render(label, True, (180, 180, 100))
            rect = surf.get_rect(y=header_y)
            rect.right = x if align == "r" else rect.right
            rect.left  = x if align == "l" else rect.left
            self.screen.blit(surf, rect)

        pygame.draw.line(self.screen, (80, 80, 80), (40, div_y), (SCREEN_WIDTH - 40, div_y), 1)

        for row_i, rec in enumerate(shown):
            y = div_y + 4 + row_i * self._ROW_H
            shade = (22, 22, 30) if row_i % 2 == 0 else (0, 0, 0, 0)
            pygame.draw.rect(self.screen, shade,
                             pygame.Rect(40, y, SCREEN_WIDTH - 80, self._ROW_H - 2))

            abs_rank = scroll + row_i
            rank_color = {0: (255, 215, 50), 1: (200, 200, 210), 2: (200, 130, 60)}.get(abs_rank, (140, 140, 140))
            rank_surf = self.font_small.render(f"{abs_rank + 1}", True, rank_color)
            self.screen.blit(rank_surf, rank_surf.get_rect(
                right=self._COL_X[0], y=y + (self._ROW_H - rank_surf.get_height()) // 2))

            color = (255, 220, 50) if abs_rank == 0 else HUD_COLOR
            mins, secs = divmod(int(rec["time"]), 60)
            cells = (rec["level"], f"{rec['score']:,}", f"{mins}:{secs:02d}", rec["date"])
            cell_x     = (self._COL_X[2], self._COL_X[3], self._COL_X[4], self._COL_X[5])
            cell_align = ("l", "r", "r", "r")
            for cell, x, align in zip(cells, cell_x, cell_align):
                surf = self.font_small.render(cell, True, color)
                rect = surf.get_rect(y=y + (self._ROW_H - surf.get_height()) // 2)
                rect.right = x if align == "r" else rect.right
                rect.left  = x if align == "l" else rect.left
                self.screen.blit(surf, rect)

        if len(records) > max_rows:
            total = len(records)
            end   = scroll + len(shown)
            nav = self.font_small.render(
                f"{scroll + 1}–{end} of {total}  ·  up/down or scroll to navigate",
                True, (100, 100, 100))
            self.screen.blit(nav, nav.get_rect(
                centerx=SCREEN_WIDTH // 2, bottom=SCREEN_HEIGHT - 28 - self.font_small.get_height()))

    def draw_records(self, records: list, scroll: int = 0, tab: int = 0,
                     best_by_level: dict | None = None,
                     endless_records: list | None = None,
                     best_by_endless: dict | None = None) -> None:
        title = self.font_large.render("RECORDS", True, HUD_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 78)))

        self._draw_records_tabs(tab)

        no_normal  = not records
        no_endless = not endless_records
        if no_normal and no_endless:
            msg = self.font_med.render("No records yet — win a level to get started!", True, (160, 160, 160))
            self.screen.blit(msg, msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
            hint = self.font_small.render("ESC  ·  main menu", True, (120, 120, 120))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18)))
            return

        if tab == 0:
            self._draw_records_grid(best_by_level or {})
        elif tab == 1:
            self._draw_records_endless(best_by_endless or {})
        else:
            self._draw_records_all(records, scroll)

        scroll_hint = "  ·  up/down or scroll to navigate" if tab == 2 else ""
        hint = self.font_small.render(
            f"ESC  ·  main menu    left/right — switch tabs{scroll_hint}", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18)))

    # ------------------------------------------------------------------ #
    # Settings screen                                                      #
    # ------------------------------------------------------------------ #

    _SLIDER_W = 400
    _SLIDER_H = 10
    _SETTINGS_ROW_H = 88
    _SETTINGS_CTRL_X = SCREEN_WIDTH // 2 + 80  # left edge of controls column

    def _settings_rows_y(self) -> list:
        n = 7
        title_bottom = 100 + self.font_large.get_height() // 2
        hint_top = SCREEN_HEIGHT - 18 - self.font_small.get_height()
        available = hint_top - title_bottom
        total_h = n * self._SETTINGS_ROW_H
        start = title_bottom + (available - total_h) // 2 + self._SETTINGS_ROW_H // 2
        return [start + i * self._SETTINGS_ROW_H for i in range(n)]

    def _slider_rect(self, row: int) -> pygame.Rect:
        y = self._settings_rows_y()[row]
        return pygame.Rect(self._SETTINGS_CTRL_X, y - self._SLIDER_H // 2,
                           self._SLIDER_W, self._SLIDER_H)

    def _toggle_rect(self, row: int) -> pygame.Rect:
        y = self._settings_rows_y()[row]
        return pygame.Rect(self._SETTINGS_CTRL_X, y - 22, 72, 44)

    def _draw_slider(self, mouse_pos, y: int, value: float, color: tuple) -> None:
        track = pygame.Rect(self._SETTINGS_CTRL_X, y - self._SLIDER_H // 2,
                            self._SLIDER_W, self._SLIDER_H)
        pygame.draw.rect(self.screen, (60, 60, 60), track, border_radius=5)
        fill_w = int(track.w * value)
        if fill_w > 0:
            pygame.draw.rect(self.screen, color,
                             pygame.Rect(track.x, track.y, fill_w, track.h), border_radius=5)
        knob_x = track.x + fill_w
        hovered = math.hypot(mouse_pos[0] - knob_x, mouse_pos[1] - track.centery) < 14
        light = tuple(min(255, c + 60) for c in color)
        self._aa_circle(self.screen, light if hovered else color, (knob_x, track.centery), 12)
        pct = self.font_small.render(f"{int(value * 100)}%", True, HUD_COLOR)
        self.screen.blit(pct, pct.get_rect(midleft=(track.right + 20, y)))

    def _draw_toggle(self, y: int, on: bool) -> None:
        tog = pygame.Rect(self._SETTINGS_CTRL_X, y - 22, 72, 44)
        pygame.draw.rect(self.screen, (60, 140, 60) if on else (60, 60, 60), tog, border_radius=22)
        pygame.draw.rect(self.screen, (120, 220, 120) if on else (100, 100, 100), tog, 2, border_radius=22)
        knob_x = tog.right - 26 if on else tog.left + 26
        self._aa_circle(self.screen, (220, 255, 220) if on else (160, 160, 160), (knob_x, tog.centery), 16)
        lbl = self.font_small.render("ON" if on else "OFF", True,
                                     (120, 220, 120) if on else (120, 120, 120))
        self.screen.blit(lbl, lbl.get_rect(midleft=(tog.right + 20, y)))

    def draw_settings(self, mouse_pos, settings) -> None:
        cx = SCREEN_WIDTH // 2
        title = self.font_large.render("SETTINGS", True, HUD_COLOR)
        self.screen.blit(title, title.get_rect(center=(cx, 100)))

        rows_y = self._settings_rows_y()
        label_x = cx - 60

        # --- Music Volume ---
        label = self.font_med.render("MUSIC VOLUME", True, (180, 180, 180))
        self.screen.blit(label, label.get_rect(midright=(label_x, rows_y[0])))
        self._draw_slider(mouse_pos, rows_y[0], settings.music_volume, (80, 180, 80))

        # --- SFX Volume ---
        label = self.font_med.render("SFX VOLUME", True, (180, 180, 180))
        self.screen.blit(label, label.get_rect(midright=(label_x, rows_y[1])))
        self._draw_slider(mouse_pos, rows_y[1], settings.sfx_volume, (80, 140, 200))

        # --- Fullscreen ---
        label = self.font_med.render("FULLSCREEN", True, (180, 180, 180))
        self.screen.blit(label, label.get_rect(midright=(label_x, rows_y[2])))
        self._draw_toggle(rows_y[2], settings.fullscreen)

        # --- Colorblind Mode ---
        label = self.font_med.render("COLORBLIND MODE", True, (180, 180, 180))
        self.screen.blit(label, label.get_rect(midright=(label_x, rows_y[3])))
        self._draw_toggle(rows_y[3], settings.colorblind_mode)

        # --- Show FPS ---
        label = self.font_med.render("SHOW FPS", True, (180, 180, 180))
        self.screen.blit(label, label.get_rect(midright=(label_x, rows_y[4])))
        self._draw_toggle(rows_y[4], settings.show_fps)

        # --- Danger Vignette ---
        label = self.font_med.render("DANGER VIGNETTE", True, (180, 180, 180))
        self.screen.blit(label, label.get_rect(midright=(label_x, rows_y[5])))
        self._draw_toggle(rows_y[5], settings.danger_vignette)

        # --- Particles ---
        label = self.font_med.render("PARTICLES", True, (180, 180, 180))
        self.screen.blit(label, label.get_rect(midright=(label_x, rows_y[6])))
        self._draw_toggle(rows_y[6], settings.particles)

        hint = self.font_small.render("ESC  ·  back", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(center=(cx, SCREEN_HEIGHT - 18)))

    def settings_interact(self, mouse_pos, settings) -> "str | None":
        # Sliders
        for row, attr, action in (
            (0, "music_volume", "volume_changed"),
            (1, "sfx_volume",   "sfx_changed"),
        ):
            track = self._slider_rect(row)
            if track.inflate(0, 40).collidepoint(mouse_pos):
                t = (mouse_pos[0] - track.x) / track.w
                setattr(settings, attr, max(0.0, min(1.0, t)))
                return action

        # Toggles
        if self._toggle_rect(2).collidepoint(mouse_pos):
            settings.fullscreen = not settings.fullscreen
            return "fullscreen_toggled"
        if self._toggle_rect(3).collidepoint(mouse_pos):
            settings.colorblind_mode = not settings.colorblind_mode
            return "colorblind_toggled"
        if self._toggle_rect(4).collidepoint(mouse_pos):
            settings.show_fps = not settings.show_fps
            return "setting_toggled"
        if self._toggle_rect(5).collidepoint(mouse_pos):
            settings.danger_vignette = not settings.danger_vignette
            return "setting_toggled"
        if self._toggle_rect(6).collidepoint(mouse_pos):
            settings.particles = not settings.particles
            return "setting_toggled"

        return None
