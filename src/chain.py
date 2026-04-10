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
# Insertion animation
_ENTRY_SPEED = 1.0 / 0.17             # entry animation: 0→1 in ~0.17 s
_GAP_OPEN_SPEED = BALL_DIAMETER / 0.15  # px/s — how fast the front slides to make room


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
        if not self.balls:
            return True  # chain emptied (e.g. by bomb) — allow fresh spawn at origin
        return self.balls[0].path_distance >= BALL_DIAMETER

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

        # --- Gap-opening for inserting balls ---
        # Push balls ahead in the SAME segment only (stop at first open gap).
        for i, b in enumerate(self.balls):
            gap_rem = getattr(b, '_gap_remaining', 0.0)
            if gap_rem > 0:
                push = min(gap_rem, _GAP_OPEN_SPEED * dt)
                b._gap_remaining = gap_rem - push
                # Only push if no other inserter ahead in the same segment
                has_gap_ahead = False
                for k in range(i + 1, len(self.balls)):
                    if self.balls[k].path_distance - self.balls[k - 1].path_distance > _GAP_THRESHOLD:
                        break
                    if getattr(self.balls[k], '_gap_remaining', 0.0) > 0:
                        has_gap_ahead = True
                        break
                if not has_gap_ahead:
                    for j in range(i + 1, len(self.balls)):
                        if j > i + 1:
                            if self.balls[j].path_distance - self.balls[j - 1].path_distance > _GAP_THRESHOLD:
                                break
                        self.balls[j].path_distance += push
            if b.entry_t < 1.0:
                b.entry_t = min(1.0, b.entry_t + _ENTRY_SPEED * dt)

        # --- Recompute gaps after gap-opening so freeze/catch-up uses current state ---
        cur_gaps = [
            self.balls[i + 1].path_distance - self.balls[i].path_distance
            for i in range(len(self.balls) - 1)
        ]

        # --- Identify open gaps (skip insertion gaps) ---
        open_gaps: list[tuple[int, bool]] = []  # (index, colors_match)
        for i, gap in enumerate(cur_gaps):
            if getattr(self.balls[i], '_gap_remaining', 0.0) > 0:
                continue
            if gap > _GAP_THRESHOLD:
                match = self.balls[i].color == self.balls[i + 1].color
                open_gaps.append((i, match))

        # --- Freeze (non-matching) and catch-up (matching) ---
        # Each gap only affects balls up to the NEXT open gap (segment-local).
        catch_up_extra = self.speed * (_CATCH_UP_MULTIPLIER - 1.0) * dt

        for gi, (gap_idx, colors_match) in enumerate(open_gaps):
            # Find the end of this segment: the next open gap, or end of chain
            next_boundary = len(self.balls)
            for gi2 in range(gi + 1, len(open_gaps)):
                next_boundary = open_gaps[gi2][0] + 1
                break

            if not colors_match:
                # Freeze: undo the normal advance for balls in this segment
                for j in range(gap_idx + 1, next_boundary):
                    self.balls[j].path_distance -= delta
            else:
                # Catch-up: pull this segment backward to close the gap
                for j in range(gap_idx + 1, next_boundary):
                    self.balls[j].path_distance -= catch_up_extra

        # --- Detect newly closed gaps ---
        if self._cascade_pending:
            return  # don't queue another cascade while one is in flight

        for i in range(len(self.balls) - 1):
            if getattr(self.balls[i], '_gap_remaining', 0.0) > 0:
                continue
            was_open = i < len(prev_gaps) and prev_gaps[i] > _GAP_THRESHOLD
            if not was_open:
                continue
            gap_now = self.balls[i + 1].path_distance - self.balls[i].path_distance
            if gap_now <= _GAP_THRESHOLD:
                if self.balls[i].color != self.balls[i + 1].color:
                    # Non-matching join: snap ball i behind ball i+1, shift rear
                    # segment only (stop at previous open gap going backward).
                    # First find the rear-segment boundary using pre-shift gaps.
                    seg_start = 0
                    for k in range(i - 1, -1, -1):
                        orig_gap = self.balls[k + 1].path_distance - self.balls[k].path_distance
                        if orig_gap > _GAP_THRESHOLD:
                            seg_start = k + 1
                            break
                    old_pos = self.balls[i].path_distance
                    self.balls[i].path_distance = self.balls[i + 1].path_distance - BALL_DIAMETER
                    snap_amount = self.balls[i].path_distance - old_pos
                    for k in range(seg_start, i):
                        self.balls[k].path_distance += snap_amount
                    # Re-pack rear segment (descending from i)
                    for k in range(i - 1, seg_start - 1, -1):
                        expected = self.balls[k + 1].path_distance - BALL_DIAMETER
                        if abs(self.balls[k].path_distance - expected) > 0.5:
                            self.balls[k].path_distance = expected
                else:
                    # Matching join: snap front segment, stop at next open gap.
                    # Find the segment end using pre-shift gaps.
                    seg_end = len(self.balls)
                    for j in range(i + 1, len(self.balls) - 1):
                        fwd_gap = self.balls[j + 1].path_distance - self.balls[j].path_distance
                        if fwd_gap > _GAP_THRESHOLD:
                            seg_end = j + 1
                            break
                    snap_delta = (self.balls[i].path_distance + BALL_DIAMETER) - self.balls[i + 1].path_distance
                    for j in range(i + 1, seg_end):
                        self.balls[j].path_distance += snap_delta
                    # Re-pack: enforce exact spacing within segment
                    for j in range(i + 1, seg_end - 1):
                        expected = self.balls[j].path_distance + BALL_DIAMETER
                        if abs(self.balls[j + 1].path_distance - expected) > 0.5:
                            self.balls[j + 1].path_distance = expected
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
        """Insert ball at path_dist.  Balls ahead are NOT shifted instantly;
        instead advance() will accelerate them to open a gap over a few frames.
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
            ball.path_distance = self.balls[0].path_distance - BALL_DIAMETER
        else:
            ball.path_distance = self.balls[idx - 1].path_distance + BALL_DIAMETER

        # Record fired position for the entry animation
        ball.entry_x = ball.x
        ball.entry_y = ball.y
        ball.entry_t = 0.0
        # How much gap still needs to open ahead (animated in advance())
        ball._gap_remaining = float(BALL_DIAMETER)

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
