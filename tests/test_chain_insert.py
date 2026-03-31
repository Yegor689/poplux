"""Unit tests for Chain.insert(), Chain.check_matches(), and cascade bookkeeping."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ball import Ball
from chain import Chain, _GAP_THRESHOLD, _CASCADE_DELAY
from settings import BALL_DIAMETER, MATCH_MINIMUM


def _chain(speed: float = 100.0) -> Chain:
    return Chain(path=None, speed=speed)


def _balls(chain: Chain, *specs: tuple[float, str]) -> None:
    """Replace chain.balls with new balls given as (path_distance, color) pairs.
    balls[0] is the rear (smallest path_distance), balls[-1] is the front."""
    chain.balls = [Ball(color=color, path_distance=pos) for pos, color in specs]


def _fired_ball(color: str) -> Ball:
    """Return a plain Ball as if it were a fired projectile about to be inserted."""
    return Ball(color=color)


# A gap size that is clearly open (above the threshold) but not too large
_OPEN_GAP = _GAP_THRESHOLD + BALL_DIAMETER


# ===========================================================================
# insert()
# ===========================================================================

class TestInsertSnugPlacement(unittest.TestCase):
    """Verify that the inserted ball's path_distance is snapped to one diameter
    ahead of its rear neighbour, not left at the raw hit position."""

    def test_inserted_ball_is_one_diameter_ahead_of_rear_neighbour(self):
        """Ball inserted between two touching same-color balls sits exactly one
        BALL_DIAMETER ahead of the ball immediately behind it (rear neighbour)."""
        chain = _chain()
        # Two touching red balls
        _balls(chain,
               (0.0,           "red"),
               (BALL_DIAMETER, "red"))

        # Fire at a position roughly in the middle of the first ball
        hit_pos = BALL_DIAMETER * 0.5
        new_ball = _fired_ball("blue")
        idx = chain.insert(new_ball, hit_pos)

        rear_dist = chain.balls[idx - 1].path_distance
        self.assertAlmostEqual(
            chain.balls[idx].path_distance,
            rear_dist + BALL_DIAMETER,
            places=5,
            msg="inserted ball must sit exactly one diameter ahead of its rear neighbour",
        )

    def test_inserted_ball_position_independent_of_raw_hit_position(self):
        """Two different raw hit positions that land in the same gap produce the
        same final ball placement (snug snap, not at the raw position)."""
        def insert_at(hit_pos: float) -> float:
            c = _chain()
            _balls(c,
                   (0.0,                   "red"),
                   (BALL_DIAMETER,         "red"),
                   (BALL_DIAMETER * 2,     "red"))
            b = _fired_ball("blue")
            idx = c.insert(b, hit_pos)
            return c.balls[idx].path_distance

        # Both hits land between ball[0] and ball[1], but at different raw positions
        pos_a = insert_at(BALL_DIAMETER * 0.3)
        pos_b = insert_at(BALL_DIAMETER * 0.7)
        self.assertAlmostEqual(pos_a, pos_b, places=5,
                               msg="snap placement must not depend on raw hit position")


class TestInsertShifting(unittest.TestCase):
    """Verify that balls ahead of the insertion point are shifted by one diameter,
    but only up to the first non-matching open gap (the freeze boundary)."""

    def test_balls_between_insertion_and_open_gap_are_shifted(self):
        """All touching balls between the insertion point and the first open
        non-matching gap are shifted forward by exactly BALL_DIAMETER."""
        chain = _chain()
        # Rear segment: three touching reds
        # Then a clearly open non-matching gap before a blue
        rear_end = BALL_DIAMETER * 2
        _balls(chain,
               (0.0,                       "red"),
               (BALL_DIAMETER,             "red"),
               (BALL_DIAMETER * 2,         "red"),
               (BALL_DIAMETER * 2 + _OPEN_GAP, "blue"))

        before = [b.path_distance for b in chain.balls]
        new_ball = _fired_ball("green")
        # Hit near ball[1] — inserts between ball[0] and ball[1]
        idx = chain.insert(new_ball, BALL_DIAMETER * 0.9)

        # Balls at original indices 1 and 2 (now idx+1, idx+2) must have shifted
        # by BALL_DIAMETER.  The blue ball (beyond the gap) must not shift.
        for orig_i, new_i in [(1, idx + 1), (2, idx + 2)]:
            self.assertAlmostEqual(
                chain.balls[new_i].path_distance,
                before[orig_i] + BALL_DIAMETER,
                places=5,
                msg=f"ball originally at index {orig_i} should be shifted forward",
            )

    def test_balls_beyond_open_nonmatching_gap_are_not_shifted(self):
        """Balls on the far side of an open non-matching gap must NOT be shifted."""
        chain = _chain()
        blue_start = BALL_DIAMETER * 3 + _OPEN_GAP
        _balls(chain,
               (0.0,                       "red"),
               (BALL_DIAMETER,             "red"),
               (BALL_DIAMETER * 2,         "red"),
               (blue_start,                "blue"),
               (blue_start + BALL_DIAMETER,"blue"))

        before_blue0 = chain.balls[3].path_distance
        before_blue1 = chain.balls[4].path_distance

        new_ball = _fired_ball("green")
        chain.insert(new_ball, BALL_DIAMETER * 0.9)

        # Find the blue balls by identity — they must not have moved
        blue_balls = [b for b in chain.balls if b.color == "blue"]
        self.assertEqual(len(blue_balls), 2)
        positions = sorted(b.path_distance for b in blue_balls)
        self.assertAlmostEqual(positions[0], before_blue0, places=5,
                               msg="first blue ball must not be shifted past the gap")
        self.assertAlmostEqual(positions[1], before_blue1, places=5,
                               msg="second blue ball must not be shifted past the gap")

    def test_insert_at_index_zero_places_ball_behind_existing_rear(self):
        """Inserting at the very rear (path_dist less than all balls) places the
        new ball exactly one diameter behind the pre-insertion rearmost ball's
        position.

        Specifically: insert() sets new_ball.path_distance = original_rear.path_distance
        - BALL_DIAMETER before any shifting occurs.  The original rear ball is
        subsequently shifted forward (it is inside the non-frozen segment), so
        the final gap between the new ball and the shifted former-rear is
        2 × BALL_DIAMETER.  The important invariant is that the new ball's final
        position equals original_rear_distance - BALL_DIAMETER."""
        chain = _chain()
        rear_dist = BALL_DIAMETER * 5
        _balls(chain,
               (rear_dist,                 "red"),
               (rear_dist + BALL_DIAMETER, "red"))

        new_ball = _fired_ball("blue")
        # Hit position before both balls → insertion at index 0
        idx = chain.insert(new_ball, 0.0)

        self.assertEqual(idx, 0, "ball should be inserted at index 0")
        self.assertAlmostEqual(
            chain.balls[0].path_distance,
            rear_dist - BALL_DIAMETER,
            places=5,
            msg="new ball must be placed one diameter behind the original rearmost ball's position",
        )


class TestInsertPushback(unittest.TestCase):
    """Verify that the pushback step fires when shifting would cause the last
    shifted ball to overlap the first frozen (non-matching) ball."""

    def test_pushback_restores_one_diameter_gap_to_frozen_ball(self):
        """After insertion near the freeze boundary, the gap between the last
        shifted ball and the first frozen ball must be >= BALL_DIAMETER."""
        chain = _chain()
        # Place balls so the open gap is just barely over the threshold —
        # after shifting, the gap to the frozen ball would be sub-diameter.
        tiny_open = _GAP_THRESHOLD + 1.0   # barely open non-matching gap
        _balls(chain,
               (0.0,                           "red"),
               (BALL_DIAMETER,                 "red"),
               (BALL_DIAMETER + tiny_open,     "blue"))

        new_ball = _fired_ball("green")
        # Insert between ball[0] and ball[1]
        chain.insert(new_ball, BALL_DIAMETER * 0.5)

        # Find the blue ball — it should not have moved
        blue_ball = next(b for b in chain.balls if b.color == "blue")
        # Find the ball just before the blue in the list
        blue_idx = chain.balls.index(blue_ball)
        gap = blue_ball.path_distance - chain.balls[blue_idx - 1].path_distance
        self.assertGreaterEqual(
            gap, BALL_DIAMETER - 1e-4,
            msg="pushback must ensure at least one diameter of clearance to the frozen ball",
        )


# ===========================================================================
# check_matches()
# ===========================================================================

class TestCheckMatches(unittest.TestCase):
    """Verify that check_matches() returns the correct contiguous same-color group."""

    def test_returns_full_contiguous_group_around_index(self):
        """When three same-color balls are touching, check_matches on the middle
        index returns all three indices."""
        chain = _chain()
        _balls(chain,
               (0.0,               "red"),
               (BALL_DIAMETER,     "red"),
               (BALL_DIAMETER * 2, "red"),
               (BALL_DIAMETER * 3, "blue"))

        matches = chain.check_matches(1)

        self.assertEqual(sorted(matches), [0, 1, 2],
                         "should return all three touching red indices")

    def test_returns_empty_when_no_match(self):
        """check_matches on a ball surrounded by different colors returns only
        that ball's own index (below MATCH_MINIMUM)."""
        chain = _chain()
        _balls(chain,
               (0.0,               "red"),
               (BALL_DIAMETER,     "blue"),
               (BALL_DIAMETER * 2, "green"))

        matches = chain.check_matches(1)

        self.assertLess(len(matches), MATCH_MINIMUM,
                        "single isolated ball must not produce a qualifying match group")

    def test_works_at_index_zero(self):
        """check_matches works correctly when the queried index is the first ball
        (rear of chain) — it only extends forward."""
        chain = _chain()
        _balls(chain,
               (0.0,               "red"),
               (BALL_DIAMETER,     "red"),
               (BALL_DIAMETER * 2, "red"),
               (BALL_DIAMETER * 3, "blue"))

        matches = chain.check_matches(0)

        self.assertEqual(sorted(matches), [0, 1, 2],
                         "group should extend from the rear ball forward through all reds")

    def test_works_at_last_index(self):
        """check_matches works correctly when the queried index is the last ball
        (front of chain) — it only extends backward."""
        chain = _chain()
        _balls(chain,
               (0.0,               "blue"),
               (BALL_DIAMETER,     "red"),
               (BALL_DIAMETER * 2, "red"),
               (BALL_DIAMETER * 3, "red"))

        matches = chain.check_matches(3)

        self.assertEqual(sorted(matches), [1, 2, 3],
                         "group should extend from the last ball backward through all reds")

    def test_returns_empty_for_out_of_range_index(self):
        """check_matches with an out-of-bounds index returns an empty list without
        raising an exception."""
        chain = _chain()
        _balls(chain, (0.0, "red"), (BALL_DIAMETER, "red"))

        self.assertEqual(chain.check_matches(-1), [])
        self.assertEqual(chain.check_matches(99), [])

    def test_group_does_not_cross_color_boundary(self):
        """The returned group stops at the first ball of a different color on
        either side and does not include any mismatched neighbors."""
        chain = _chain()
        _balls(chain,
               (0.0,               "blue"),
               (BALL_DIAMETER,     "red"),
               (BALL_DIAMETER * 2, "red"),
               (BALL_DIAMETER * 3, "red"),
               (BALL_DIAMETER * 4, "green"))

        matches = chain.check_matches(2)

        self.assertEqual(sorted(matches), [1, 2, 3],
                         "group must not include the blue or green neighbors")


# ===========================================================================
# Cascade bookkeeping
# ===========================================================================

class TestCascadeBookkeeping(unittest.TestCase):
    """Verify recent_pops / bonus_popped reset and cascade-level sequencing."""

    def test_recent_pops_cleared_at_start_of_advance_on_empty_chain(self):
        """recent_pops is reset to empty at the start of advance() even when the
        chain has no balls (guards against particle spam on chain clear)."""
        chain = _chain()
        # Pre-pollute with stale data
        chain.recent_pops = [(999.0, "red", 1), (888.0, "blue", 2)]
        chain.advance(0.016)
        self.assertEqual(chain.recent_pops, [],
                         "recent_pops must be cleared at the beginning of every advance() call")

    def test_bonus_popped_cleared_at_start_of_advance_on_empty_chain(self):
        """bonus_popped is reset to False at the start of advance() even when the
        chain has no balls."""
        chain = _chain()
        chain.bonus_popped = True
        chain.advance(0.016)
        self.assertFalse(chain.bonus_popped,
                         "bonus_popped must be cleared at the beginning of every advance() call")

    def test_cascade_level_increments_after_gap_based_cascade(self):
        """After a level-1 cascade fires, _next_cascade_level is promoted to 2
        so that any subsequent gap-based cascade is stamped with the correct depth.

        Layout (rear → front):
          red | open-matching-gap | red red red

        The open matching gap triggers catch-up; when it closes all four reds
        form a group >= MATCH_MINIMUM and a level-1 cascade is queued.  After
        it fires, _next_cascade_level must be 2."""
        chain = _chain()
        tiny_open = _GAP_THRESHOLD + 0.5

        # One rear red separated from three front reds by a barely-open matching gap
        chain.balls = [
            Ball(color="red", path_distance=0.0),
            Ball(color="red", path_distance=tiny_open),
            Ball(color="red", path_distance=tiny_open + BALL_DIAMETER),
            Ball(color="red", path_distance=tiny_open + BALL_DIAMETER * 2),
        ]

        # Step 1: one advance tick closes the matching gap and queues cascade level 1
        chain.advance(0.01)
        self.assertGreater(len(chain._cascade_pending), 0,
                           "cascade should be pending after the matching gap closes")
        self.assertEqual(chain._cascade_level, 1,
                         "first cascade must be stamped at level 1")

        # Step 2: fire the cascade (advance past the delay)
        chain.advance(_CASCADE_DELAY + 0.01)

        # _next_cascade_level must be 2 — the counter was promoted when the cascade fired
        self.assertEqual(chain._next_cascade_level, 2,
                         "_next_cascade_level must advance to 2 after the first cascade fires")

    def test_second_queue_match_while_cascade_in_flight_is_ignored(self):
        """A second call to queue_match() while a cascade is already pending must
        not overwrite _cascade_pending (the in-flight cascade takes precedence)."""
        chain = _chain()
        _balls(chain,
               (0.0,               "red"),
               (BALL_DIAMETER,     "red"),
               (BALL_DIAMETER * 2, "red"))

        # Queue first match manually
        chain.queue_match([0, 1, 2])
        original_pending = list(chain._cascade_pending)
        self.assertEqual(len(original_pending), 3, "pre-condition: first match queued")

        # Attempt a second queue_match with a different set of balls
        extra = [Ball(color="blue", path_distance=100.0)]
        chain.balls = chain.balls + extra
        chain.queue_match([3])

        # _cascade_pending must still reference the first match's balls
        self.assertEqual(
            [id(b) for b in chain._cascade_pending],
            [id(b) for b in original_pending],
            "second queue_match must be ignored while a cascade is already in flight",
        )


if __name__ == "__main__":
    unittest.main()
