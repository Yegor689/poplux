import math
import pygame
import pygame.gfxdraw
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, BALL_COLORS, BG_COLOR, PATH_COLOR,
    FROG_COLOR, HOLE_COLOR, HUD_COLOR, BALL_RADIUS, LEVELS,
)


class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_large = pygame.font.SysFont(None, 72)
        self.font_med = pygame.font.SysFont(None, 36)
        self.font_small = pygame.font.SysFont(None, 28)
        self.font_score = pygame.font.SysFont(None, 48, bold=True)

    def clear(self) -> None:
        self.screen.fill(BG_COLOR)

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

    def _ball_color(self, color_name: str) -> tuple:
        return BALL_COLORS.get(color_name, (200, 200, 200))

    def _draw_ball(self, surface: pygame.Surface, color_name: str, cx: int, cy: int, radius: int,
                   spin_angle: float = 0.0, tangent: float = 0.0) -> None:
        color = self._ball_color(color_name)
        dark  = tuple(max(0,   c - 70) for c in color)
        mid   = tuple(min(255, c + 30) for c in color)
        light = tuple(min(255, c + 80) for c in color)
        seam  = tuple(max(0,   c - 55) for c in color)

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

    def draw_chain(self, chain, path) -> None:
        for ball in chain.balls:
            cx, cy = path.point_at(ball.path_distance + ball.path_offset)
            if ball.entry_t < 1.0:
                # ease-out: decelerate into the chain position
                t = 1.0 - (1.0 - ball.entry_t) ** 2
                cx = ball.entry_x + (cx - ball.entry_x) * t
                cy = ball.entry_y + (cy - ball.entry_y) * t
            tangent = path.direction_at(ball.path_distance)
            spin = ball.path_distance / ball.radius
            self._draw_ball(self.screen, ball.color, int(cx), int(cy), ball.radius,
                            spin, tangent)

    def draw_particles(self, particles: list) -> None:
        for p in particles:
            r = max(1, int(p.radius * p.t))
            self._aa_circle(self.screen, p.color, (int(p.x), int(p.y)), r)

    def draw_fired_balls(self, fired_balls: list) -> None:
        for ball in fired_balls:
            if ball.active:
                self._draw_ball(self.screen, ball.color, int(ball.x), int(ball.y), ball.radius)

    def draw_frog(self, frog) -> None:
        cx = int(frog.x - math.cos(frog.angle) * frog.recoil)
        cy = int(frog.y - math.sin(frog.angle) * frog.recoil)
        angle  = frog.angle
        perp   = angle + math.pi / 2
        R = BALL_RADIUS * 2  # body radius

        # --- Feet (drawn behind body) ---
        foot_angles = [angle + math.pi * 0.55, angle - math.pi * 0.55,
                       angle + math.pi * 0.85, angle - math.pi * 0.85]
        for fa in foot_angles:
            fx = cx + int(math.cos(fa) * R * 0.95)
            fy = cy + int(math.sin(fa) * R * 0.95)
            self._aa_circle(self.screen, (20, 100, 50), (fx, fy), 9)
            self._aa_circle(self.screen, (30, 140, 70), (fx, fy), 7)

        # --- Body layers ---
        self._aa_circle(self.screen, (18, 100, 52),  (cx, cy), R + 2)      # dark rim / shadow
        self._aa_circle(self.screen, (39, 174, 96),  (cx, cy), R)           # main body
        # Underbelly — lighter oval toward the front
        bx = cx + int(math.cos(angle) * 5)
        by = cy + int(math.sin(angle) * 5)
        self._aa_circle(self.screen, (140, 215, 155), (bx, by), R // 2)
        # Sheen highlight — top-left of body
        hx = cx + int(math.cos(angle - 2.4) * (R * 0.45))
        hy = cy + int(math.sin(angle - 2.4) * (R * 0.45))
        self._aa_circle(self.screen, (90, 210, 130), (hx, hy), R // 3)

        # --- Nostrils ---
        for side in (-1, 1):
            nx2 = cx + int(math.cos(angle) * (R * 0.65) + math.cos(perp) * side * 5)
            ny2 = cy + int(math.sin(angle) * (R * 0.65) + math.sin(perp) * side * 5)
            self._aa_circle(self.screen, (18, 100, 52), (nx2, ny2), 2)

        # --- Eyes (bulging on stalks) ---
        for side in (-1, 1):
            ex = cx + int(math.cos(angle) * (R * 0.35) + math.cos(perp) * side * (R * 0.65))
            ey = cy + int(math.sin(angle) * (R * 0.35) + math.sin(perp) * side * (R * 0.65))
            self._aa_circle(self.screen, (18, 100, 52),   (ex, ey), 9)     # stalk base
            self._aa_circle(self.screen, (220, 210, 170), (ex, ey), 8)     # sclera
            self._aa_circle(self.screen, (170, 130, 20),  (ex, ey), 5)     # gold iris
            self._aa_circle(self.screen, (10,  10,  10),  (ex, ey), 3)     # pupil
            self._aa_circle(self.screen, (255, 255, 255), (ex - 2, ey - 2), 1)  # glint

        # --- Current ball at mouth ---
        mouth_dist = R + BALL_RADIUS + 4
        mx = cx + int(math.cos(angle) * mouth_dist)
        my = cy + int(math.sin(angle) * mouth_dist)
        self._draw_ball(self.screen, frog.current_ball.color, mx, my, frog.current_ball.radius)

        # --- Next ball behind frog (smaller) ---
        next_dist = R + BALL_RADIUS
        nx = cx - int(math.cos(angle) * next_dist)
        ny = cy - int(math.sin(angle) * next_dist)
        self._draw_ball(self.screen, frog.next_ball.color, nx, ny, int(frog.next_ball.radius * 0.7))

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

    _BTN_W = 250
    _BTN_H = 200
    _BTN_GAP = 40
    _BTN_Y = 200

    def _level_button_rects(self) -> list:
        total_w = len(LEVELS) * self._BTN_W + (len(LEVELS) - 1) * self._BTN_GAP
        start_x = (SCREEN_WIDTH - total_w) // 2
        rects = []
        for i in range(len(LEVELS)):
            x = start_x + i * (self._BTN_W + self._BTN_GAP)
            rects.append(pygame.Rect(x, self._BTN_Y, self._BTN_W, self._BTN_H))
        return rects

    def level_button_at(self, pos) -> "int | None":
        for i, rect in enumerate(self._level_button_rects()):
            if rect.collidepoint(pos):
                return i
        return None

    def draw_level_select(self, mouse_pos) -> None:
        self.screen.fill(BG_COLOR)

        # Title
        title = self.font_large.render("Select Level", True, HUD_COLOR)
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 110)))

        rects = self._level_button_rects()
        for i, (rect, cfg) in enumerate(zip(rects, LEVELS)):
            hovered = rect.collidepoint(mouse_pos)
            fill = (60, 60, 80) if hovered else (40, 40, 55)
            border = (180, 180, 220) if hovered else (100, 100, 140)

            pygame.draw.rect(self.screen, fill, rect, border_radius=12)
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=12)

            # Level name
            name_surf = self.font_med.render(cfg["name"], True, HUD_COLOR)
            self.screen.blit(name_surf, name_surf.get_rect(
                center=(rect.centerx, rect.y + 40)))

            # Subtitle
            sub_surf = self.font_small.render(cfg["subtitle"], True, (180, 180, 180))
            self.screen.blit(sub_surf, sub_surf.get_rect(
                center=(rect.centerx, rect.y + 80)))

            # Balls count
            balls_surf = self.font_small.render(
                f"{cfg['total_balls']} balls", True, (160, 200, 160))
            self.screen.blit(balls_surf, balls_surf.get_rect(
                center=(rect.centerx, rect.y + 120)))

            # Speed
            speed_surf = self.font_small.render(
                f"Speed: {int(cfg['chain_speed'])} px/s", True, (160, 160, 200))
            self.screen.blit(speed_surf, speed_surf.get_rect(
                center=(rect.centerx, rect.y + 155)))

        # Hint
        hint = self.font_small.render("ESC  ·  main menu", True, (120, 120, 120))
        self.screen.blit(hint, hint.get_rect(center=(SCREEN_WIDTH // 2, 540)))

    # ------------------------------------------------------------------ #
    # Main menu                                                            #
    # ------------------------------------------------------------------ #

    _MENU_BTN_W = 300
    _MENU_BTN_H = 58
    _MENU_BTN_GAP = 18
    _MENU_LABELS = ["PLAY", "SELECT LEVEL", "QUIT"]

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
        self.screen.fill(BG_COLOR)

        title = self.font_large.render("POPLUX", True, (80, 210, 80))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 170)))

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
