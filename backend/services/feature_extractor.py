"""Spatial feature extraction service for PigeonLab.

Computes all per-frame spatial features for the ``features`` and ``pairwise``
database tables from tracking results.  Uses only NumPy and the standard
library — no external dependencies.
"""

import logging
import math
from itertools import combinations

import numpy as np

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """Compute spatial features from tracked detections.

    Usage::

        fe = FeatureExtractor()
        features = fe.compute_features(frame_idx, video_id, tracked, shape)
        pairwise = fe.compute_pairwise(frame_idx, video_id, features)
    """

    def __init__(
        self,
        arena_width_mm: float = 1000.0,
        arena_height_mm: float = 800.0,
    ) -> None:
        """Initialise the feature extractor.

        Args:
            arena_width_mm: Physical width of the arena in millimetres.
            arena_height_mm: Physical height of the arena in millimetres.
        """
        self._arena_width_mm = arena_width_mm
        self._arena_height_mm = arena_height_mm
        self._zones: dict[str, tuple[int, int, int, int]] = {}

    # ------------------------------------------------------------------
    # Zone configuration
    # ------------------------------------------------------------------

    def set_zone_map(
        self, zones: dict[str, tuple[int, int, int, int]],
    ) -> None:
        """Set the zone lookup map.

        Args:
            zones: Mapping of zone name to ``(x1, y1, x2, y2)`` pixel bbox.
        """
        self._zones = dict(zones)

    # ------------------------------------------------------------------
    # Per-frame features
    # ------------------------------------------------------------------

    def compute_features(
        self,
        frame_idx: int,
        video_id: int,
        tracked_detections: list[dict],
        frame_shape: tuple[int, int],
        prev_detections: list[dict] | None = None,
        fps: float = 30.0,
    ) -> list[dict]:
        """Compute spatial features for every tracked detection in a frame.

        Args:
            frame_idx: Zero-based frame index.
            video_id: Database video ID.
            tracked_detections: Detections with ``mask``, ``bbox``,
                ``confidence``, and ``track_id`` keys.
            frame_shape: ``(height, width)`` of the frame in pixels.
            prev_detections: Detections from the previous frame (used for
                velocity and heading). ``None`` on the first frame.
            fps: Video frame rate in frames per second.

        Returns:
            List of dicts whose keys match the ``features`` table columns.
        """
        frame_h, frame_w = frame_shape

        # Build lookup for previous centroids by track_id
        prev_map: dict[int, tuple[float, float]] = {}
        if prev_detections:
            for det in prev_detections:
                tid = det.get("track_id")
                if tid is not None:
                    bbox = det["bbox"]
                    prev_map[tid] = (
                        (bbox[0] + bbox[2]) / 2.0,
                        (bbox[1] + bbox[3]) / 2.0,
                    )

        results: list[dict] = []
        for det in tracked_detections:
            bbox = det["bbox"]
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            track_id = det["track_id"]

            mm_x, mm_y = self._pixel_to_mm(cx, cy, frame_w, frame_h)

            # Area
            mask = det.get("mask")
            if mask is not None:
                area_px = float(np.count_nonzero(mask))
            else:
                area_px = float((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))

            scale_x = self._arena_width_mm / frame_w
            scale_y = self._arena_height_mm / frame_h
            area_mm2 = area_px * scale_x * scale_y

            # Velocity
            prev_centroid = prev_map.get(track_id)
            if prev_centroid is not None:
                dx = cx - prev_centroid[0]
                dy = cy - prev_centroid[1]
                velocity_px = math.sqrt(dx * dx + dy * dy)
                velocity_mm_s = velocity_px * (self._arena_width_mm / frame_w) * fps
            else:
                velocity_px = 0.0
                velocity_mm_s = 0.0

            # Heading
            heading_deg = self._estimate_heading(
                (cx, cy), prev_centroid,
            )

            # Distance to nearest wall
            dist_wall = min(cx, cy, frame_w - cx, frame_h - cy)

            # Zone
            zone = self._get_zone(cx, cy)

            results.append({
                "video_id": video_id,
                "frame_idx": frame_idx,
                "pigeon_id": str(track_id),
                "centroid_x": round(cx, 2),
                "centroid_y": round(cy, 2),
                "centroid_mm_x": round(mm_x, 2),
                "centroid_mm_y": round(mm_y, 2),
                "area_px": round(area_px, 2),
                "area_mm2": round(area_mm2, 2),
                "velocity_px": round(velocity_px, 2),
                "velocity_mm_s": round(velocity_mm_s, 2),
                "heading_deg": round(heading_deg, 2) if heading_deg is not None else None,
                "current_zone": zone,
                "distance_to_nearest_wall_px": round(dist_wall, 2),
                "confidence": round(det.get("confidence", 1.0), 4),
            })

        return results

    # ------------------------------------------------------------------
    # Pairwise distances
    # ------------------------------------------------------------------

    def compute_pairwise(
        self,
        frame_idx: int,
        video_id: int,
        features: list[dict],
    ) -> list[dict]:
        """Compute pairwise distances for every unique pair of pigeons.

        Args:
            frame_idx: Zero-based frame index.
            video_id: Database video ID.
            features: Feature dicts from :meth:`compute_features`.

        Returns:
            List of dicts whose keys match the ``pairwise`` table columns.
            ``pigeon_a`` is always lexicographically less than ``pigeon_b``.
        """
        results: list[dict] = []

        for fa, fb in combinations(features, 2):
            pid_a = fa["pigeon_id"]
            pid_b = fb["pigeon_id"]

            # Consistent ordering
            if pid_a > pid_b:
                pid_a, pid_b = pid_b, pid_a
                fa, fb = fb, fa

            dx = fa["centroid_x"] - fb["centroid_x"]
            dy = fa["centroid_y"] - fb["centroid_y"]
            dist_px = math.sqrt(dx * dx + dy * dy)

            dx_mm = fa["centroid_mm_x"] - fb["centroid_mm_x"]
            dy_mm = fa["centroid_mm_y"] - fb["centroid_mm_y"]
            dist_mm = math.sqrt(dx_mm * dx_mm + dy_mm * dy_mm)

            results.append({
                "video_id": video_id,
                "frame_idx": frame_idx,
                "pigeon_a": pid_a,
                "pigeon_b": pid_b,
                "distance_px": round(dist_px, 2),
                "distance_mm": round(dist_mm, 2),
                "overlap_iou": 0.0,
            })

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_zone(self, cx: float, cy: float) -> str | None:
        """Return the zone name containing the point, or ``None``."""
        for name, (x1, y1, x2, y2) in self._zones.items():
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return name
        return None

    def _pixel_to_mm(
        self, x_px: float, y_px: float, frame_w: int, frame_h: int,
    ) -> tuple[float, float]:
        """Convert pixel coordinates to millimetre coordinates."""
        mm_x = x_px * (self._arena_width_mm / frame_w)
        mm_y = y_px * (self._arena_height_mm / frame_h)
        return (mm_x, mm_y)

    def _estimate_heading(
        self,
        curr: tuple[float, float],
        prev: tuple[float, float] | None,
    ) -> float | None:
        """Estimate heading in degrees (0=north/up, 90=east/right).

        Returns ``None`` if there is no previous position.
        """
        if prev is None:
            return None
        dx = curr[0] - prev[0]
        dy = curr[1] - prev[1]
        if dx == 0.0 and dy == 0.0:
            return 0.0
        # atan2 with y-axis inverted (screen coords: y increases downward)
        # 0 = north (up), 90 = east (right)
        angle_rad = math.atan2(dx, -dy)
        angle_deg = math.degrees(angle_rad) % 360.0
        return angle_deg
