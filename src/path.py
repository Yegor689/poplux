import math
import bisect
from settings import PATH_NUM_POINTS, SCREEN_WIDTH, SCREEN_HEIGHT

# Levels are authored for a 1280×960 canvas. Scale and offset so the path
# fills and centres on the actual logical canvas size.
_PATH_AUTHORED_WIDTH  = 1280
_PATH_AUTHORED_HEIGHT = 960
_PATH_SCALE_X = SCREEN_HEIGHT / _PATH_AUTHORED_HEIGHT
_PATH_SCALE_Y = SCREEN_HEIGHT / _PATH_AUTHORED_HEIGHT
_PATH_X_OFFSET = (SCREEN_WIDTH - _PATH_AUTHORED_WIDTH * _PATH_SCALE_X) / 2
_PATH_Y_OFFSET = 0


class Path:
    def __init__(self, cfg=None):
        cfg = cfg or {}
        control = [tuple(p) for p in cfg.get("waypoints", [])]
        if len(control) < 2:
            raise ValueError("A level must have at least 2 waypoints.")
        self.waypoints = self._resample(self._catmull_rom_chain(control))
        self.waypoints = [(x * _PATH_SCALE_X + _PATH_X_OFFSET, y * _PATH_SCALE_Y) for x, y in self.waypoints]
        self._arc_lengths = self._compute_arc_lengths()
        self.total_length = self._arc_lengths[-1]

    def _catmull_rom_chain(self, control: list[tuple], samples_per_seg: int = 20) -> list[tuple]:
        """Return a dense polyline using centripetal Catmull-Rom splines (alpha=0.5).
        Centripetal parameterisation produces rounder curves without cusps or self-intersections.
        Endpoints are duplicated as phantom points so the curve passes through all waypoints."""
        pts = [control[0]] + list(control) + [control[-1]]
        result = []
        for i in range(1, len(pts) - 2):
            p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
            # Centripetal knot spacing: t_{i+1} = t_i + |P_{i+1} - P_i|^0.5
            def knot(a, b):
                return (math.hypot(b[0] - a[0], b[1] - a[1])) ** 0.5
            t0 = 0.0
            t1 = t0 + knot(p0, p1)
            t2 = t1 + knot(p1, p2)
            t3 = t2 + knot(p2, p3)
            if t1 == t0 or t2 == t1 or t3 == t2:
                result.append(p1)
                continue
            for j in range(samples_per_seg):
                t = t1 + (t2 - t1) * j / samples_per_seg
                # Barry-Goldman algorithm
                a1x = (t1 - t) / (t1 - t0) * p0[0] + (t - t0) / (t1 - t0) * p1[0]
                a1y = (t1 - t) / (t1 - t0) * p0[1] + (t - t0) / (t1 - t0) * p1[1]
                a2x = (t2 - t) / (t2 - t1) * p1[0] + (t - t1) / (t2 - t1) * p2[0]
                a2y = (t2 - t) / (t2 - t1) * p1[1] + (t - t1) / (t2 - t1) * p2[1]
                a3x = (t3 - t) / (t3 - t2) * p2[0] + (t - t2) / (t3 - t2) * p3[0]
                a3y = (t3 - t) / (t3 - t2) * p2[1] + (t - t2) / (t3 - t2) * p3[1]
                b1x = (t2 - t) / (t2 - t0) * a1x + (t - t0) / (t2 - t0) * a2x
                b1y = (t2 - t) / (t2 - t0) * a1y + (t - t0) / (t2 - t0) * a2y
                b2x = (t3 - t) / (t3 - t1) * a2x + (t - t1) / (t3 - t1) * a3x
                b2y = (t3 - t) / (t3 - t1) * a2y + (t - t1) / (t3 - t1) * a3y
                cx = (t2 - t) / (t2 - t1) * b1x + (t - t1) / (t2 - t1) * b2x
                cy = (t2 - t) / (t2 - t1) * b1y + (t - t1) / (t2 - t1) * b2y
                result.append((cx, cy))
        result.append(control[-1])
        return result

    def _resample(self, control: list[tuple]) -> list[tuple]:
        """Uniformly sample PATH_NUM_POINTS points along the control polyline."""
        seg_lengths = []
        total = 0.0
        for i in range(len(control) - 1):
            x0, y0 = control[i]
            x1, y1 = control[i + 1]
            seg_lengths.append(math.hypot(x1 - x0, y1 - y0))
            total += seg_lengths[-1]

        waypoints = []
        for i in range(PATH_NUM_POINTS):
            target = total * i / (PATH_NUM_POINTS - 1)
            accumulated = 0.0
            for j, seg_len in enumerate(seg_lengths):
                if accumulated + seg_len >= target or j == len(seg_lengths) - 1:
                    t = (target - accumulated) / seg_len if seg_len > 1e-9 else 0.0
                    t = max(0.0, min(1.0, t))
                    x0, y0 = control[j]
                    x1, y1 = control[j + 1]
                    waypoints.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
                    break
                accumulated += seg_len
        return waypoints

    def _compute_arc_lengths(self):
        lengths = [0.0]
        for i in range(1, len(self.waypoints)):
            dx = self.waypoints[i][0] - self.waypoints[i - 1][0]
            dy = self.waypoints[i][1] - self.waypoints[i - 1][1]
            lengths.append(lengths[-1] + math.hypot(dx, dy))
        return lengths

    def point_at(self, distance: float) -> tuple[float, float]:
        distance = max(0.0, min(distance, self.total_length))
        idx = bisect.bisect_right(self._arc_lengths, distance) - 1
        idx = max(0, min(idx, len(self.waypoints) - 2))
        seg_start = self._arc_lengths[idx]
        seg_end = self._arc_lengths[idx + 1]
        seg_len = seg_end - seg_start
        if seg_len < 1e-9:
            return self.waypoints[idx]
        t = (distance - seg_start) / seg_len
        x0, y0 = self.waypoints[idx]
        x1, y1 = self.waypoints[idx + 1]
        return (x0 + t * (x1 - x0), y0 + t * (y1 - y0))

    def direction_at(self, distance: float) -> float:
        distance = max(0.0, min(distance, self.total_length))
        idx = bisect.bisect_right(self._arc_lengths, distance) - 1
        idx = max(0, min(idx, len(self.waypoints) - 2))
        x0, y0 = self.waypoints[idx]
        x1, y1 = self.waypoints[idx + 1]
        return math.atan2(y1 - y0, x1 - x0)

    def nearest_distance(self, x: float, y: float) -> float:
        best_dist_sq = float('inf')
        best_arc = 0.0
        for i in range(len(self.waypoints) - 1):
            x0, y0 = self.waypoints[i]
            x1, y1 = self.waypoints[i + 1]
            seg_dx = x1 - x0
            seg_dy = y1 - y0
            seg_len_sq = seg_dx * seg_dx + seg_dy * seg_dy
            if seg_len_sq < 1e-12:
                t = 0.0
            else:
                t = ((x - x0) * seg_dx + (y - y0) * seg_dy) / seg_len_sq
                t = max(0.0, min(1.0, t))
            px = x0 + t * seg_dx
            py = y0 + t * seg_dy
            dist_sq = (x - px) ** 2 + (y - py) ** 2
            if dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                best_arc = self._arc_lengths[i] + t * math.sqrt(seg_len_sq)
        return best_arc
