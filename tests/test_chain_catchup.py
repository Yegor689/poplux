"""Unit tests for Chain.advance() catch-up behaviour."""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ball import Ball
from chain import Chain, _CATCH_UP_MULTIPLIER, _GAP_THRESHOLD, _CASCADE_DELAY
from settings import BALL_DIAMETER, MATCH_MINIMUM


def _chain(speed: float = 100.0) -> Chain:
    return Chain(path=None, speed=speed)


def _balls(chain: Chain, *specs: tuple[float, str]) -> None:
    """Replace chain.balls with new balls given as (path_distance, color) pairs.
    balls[0] is the rear (smallest path_distance), balls[-1] is the front."""
    chain.balls = [Ball(color=color, path_distance=pos) for pos, color in specs]


# ---------------------------------------------------------------------------
# Helper: net displacement expected per ball under catch-up
# ---------------------------------------------------------------------------
_SPEED = 100.0
_DT = 0.01
_DELTA = _SPEED * _DT                                    # normal forward step
_CATCH_EXTRA = _SPEED * (_CATCH_UP_MULTIPLIER - 1) * _DT  # extra backward for catch-up
_OPEN_GAP = _GAP_THRESHOLD + BALL_DIAMETER              # clearly open gap


class TestCatchUpBasics(unittest.TestCase):
    """Verify the per-ball displacement produced by catch-up and freeze passes."""

    def test_matching_gap_front_moves_backward(self):
        """Front segment net-moves backward when a matching (same-color) gap is open."""
        chain = _chain()
        _balls(chain, (0.0, "red"), (_OPEN_GAP, "red"))

        initial_front = chain.balls[1].path_distance
        chain.advance(_DT)

        expected = initial_front + _DELTA - _CATCH_EXTRA
        self.assertAlmostEqual(chain.balls[1].path_distance, expected, places=5)

    def test_matching_gap_rear_advances_normally(self):
        """Rear ball is unaffected by catch-up and advances at normal speed."""
        chain = _chain()
        _balls(chain, (0.0, "red"), (_OPEN_GAP, "red"))

        initial_rear = chain.balls[0].path_distance
        chain.advance(_DT)

        self.assertAlmostEqual(chain.balls[0].path_distance, initial_rear + _DELTA, places=5)

    def test_nonmatching_gap_front_frozen(self):
        """Front segment net-movement is zero when a non-matching gap is open."""
        chain = _chain()
        _balls(chain, (0.0, "red"), (_OPEN_GAP, "blue"))

        initial_front = chain.balls[1].path_distance
        chain.advance(_DT)

        self.assertAlmostEqual(chain.balls[1].path_distance, initial_front, places=5)

    def test_closed_gap_all_balls_advance_normally(self):
        """No catch-up or freeze when balls are already touching (gap <= threshold)."""
        chain = _chain()
        _balls(chain, (0.0, "red"), (BALL_DIAMETER, "blue"))

        pos0, pos1 = chain.balls[0].path_distance, chain.balls[1].path_distance
        chain.advance(_DT)

        self.assertAlmostEqual(chain.balls[0].path_distance, pos0 + _DELTA, places=5)
        self.assertAlmostEqual(chain.balls[1].path_distance, pos1 + _DELTA, places=5)

    def test_multiple_front_balls_all_catch_up(self):
        """Every ball in the front segment reverse-catches-up, not just the first one."""
        chain = _chain()
        _balls(
            chain,
            (0.0, "red"),
            (_OPEN_GAP, "red"),
            (_OPEN_GAP + BALL_DIAMETER, "red"),
            (_OPEN_GAP + 2 * BALL_DIAMETER, "red"),
        )
        initial = [b.path_distance for b in chain.balls]
        chain.advance(_DT)

        # Rear: normal advance
        self.assertAlmostEqual(chain.balls[0].path_distance, initial[0] + _DELTA, places=5)

        # Front segment (indices 1-3): delta − catch_up_extra
        for i in range(1, 4):
            expected = initial[i] + _DELTA - _CATCH_EXTRA
            self.assertAlmostEqual(chain.balls[i].path_distance, expected, places=5,
                                   msg=f"ball[{i}] mismatch")

    def test_two_matching_gaps_cumulative_catchup(self):
        """A ball behind TWO open matching gaps should have catch_up_extra applied
        twice — once per gap — so it closes both gaps simultaneously.

        Layout: rear(red) --gap-- mid(red) --gap-- front(red)

        Expected net displacement:
          rear  (ball[0]): +delta            (unaffected)
          mid   (ball[1]): +delta - 1×extra  (behind gap 0→1)
          front (ball[2]): +delta - 2×extra  (behind gap 0→1 AND gap 1→2)
        """
        chain = _chain()
        _balls(
            chain,
            (0.0, "red"),
            (_OPEN_GAP, "red"),
            (_OPEN_GAP * 2, "red"),
        )
        initial = [b.path_distance for b in chain.balls]
        chain.advance(_DT)

        self.assertAlmostEqual(chain.balls[0].path_distance,
                               initial[0] + _DELTA, places=5,
                               msg="rear ball should advance normally")
        self.assertAlmostEqual(chain.balls[1].path_distance,
                               initial[1] + _DELTA - _CATCH_EXTRA, places=5,
                               msg="mid ball should have 1× catch-up applied")
        self.assertAlmostEqual(chain.balls[2].path_distance,
                               initial[2] + _DELTA - 2 * _CATCH_EXTRA, places=5,
                               msg="front ball should have 2× catch-up applied (one per gap)")

    def test_empty_chain_does_not_raise(self):
        """advance() on an empty chain is a no-op."""
        chain = _chain()
        chain.advance(_DT)
        self.assertEqual(chain.balls, [])


class TestFreezeVsCatchUpPriority(unittest.TestCase):
    """Freeze stops a segment from advancing, but matching gaps *within* that
    frozen segment still close normally."""

    def test_freeze_stops_forward_movement(self):
        """Layout: rear(red) --non-match-gap-- mid(blue) --match-gap-- front(blue).
        The non-match gap freezes both mid and front (net forward movement = 0).
        The match gap is inside the frozen segment, so front still catches up
        toward mid (moves backward by catch_up_extra)."""
        chain = _chain()
        _balls(
            chain,
            (0.0, "red"),
            (_OPEN_GAP, "blue"),
            (_OPEN_GAP * 2, "blue"),
        )
        initial_1 = chain.balls[1].path_distance
        initial_2 = chain.balls[2].path_distance
        chain.advance(_DT)

        self.assertAlmostEqual(chain.balls[1].path_distance, initial_1, places=5,
                               msg="mid ball should be frozen (net zero forward movement)")
        self.assertAlmostEqual(chain.balls[2].path_distance, initial_2 - _CATCH_EXTRA, places=5,
                               msg="front ball catches up toward mid within the frozen segment")

    def test_freeze_beats_catchup_when_nonmatch_gap_is_closer(self):
        """Layout: rear(A) --match-gap-- mid(A) --non-match-gap-- front(B).
        The non-match gap is between the matching gap and front, so front must
        be frozen and must NOT be pulled backward by the A=A match."""
        chain = _chain()
        _balls(
            chain,
            (0.0, "red"),
            (_OPEN_GAP, "red"),
            (_OPEN_GAP * 2, "blue"),
        )
        initial_1 = chain.balls[1].path_distance
        initial_2 = chain.balls[2].path_distance
        chain.advance(_DT)

        self.assertAlmostEqual(chain.balls[1].path_distance,
                               initial_1 + _DELTA - _CATCH_EXTRA, places=5,
                               msg="mid(red) catches up toward rear(red)")
        self.assertAlmostEqual(chain.balls[2].path_distance, initial_2, places=5,
                               msg="front(blue) must be frozen; non-match gap beats the A=A match")

    def test_catchup_within_frozen_segment_three_clumps(self):
        """Layout: rear(B) --non-match-- mid-R mid-R --match-- front-R front-R.
        The whole front half is frozen by the non-match gap, but the matching
        R=R gap inside it must still close."""
        chain = _chain()
        _balls(
            chain,
            (0.0, "blue"),
            (_OPEN_GAP,                          "red"),
            (_OPEN_GAP + BALL_DIAMETER,          "red"),
            (_OPEN_GAP * 2 + BALL_DIAMETER,      "red"),
            (_OPEN_GAP * 2 + BALL_DIAMETER * 2,  "red"),
        )
        initial = [b.path_distance for b in chain.balls]
        chain.advance(_DT)

        # mid-R balls frozen (net 0)
        self.assertAlmostEqual(chain.balls[1].path_distance, initial[1], places=5,
                               msg="mid-R[0] should be frozen")
        self.assertAlmostEqual(chain.balls[2].path_distance, initial[2], places=5,
                               msg="mid-R[1] should be frozen")
        # front-R balls are touching each other (closed gap between them), so
        # only the one open matching gap drives catch-up — both get 1× extra.
        self.assertAlmostEqual(chain.balls[3].path_distance,
                               initial[3] - _CATCH_EXTRA, places=5,
                               msg="front-R[0] catches up toward mid-R segment")
        self.assertAlmostEqual(chain.balls[4].path_distance,
                               initial[4] - _CATCH_EXTRA, places=5,
                               msg="front-R[1] same 1× catch-up (gap to front-R[0] is closed)")


class TestGapClosing(unittest.TestCase):
    """Verify snap-on-close behaviour for both matching and non-matching gaps."""

    def test_nonmatching_gap_snaps_to_one_diameter(self):
        """When rear catches up to frozen front (different colors), the gap is snapped
        to exactly BALL_DIAMETER (touching, not overlapping)."""
        chain = _chain()
        tiny_open = _GAP_THRESHOLD + 0.5   # barely open
        _balls(chain, (0.0, "red"), (tiny_open, "blue"))

        # rear advances at 100 px/s, front frozen → gap closes in ~0.085 s
        chain.advance(0.1)

        gap = chain.balls[1].path_distance - chain.balls[0].path_distance
        self.assertAlmostEqual(gap, BALL_DIAMETER, places=4,
                               msg="gap should snap to exactly one diameter")

    def test_matching_gap_closes_and_queues_cascade(self):
        """When a matching gap closes and >= MATCH_MINIMUM same-color balls touch,
        a cascade is queued."""
        chain = _chain()
        tiny_open = _GAP_THRESHOLD + 0.5
        # 1 rear red + 3 front reds = 4 red total (>= MATCH_MINIMUM=3)
        chain.balls = [
            Ball(color="red", path_distance=0.0),
            Ball(color="red", path_distance=tiny_open),
            Ball(color="red", path_distance=tiny_open + BALL_DIAMETER),
            Ball(color="red", path_distance=tiny_open + 2 * BALL_DIAMETER),
        ]
        chain.advance(0.01)

        self.assertGreater(len(chain._cascade_pending), 0,
                           "cascade should be queued after matching gap closes")

    def test_matching_gap_no_cascade_if_below_minimum(self):
        """If fewer than MATCH_MINIMUM balls match, no cascade is queued."""
        chain = _chain()
        tiny_open = _GAP_THRESHOLD + 0.5
        # Only 2 reds total — below MATCH_MINIMUM (3)
        chain.balls = [
            Ball(color="red", path_distance=0.0),
            Ball(color="red", path_distance=tiny_open),
            Ball(color="blue", path_distance=tiny_open + BALL_DIAMETER),
        ]
        chain.advance(0.01)

        self.assertEqual(len(chain._cascade_pending), 0,
                         "no cascade when fewer than MATCH_MINIMUM balls match")


class TestCascadeFiring(unittest.TestCase):
    """Verify the cascade delay and ball removal after a catch-up closes a matching gap."""

    def _setup_cascade(self) -> Chain:
        """Return a chain where a single advance(0.01) queues a cascade."""
        chain = _chain()
        tiny_open = _GAP_THRESHOLD + 0.5
        chain.balls = [
            Ball(color="red", path_distance=0.0),
            Ball(color="red", path_distance=tiny_open),
            Ball(color="red", path_distance=tiny_open + BALL_DIAMETER),
            Ball(color="red", path_distance=tiny_open + 2 * BALL_DIAMETER),
        ]
        chain.advance(0.01)
        return chain

    def test_cascade_pending_before_delay_expires(self):
        """Matched balls are queued but not yet removed before CASCADE_DELAY elapses."""
        chain = self._setup_cascade()
        count_before = len(chain.balls)

        chain.advance(_CASCADE_DELAY * 0.5)  # half the delay

        self.assertEqual(len(chain.balls), count_before,
                         "balls must not be removed before the cascade delay expires")

    def test_cascade_fires_after_delay(self):
        """Matched balls are removed once CASCADE_DELAY elapses."""
        chain = self._setup_cascade()
        count_before = len(chain.balls)

        chain.advance(_CASCADE_DELAY + 0.01)  # past the delay

        self.assertLess(len(chain.balls), count_before,
                        "matched balls should be removed after cascade delay")

    def test_recent_pops_populated_after_cascade(self):
        """recent_pops is filled with (path_distance, color, level) entries on fire."""
        chain = self._setup_cascade()

        chain.advance(_CASCADE_DELAY + 0.01)

        self.assertGreater(len(chain.recent_pops), 0,
                           "recent_pops should record the popped balls")
        for entry in chain.recent_pops:
            self.assertEqual(len(entry), 3, "each pop entry is (path_dist, color, level)")


if __name__ == "__main__":
    unittest.main()
