from __future__ import annotations
import random
from ball import Ball
from settings import BALL_DIAMETER, MATCH_MINIMUM, MAX_SAME_IN_ROW, BALL_COLORS

COLOR_NAMES = list(BALL_COLORS.keys())

# Front-segment reverse speed multiplier (relative to normal chain speed)
_CATCH_UP_MULTIPLIER = 10.0
# A gap larger than this threshold is considered "open" (needs closing)
_GAP_THRESHOLD = BALL_DIAMETER * 1.2
# Seconds to wait between cascade pops
_CASCADE_DELAY = 0.25
# Insertion animation: how many balls ahead animate + decay rate (px/s)
_ANIM_BALLS  = 5
_ANIM_RATE   = BALL_DIAMETER / 0.17   # completes in ~0.17 s
_ENTRY_SPEED = 1.0 / 0.17             # entry animation: 0→1 in ~0.17 s


def _random_color(last_two: list[str]) -> str:
    """Pick a random color, avoiding more than MAX_SAME_IN_ROW consecutive."""
    if len(last_two) >= MAX_SAME_IN_ROW and len(set(last_two[-MAX_SAME_IN_ROW:])) == 1:
        choices = [c for c in COLOR_NAMES if c != last_two[-1]]
    else:
        choices = COLOR_NAMES
    return random.choice(choices)


class Chain:
    def __init__(self, path, speed: float):
        self.path = path
        self.speed = speed
        # balls[0] = rear/spawn-side (smallest path_distance)
        # balls[-1] = front/hole-side (largest path_distance)
        self.balls: list[Ball] = []
        self._cascade_pending: list[Ball] = []  # balls queued to pop after delay
        self._cascade_timer: float = 0.0
        self._cascade_level: int = 0            # current cascade depth (1 = first pop, 2 = first cascade, …)
        self.recent_pops: list[tuple[float, str, int]] = []  # (path_distance, color, cascade_level)

    # ------------------------------------------------------------------
    # Population / spawning
    # ------------------------------------------------------------------

    def populate(self, count: int) -> None:
        """Pre-place `count` touching balls at the spawn end."""
        last_two: list[str] = []
        for i in range(count):
            color = _random_color(last_two)
            last_two.append(color)
            self.balls.append(Ball(color=color, path_distance=float(i * BALL_DIAMETER)))

    def spawn_one(self) -> Ball:
        """Slot a new ball just behind the current rear ball (no shifting needed).
        Call only when needs_spawn() is True."""
        last_two = [b.color for b in self.balls[:2]]
        color = _random_color(last_two)
        new_dist = (self.balls[0].path_distance - BALL_DIAMETER) if self.balls else 0.0
        new_ball = Ball(color=color, path_distance=max(0.0, new_dist))
        self.balls.insert(0, new_ball)
        return new_ball

    def needs_spawn(self) -> bool:
        """True when the rear ball has moved far enough to fit a new ball behind it."""
        return bool(self.balls) and self.balls[0].path_distance >= BALL_DIAMETER

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------

    def advance(self, dt: float) -> None:
        """Move all balls toward the endpoint.

        Front segments reverse across open gaps at _CATCH_UP_MULTIPLIER speed.
        When a gap closes, matches are queued with a _CASCADE_DELAY between pops.
        """
        if not self.balls:
            return

        self.recent_pops.clear()

        # --- Tick cascade timer; fire when ready ---
        if self._cascade_pending:
            self._cascade_timer -= dt
            if self._cascade_timer <= 0:
                self._fire_cascade()
            # Keep advancing while waiting (rear segment still moves)

        delta = self.speed * dt

        # Snapshot gap sizes BEFORE advancing
        prev_gaps = [
            self.balls[i + 1].path_distance - self.balls[i].path_distance
            for i in range(len(self.balls) - 1)
        ]

        # --- Normal advance ---
        for b in self.balls:
            b.path_distance += delta

        # --- Insertion-animation offset decay ---
        for b in self.balls:
            if b.path_offset < 0:
                b.path_offset = min(0.0, b.path_offset + _ANIM_RATE * dt)
            if b.entry_t < 1.0:
                b.entry_t = min(1.0, b.entry_t + _ENTRY_SPEED * dt)

        # --- Reverse catch-up ---
        catch_up_extra = self.speed * (_CATCH_UP_MULTIPLIER - 1.0) * dt
        boosted: set[int] = set()
        for i, gap in enumerate(prev_gaps):
            if gap > _GAP_THRESHOLD:
                for j in range(i + 1, len(self.balls)):
                    if j not in boosted:
                        self.balls[j].path_distance -= catch_up_extra
                        boosted.add(j)

        # --- Detect newly closed gaps; queue matches instead of instant removal ---
        if self._cascade_pending:
            return  # don't queue another cascade while one is in flight

        for i in range(len(self.balls) - 1):
            was_open = i < len(prev_gaps) and prev_gaps[i] > _GAP_THRESHOLD
            if not was_open:
                continue
            gap_now = self.balls[i + 1].path_distance - self.balls[i].path_distance
            if gap_now <= _GAP_THRESHOLD:
                self.balls[i + 1].path_distance = self.balls[i].path_distance + BALL_DIAMETER
                matches = self.check_matches(i)
                if len(matches) < MATCH_MINIMUM:
                    matches = self.check_matches(i + 1)
                if len(matches) >= MATCH_MINIMUM:
                    self._cascade_pending = [self.balls[j] for j in matches]
                    self._cascade_timer = _CASCADE_DELAY
                    self._cascade_level = 1
                    break  # one cascade at a time

    def _fire_cascade(self) -> None:
        """Remove the queued cascade balls and check for a follow-up match."""
        pending_ids = {id(b) for b in self._cascade_pending}
        indices = [i for i, b in enumerate(self.balls) if id(b) in pending_ids]
        # Record pops for the particle system and score
        for i in indices:
            self.recent_pops.append((self.balls[i].path_distance, self.balls[i].color, self._cascade_level))
        self._cascade_pending = []
        if not indices:
            return
        min_idx = min(indices)
        self.remove_balls(indices)
        # Check for a new match at the junction left behind
        for ci in (min_idx, min_idx - 1):
            if 0 <= ci < len(self.balls):
                matches = self.check_matches(ci)
                if len(matches) >= MATCH_MINIMUM:
                    self._cascade_pending = [self.balls[j] for j in matches]
                    self._cascade_timer = _CASCADE_DELAY
                    self._cascade_level += 1     # each follow-up cascade raises the multiplier
                    break

    def front_distance(self) -> float:
        return self.balls[-1].path_distance if self.balls else 0.0

    def is_empty(self) -> bool:
        return not self.balls

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------

    def insert(self, ball: Ball, path_dist: float) -> int:
        """Insert ball near path_dist; snap it snugly to its rear neighbour.
        All balls ahead of the insertion point shift forward by one diameter.
        Returns the index of the inserted ball."""
        if not self.balls:
            ball.path_distance = path_dist
            self.balls.append(ball)
            return 0

        # Find insertion index: first ball whose path_distance > path_dist
        idx = len(self.balls)
        for i, b in enumerate(self.balls):
            if b.path_distance > path_dist:
                idx = i
                break

        # Place ball snugly — one diameter ahead of the ball behind it
        if idx == 0:
            # Inserting at the very rear
            ball.path_distance = self.balls[0].path_distance - BALL_DIAMETER
        else:
            ball.path_distance = self.balls[idx - 1].path_distance + BALL_DIAMETER

        # Shift all balls ahead to make room (no overlap with the new ball)
        for i in range(idx, len(self.balls)):
            self.balls[i].path_distance += BALL_DIAMETER

        # Animate the nearest neighbours sliding out of the way
        for i in range(idx, min(idx + _ANIM_BALLS, len(self.balls))):
            self.balls[i].path_offset = -BALL_DIAMETER

        # Record fired position for the entry animation
        ball.entry_x = ball.x
        ball.entry_y = ball.y
        ball.entry_t = 0.0

        self.balls.insert(idx, ball)
        return idx

    # ------------------------------------------------------------------
    # Match detection & removal
    # ------------------------------------------------------------------

    def check_matches(self, index: int) -> list[int]:
        """Return indices of the contiguous same-color group around index."""
        if not self.balls or index < 0 or index >= len(self.balls):
            return []
        color = self.balls[index].color
        group = [index]
        i = index - 1
        while i >= 0 and self.balls[i].color == color:
            group.append(i)
            i -= 1
        i = index + 1
        while i < len(self.balls) and self.balls[i].color == color:
            group.append(i)
            i += 1
        return group

    def queue_match(self, indices: list[int]) -> None:
        """Schedule matched balls to pop after the entry animation completes."""
        if not self._cascade_pending:
            self._cascade_pending = [self.balls[j] for j in indices]
            self._cascade_timer = 1.0 / _ENTRY_SPEED  # wait for entry anim (~0.12 s)
            self._cascade_level = 1

    def remove_balls(self, indices: list[int]) -> None:
        """Remove balls at the given indices.
        The resulting gap is left open; advance() will close it with reverse catch-up."""
        for i in reversed(sorted(indices)):
            del self.balls[i]
