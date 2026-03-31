from __future__ import annotations
import random
from ball import Ball
from settings import BALL_DIAMETER, MATCH_MINIMUM, MAX_SAME_IN_ROW, BALL_COLORS

_BONUS_CHANCE = 0.03  # probability a spawned chain ball is a bonus ball

COLOR_NAMES = list(BALL_COLORS.keys())

# Front-segment reverse speed multiplier (relative to normal chain speed)
_CATCH_UP_MULTIPLIER = 10.0
# A gap larger than this threshold is considered "open" (needs closing)
_GAP_THRESHOLD = BALL_DIAMETER * 1.2
# Seconds to wait after catch-up closes a gap before the matched balls pop
_CASCADE_DELAY = 0.5
# Insertion animation: how many balls ahead animate + decay rate (px/s)
_ANIM_BALLS  = 5
_ANIM_RATE   = BALL_DIAMETER / 0.17   # completes in ~0.17 s
_ENTRY_SPEED = 1.0 / 0.17             # entry animation: 0→1 in ~0.17 s


def _random_color(last_two: list[str], pool: list[str]) -> str:
    """Pick a random color from pool, avoiding more than MAX_SAME_IN_ROW consecutive."""
    if len(last_two) >= MAX_SAME_IN_ROW and len(set(last_two[-MAX_SAME_IN_ROW:])) == 1:
        choices = [c for c in pool if c != last_two[-1]]
    else:
        choices = pool
    return random.choice(choices if choices else pool)


class Chain:
    def __init__(self, path, speed: float, color_pool: list[str] | None = None,
                 pair_mode: bool = False):
        self.path = path
        self.speed = speed
        self.color_pool: list[str] = list(color_pool) if color_pool is not None else COLOR_NAMES
        self.pair_mode: bool = pair_mode
        self._pair_color: str | None = None  # current pair colour
        self._pair_count: int = 0            # how many of this colour spawned so far
        # balls[0] = rear/spawn-side (smallest path_distance)
        # balls[-1] = front/hole-side (largest path_distance)
        self.movement_mult: float = 1.0  # applied only to forward delta, not catch-up
        self.balls: list[Ball] = []
        self._cascade_pending: list[Ball] = []  # balls queued to pop after delay
        self._cascade_timer: float = 0.0
        self._cascade_level: int = 0            # current cascade depth (1 = first pop, 2 = first cascade, …)
        self._next_cascade_level: int = 1       # level to use when the next gap-based cascade is queued
        self.recent_pops: list[tuple[float, str, int]] = []  # (path_distance, color, cascade_level)
        self.bonus_popped: bool = False
        self.bonus_pop_dist: float = 0.0

    # ------------------------------------------------------------------
    # Population / spawning
    # ------------------------------------------------------------------

    def _next_pair_color(self) -> str:
        """Return the next colour in pair-mode (R R B B R R …)."""
        if self._pair_count >= 2 or self._pair_color is None:
            others = [c for c in self.color_pool if c != self._pair_color]
            self._pair_color = random.choice(others if others else self.color_pool)
            self._pair_count = 0
        self._pair_count += 1
        return self._pair_color

    def populate(self, count: int) -> None:
        """Pre-place `count` touching balls at the spawn end."""
        last_two: list[str] = []
        for i in range(count):
            color = self._next_pair_color() if self.pair_mode else _random_color(last_two, self.color_pool)
            last_two.append(color)
            self.balls.append(Ball(color=color, path_distance=float(i * BALL_DIAMETER),
                                   is_bonus=random.random() < _BONUS_CHANCE))

    def spawn_one(self) -> Ball:
        """Slot a new ball just behind the current rear ball (no shifting needed).
        Call only when needs_spawn() is True."""
        last_two = [b.color for b in self.balls[:2]]
        color = self._next_pair_color() if self.pair_mode else _random_color(last_two, self.color_pool)
        new_dist = (self.balls[0].path_distance - BALL_DIAMETER) if self.balls else 0.0
        new_ball = Ball(color=color, path_distance=max(0.0, new_dist),
                        is_bonus=random.random() < _BONUS_CHANCE)
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
        self.recent_pops.clear()
        self.bonus_popped = False

        if not self.balls:
            return

        # --- Tick cascade timer; fire when ready ---
        if self._cascade_pending:
            self._cascade_timer -= dt
            if self._cascade_timer <= 0:
                self._fire_cascade()
            # Keep advancing while waiting (rear segment still moves)

        delta = self.speed * self.movement_mult * dt

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

        # --- Catch-up (matching) / freeze (non-matching) ---
        # Two-pass approach so freeze always wins over catch-up for the same
        # gap boundary, while still letting matching gaps that are wholly
        # inside a frozen segment close normally.
        #
        # Pass 1 – freeze: for each non-matching open gap, subtract delta from
        #   every ball ahead so their net movement is zero.  Also record the
        #   *nearest* (rightmost) non-matching gap that froze each ball; later
        #   non-matching gaps overwrite earlier ones for balls they also cover.
        # Pass 2 – catch-up: for each matching open gap at index i, subtract
        #   catch_up_extra from balls ahead UNLESS the nearest freeze source
        #   for that ball is at index >= i, meaning a non-matching gap sits
        #   between the matching gap and the ball (freeze wins).  When the
        #   nearest freeze source is *behind* the matching gap (< i), the
        #   matching gap is inside the frozen segment and catch-up applies.
        catch_up_extra = self.speed * (_CATCH_UP_MULTIPLIER - 1.0) * dt
        frozen: set[int] = set()
        frozen_by: dict[int, int] = {}   # ball index → nearest non-matching gap index
        for i, gap in enumerate(prev_gaps):
            if gap > _GAP_THRESHOLD and self.balls[i].color != self.balls[i + 1].color:
                for j in range(i + 1, len(self.balls)):
                    if j not in frozen:
                        self.balls[j].path_distance -= delta
                        frozen.add(j)
                    frozen_by[j] = i   # always overwrite → tracks nearest freeze source

        for i, gap in enumerate(prev_gaps):
            if gap > _GAP_THRESHOLD and self.balls[i].color == self.balls[i + 1].color:
                for j in range(i + 1, len(self.balls)):
                    nearest = frozen_by.get(j)
                    if nearest is None or nearest < i:
                        self.balls[j].path_distance -= catch_up_extra

        # --- Detect newly closed gaps ---
        if self._cascade_pending:
            return  # don't queue another cascade while one is in flight

        for i in range(len(self.balls) - 1):
            was_open = i < len(prev_gaps) and prev_gaps[i] > _GAP_THRESHOLD
            if not was_open:
                continue
            gap_now = self.balls[i + 1].path_distance - self.balls[i].path_distance
            if gap_now <= _GAP_THRESHOLD:
                if self.balls[i].color != self.balls[i + 1].color:
                    # Non-matching join: rear caught up to frozen front.
                    # Snap the rear ball (and the whole rear segment) forward so
                    # the front segment never jumps; chain is now one piece again.
                    old_pos = self.balls[i].path_distance
                    self.balls[i].path_distance = self.balls[i + 1].path_distance - BALL_DIAMETER
                    snap_amount = self.balls[i].path_distance - old_pos
                    for k in range(i):
                        self.balls[k].path_distance += snap_amount
                else:
                    # Matching join: snap front segment into perfect alignment then
                    # check whether a combo formed.
                    snap_delta = (self.balls[i].path_distance + BALL_DIAMETER) - self.balls[i + 1].path_distance
                    for j in range(i + 1, len(self.balls)):
                        self.balls[j].path_distance += snap_delta
                    matches = self.check_matches(i)
                    if len(matches) < MATCH_MINIMUM:
                        matches = self.check_matches(i + 1)
                    if len(matches) >= MATCH_MINIMUM:
                        self._cascade_pending = [self.balls[j] for j in matches]
                        self._cascade_timer = _CASCADE_DELAY
                        self._cascade_level = self._next_cascade_level
                        self._next_cascade_level = 1
                        break  # one cascade at a time

    def _fire_cascade(self) -> None:
        """Remove the queued cascade balls.
        The gap left behind is detected by advance(): if the colours match across
        it the front segment catches up, the gap closes, and the cycle repeats."""
        pending_ids = {id(b) for b in self._cascade_pending}
        indices = [i for i, b in enumerate(self.balls) if id(b) in pending_ids]
        # Record pops for the particle system and score
        for i in indices:
            self.recent_pops.append((self.balls[i].path_distance, self.balls[i].color, self._cascade_level))
        # Check if any bonus ball is among the popped ones
        for b in self._cascade_pending:
            if b.is_bonus:
                self.bonus_popped = True
                self.bonus_pop_dist = b.path_distance
                break
        # Prime the next level before clearing so advance() can pick it up
        self._next_cascade_level = self._cascade_level + 1
        self._cascade_pending = []
        if not indices:
            return
        self.remove_balls(indices)

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

        # Find the first non-matching open gap at or just before the insertion point;
        # balls beyond it are frozen and must not be shifted.
        freeze_at = len(self.balls)
        for gi in range(max(0, idx - 1), len(self.balls) - 1):
            gap = self.balls[gi + 1].path_distance - self.balls[gi].path_distance
            if gap > _GAP_THRESHOLD and self.balls[gi].color != self.balls[gi + 1].color:
                freeze_at = gi + 1
                break

        # Shift balls ahead to make room, stopping at the freeze boundary
        for i in range(idx, freeze_at):
            self.balls[i].path_distance += BALL_DIAMETER

        # After shifting the rear segment, check both overlap scenarios:
        #
        # Case A – inserted inside the rear segment (idx < freeze_at):
        #   The shift moved every ball between idx and the freeze boundary forward
        #   by a full diameter. If the gap to the frozen section was smaller than
        #   2×BALL_DIAMETER, the last shifted ball now overlaps the first frozen
        #   ball. Pull the entire rear segment (and the new ball) back far enough
        #   to restore exactly one diameter of clearance.
        if freeze_at > idx and freeze_at < len(self.balls):
            gap_to_frozen = self.balls[freeze_at].path_distance - self.balls[freeze_at - 1].path_distance
            if gap_to_frozen < BALL_DIAMETER:
                pushback = BALL_DIAMETER - gap_to_frozen
                ball.path_distance -= pushback
                for k in range(freeze_at):
                    self.balls[k].path_distance -= pushback

        # Case B – inserted at or past the freeze boundary (idx >= freeze_at):
        #   No rear-segment balls were shifted, but the new ball itself might be
        #   placed too close to the (unshifted) frozen ball directly ahead.
        elif idx < len(self.balls) and idx >= freeze_at:
            gap_ahead = self.balls[idx].path_distance - ball.path_distance
            if gap_ahead < BALL_DIAMETER:
                pushback = BALL_DIAMETER - gap_ahead
                ball.path_distance -= pushback
                for k in range(idx):
                    self.balls[k].path_distance -= pushback

        # Animate the nearest neighbours sliding out of the way
        for i in range(idx, min(idx + _ANIM_BALLS, freeze_at)):
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
            self._next_cascade_level = 1

    def remove_balls(self, indices: list[int]) -> None:
        """Remove balls at the given indices.
        The resulting gap is left open; advance() will close it with reverse catch-up."""
        for i in reversed(sorted(indices)):
            del self.balls[i]
