import json
import os

# Display
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
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
PATH_COLOR = (80, 80, 80)
FROG_COLOR = (39, 174, 96)
HOLE_COLOR = (10, 10, 10)
HUD_COLOR = (220, 220, 220)

# Gameplay
BALL_RADIUS = 20
BALL_DIAMETER = BALL_RADIUS * 2
CHAIN_SPEED = 30.0          # chain advance speed (px/sec)
SHOOT_SPEED = 800.0         # fired ball speed (px/sec)
TOTAL_BALLS = 50            # balls to spawn for the level
MATCH_MINIMUM = 3           # minimum group size to pop
MAX_SAME_IN_ROW = 2         # max consecutive same-color spawns
PRE_PLACED_BALLS = 15       # balls placed at start before spawning begins

# Path
PATH_CENTER = (400, 300)
PATH_NUM_POINTS = 500

_levels_dir = os.path.join(os.path.dirname(__file__), "levels")
LEVELS = [
    json.load(open(os.path.join(_levels_dir, fname)))
    for fname in sorted(os.listdir(_levels_dir))
    if fname.endswith(".json")
]
