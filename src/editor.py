"""
Poplux level editor  —  run with:  python src/editor.py [levels/levelN.json]
"""
import sys
import os
import json
import math

sys.path.insert(0, os.path.dirname(__file__))

import pygame
import pygame.gfxdraw
from path import Path
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, BALL_RADIUS

# ── constants ────────────────────────────────────────────────────────────────

FPS        = 60
BG_COLOR   = (18, 18, 28)
PANEL_W    = 220   # fallback; actual sidebar width = screen_w - canvas_screen_w at runtime
CANVAS_W   = SCREEN_WIDTH
WINDOW_W   = SCREEN_WIDTH

WAYPOINT_R = 7
HIT_RADIUS = 18
FROG_R     = 12
COIN_R     = 10
AIM_R      = 10

C = {
    "wp":       (100, 200, 255),
    "wp_hov":   (255, 255, 100),
    "wp_drag":  (255, 140,  40),
    "frog":     ( 80, 220,  80),
    "coin":     (255, 210,  40),
    "aim":      (  0, 220, 255),
    "path":     ( 55,  55,  55),
    "text":     (220, 220, 220),
    "dim":      (120, 120, 120),
    "btn":      ( 50,  60,  80),
    "btn_hov":  ( 70,  90, 120),
    "btn_act":  ( 40, 120, 180),
    "sep":      ( 60,  60,  80),
    "panel":    (  0,   0,   0, 160),
    "item_hov": ( 40,  50,  70),
}

LEVELS_DIR = os.path.join(os.path.dirname(__file__), "levels")

# ── helpers ──────────────────────────────────────────────────────────────────

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def nearest_wp(waypoints, pos, max_d=HIT_RADIUS):
    best_i, best_d = None, max_d
    for i, wp in enumerate(waypoints):
        d = dist(wp, pos)
        if d < best_d:
            best_d, best_i = d, i
    return best_i

def next_filename():
    existing = sorted(f for f in os.listdir(LEVELS_DIR) if f.endswith(".json"))
    return os.path.join(LEVELS_DIR, f"level{len(existing) + 1}.json")

def aa_circle(surf, color, pos, r):
    x, y, r = int(pos[0]), int(pos[1]), max(0, int(r))
    pygame.gfxdraw.filled_circle(surf, x, y, r, color)
    pygame.gfxdraw.aacircle(surf, x, y, r, color)

def level_files():
    return sorted(f for f in os.listdir(LEVELS_DIR) if f.endswith(".json"))

# ── tiny widget helpers ───────────────────────────────────────────────────────

def draw_btn(screen, rect, label, font, hovered, active=False):
    col = C["btn_act"] if active else (C["btn_hov"] if hovered else C["btn"])
    pygame.draw.rect(screen, col, rect, border_radius=4)
    pygame.draw.rect(screen, C["sep"], rect, 1, border_radius=4)
    t = font.render(label, True, C["text"])
    screen.blit(t, t.get_rect(center=rect.center))

# placement modes
MODE_WP   = "waypoint"
MODE_FROG = "frog"
MODE_COIN = "coin"
MODE_AIM  = "aim"

# ── editor ───────────────────────────────────────────────────────────────────

class Editor:
    def __init__(self, load_path: str | None = None):
        self.waypoints:  list[tuple] = []
        self.frog_pos:   tuple | None = None
        self.coin_spots: list[tuple] = []
        self.aim_spots:  list[tuple] = []
        self.path: Path | None = None

        self.meta = {
            "name":        "New Level",
            "subtitle":    "",
            "chain_speed": 30.0,
            "total_balls": 50,
            "pre_placed":  15,
        }

        self.dragging_idx: int | None = None
        self.dragging_coin_idx: int | None = None
        self.dragging_aim_idx: int | None = None
        self.mode = MODE_WP          # current placement / interaction mode
        self.dropdown_open = False
        self._loaded_file: str | None = None

        self.filename         = ""
        self.filename_focused = False
        self._cursor_blink    = 0.0
        self._cursor_visible  = True

        self.status_msg   = ""
        self.status_timer = 0.0

        self._ui_hits: list[tuple] = []
        self._panel_w: int = PANEL_W
        self._sidebar_x: int = SCREEN_WIDTH - PANEL_W  # updated each frame by main loop

        self.font    = pygame.font.SysFont(None, 26)
        self.font_sm = pygame.font.SysFont(None, 21)
        self.font_lg = pygame.font.SysFont(None, 36)

        if load_path:
            self._load(load_path)

    # ── path ─────────────────────────────────────────────────────────────────

    def _rebuild_path(self):
        if len(self.waypoints) >= 2:
            try:
                self.path = Path({"waypoints": self.waypoints})
            except Exception:
                self.path = None
        else:
            self.path = None

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self, filepath: str):
        try:
            with open(filepath) as f:
                data = json.load(f)
            self.waypoints  = [tuple(p) for p in data.get("waypoints", [])]
            self.frog_pos   = tuple(data["frog_pos"]) if data.get("frog_pos") else None
            self.coin_spots = [tuple(p) for p in data.get("coin_spots", [])]
            self.aim_spots  = [tuple(p) for p in data.get("aim_powerup_spots", [])]
            for k in ("name", "subtitle", "chain_speed", "total_balls", "pre_placed"):
                if k in data:
                    self.meta[k] = data[k]
            self._rebuild_path()
            self._loaded_file = filepath
            self.filename      = os.path.splitext(os.path.basename(filepath))[0]
            self.dropdown_open = False
            self._set_status(f"Loaded: {os.path.basename(filepath)}")
        except Exception as e:
            self._set_status(f"Load failed: {e}")

    def _save(self, filepath: str | None = None):
        if len(self.waypoints) < 2:
            self._set_status("Need at least 2 waypoints to save.")
            return
        if filepath is None:
            if self.filename.strip():
                fname = self.filename.strip()
                if not fname.endswith(".json"):
                    fname += ".json"
                filepath = os.path.join(LEVELS_DIR, fname)
            else:
                filepath = self._loaded_file or next_filename()
        data = dict(self.meta)
        data["waypoints"] = [list(p) for p in self.waypoints]
        if self.frog_pos:
            data["frog_pos"] = list(self.frog_pos)
        if self.coin_spots:
            data["coin_spots"] = [list(p) for p in self.coin_spots]
        if self.aim_spots:
            data["aim_powerup_spots"] = [list(p) for p in self.aim_spots]
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
        self._loaded_file = filepath
        self._set_status(f"Saved → {os.path.basename(filepath)}")

    def _save_new(self):
        self._loaded_file = None
        self._save(next_filename())

    # ── status ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, dur: float = 3.0):
        self.status_msg   = msg
        self.status_timer = dur

    # ── input ────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            self._on_key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._on_mouse_down(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging_idx = None
                self.dragging_coin_idx = None
                self.dragging_aim_idx = None
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging_idx is not None and self.mode == MODE_WP:
                self.waypoints[self.dragging_idx] = event.pos
                self._rebuild_path()
            elif self.dragging_coin_idx is not None:
                self.coin_spots[self.dragging_coin_idx] = event.pos
            elif self.dragging_aim_idx is not None:
                self.aim_spots[self.dragging_aim_idx] = event.pos

    def _on_key(self, event):
        if self.filename_focused:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                self.filename_focused = False
            elif event.key == pygame.K_BACKSPACE:
                self.filename = self.filename[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.filename += event.unicode
            return

        if event.key == pygame.K_s:
            mods = pygame.key.get_mods()
            if mods & pygame.KMOD_SHIFT:
                self._save_new()
            else:
                self._save()
        elif event.key == pygame.K_f:
            self._set_mode(MODE_FROG)
        elif event.key == pygame.K_g:
            self._set_mode(MODE_COIN)
        elif event.key == pygame.K_a:
            self._set_mode(MODE_AIM)
        elif event.key == pygame.K_w:
            self._set_mode(MODE_WP)
        elif event.key == pygame.K_z:
            if self.mode == MODE_WP and self.waypoints:
                self.waypoints.pop()
                self._rebuild_path()
            elif self.mode == MODE_COIN and self.coin_spots:
                self.coin_spots.pop()
                self._set_status(f"Coin undone ({len(self.coin_spots)} total)", 1.5)
            elif self.mode == MODE_AIM and self.aim_spots:
                self.aim_spots.pop()
                self._set_status(f"Aim powerup undone ({len(self.aim_spots)} total)", 1.5)
        elif event.key == pygame.K_c:
            self.waypoints.clear()
            self.frog_pos = None
            self.coin_spots.clear()
            self.aim_spots.clear()
            self.path = None
            self._set_status("Cleared.")
        elif event.key == pygame.K_ESCAPE:
            if self.mode != MODE_WP:
                self._set_mode(MODE_WP)
            else:
                pygame.quit()
                sys.exit()

    def _set_mode(self, mode: str):
        self.mode = mode
        labels = {
            MODE_WP:   "Mode: Waypoints",
            MODE_FROG: "Mode: Place frog — click canvas",
            MODE_COIN: "Mode: Place coins — click to add, RClick to remove",
            MODE_AIM:  "Mode: Place aim powerups — click to add, RClick to remove",
        }
        self._set_status(labels[mode], 3.0)

    def _on_mouse_down(self, event):
        pos = event.pos

        # sidebar intercepts all clicks (use stored panel boundary)
        if pos[0] >= self._sidebar_x:
            if event.button == 1:
                for rect, cb in self._ui_hits:
                    if rect.collidepoint(pos):
                        cb()
                        return
                self.filename_focused = False
            return

        self.filename_focused = False

        if event.button == 1:
            if self.mode == MODE_FROG:
                self.frog_pos = pos
                self._set_mode(MODE_WP)
                self._set_status("Frog position set.")
            elif self.mode == MODE_COIN:
                idx = nearest_wp(self.coin_spots, pos, HIT_RADIUS * 1.5)
                if idx is not None:
                    self.dragging_coin_idx = idx
                else:
                    self.coin_spots.append(pos)
                    self._set_status(f"Coin added ({len(self.coin_spots)} total)", 1.5)
            elif self.mode == MODE_AIM:
                idx = nearest_wp(self.aim_spots, pos, HIT_RADIUS * 1.5)
                if idx is not None:
                    self.dragging_aim_idx = idx
                else:
                    self.aim_spots.append(pos)
                    self._set_status(f"Aim powerup added ({len(self.aim_spots)} total)", 1.5)
            else:  # MODE_WP
                idx = nearest_wp(self.waypoints, pos)
                if idx is not None:
                    self.dragging_idx = idx
                else:
                    self.waypoints.append(pos)
                    self._rebuild_path()

        elif event.button == 3:
            if self.mode == MODE_COIN:
                idx = nearest_wp(self.coin_spots, pos, HIT_RADIUS * 1.5)
                if idx is not None:
                    self.coin_spots.pop(idx)
                    self._set_status(f"Coin removed ({len(self.coin_spots)} total)", 1.5)
            elif self.mode == MODE_AIM:
                idx = nearest_wp(self.aim_spots, pos, HIT_RADIUS * 1.5)
                if idx is not None:
                    self.aim_spots.pop(idx)
                    self._set_status(f"Aim powerup removed ({len(self.aim_spots)} total)", 1.5)
            else:  # MODE_WP
                idx = nearest_wp(self.waypoints, pos)
                if idx is not None:
                    self.waypoints.pop(idx)
                    self._rebuild_path()

    # ── update ───────────────────────────────────────────────────────────────

    def update(self, dt: float):
        if self.status_timer > 0:
            self.status_timer = max(0.0, self.status_timer - dt)
        self._cursor_blink += dt
        if self._cursor_blink >= 0.5:
            self._cursor_blink    -= 0.5
            self._cursor_visible   = not self._cursor_visible

    # ── render ───────────────────────────────────────────────────────────────

    def draw(self, canvas: pygame.Surface, screen: pygame.Surface,
             canvas_rect: pygame.Rect, logical_mouse: tuple,
             screen_mouse: tuple) -> None:
        """Draw the editor.

        canvas      — logical 1280×960 surface (scaled & blitted to screen by caller)
        screen      — the real display surface (sidebar drawn here in screen-space)
        canvas_rect — where the canvas sits on screen (Rect)
        logical_mouse  — mouse pos in logical canvas coordinates
        screen_mouse   — mouse pos in raw screen coordinates
        """
        canvas.fill(BG_COLOR)
        self._ui_hits = []   # reset; rebuilt by _draw_sidebar in screen space

        self._draw_path(canvas)
        self._draw_coins(canvas)
        self._draw_aim_spots(canvas)
        self._draw_waypoints(canvas, logical_mouse)
        self._draw_frog(canvas)
        self._draw_overlays(canvas)

        # sidebar lives in screen space (right of the canvas)
        sidebar_x = canvas_rect.right
        sidebar_w = screen.get_width() - sidebar_x
        if sidebar_w > 0:
            self._draw_sidebar(screen, screen_mouse, sidebar_x, sidebar_w)

    # ── canvas drawing ───────────────────────────────────────────────────────

    def _draw_path(self, screen):
        if self.path and len(self.path.waypoints) >= 2:
            col = C["path"]
            pts = [(int(x), int(y)) for x, y in self.path.waypoints]
            pygame.draw.lines(screen, col, False, pts, BALL_RADIUS * 2)
            for p in pts:
                aa_circle(screen, col, p, BALL_RADIUS)
            hx, hy = pts[-1]
            aa_circle(screen, (10, 10, 10), (hx, hy), BALL_RADIUS + 4)
            pygame.gfxdraw.aacircle(screen, hx, hy, BALL_RADIUS + 4, (150, 50, 50))

    def _draw_waypoints(self, screen, mouse):
        for i, wp in enumerate(self.waypoints):
            if i == self.dragging_idx:
                col = C["wp_drag"]
            elif dist(wp, mouse) < HIT_RADIUS:
                col = C["wp_hov"]
            else:
                col = C["wp"]
            aa_circle(screen, col, wp, WAYPOINT_R)
            lbl = self.font_sm.render(str(i), True, col)
            screen.blit(lbl, (wp[0] + WAYPOINT_R + 2, wp[1] - 8))

    def _draw_frog(self, screen):
        if self.frog_pos:
            x, y = int(self.frog_pos[0]), int(self.frog_pos[1])
            aa_circle(screen, C["frog"], (x, y), FROG_R)
            aa_circle(screen, BG_COLOR,  (x, y), FROG_R - 4)
            lbl = self.font_sm.render("FROG", True, C["frog"])
            screen.blit(lbl, (x + FROG_R + 3, y - 8))

    def _draw_coins(self, screen):
        for i, pos in enumerate(self.coin_spots):
            x, y = int(pos[0]), int(pos[1])
            aa_circle(screen, C["coin"], (x, y), COIN_R)
            aa_circle(screen, BG_COLOR,  (x, y), COIN_R - 4)
            lbl = self.font_sm.render(f"${i}", True, C["coin"])
            screen.blit(lbl, (x + COIN_R + 2, y - 7))

    def _draw_aim_spots(self, screen):
        for i, pos in enumerate(self.aim_spots):
            x, y = int(pos[0]), int(pos[1])
            r = AIM_R
            # crosshair
            pygame.draw.line(screen, C["aim"], (x - r, y), (x + r, y), 1)
            pygame.draw.line(screen, C["aim"], (x, y - r), (x, y + r), 1)
            pygame.gfxdraw.aacircle(screen, x, y, r, C["aim"])
            lbl = self.font_sm.render(f"A{i}", True, C["aim"])
            screen.blit(lbl, (x + r + 2, y - 7))

    # ── sidebar ──────────────────────────────────────────────────────────────

    def _draw_sidebar(self, screen, mouse, px: int, panel_w: int):
        self._panel_w  = panel_w   # used by _hline / _stepper helpers
        self._sidebar_x = px
        sh = screen.get_height()
        panel = pygame.Surface((panel_w, sh), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 230))
        screen.blit(panel, (px, 0))

        cx = px + panel_w // 2
        y  = 10

        # title
        t = self.font_lg.render("EDITOR", True, (100, 200, 255))
        screen.blit(t, t.get_rect(centerx=cx, top=y))
        y += t.get_height() + 8

        self._hline(screen, px, y); y += 6

        # load level dropdown
        label = self.font_sm.render("LOAD LEVEL", True, C["dim"])
        screen.blit(label, (px + 8, y))
        y += label.get_height() + 4

        files = level_files()
        arrow = "▲" if self.dropdown_open else "▼"
        dd_label = self._loaded_file and os.path.basename(self._loaded_file) or "select…"
        dd_rect = pygame.Rect(px + 6, y, panel_w - 12, 24)
        hov = dd_rect.collidepoint(mouse)
        pygame.draw.rect(screen, C["btn_hov"] if hov else C["btn"], dd_rect, border_radius=4)
        pygame.draw.rect(screen, C["sep"], dd_rect, 1, border_radius=4)
        txt = self.font_sm.render(dd_label, True, C["text"])
        screen.blit(txt, txt.get_rect(midleft=(dd_rect.x + 6, dd_rect.centery)))
        atxt = self.font_sm.render(arrow, True, C["dim"])
        screen.blit(atxt, atxt.get_rect(midright=(dd_rect.right - 5, dd_rect.centery)))
        self._ui_hits.append((dd_rect, self._toggle_dropdown))
        y += 28

        if self.dropdown_open and files:
            for fname in files:
                item_rect = pygame.Rect(px + 6, y, panel_w - 12, 22)
                hov = item_rect.collidepoint(mouse)
                if hov:
                    pygame.draw.rect(screen, C["item_hov"], item_rect, border_radius=3)
                active = self._loaded_file and os.path.basename(self._loaded_file) == fname
                col = (100, 220, 100) if active else C["text"]
                ft = self.font_sm.render(fname, True, col)
                screen.blit(ft, ft.get_rect(midleft=(item_rect.x + 6, item_rect.centery)))
                fpath = os.path.join(LEVELS_DIR, fname)
                self._ui_hits.append((item_rect, lambda p=fpath: self._load(p)))
                y += 24

        self._hline(screen, px, y); y += 8

        # stats
        self._row(screen, px, y, f"Waypoints:  {len(self.waypoints)}"); y += 18
        pl = f"{int(self.path.total_length)} px" if self.path else "--"
        self._row(screen, px, y, f"Path length: {pl}"); y += 18
        fp = "set" if self.frog_pos else "unset"
        self._row(screen, px, y, f"Frog pos:  {fp}", C["frog"]); y += 18
        self._row(screen, px, y, f"Coins:  {len(self.coin_spots)}", C["coin"]); y += 18
        self._row(screen, px, y, f"Aim spots:  {len(self.aim_spots)}", C["aim"]); y += 18

        self._hline(screen, px, y); y += 8

        # mode buttons
        self._row(screen, px, y, "MODE", C["dim"]); y += 18
        modes = [
            (MODE_WP,   "W  Waypoints",  C["wp"]),
            (MODE_FROG, "F  Frog",       C["frog"]),
            (MODE_COIN, "G  Coins",      C["coin"]),
            (MODE_AIM,  "A  Aim pwrup",  C["aim"]),
        ]
        for mode_key, label, col in modes:
            active = self.mode == mode_key
            r = pygame.Rect(px + 6, y, panel_w - 12, 22)
            bg = (30, 60, 30) if active else C["btn"]
            border = col if active else C["sep"]
            pygame.draw.rect(screen, bg, r, border_radius=4)
            pygame.draw.rect(screen, border, r, 1, border_radius=4)
            t = self.font_sm.render(label, True, col if active else C["text"])
            screen.blit(t, t.get_rect(midleft=(r.x + 6, r.centery)))
            self._ui_hits.append((r, lambda m=mode_key: self._set_mode(m)))
            y += 26

        self._hline(screen, px, y); y += 8

        # meta controls
        self._row(screen, px, y, "SETTINGS", C["dim"]); y += 18

        y = self._stepper(screen, mouse, px, y,
                          "Speed (px/s)",
                          self.meta["chain_speed"],
                          lambda: self._adjust("chain_speed", -5.0, 5.0, 600.0),
                          lambda: self._adjust("chain_speed",  5.0, 5.0, 600.0),
                          fmt=lambda v: f"{int(v)}")
        y = self._stepper(screen, mouse, px, y,
                          "Total balls",
                          self.meta["total_balls"],
                          lambda: self._adjust("total_balls", -5, 1, 500),
                          lambda: self._adjust("total_balls",  5, 1, 500))
        y = self._stepper(screen, mouse, px, y,
                          "Pre-placed",
                          self.meta["pre_placed"],
                          lambda: self._adjust("pre_placed", -1, 0, self.meta["total_balls"]),
                          lambda: self._adjust("pre_placed",  1, 0, self.meta["total_balls"]))

        self._hline(screen, px, y); y += 8

        # filename input
        lbl = self.font_sm.render("Filename (.json)", True, C["dim"])
        screen.blit(lbl, (px + 8, y)); y += lbl.get_height() + 3

        fn_rect = pygame.Rect(px + 6, y, panel_w - 12, 24)
        border_col = (100, 160, 220) if self.filename_focused else C["sep"]
        pygame.draw.rect(screen, (20, 24, 36), fn_rect, border_radius=4)
        pygame.draw.rect(screen, border_col,   fn_rect, 1, border_radius=4)

        display_text = self.filename or ""
        cursor_str   = "|" if (self.filename_focused and self._cursor_visible) else ""
        ft = self.font_sm.render(display_text + cursor_str, True,
                                 C["text"] if self.filename else C["dim"])
        if not self.filename and not self.filename_focused:
            ft = self.font_sm.render("auto", True, C["dim"])
        screen.blit(ft, ft.get_rect(midleft=(fn_rect.x + 6, fn_rect.centery)))

        self._ui_hits.append((fn_rect, self._focus_filename))
        y += fn_rect.height + 8

        # save buttons
        bw = (panel_w - 18) // 2
        save_r  = pygame.Rect(px + 6,            y, bw, 26)
        savew_r = pygame.Rect(px + 6 + bw + 6,   y, bw, 26)
        draw_btn(screen, save_r,  "Save",     self.font_sm, save_r.collidepoint(mouse))
        draw_btn(screen, savew_r, "Save New", self.font_sm, savew_r.collidepoint(mouse))
        self._ui_hits.append((save_r,  self._save))
        self._ui_hits.append((savew_r, self._save_new))
        y += 32

        # controls reference
        self._hline(screen, px, y); y += 6
        for line in ("LClick  add / drag",
                     "RClick  delete item",
                     "Z       undo last wp",
                     "S       save",
                     "Shift+S  save new",
                     "C       clear all",
                     "ESC     mode → wp / quit"):
            self._row(screen, px, y, line, C["dim"]); y += 16

    # ── sidebar helpers ───────────────────────────────────────────────────────

    def _hline(self, screen, px, y):
        pygame.draw.line(screen, C["sep"], (px + 4, y), (px + self._panel_w - 4, y))

    def _row(self, screen, px, y, text, color=None):
        color = color or C["text"]
        s = self.font_sm.render(text, True, color)
        screen.blit(s, (px + 8, y))

    def _stepper(self, screen, mouse, px, y, label, value, dec_cb, inc_cb, fmt=str):
        lbl = self.font_sm.render(label, True, C["dim"])
        screen.blit(lbl, (px + 8, y))
        y += lbl.get_height() + 2

        bsz = 22
        gap = 4
        val_w = self._panel_w - bsz * 2 - gap * 4 - 16
        dec_r = pygame.Rect(px + 8,           y, bsz, bsz)
        val_r = pygame.Rect(dec_r.right + gap, y, val_w, bsz)
        inc_r = pygame.Rect(val_r.right + gap, y, bsz, bsz)

        draw_btn(screen, dec_r, "−", self.font, dec_r.collidepoint(mouse))
        draw_btn(screen, inc_r, "+", self.font, inc_r.collidepoint(mouse))

        pygame.draw.rect(screen, (25, 28, 40), val_r, border_radius=3)
        vt = self.font_sm.render(fmt(value), True, C["text"])
        screen.blit(vt, vt.get_rect(center=val_r.center))

        self._ui_hits.append((dec_r, dec_cb))
        self._ui_hits.append((inc_r, inc_cb))

        return y + bsz + 8

    def _adjust(self, key, delta, lo, hi):
        self.meta[key] = max(lo, min(hi, self.meta[key] + delta))

    def _toggle_dropdown(self):
        self.dropdown_open = not self.dropdown_open

    def _focus_filename(self):
        self.filename_focused = True
        self._cursor_visible  = True
        self._cursor_blink    = 0.0

    # ── overlays ─────────────────────────────────────────────────────────────

    def _draw_overlays(self, screen):
        mode_labels = {
            MODE_FROG: ("Place FROG — click canvas", C["frog"]),
            MODE_COIN: ("Place COIN — LClick add  RClick remove", C["coin"]),
            MODE_AIM:  ("Place AIM POWERUP — LClick add  RClick remove", C["aim"]),
        }
        if self.mode in mode_labels:
            msg, col = mode_labels[self.mode]
            surf = self.font.render(msg, True, col)
            screen.blit(surf, surf.get_rect(center=(CANVAS_W // 2, 28)))

        if len(self.waypoints) < 2:
            hint = self.font.render("Click on the canvas to place waypoints", True, C["dim"])
            screen.blit(hint, hint.get_rect(center=(CANVAS_W // 2, SCREEN_HEIGHT // 2)))

        if self.status_msg and self.status_timer > 0:
            alpha = min(255, int(self.status_timer / 0.4 * 255))
            surf  = self.font.render(self.status_msg, True, (255, 230, 80))
            surf.set_alpha(alpha)
            screen.blit(surf, surf.get_rect(center=(CANVAS_W // 2, SCREEN_HEIGHT - 28)))


# ── main ─────────────────────────────────────────────────────────────────────

def _canvas_layout(screen):
    """Return (scale, canvas_rect) so the 1280×960 canvas fills the screen height,
    left-anchored, with any remaining width available for the sidebar."""
    _, sh = screen.get_size()
    scale  = sh / SCREEN_HEIGHT          # fit to height exactly
    cw     = int(SCREEN_WIDTH  * scale)
    ch     = int(SCREEN_HEIGHT * scale)
    return scale, pygame.Rect(0, 0, cw, ch)

def _logical_pos(screen_pos, scale):
    lx = int(screen_pos[0] / scale)
    ly = int(screen_pos[1] / scale)
    return (max(0, min(SCREEN_WIDTH, lx)), max(0, min(SCREEN_HEIGHT, ly)))

def _remap_event(event, scale):
    if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
        d = event.__dict__.copy()
        d["pos"] = _logical_pos(event.pos, scale)
        return pygame.event.Event(event.type, d)
    return event

def main():
    pygame.init()
    screen  = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    logical = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Poplux — Level Editor")
    clock   = pygame.time.Clock()

    load_path = sys.argv[1] if len(sys.argv) > 1 else None
    editor    = Editor(load_path)

    while True:
        dt = clock.tick(FPS) / 1000.0
        scale, canvas_rect = _canvas_layout(screen)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            editor.handle_event(_remap_event(event, scale))

        editor.update(dt)

        screen_mouse  = pygame.mouse.get_pos()
        logical_mouse = _logical_pos(screen_mouse, scale)

        screen.fill((10, 10, 18))
        editor.draw(logical, screen, canvas_rect, logical_mouse, screen_mouse)
        screen.blit(pygame.transform.smoothscale(logical, canvas_rect.size), (0, 0))
        pygame.display.flip()


if __name__ == "__main__":
    main()
