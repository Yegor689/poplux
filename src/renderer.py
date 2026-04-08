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
        self.font_icon_sm  = pygame.font.Font(_FONT_SYMBOLS, 52)
        self._palettes = self._build_palettes()
        # Cached surfaces — allocated once, cleared and reused each frame
        self._aim_line_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._overlay_surf  = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

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
            r = p.radius + int(math.sin(p.pulse) * 2)
            size = (r + 10) * 2
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            sc = r + 10
            # Outer glow rings
            pygame.gfxdraw.filled_circle(surf, sc, sc, r + 8, (0, 220, 255, alpha // 6))
            pygame.gfxdraw.filled_circle(surf, sc, sc, r + 5, (0, 220, 255, alpha // 3))
            # Dark fill with cyan border
            pygame.gfxdraw.filled_circle(surf, sc, sc, r, (8, 18, 38, alpha))
            pygame.gfxdraw.aacircle(surf, sc, sc, r, (0, 220, 255, alpha))
            pygame.gfxdraw.aacircle(surf, sc, sc, r - 2, (0, 180, 220, alpha // 2))
            # Crosshair lines (broken at centre)
            gap = r // 3
            lc = (0, 230, 255, alpha)
            pygame.draw.line(surf, lc, (sc - r + 3, sc), (sc - gap, sc), 1)
            pygame.draw.line(surf, lc, (sc + gap, sc), (sc + r - 3, sc), 1)
            pygame.draw.line(surf, lc, (sc, sc - r + 3), (sc, sc - gap), 1)
            pygame.draw.line(surf, lc, (sc, sc + gap), (sc, sc + r - 3), 1)
            # Centre dot
            pygame.gfxdraw.filled_circle(surf, sc, sc, 2, (0, 255, 255, alpha))
            self.screen.blit(surf, (cx - sc, cy - sc))

    def draw_aim_line(self, frog, aim_timer: float) -> None:
        if aim_timer <= 0:
            return
        base_alpha = int(200 * min(aim_timer / 2.0, 1.0))  # fade in over 2 s
        mouth_dist = BALL_RADIUS * 4
        sx = frog.x + math.cos(frog.angle) * mouth_dist
        sy = frog.y + math.sin(frog.angle) * mouth_dist
        dx = math.cos(frog.angle)
        dy = math.sin(frog.angle)
        # Animate dots scrolling toward the target
        phase = (pygame.time.get_ticks() / 120) % 22
        line_surf = self._aim_line_surf
        line_surf.fill((0, 0, 0, 0))
        t = phase
        while True:
            x = sx + dx * t
            y = sy + dy * t
            if not (0 <= x < SCREEN_WIDTH and 0 <= y < SCREEN_HEIGHT):
                break
            fade = max(0.25, 1.0 - t / 700)
            dot_alpha = int(base_alpha * fade)
            pygame.gfxdraw.filled_circle(line_surf, int(x), int(y), 3, (255, 255, 255, dot_alpha))
            t += 22
        self.screen.blit(line_surf, (0, 0))

    def draw_coins(self, coins: list) -> None:
        for coin in coins:
            cx, cy = int(coin.x), int(coin.y)
            r = max(8, int(coin.radius + math.sin(coin.pulse) * 2))
            alpha = coin.alpha
            size = (r + 6) * 2
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            sc = r + 6
            pygame.gfxdraw.filled_circle(surf, sc, sc, r + 4, (255, 215, 0, alpha // 4))
            pygame.gfxdraw.filled_circle(surf, sc, sc, r + 2, (255, 215, 0, alpha // 2))
            pygame.gfxdraw.filled_circle(surf, sc, sc, r, (255, 215, 0, alpha))
            pygame.gfxdraw.aacircle(surf, sc, sc, r, (180, 140, 0, alpha))
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
            surf = self.font_score.render(p.text, True, p.color)
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

    def draw_hud(self, remaining: int, spawned: int, total: int, level_name: str = "", elapsed_time: float = 0.0, score: int = 0, show_debug: bool = False, aim_timer: float = 0.0, slowdown_timer: float = 0.0) -> None:
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
            bar_w, bar_h = 220, 29
            bx = SCREEN_WIDTH - bar_w - 14
            if aim_timer > 0:
                bx -= bar_w + 18   # sit left of aim bar
            by = SCREEN_HEIGHT - bar_h - 14
            fill_w = int(bar_w * slowdown_timer / self._SLOWDOWN_DURATION)
            label = self.font_small.render("SLOWDOWN", True, (80, 180, 255))
            backing_w = max(bar_w, label.get_width()) + 16
            backing = pygame.Surface((backing_w, bar_h + 35), pygame.SRCALPHA)
            pygame.draw.rect(backing, (0, 0, 0, 140), backing.get_rect(), border_radius=6)
            self.screen.blit(backing, (bx - 4, by - 18))
            self.screen.blit(label, label.get_rect(centerx=bx + bar_w // 2, bottom=by - 1))
            pygame.draw.rect(self.screen, (10, 20, 50), (bx, by, bar_w, bar_h), border_radius=4)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (60, 140, 255), (bx, by, fill_w, bar_h), border_radius=4)
            pygame.draw.rect(self.screen, (40, 100, 200), (bx, by, bar_w, bar_h), 1, border_radius=4)

        # --- Aim line indicator — bottom-right when active ---
        if aim_timer > 0:
            bar_w, bar_h = 220, 29
            bx, by = SCREEN_WIDTH - bar_w - 14, SCREEN_HEIGHT - bar_h - 14
            fill_w = int(bar_w * aim_timer / self._AIM_LINE_DURATION)
            label = self.font_small.render("AIM LINE", True, (0, 220, 255))
            backing_w = max(bar_w, label.get_width()) + 16
            backing = pygame.Surface((backing_w, bar_h + 35), pygame.SRCALPHA)
            pygame.draw.rect(backing, (0, 0, 0, 140), backing.get_rect(), border_radius=6)
            self.screen.blit(backing, (bx - 4, by - 18))
            self.screen.blit(label, label.get_rect(centerx=bx + bar_w // 2, bottom=by - 1))
            pygame.draw.rect(self.screen, (20, 40, 60), (bx, by, bar_w, bar_h), border_radius=4)
            if fill_w > 0:
                pygame.draw.rect(self.screen, (0, 200, 255), (bx, by, fill_w, bar_h), border_radius=4)
            pygame.draw.rect(self.screen, (0, 150, 200), (bx, by, bar_w, bar_h), 1, border_radius=4)

        # --- Debug info — top-right (toggle with S) ---
        if show_debug:
            debug_x = SCREEN_WIDTH - 23
            y = 23
            items = []
            if level_name:
                items.append(level_name)
            items.append(f"On path: {remaining}")
            items.append(f"To spawn: {max(0, total - spawned)}")
            for item in items:
                surf = self.font_small.render(item, True, HUD_COLOR)
                self.screen.blit(surf, surf.get_rect(topright=(debug_x, y)))
                y += surf.get_height() + 4

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

    _CARD_W      = 380
    _CARD_H      = 390
    _CARD_GAP    = 40
    _MAX_PER_ROW = 4

    def _level_card_rects(self) -> list:
        """Return list of (rect, level_idx) for all levels in a wrapping grid."""
        n       = len(LEVELS)
        per_row = min(self._MAX_PER_ROW, n)
        cards   = []
        y       = 210
        for row_start in range(0, n, per_row):
            row     = list(range(row_start, min(row_start + per_row, n)))
            total_w = len(row) * self._CARD_W + (len(row) - 1) * self._CARD_GAP
            x       = (SCREEN_WIDTH - total_w) // 2
            for li in row:
                cards.append((pygame.Rect(x, y, self._CARD_W, self._CARD_H), li))
                x += self._CARD_W + self._CARD_GAP
            y += self._CARD_H + self._CARD_GAP
        return cards

    def level_button_at(self, pos) -> "int | None":
        for rect, li in self._level_card_rects():
            if rect.collidepoint(pos):
                return li
        return None

    def draw_level_select(self, mouse_pos, best_scores: dict | None = None) -> None:
        title = self.font_large.render("Select Level", True, HUD_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 104)))

        for rect, li in self._level_card_rects():
            cfg     = LEVELS[li]
            hovered = rect.collidepoint(mouse_pos)
            fill    = (60, 60, 80) if hovered else (40, 40, 55)
            border  = (180, 180, 220) if hovered else (100, 100, 140)

            pygame.draw.rect(self.screen, fill,   rect, border_radius=10)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=10)

            pad = 8
            cy = rect.y + pad

            name_surf = self.font_med.render(cfg["name"], True, HUD_COLOR)
            self.screen.blit(name_surf, name_surf.get_rect(centerx=rect.centerx, top=cy))
            cy += name_surf.get_height() + 6

            sub_surf = self.font_small.render(cfg.get("subtitle", ""), True, (180, 180, 180))
            max_w = self._CARD_W - 16
            if sub_surf.get_width() > max_w:
                sub_surf = pygame.transform.smoothscale(sub_surf, (max_w, sub_surf.get_height()))
            self.screen.blit(sub_surf, sub_surf.get_rect(centerx=rect.centerx, top=cy))
            cy += sub_surf.get_height() + 10

            pygame.draw.line(self.screen, (70, 70, 90), (rect.x + 16, cy), (rect.right - 16, cy))
            cy += 8

            balls_surf = self.font_small.render(f"{cfg['total_balls']} balls", True, (160, 200, 160))
            self.screen.blit(balls_surf, balls_surf.get_rect(centerx=rect.centerx, top=cy))
            cy += balls_surf.get_height() + 4

            speed_surf = self.font_small.render(f"{int(cfg['chain_speed'])} px/s", True, (180, 150, 210))
            self.screen.blit(speed_surf, speed_surf.get_rect(centerx=rect.centerx, top=cy))
            cy += speed_surf.get_height() + 10

            pygame.draw.line(self.screen, (70, 70, 90), (rect.x + 16, cy), (rect.right - 16, cy))
            cy += 8

            best = (best_scores or {}).get(cfg["name"])
            if best:
                mins = int(best["time"]) // 60
                secs = int(best["time"]) % 60
                score_surf = self.font_small.render(f"Best: {best['score']:,}", True, (255, 220, 60))
                time_surf  = self.font_small.render(f"{mins}:{secs:02d}", True, (180, 200, 180))
                self.screen.blit(score_surf, score_surf.get_rect(centerx=rect.centerx, top=cy))
                cy += score_surf.get_height() + 4
                self.screen.blit(time_surf, time_surf.get_rect(centerx=rect.centerx, top=cy))
            else:
                no_surf = self.font_small.render("No record yet", True, (100, 100, 120))
                self.screen.blit(no_surf, no_surf.get_rect(centerx=rect.centerx, top=cy))


        hint = self.font_small.render("ESC  ·  main menu", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18)))

    # ------------------------------------------------------------------ #
    # Main menu                                                            #
    # ------------------------------------------------------------------ #

    _MENU_BTN_W      = 700
    _MENU_BTN_H      = 108
    _MENU_BTN_H_PLAY = 136   # PLAY button is taller
    _MENU_BTN_GAP    = 26
    # (label, icon, fill, fill_hover, border, border_hover)
    _MENU_BTNS = [
        ("PLAY",         "▶",  (30,  90,  30),  (50,  130, 50),  (80,  210, 80),  (130, 255, 130)),
        ("SELECT LEVEL", "▦",  (25,  55,  100), (40,  80,  150), (60,  130, 220), (100, 180, 255)),
        ("RECORDS",      "◈",  (100, 85,  15),  (140, 115, 20),  (220, 185, 50),  (255, 220, 80)),
        ("SETTINGS",     "⌘",  (50,  50,  70),  (70,  70,  100), (120, 120, 170), (170, 170, 220)),
        ("QUIT",         "✕",  (90,  25,  25),  (130, 40,  40),  (200, 70,  70),  (255, 100, 100)),
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

        # --- Animated logo ---
        # Pulsing glow behind the title
        glow_alpha = int(60 + 40 * math.sin(t * 2.0))
        glow_w, glow_h = 860, 140
        glow_surf = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
        for r, a in ((glow_h // 2, glow_alpha // 3), (glow_h // 3, glow_alpha // 2), (glow_h // 4, glow_alpha)):
            pygame.gfxdraw.filled_ellipse(glow_surf, glow_w // 2, glow_h // 2, glow_w // 2, r, (80, 220, 80, a))
        self.screen.blit(glow_surf, glow_surf.get_rect(center=(cx, 118)))

        # Letter-by-letter title — each letter tinted to its ball color
        letter_surfs = []
        letter_colors = [
            tuple(min(255, c + 60) for c in BALL_COLORS[col])
            for col in self._LOGO_COLORS
        ]
        for letter, color in zip(self._LOGO_LETTERS, letter_colors):
            letter_surfs.append(self.font_large.render(letter, True, color))

        total_w = sum(s.get_width() for s in letter_surfs) + 8 * (len(letter_surfs) - 1)
        lx = cx - total_w // 2
        logo_y = 48
        for i, surf in enumerate(letter_surfs):
            # Each letter bobs at a different phase
            bob = math.sin(t * 2.5 + i * 0.55) * 7
            self.screen.blit(surf, (lx, logo_y + bob))
            lx += surf.get_width() + 8

        # --- Colored ball row beneath the title ---
        ball_y = 178
        ball_r = 22
        ball_spacing = ball_r * 2 + 14
        total_bw = len(self._LOGO_COLORS) * ball_spacing - 14
        bx = cx - total_bw // 2 + ball_r
        for i, color_name in enumerate(self._LOGO_COLORS):
            # Each ball pulses in size at its own phase
            pulse = math.sin(t * 3.0 + i * 0.9) * 3
            r = int(ball_r + pulse)
            self._draw_ball(self.screen, color_name, bx, ball_y, r)
            bx += ball_spacing

        # --- Tagline ---
        tagline = self.font_small.render("clear the chain before it reaches the hole", True, (140, 140, 140))
        self.screen.blit(tagline, tagline.get_rect(center=(cx, 222)))

        # --- Buttons ---
        rects = self._main_menu_button_rects()
        for i, (rect, (label, icon, fill, fill_h, border, border_h)) in enumerate(
                zip(rects, self._MENU_BTNS)):
            hovered    = rect.collidepoint(mouse_pos)
            col_fill   = fill_h   if hovered else fill
            col_border = border_h if hovered else border
            pygame.draw.rect(self.screen, col_fill,   rect, border_radius=10)
            pygame.draw.rect(self.screen, col_border, rect, 2, border_radius=10)

            # Accent bar on the left edge
            accent = pygame.Rect(rect.x, rect.y + 10, 5, rect.h - 20)
            pygame.draw.rect(self.screen, col_border, accent, border_radius=3)

            # Icon + label centered together
            font      = self.font_large  if i == 0 else self.font_med
            icon_font = self.font_icon_lg if i == 0 else self.font_icon_sm
            icon_surf = icon_font.render(icon, True, col_border)
            txt_surf  = font.render(label, True, HUD_COLOR)
            gap       = 20
            total_w   = icon_surf.get_width() + gap + txt_surf.get_width()
            ix        = rect.centerx - total_w // 2
            # Align icon to label's cap-height midpoint using ascent offset
            txt_top  = rect.centery - txt_surf.get_height() // 2
            txt_cap_mid = txt_top + font.get_ascent() // 2
            icon_y   = txt_cap_mid - icon_font.get_ascent() // 2
            self.screen.blit(icon_surf, (ix, icon_y))
            self.screen.blit(txt_surf,  (ix + icon_surf.get_width() + gap, txt_top))

        hint = self.font_small.render("ESC to quit", True, (120, 120, 120))
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

    def draw_pause_menu(self, mouse_pos) -> None:
        overlay = self._overlay_surf
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        title = self.font_large.render("PAUSED", True, HUD_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 280)))

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

        hint = self.font_small.render("ESC to resume", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 256)))

    # ------------------------------------------------------------------ #
    # Level-complete overlay                                               #
    # ------------------------------------------------------------------ #

    _LC_BTN_W = 384
    _LC_BTN_H = 83
    _LC_BTN_GAP = 32

    def _level_complete_button_rects(self) -> list:
        total_w = 2 * self._LC_BTN_W + self._LC_BTN_GAP
        x = (SCREEN_WIDTH - total_w) // 2
        y = SCREEN_HEIGHT // 2 + 88
        return [
            pygame.Rect(x, y, self._LC_BTN_W, self._LC_BTN_H),
            pygame.Rect(x + self._LC_BTN_W + self._LC_BTN_GAP, y, self._LC_BTN_W, self._LC_BTN_H),
        ]

    def level_complete_button_at(self, pos) -> "int | None":
        for i, rect in enumerate(self._level_complete_button_rects()):
            if rect.collidepoint(pos):
                return i
        return None

    def draw_level_complete(self, mouse_pos, next_level_name: str) -> None:
        overlay = self._overlay_surf
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        t = self.font_large.render("LEVEL COMPLETE!", True, (100, 240, 100))
        self.screen.blit(t, t.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 48)))

        labels = [f"Next: {next_level_name}", "Main Menu"]
        colors = [(55, 130, 55), (130, 55, 55)]
        hover_colors = [(80, 170, 80), (170, 80, 80)]
        rects = self._level_complete_button_rects()
        for i, (rect, label) in enumerate(zip(rects, labels)):
            hovered = rect.collidepoint(mouse_pos)
            fill = hover_colors[i] if hovered else colors[i]
            pygame.draw.rect(self.screen, fill, rect, border_radius=10)
            pygame.draw.rect(self.screen, (200, 200, 200), rect, 2, border_radius=10)
            txt = self.font_small.render(label, True, HUD_COLOR)
            self.screen.blit(txt, txt.get_rect(center=rect.center))

    # ------------------------------------------------------------------ #
    # Game-complete screen                                                 #
    # ------------------------------------------------------------------ #

    def draw_game_complete(self, mouse_pos, score: int, elapsed_time: float) -> None:
        overlay = self._overlay_surf
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2

        # Title
        title = self.font_large.render("YOU WIN!", True, (255, 220, 60))
        self.screen.blit(title, title.get_rect(center=(cx, cy - 240)))

        sub = self.font_med.render("All levels cleared!", True, (200, 200, 200))
        self.screen.blit(sub, sub.get_rect(center=(cx, cy - 148)))

        # Divider
        pygame.draw.line(self.screen, (80, 80, 80), (cx - 300, cy - 100), (cx + 300, cy - 100), 1)

        # Stats
        mins = int(elapsed_time) // 60
        secs = int(elapsed_time) % 60
        time_str = f"{mins}:{secs:02d}"

        score_label = self.font_small.render("FINAL SCORE", True, (150, 150, 150))
        score_value = self.font_score.render(f"{score:,}", True, (255, 215, 60))
        time_label  = self.font_small.render("TIME", True, (150, 150, 150))
        time_value  = self.font_score.render(time_str, True, (120, 200, 255))

        # Score block (left of center)
        self.screen.blit(score_label, score_label.get_rect(center=(cx - 180, cy - 44)))
        self.screen.blit(score_value, score_value.get_rect(center=(cx - 180, cy + 20)))

        # Time block (right of center)
        self.screen.blit(time_label, time_label.get_rect(center=(cx + 180, cy - 44)))
        self.screen.blit(time_value, time_value.get_rect(center=(cx + 180, cy + 20)))

        pygame.draw.line(self.screen, (80, 80, 80), (cx - 300, cy + 68), (cx + 300, cy + 68), 1)

        # Button
        btn_w, btn_h = 320, 72
        btn_rect = pygame.Rect(cx - btn_w // 2, cy + 100, btn_w, btn_h)
        hovered = btn_rect.collidepoint(mouse_pos)
        pygame.draw.rect(self.screen, (80, 55, 130) if hovered else (55, 35, 100), btn_rect, border_radius=10)
        pygame.draw.rect(self.screen, (180, 150, 255) if hovered else (120, 90, 200), btn_rect, 2, border_radius=10)
        btn_txt = self.font_med.render("MAIN MENU", True, HUD_COLOR)
        self.screen.blit(btn_txt, btn_txt.get_rect(center=btn_rect.center))

        hint = self.font_small.render("or click anywhere", True, (90, 90, 90))
        self.screen.blit(hint, hint.get_rect(center=(cx, cy + 200)))

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

    # Column right-edges (for "r") or left-edges (for "l")
    _COL_X      = (120, 220, 820, 1200, 1520, 1860)  # rank, #, Level, Score, Time, Date
    _COL_LABELS = ("#",  "",   "LEVEL", "SCORE", "TIME", "DATE")
    _COL_ALIGN  = ("r",  "l",  "l",     "r",     "r",    "r")
    _ROW_H      = 62
    _TABLE_TOP  = 200

    def records_max_rows(self) -> int:
        div_y = self._TABLE_TOP + self.font_small.get_height() + 6
        hint_h = self.font_small.get_height() + 28
        return (SCREEN_HEIGHT - div_y - hint_h) // self._ROW_H

    def draw_records(self, records: list, scroll: int = 0) -> None:
        title = self.font_large.render("RECORDS", True, HUD_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 78)))

        if not records:
            msg = self.font_med.render("No records yet — win a level to get started!", True, (160, 160, 160))
            self.screen.blit(msg, msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
            hint = self.font_small.render("ESC  ·  main menu", True, (120, 120, 120))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18)))
            return

        max_rows = self.records_max_rows()
        scroll = max(0, min(scroll, max(0, len(records) - max_rows)))
        shown = records[scroll:scroll + max_rows]

        # Subtitle
        total = len(records)
        end = scroll + len(shown)
        sub_text = f"Showing {scroll + 1}–{end} of {total}  ·  sorted by score" if total > max_rows else f"Top {total} runs by score  ·  all levels"
        sub = self.font_small.render(sub_text, True, (120, 120, 120))
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_WIDTH // 2, 150)))

        # Header row
        header_y = self._TABLE_TOP
        div_y = header_y + self.font_small.get_height() + 6
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

        # Data rows
        for row_i, rec in enumerate(shown):
            y = div_y + 4 + row_i * self._ROW_H
            shade = (22, 22, 30) if row_i % 2 == 0 else (0, 0, 0, 0)
            pygame.draw.rect(self.screen, shade,
                             pygame.Rect(40, y, SCREEN_WIDTH - 80, self._ROW_H - 2))

            is_top = row_i == 0
            color  = (255, 220, 50) if is_top else HUD_COLOR

            # Rank — medal colors for global top 3
            abs_rank = scroll + row_i
            rank_color = {
                0: (255, 215,  50),
                1: (200, 200, 210),
                2: (200, 130,  60),
            }.get(abs_rank, (140, 140, 140))
            rank_surf = self.font_small.render(f"{abs_rank + 1}", True, rank_color)
            rank_rect = rank_surf.get_rect(right=self._COL_X[0], y=y + (self._ROW_H - rank_surf.get_height()) // 2)
            self.screen.blit(rank_surf, rank_rect)

            mins, secs = divmod(int(rec["time"]), 60)
            cells = (rec["level"], str(rec["score"]), f"{mins}:{secs:02d}", rec["date"])
            cell_x     = (self._COL_X[2], self._COL_X[3], self._COL_X[4], self._COL_X[5])
            cell_align = ("l", "r", "r", "r")
            for cell, x, align in zip(cells, cell_x, cell_align):
                surf = self.font_small.render(cell, True, color)
                rect = surf.get_rect(y=y + (self._ROW_H - surf.get_height()) // 2)
                rect.right = x if align == "r" else rect.right
                rect.left  = x if align == "l" else rect.left
                self.screen.blit(surf, rect)

        scroll_hint = "  ·  up/down or scroll to navigate" if len(records) > max_rows else ""
        hint = self.font_small.render(f"ESC  ·  main menu{scroll_hint}", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18)))

    # ------------------------------------------------------------------ #
    # Settings screen                                                      #
    # ------------------------------------------------------------------ #

    _SLIDER_W = 400
    _SLIDER_H = 10
    _SETTINGS_ROW_H = 110
    _SETTINGS_CTRL_X = SCREEN_WIDTH // 2 + 80  # left edge of controls column

    def _settings_rows_y(self) -> list:
        n = 4
        total_h = n * self._SETTINGS_ROW_H
        start = SCREEN_HEIGHT // 2 - total_h // 2
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

        if settings.colorblind_mode:
            preview_y = rows_y[3] + 58
            note = self.font_small.render("symbol preview:", True, (120, 120, 120))
            self.screen.blit(note, note.get_rect(midright=(label_x, preview_y)))
            for i, color_name in enumerate(("red", "green", "blue", "yellow")):
                px = self._SETTINGS_CTRL_X + 30 + i * 80
                self._draw_ball(self.screen, color_name, px, preview_y, 28)

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

        return None
