import json
import os

# Display
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 960
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

def _read_levels():
    fnames = sorted(f for f in os.listdir(_levels_dir) if f.endswith(".json"))
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
