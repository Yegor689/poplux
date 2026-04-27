import json
import os
import re

# Display
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FPS = 60
TITLE = "Poplux"

# Colors
BALL_COLORS = {
    "red":    (231, 76, 60),
    "green":  (46, 204, 113),
    "blue":   (52, 152, 219),
    "yellow": (241, 196, 15),
}
BG_COLOR = (30, 30, 30)
HOLE_COLOR = (10, 10, 10)
HUD_COLOR = (220, 220, 220)

# Gameplay
BALL_RADIUS = 32
BALL_DIAMETER = BALL_RADIUS * 2
SHOOT_SPEED = 1280.0        # fired ball speed (px/sec)
MATCH_MINIMUM = 3           # minimum group size to pop
MAX_SAME_IN_ROW = 2         # max consecutive same-color spawns

# Path
PATH_CENTER = (640, 480)
PATH_NUM_POINTS = 500

_levels_dir = os.path.join(os.path.dirname(__file__), "levels")

def _level_sort_key(fname):
    m = re.search(r'(\d+)', fname)
    return int(m.group(1)) if m else fname

def _read_levels():
    fnames = sorted((f for f in os.listdir(_levels_dir) if f.endswith(".json")), key=_level_sort_key)
    files  = [os.path.join(_levels_dir, f) for f in fnames]
    data = []
    for fp in files:
        with open(fp) as f:
            data.append(json.load(f))
    return files, data

_files, _data = _read_levels()
LEVEL_FILES = _files   # parallel list: full path for each entry in LEVELS
LEVELS      = _data

def reload_levels():
    """Reload from disk in-place so all existing imports stay valid."""
    files, data = _read_levels()
    LEVEL_FILES[:] = files
    LEVELS[:]      = data


_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "..", "settings.json")

class Settings:
    """Global mutable settings — single instance, imported everywhere as needed."""
    def __init__(self):
        self.music_volume: float = 0.4   # 0.0 – 1.0
        self.sfx_volume: float = 0.5     # 0.0 – 1.0
        self.colorblind_mode: bool = False
        self.fullscreen: bool = True
        self.show_fps: bool = False
        self.danger_vignette: bool = True
        self.particles: bool = True
        self._load()

    def _load(self) -> None:
        try:
            with open(_SETTINGS_FILE) as f:
                data = json.load(f)
            self.music_volume    = float(data.get("music_volume",    self.music_volume))
            self.sfx_volume      = float(data.get("sfx_volume",      self.sfx_volume))
            self.fullscreen      = bool(data.get("fullscreen",       self.fullscreen))
            self.colorblind_mode = bool(data.get("colorblind_mode",  self.colorblind_mode))
            self.show_fps        = bool(data.get("show_fps",         self.show_fps))
            self.danger_vignette = bool(data.get("danger_vignette",  self.danger_vignette))
            self.particles       = bool(data.get("particles",        self.particles))
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass  # use defaults

    def save(self) -> None:
        try:
            with open(_SETTINGS_FILE, "w") as f:
                json.dump({
                    "music_volume":    self.music_volume,
                    "sfx_volume":      self.sfx_volume,
                    "fullscreen":      self.fullscreen,
                    "colorblind_mode": self.colorblind_mode,
                    "show_fps":        self.show_fps,
                    "danger_vignette": self.danger_vignette,
                    "particles":       self.particles,
                }, f, indent=2)
        except OSError:
            pass


SETTINGS = Settings()
