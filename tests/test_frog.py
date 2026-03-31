"""Unit tests for Frog: update_available_colors, shoot, and swap."""
import sys
import os
import random
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ball import Ball
from frog import Frog
from settings import BALL_COLORS, SHOOT_SPEED

COLOR_NAMES = list(BALL_COLORS.keys())


def _frog(colors: list[str] | None = None) -> Frog:
    """Return a Frog with a deterministic position and an explicit color pool."""
    pool = colors if colors is not None else list(COLOR_NAMES)
    return Frog(pos=(400.0, 300.0), color_pool=pool)


def _force_ball(color: str, is_bomb: bool = False, is_rainbow: bool = False) -> Ball:
    """Return a Ball with the given properties."""
    return Ball(color=color, is_bomb=is_bomb, is_rainbow=is_rainbow)


# ===========================================================================
# update_available_colors()
# ===========================================================================

class TestUpdateAvailableColors(unittest.TestCase):
    """Verify that the frog's color pool shrinks when active_colors changes, and
    that pre-loaded balls are refreshed only when appropriate."""

    def test_next_ball_regenerated_when_its_color_is_removed(self):
        """next_ball is replaced with a new ball when its color disappears from
        active_colors and it is neither a bomb nor a rainbow."""
        frog = _frog(["red", "blue", "green"])
        # Force next_ball to a specific non-special color
        frog.next_ball = _force_ball("red")
        original_id = id(frog.next_ball)

        # Remove "red" from active colors
        frog.update_available_colors({"blue", "green"})

        self.assertIsNot(frog.next_ball, frog.current_ball,
                         "next_ball should be a new object")
        self.assertNotEqual(id(frog.next_ball), original_id,
                            "next_ball must be regenerated when its color is exhausted")
        self.assertIn(frog.next_ball.color, {"blue", "green"},
                      "regenerated next_ball color must come from the remaining active colors")

    def test_current_ball_regenerated_when_its_color_is_removed(self):
        """current_ball is replaced with a new ball when its color disappears from
        active_colors and it is neither a bomb nor a rainbow."""
        frog = _frog(["red", "blue", "green"])
        frog.current_ball = _force_ball("red")
        original_id = id(frog.current_ball)

        frog.update_available_colors({"blue", "green"})

        self.assertNotEqual(id(frog.current_ball), original_id,
                            "current_ball must be regenerated when its color is exhausted")
        self.assertIn(frog.current_ball.color, {"blue", "green"},
                      "regenerated current_ball color must come from the remaining active colors")

    def test_bomb_next_ball_is_not_regenerated(self):
        """A bomb next_ball is never regenerated, even if its color is no longer
        active (bombs are color-independent)."""
        frog = _frog(["red", "blue"])
        bomb = _force_ball("red", is_bomb=True)
        frog.next_ball = bomb

        frog.update_available_colors({"blue"})

        self.assertIs(frog.next_ball, bomb,
                      "bomb next_ball must not be replaced when its color is removed")

    def test_rainbow_next_ball_is_not_regenerated(self):
        """A rainbow next_ball is never regenerated, even if its color is no longer
        active (rainbow balls are color-independent)."""
        frog = _frog(["red", "blue"])
        rainbow = _force_ball("red", is_rainbow=True)
        frog.next_ball = rainbow

        frog.update_available_colors({"blue"})

        self.assertIs(frog.next_ball, rainbow,
                      "rainbow next_ball must not be replaced when its color is removed")

    def test_pool_never_emptied_when_active_colors_is_empty(self):
        """If active_colors is empty, available_colors remains unchanged (the pool
        must never be wiped out mid-game, which would crash _new_ball)."""
        frog = _frog(["red", "blue", "green"])
        before = list(frog.available_colors)

        frog.update_available_colors(set())  # no active colors at all

        self.assertEqual(frog.available_colors, before,
                         "available_colors must be unchanged when active_colors is empty")

    def test_available_colors_reflects_only_active_colors(self):
        """After a successful update, available_colors contains exactly the colors
        that appear in both COLOR_NAMES and active_colors (in COLOR_NAMES order)."""
        frog = _frog(list(COLOR_NAMES))
        active = {"red", "green"}

        frog.update_available_colors(active)

        expected = [c for c in COLOR_NAMES if c in active]
        self.assertEqual(frog.available_colors, expected,
                         "available_colors must be the ordered intersection of "
                         "COLOR_NAMES and active_colors")

    def test_ball_not_regenerated_when_color_still_active(self):
        """If next_ball's color is still in active_colors, it must not be touched."""
        frog = _frog(["red", "blue", "green"])
        original = _force_ball("blue")
        frog.next_ball = original

        frog.update_available_colors({"blue", "green"})

        self.assertIs(frog.next_ball, original,
                      "next_ball whose color remains active must not be regenerated")


# ===========================================================================
# shoot()
# ===========================================================================

class TestShoot(unittest.TestCase):
    """Verify the mechanics of firing a ball: which ball is returned, what
    happens to current/next, and the kinematics of the fired projectile."""

    def setUp(self):
        random.seed(42)
        self.frog = _frog()
        self.frog.angle = 0.0  # aim directly to the right for easy math

    def test_returns_the_ball_that_was_current_ball(self):
        """shoot() returns the exact Ball object that was current_ball before
        the call."""
        original_current = self.frog.current_ball
        fired = self.frog.shoot()
        self.assertIs(fired, original_current,
                      "shoot() must return the pre-call current_ball")

    def test_current_ball_becomes_next_ball_after_shoot(self):
        """After shooting, current_ball is the object that was next_ball before
        the call."""
        original_next = self.frog.next_ball
        self.frog.shoot()
        self.assertIs(self.frog.current_ball, original_next,
                      "current_ball must become the former next_ball after shoot()")

    def test_new_next_ball_is_a_different_object(self):
        """After shooting, a brand-new next_ball is generated (not the same object
        as the former next_ball or the fired ball)."""
        original_next = self.frog.next_ball
        fired = self.frog.shoot()
        self.assertIsNot(self.frog.next_ball, original_next,
                         "next_ball must be a newly generated ball after shoot()")
        self.assertIsNot(self.frog.next_ball, fired,
                         "next_ball must not be the same object as the fired ball")

    def test_fired_ball_is_active(self):
        """The fired ball must have active=True so the game loop moves it."""
        fired = self.frog.shoot()
        self.assertTrue(fired.active,
                        "fired ball must have active=True")

    def test_fired_ball_has_nonzero_velocity(self):
        """The fired ball must have non-zero dx or dy so it actually travels."""
        fired = self.frog.shoot()
        speed_sq = fired.dx ** 2 + fired.dy ** 2
        self.assertGreater(speed_sq, 0.0,
                           "fired ball must have non-zero velocity components")

    def test_fired_ball_velocity_magnitude_equals_shoot_speed(self):
        """The fired ball's speed must equal SHOOT_SPEED (within floating-point
        rounding)."""
        import math
        fired = self.frog.shoot()
        actual_speed = math.sqrt(fired.dx ** 2 + fired.dy ** 2)
        self.assertAlmostEqual(actual_speed, SHOOT_SPEED, places=4,
                               msg="fired ball speed must equal SHOOT_SPEED")

    def test_fired_ball_velocity_direction_matches_frog_angle(self):
        """dx/dy direction must match the frog's current aim angle."""
        import math
        angle = math.pi / 4  # 45 degrees
        self.frog.angle = angle
        fired = self.frog.shoot()
        fired_angle = math.atan2(fired.dy, fired.dx)
        self.assertAlmostEqual(fired_angle, angle, places=5,
                               msg="fired ball direction must match frog.angle")

    def test_new_next_ball_color_from_available_colors(self):
        """The newly generated next_ball's color must come from available_colors
        (unless it is a bomb/rainbow, which can be any color)."""
        frog = _frog(["red", "blue"])
        # Shoot many times to get a non-special next_ball; verify each one
        for _ in range(50):
            frog.shoot()
            if not (frog.next_ball.is_bomb or frog.next_ball.is_rainbow):
                self.assertIn(frog.next_ball.color, frog.available_colors,
                              "new next_ball color must be drawn from available_colors")


# ===========================================================================
# swap()
# ===========================================================================

class TestSwap(unittest.TestCase):
    """Verify that swap() exchanges current_ball and next_ball."""

    def test_swap_exchanges_current_and_next(self):
        """After swap(), the former next_ball is current_ball and vice versa."""
        frog = _frog()
        original_current = frog.current_ball
        original_next = frog.next_ball

        frog.swap()

        self.assertIs(frog.current_ball, original_next,
                      "current_ball must become the former next_ball after swap()")
        self.assertIs(frog.next_ball, original_current,
                      "next_ball must become the former current_ball after swap()")

    def test_double_swap_restores_original_state(self):
        """Two consecutive swaps return current_ball and next_ball to their
        original identities."""
        frog = _frog()
        original_current = frog.current_ball
        original_next = frog.next_ball

        frog.swap()
        frog.swap()

        self.assertIs(frog.current_ball, original_current,
                      "double swap must restore original current_ball")
        self.assertIs(frog.next_ball, original_next,
                      "double swap must restore original next_ball")


if __name__ == "__main__":
    unittest.main()
