import math
import pygame
import pygame.gfxdraw
from settings import (
    BALL_COLORS, HOLE_COLOR, HUD_COLOR, BALL_RADIUS, LEVELS,
    SCREEN_WIDTH, SCREEN_HEIGHT,
)


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_large = pygame.font.SysFont(None, 72)
        self.font_med = pygame.font.SysFont(None, 36)
        self.font_small = pygame.font.SysFont(None, 28)
        self.font_score = pygame.font.SysFont(None, 48, bold=True)
        self._palettes = self._build_palettes()

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
        color = (55, 55, 55)
        # Draw segments then fill every joint with a circle to eliminate gaps
        pts = [(int(x), int(y)) for x, y in path.waypoints]
        pygame.draw.lines(self.screen, color, False, pts, BALL_RADIUS * 2)
        for x, y in pts:
            self._aa_circle(self.screen, color, (x, y), BALL_RADIUS)
        hole_x, hole_y = path.waypoints[-1]
        self._aa_circle(self.screen, HOLE_COLOR, (int(hole_x), int(hole_y)), BALL_RADIUS + 4)
        pygame.gfxdraw.aacircle(self.screen, int(hole_x), int(hole_y), BALL_RADIUS + 4, (150, 50, 50))

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

    def draw_hud(self, remaining: int, spawned: int, total: int, level_name: str = "", elapsed_time: float = 0.0, score: int = 0, show_debug: bool = False) -> None:
        # --- Score — top-left, prominent ---
        label_surf = self.font_small.render("SCORE", True, (180, 180, 100))
        value_surf = self.font_score.render(f"{score:,}", True, (255, 240, 80))
        pad_x, pad_y = 14, 10
        box_w = max(label_surf.get_width(), value_surf.get_width()) + pad_x * 2
        box_h = label_surf.get_height() + value_surf.get_height() + pad_y * 2 + 4
        box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        pygame.draw.rect(box_surf, (0, 0, 0, 140), box_surf.get_rect(), border_radius=10)
        pygame.draw.rect(box_surf, (180, 160, 40, 80), box_surf.get_rect(), width=1, border_radius=10)
        self.screen.blit(box_surf, (14, 14))
        self.screen.blit(label_surf, label_surf.get_rect(centerx=14 + box_w // 2, top=14 + pad_y))
        self.screen.blit(value_surf, value_surf.get_rect(centerx=14 + box_w // 2, top=14 + pad_y + label_surf.get_height() + 4))

        # --- Timer — top-center ---
        mins = int(elapsed_time) // 60
        secs = int(elapsed_time) % 60
        timer_text = self.font_med.render(f"{mins}:{secs:02d}", True, HUD_COLOR)
        self.screen.blit(timer_text, timer_text.get_rect(center=(SCREEN_WIDTH // 2, 30)))

        # --- Debug info — top-right (toggle with S) ---
        if show_debug:
            debug_x = SCREEN_WIDTH - 14
            y = 14
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
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))
        t = self.font_large.render(title, True, HUD_COLOR)
        self.screen.blit(t, t.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40)))
        if subtitle:
            s = self.font_med.render(subtitle, True, HUD_COLOR)
            self.screen.blit(s, s.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30)))

    # ------------------------------------------------------------------ #
    # Level-select screen                                                  #
    # ------------------------------------------------------------------ #

    _CARD_W      = 185
    _CARD_H      = 145
    _CARD_GAP    = 20
    _MAX_PER_ROW = 4

    def _level_card_rects(self) -> list:
        """Return list of (rect, level_idx) for all levels in a wrapping grid."""
        n       = len(LEVELS)
        per_row = min(self._MAX_PER_ROW, n)
        cards   = []
        y       = 120
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

    def draw_level_select(self, mouse_pos) -> None:
        title = self.font_large.render("Select Level", True, HUD_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 65)))

        for rect, li in self._level_card_rects():
            cfg     = LEVELS[li]
            hovered = rect.collidepoint(mouse_pos)
            fill    = (60, 60, 80) if hovered else (40, 40, 55)
            border  = (180, 180, 220) if hovered else (100, 100, 140)

            pygame.draw.rect(self.screen, fill,   rect, border_radius=10)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=10)

            name_surf = self.font_med.render(cfg["name"], True, HUD_COLOR)
            self.screen.blit(name_surf, name_surf.get_rect(center=(rect.centerx, rect.y + 32)))

            sub_surf = self.font_small.render(cfg.get("subtitle", ""), True, (180, 180, 180))
            self.screen.blit(sub_surf, sub_surf.get_rect(center=(rect.centerx, rect.y + 62)))

            balls_surf = self.font_small.render(f"{cfg['total_balls']} balls", True, (160, 200, 160))
            self.screen.blit(balls_surf, balls_surf.get_rect(center=(rect.centerx, rect.y + 92)))

            speed_surf = self.font_small.render(f"Speed: {int(cfg['chain_speed'])} px/s", True, (160, 160, 200))
            self.screen.blit(speed_surf, speed_surf.get_rect(center=(rect.centerx, rect.y + 116)))

        hint = self.font_small.render("ESC  ·  main menu", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18)))

    # ------------------------------------------------------------------ #
    # Main menu                                                            #
    # ------------------------------------------------------------------ #

    _MENU_BTN_W = 300
    _MENU_BTN_H = 58
    _MENU_BTN_GAP = 18
    _MENU_LABELS = ["PLAY", "SELECT LEVEL", "RECORDS", "QUIT"]

    def _main_menu_button_rects(self) -> list:
        n = len(self._MENU_LABELS)
        total_h = n * self._MENU_BTN_H + (n - 1) * self._MENU_BTN_GAP
        start_y = SCREEN_HEIGHT // 2 - total_h // 2 + 30
        x = (SCREEN_WIDTH - self._MENU_BTN_W) // 2
        return [
            pygame.Rect(x, start_y + i * (self._MENU_BTN_H + self._MENU_BTN_GAP),
                        self._MENU_BTN_W, self._MENU_BTN_H)
            for i in range(n)
        ]

    def main_menu_button_at(self, pos) -> "int | None":
        for i, rect in enumerate(self._main_menu_button_rects()):
            if rect.collidepoint(pos):
                return i
        return None

    def draw_main_menu(self, mouse_pos) -> None:
        title = self.font_large.render("POPLUX", True, (80, 210, 80))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 105)))

        rects = self._main_menu_button_rects()
        for i, (rect, label) in enumerate(zip(rects, self._MENU_LABELS)):
            hovered = rect.collidepoint(mouse_pos)
            fill   = (60, 100, 60) if hovered else (35, 60, 35)
            border = (100, 220, 100) if hovered else (55, 130, 55)
            pygame.draw.rect(self.screen, fill, rect, border_radius=10)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=10)
            txt = self.font_med.render(label, True, HUD_COLOR)
            self.screen.blit(txt, txt.get_rect(center=rect.center))

        hint = self.font_small.render("ESC to quit", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, 545)))

    # ------------------------------------------------------------------ #
    # Pause menu                                                           #
    # ------------------------------------------------------------------ #

    _PAUSE_BTN_W = 280
    _PAUSE_BTN_H = 54
    _PAUSE_BTN_GAP = 16
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
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        title = self.font_large.render("PAUSED", True, HUD_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 110)))

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
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 160)))

    # ------------------------------------------------------------------ #
    # Level-complete overlay                                               #
    # ------------------------------------------------------------------ #

    _LC_BTN_W = 240
    _LC_BTN_H = 52
    _LC_BTN_GAP = 20

    def _level_complete_button_rects(self) -> list:
        total_w = 2 * self._LC_BTN_W + self._LC_BTN_GAP
        x = (SCREEN_WIDTH - total_w) // 2
        y = SCREEN_HEIGHT // 2 + 55
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
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        t = self.font_large.render("LEVEL COMPLETE!", True, (100, 240, 100))
        self.screen.blit(t, t.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30)))

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
    # Cheat-code menu                                                      #
    # ------------------------------------------------------------------ #

    _CHEAT_INPUT_W = 360
    _CHEAT_INPUT_H = 52

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
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 90)))

        # Input box
        box_x = (SCREEN_WIDTH - self._CHEAT_INPUT_W) // 2
        box_y = 145
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

    _COL_X      = (55, 310, 460, 590, 720)   # #, Level, Score, Time, Date
    _COL_LABELS = ("#",  "LEVEL", "SCORE", "TIME", "DATE")
    _COL_ALIGN  = ("r",  "l",     "r",     "r",    "r")
    _ROW_H      = 26
    _TABLE_TOP  = 120

    def draw_records(self, records: list) -> None:
        title = self.font_large.render("RECORDS", True, HUD_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 50)))

        if not records:
            msg = self.font_med.render("No records yet — win a level to get started!", True, (160, 160, 160))
            self.screen.blit(msg, msg.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
            hint = self.font_small.render("ESC  ·  main menu", True, (120, 120, 120))
            self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18)))
            return

        # Header row
        header_y = self._TABLE_TOP
        for label, x, align in zip(self._COL_LABELS, self._COL_X, self._COL_ALIGN):
            surf = self.font_small.render(label, True, (180, 180, 100))
            rect = surf.get_rect(y=header_y)
            if align == "r":
                rect.right = x
            else:
                rect.left = x
            self.screen.blit(surf, rect)

        # Divider
        div_y = header_y + self.font_small.get_height() + 4
        pygame.draw.line(self.screen, (80, 80, 80), (40, div_y), (SCREEN_WIDTH - 40, div_y))

        # Data rows
        max_rows = (SCREEN_HEIGHT - div_y - 40) // self._ROW_H
        for row_i, rec in enumerate(records[:max_rows]):
            y = div_y + 6 + row_i * self._ROW_H
            shade = (22, 22, 30) if row_i % 2 == 0 else (0, 0, 0, 0)
            pygame.draw.rect(self.screen, shade,
                             pygame.Rect(40, y - 2, SCREEN_WIDTH - 80, self._ROW_H - 2))

            mins, secs = divmod(int(rec["time"]), 60)
            cells = (
                str(row_i + 1),
                rec["level"],
                str(rec["score"]),
                f"{mins}:{secs:02d}",
                rec["date"],
            )
            color = (255, 220, 50) if row_i == 0 else HUD_COLOR
            for cell, x, align in zip(cells, self._COL_X, self._COL_ALIGN):
                surf = self.font_small.render(cell, True, color)
                rect = surf.get_rect(y=y)
                if align == "r":
                    rect.right = x
                else:
                    rect.left = x
                self.screen.blit(surf, rect)

        hint = self.font_small.render("ESC  ·  main menu", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 18)))
