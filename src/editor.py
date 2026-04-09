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
from path import Path, _PATH_SCALE_X, _PATH_SCALE_Y, _PATH_X_OFFSET
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

def to_screen(pos):
    """Convert authored (1280×960) coordinates to logical screen coordinates."""
    return (pos[0] * _PATH_SCALE_X + _PATH_X_OFFSET, pos[1] * _PATH_SCALE_Y)

def from_screen(pos):
    """Convert logical screen coordinates back to authored (1280×960) coordinates."""
    return ((pos[0] - _PATH_X_OFFSET) / _PATH_SCALE_X, pos[1] / _PATH_SCALE_Y)

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def nearest_segment(waypoints, pos):
    """Return the index to insert AFTER (0-based) so the new point splits the
    nearest segment.  Returns len(waypoints)-1 (append) when < 2 points exist."""
    if len(waypoints) < 2:
        return len(waypoints) - 1
    best_i, best_d = 0, float("inf")
    px, py = pos
    for i in range(len(waypoints) - 1):
        ax, ay = waypoints[i]
        bx, by = waypoints[i + 1]
        # closest point on segment AB to P
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy + 1e-9)))
        cx, cy = ax + t * dx, ay + t * dy
        d = math.hypot(px - cx, py - cy)
        if d < best_d:
            best_d, best_i = d, i
    return best_i

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
MODE_WP     = "waypoint"   # drag existing waypoints
MODE_EXTEND = "extend"     # append to end of path
MODE_INSERT = "insert"     # insert into nearest segment
MODE_FROG   = "frog"
MODE_COIN   = "coin"
MODE_AIM    = "aim"

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
        self._undo_stack: list[dict] = []   # snapshots for undo
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
        self._sidebar_x: int = SCREEN_WIDTH  # canvas ends here; sidebar starts

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

    # ── undo ─────────────────────────────────────────────────────────────────

    def _snapshot(self):
        self._undo_stack.append({
            "waypoints":  list(self.waypoints),
            "coin_spots": list(self.coin_spots),
            "aim_spots":  list(self.aim_spots),
            "frog_pos":   self.frog_pos,
        })
        if len(self._undo_stack) > 64:
            self._undo_stack.pop(0)

    def _undo(self):
        if not self._undo_stack:
            self._set_status("Nothing to undo.", 1.5)
            return
        state = self._undo_stack.pop()
        self.waypoints  = state["waypoints"]
        self.coin_spots = state["coin_spots"]
        self.aim_spots  = state["aim_spots"]
        self.frog_pos   = state["frog_pos"]
        self._rebuild_path()
        self._set_status("Undone.", 1.5)

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
            apos = from_screen(event.pos)
            if self.dragging_idx is not None and self.mode == MODE_WP:
                self.waypoints[self.dragging_idx] = apos
                self._rebuild_path()
            elif self.dragging_coin_idx is not None:
                self.coin_spots[self.dragging_coin_idx] = apos
            elif self.dragging_aim_idx is not None:
                self.aim_spots[self.dragging_aim_idx] = apos

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
        elif event.key == pygame.K_e:
            self._set_mode(MODE_EXTEND)
        elif event.key == pygame.K_i:
            self._set_mode(MODE_INSERT)
        elif event.key == pygame.K_z:
            self._undo()
        elif event.key == pygame.K_c:
            self._snapshot()
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
            MODE_WP:     "Mode: Drag waypoints",
            MODE_EXTEND: "Mode: Extend — click to append to end",
            MODE_INSERT: "Mode: Insert — click to split nearest segment",
            MODE_FROG:   "Mode: Place frog — click canvas",
            MODE_COIN:   "Mode: Place coins — click to add, RClick to remove",
            MODE_AIM:    "Mode: Place aim powerups — click to add, RClick to remove",
        }
        self._set_status(labels[mode], 3.0)

    def _on_mouse_down(self, event):
        pos = event.pos

        # Sidebar events arrive in screen-space; canvas events in logical-space.
        # A click in the sidebar has pos[0] >= _sidebar_x (screen coords).
        # A click on the canvas has pos[0] < SCREEN_WIDTH (logical coords, 0-1280).
        # We distinguish them: if _sidebar_x is stored (screen-space) and pos came
        # from the sidebar path, pos[0] will be >= _sidebar_x. Canvas logical coords
        # are always < SCREEN_WIDTH (1280), while _sidebar_x > SCREEN_WIDTH when scaled.
        in_sidebar = pos[0] >= self._sidebar_x
        if in_sidebar:
            if event.button == 1:
                for rect, cb in self._ui_hits:
                    if rect.collidepoint(pos):
                        cb()
                        return
                self.filename_focused = False
            return

        self.filename_focused = False

        # Convert screen-space click to authored space for all canvas operations
        apos = from_screen(pos)

        if event.button == 1:
            if self.mode == MODE_FROG:
                self._snapshot()
                self.frog_pos = apos
                self._set_mode(MODE_WP)
                self._set_status("Frog position set.")
            elif self.mode == MODE_COIN:
                idx = nearest_wp(self.coin_spots, apos, HIT_RADIUS * 1.5)
                if idx is not None:
                    self._snapshot()
                    self.dragging_coin_idx = idx
                else:
                    self._snapshot()
                    self.coin_spots.append(apos)
                    self._set_status(f"Coin added ({len(self.coin_spots)} total)", 1.5)
            elif self.mode == MODE_AIM:
                idx = nearest_wp(self.aim_spots, apos, HIT_RADIUS * 1.5)
                if idx is not None:
                    self._snapshot()
                    self.dragging_aim_idx = idx
                else:
                    self._snapshot()
                    self.aim_spots.append(apos)
                    self._set_status(f"Aim powerup added ({len(self.aim_spots)} total)", 1.5)
            elif self.mode == MODE_EXTEND:
                self._snapshot()
                self.waypoints.append(apos)
                self._rebuild_path()
            elif self.mode == MODE_INSERT:
                self._snapshot()
                insert_after = nearest_segment(self.waypoints, apos)
                self.waypoints.insert(insert_after + 1, apos)
                self._rebuild_path()
            else:  # MODE_WP — drag only
                idx = nearest_wp(self.waypoints, apos)
                if idx is not None:
                    self._snapshot()
                    self.dragging_idx = idx

        elif event.button == 3:
            if self.mode == MODE_COIN:
                idx = nearest_wp(self.coin_spots, apos, HIT_RADIUS * 1.5)
                if idx is not None:
                    self._snapshot()
                    self.coin_spots.pop(idx)
                    self._set_status(f"Coin removed ({len(self.coin_spots)} total)", 1.5)
            elif self.mode == MODE_AIM:
                idx = nearest_wp(self.aim_spots, apos, HIT_RADIUS * 1.5)
                if idx is not None:
                    self._snapshot()
                    self.aim_spots.pop(idx)
                    self._set_status(f"Aim powerup removed ({len(self.aim_spots)} total)", 1.5)
            elif self.mode in (MODE_WP, MODE_EXTEND, MODE_INSERT):
                idx = nearest_wp(self.waypoints, apos)
                if idx is not None:
                    self._snapshot()
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

    def draw(self, screen: pygame.Surface, mouse: tuple) -> None:
        """Draw canvas content directly to screen."""
        # Only clear the canvas area, not the sidebar
        pygame.draw.rect(screen, BG_COLOR, (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        self._ui_hits = []
        self._draw_path(screen)
        self._draw_coins(screen)
        self._draw_aim_spots(screen)
        self._draw_waypoints(screen, mouse)
        self._draw_frog(screen)
        self._draw_overlays(screen)

    def draw_sidebar(self, screen: pygame.Surface, screen_mouse: tuple,
                     sidebar_x: int, sidebar_w: int) -> None:
        """Draw sidebar at sidebar_x on screen. screen_mouse must be in screen space."""
        self._sidebar_x = sidebar_x  # used by _on_mouse_down in screen space
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
            sp = to_screen(wp)
            if i == self.dragging_idx:
                col = C["wp_drag"]
            elif dist(sp, mouse) < HIT_RADIUS:
                col = C["wp_hov"]
            else:
                col = C["wp"]
            aa_circle(screen, col, sp, WAYPOINT_R)
            lbl = self.font_sm.render(str(i), True, col)
            screen.blit(lbl, (sp[0] + WAYPOINT_R + 2, sp[1] - 8))

    def _draw_frog(self, screen):
        if self.frog_pos:
            x, y = to_screen(self.frog_pos)
            x, y = int(x), int(y)
            aa_circle(screen, C["frog"], (x, y), FROG_R)
            aa_circle(screen, BG_COLOR,  (x, y), FROG_R - 4)
            lbl = self.font_sm.render("FROG", True, C["frog"])
            screen.blit(lbl, (x + FROG_R + 3, y - 8))

    def _draw_coins(self, screen):
        for i, pos in enumerate(self.coin_spots):
            x, y = to_screen(pos)
            x, y = int(x), int(y)
            aa_circle(screen, C["coin"], (x, y), COIN_R)
            aa_circle(screen, BG_COLOR,  (x, y), COIN_R - 4)
            lbl = self.font_sm.render(f"${i}", True, C["coin"])
            screen.blit(lbl, (x + COIN_R + 2, y - 7))

    def _draw_aim_spots(self, screen):
        for i, pos in enumerate(self.aim_spots):
            x, y = to_screen(pos)
            x, y = int(x), int(y)
            r = AIM_R
            pygame.draw.line(screen, C["aim"], (x - r, y), (x + r, y), 1)
            pygame.draw.line(screen, C["aim"], (x, y - r), (x, y + r), 1)
            pygame.gfxdraw.aacircle(screen, x, y, r, C["aim"])
            lbl = self.font_sm.render(f"A{i}", True, C["aim"])
            screen.blit(lbl, (x + r + 2, y - 7))

    # ── sidebar ──────────────────────────────────────────────────────────────

    def _draw_sidebar(self, screen, mouse, px: int, panel_w: int):
        self._panel_w  = panel_w   # used by _hline / _stepper helpers
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

        # mode buttons — waypoints
        self._row(screen, px, y, "WAYPOINTS", C["dim"]); y += 18
        for mode_key, label in (
            (MODE_WP,     "W  Drag"),
            (MODE_EXTEND, "E  Extend"),
            (MODE_INSERT, "I  Insert"),
        ):
            active = self.mode == mode_key
            r = pygame.Rect(px + 6, y, panel_w - 12, 22)
            pygame.draw.rect(screen, (30, 50, 80) if active else C["btn"], r, border_radius=4)
            pygame.draw.rect(screen, C["wp"] if active else C["sep"], r, 1, border_radius=4)
            t = self.font_sm.render(label, True, C["wp"] if active else C["text"])
            screen.blit(t, t.get_rect(midleft=(r.x + 6, r.centery)))
            self._ui_hits.append((r, lambda m=mode_key: self._set_mode(m)))
            y += 26

        self._hline(screen, px, y); y += 8

        # mode buttons — objects
        self._row(screen, px, y, "OBJECTS", C["dim"]); y += 18
        for mode_key, label, col in (
            (MODE_FROG, "F  Frog",       C["frog"]),
            (MODE_COIN, "G  Coins",      C["coin"]),
            (MODE_AIM,  "A  Aim pwrup",  C["aim"]),
        ):
            active = self.mode == mode_key
            r = pygame.Rect(px + 6, y, panel_w - 12, 22)
            pygame.draw.rect(screen, (30, 60, 30) if active else C["btn"], r, border_radius=4)
            pygame.draw.rect(screen, col if active else C["sep"], r, 1, border_radius=4)
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
        for line in ("W  drag  E  extend  I  insert",
                     "RClick  delete waypoint",
                     "Z       undo",
                     "S       save",
                     "Shift+S  save new",
                     "C       clear all",
                     "ESC     mode → drag / quit"):
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
            MODE_EXTEND: ("Extend path — click to append waypoint to end", C["wp"]),
            MODE_INSERT: ("Insert waypoint — click to split nearest segment", C["wp_hov"]),
            MODE_FROG:   ("Place FROG — click canvas", C["frog"]),
            MODE_COIN:   ("Place COIN — LClick add  RClick remove", C["coin"]),
            MODE_AIM:    ("Place AIM POWERUP — LClick add  RClick remove", C["aim"]),
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

def main():
    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    sw, sh = screen.get_size()
    # Scale the 1920x1080 logical canvas to fill the screen exactly.
    # The sidebar is drawn directly on the screen surface (overlaid on the right edge).
    scale = sh / SCREEN_HEIGHT
    logical = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Poplux — Level Editor")
    clock  = pygame.time.Clock()

    load_path = sys.argv[1] if len(sys.argv) > 1 else None
    editor    = Editor(load_path)

    while True:
        dt = clock.tick(FPS) / 1000.0

        blit_x = -int(_PATH_X_OFFSET * scale)
        # Remap mouse: account for canvas blit offset
        sx, sy = pygame.mouse.get_pos()
        mouse = (int((sx - blit_x) / scale), int(sy / scale))

        sidebar_screen_x = sw - PANEL_W
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
                in_sidebar = event.pos[0] >= sidebar_screen_x
                if not in_sidebar:
                    d = event.__dict__.copy()
                    d["pos"] = (int((event.pos[0] - blit_x) / scale), int(event.pos[1] / scale))
                    event = pygame.event.Event(event.type, d)
            editor.handle_event(event)

        editor.update(dt)

        # Scale canvas uniformly by height.
        # Shift the blit left by the path x-offset (scaled) so content is centered.
        logical.fill((10, 10, 18))
        editor.draw(logical, mouse)
        canvas_sw = int(SCREEN_WIDTH * scale)
        canvas_sh = int(SCREEN_HEIGHT * scale)
        blit_x = -int(_PATH_X_OFFSET * scale)
        screen.blit(pygame.transform.smoothscale(logical, (canvas_sw, canvas_sh)), (blit_x, 0))
        # Draw sidebar directly on screen (overlaid on right edge, in screen space)
        editor.draw_sidebar(screen, pygame.mouse.get_pos(), sw - PANEL_W, PANEL_W)
        pygame.display.flip()


if __name__ == "__main__":
    main()
