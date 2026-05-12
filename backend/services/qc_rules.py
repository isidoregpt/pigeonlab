"""Quality control rules engine for PigeonLab.

Runs automated QC checks on processed video data and generates entries
for the ``qc_flags`` database table.  Uses only the standard library.
"""

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QCFlag:
    """A single quality-control issue."""

    rule_name: str
    severity: str  # "low" | "medium" | "high" | "critical"
    reason: str
    frame_idx: int | None = None


class QCRulesEngine:
    """Automated QC checks for pigeon tracking data.

    Usage::

        engine = QCRulesEngine(expected_pigeon_count=4)
        flags = engine.check_frame(frame_idx, features, prev_features)
        video_flags = engine.check_video(all_features, total_frames=total_frames, fps=fps)
        rows = engine.flags_to_db_rows(flags + video_flags, video_id)
    """

    def __init__(self, expected_pigeon_count: int = 4) -> None:
        """Initialise the QC engine.

        Args:
            expected_pigeon_count: Expected number of pigeons per frame.
                Set to 0 to disable count-mismatch checks.
        """
        self._expected = expected_pigeon_count

    # ------------------------------------------------------------------
    # Per-frame checks
    # ------------------------------------------------------------------

    def check_frame(
        self,
        frame_idx: int,
        features: list[dict],
        prev_features: list[dict] | None = None,
        fps: float | None = None,
    ) -> list[QCFlag]:
        """Run per-frame QC checks.

        Args:
            frame_idx: Zero-based frame index.
            features: Feature dicts for the current frame.
            prev_features: Feature dicts for the previous frame, or ``None``.
            fps: Source video frame rate. Used to scale motion thresholds so
                15 fps and 30 fps footage produce comparable QC rates.

        Returns:
            List of :class:`QCFlag` instances for any issues found.
        """
        flags: list[QCFlag] = []

        # Count mismatches and disappearances are deliberately aggregated in
        # check_video(). Flagging them here produced hundreds of near-identical
        # review items on long real videos.

        # velocity_spike
        velocity_threshold = self._fps_scaled_velocity_threshold(fps)
        for feat in features:
            v = feat.get("velocity_mm_s", 0.0)
            if v is not None and v > velocity_threshold:
                pid = feat.get("pigeon_id", "?")
                flags.append(QCFlag(
                    rule_name="velocity_spike",
                    severity="medium",
                    reason=(
                        f"Pigeon {pid} velocity {v:.1f} mm/s "
                        f"exceeds fps-adjusted limit {velocity_threshold:.1f} mm/s"
                    ),
                    frame_idx=frame_idx,
                ))

        # overlapping_bboxes
        centroids = [
            (f.get("pigeon_id", "?"), f.get("centroid_x", 0), f.get("centroid_y", 0))
            for f in features
        ]
        for i in range(len(centroids)):
            for j in range(i + 1, len(centroids)):
                pid_a, ax, ay = centroids[i]
                pid_b, bx, by = centroids[j]
                dist = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                if dist < 20.0:
                    flags.append(QCFlag(
                        rule_name="overlapping_bboxes",
                        severity="low",
                        reason=(
                            f"Pigeons {pid_a} and {pid_b} centroids "
                            f"within 20px at frame {frame_idx}"
                        ),
                        frame_idx=frame_idx,
                    ))

        return flags

    # ------------------------------------------------------------------
    # Video-level checks
    # ------------------------------------------------------------------

    def check_video(
        self,
        all_features: list[dict],
        total_frames: int | None = None,
        fps: float | None = None,
    ) -> list[QCFlag]:
        """Run video-level QC checks across all frames.

        Args:
            all_features: All feature dicts for the entire video.
            total_frames: Total frame count for the video/chunk. When present,
                sparse detection checks are emitted once per chunk instead of
                once per missing frame.
            fps: Source video frame rate for gap thresholds.

        Returns:
            List of :class:`QCFlag` instances for any issues found.
        """
        flags: list[QCFlag] = []

        resolved_total_frames = self._resolve_total_frames(all_features, total_frames)
        frame_counts = Counter(
            int(f["frame_idx"])
            for f in all_features
            if f.get("frame_idx") is not None
        )
        flags.extend(self._detection_density_flags(frame_counts, resolved_total_frames))

        # Group features by pigeon_id
        by_pigeon: dict[str, list[dict]] = defaultdict(list)
        for feat in all_features:
            pid = feat.get("pigeon_id", "?")
            by_pigeon[pid].append(feat)

        gap_threshold = self._fps_scaled_gap_threshold(fps)
        for pid, feats in by_pigeon.items():
            frames = sorted(f["frame_idx"] for f in feats)

            # track_gap: pigeon disappears for >30 frames then reappears
            large_gaps: list[tuple[int, int, int]] = []
            for k in range(1, len(frames)):
                gap = frames[k] - frames[k - 1]
                if gap > gap_threshold:
                    large_gaps.append((frames[k - 1], frames[k], gap))
            if large_gaps:
                longest = max(large_gaps, key=lambda item: item[2])
                flags.append(QCFlag(
                    rule_name="track_gap_summary",
                    severity="medium",
                    reason=(
                        f"Pigeon {pid} had {len(large_gaps)} tracking gap"
                        f"{'' if len(large_gaps) == 1 else 's'}; longest "
                        f"{longest[2]} frames ({longest[0]}-{longest[1]}), "
                        f"threshold {gap_threshold} frames"
                    ),
                    frame_idx=longest[0],
                ))

            # low_confidence_id
            confidences = [
                f.get("confidence", 1.0) for f in feats
                if f.get("confidence") is not None
            ]
            if confidences:
                avg = sum(confidences) / len(confidences)
                if avg < 0.6:
                    flags.append(QCFlag(
                        rule_name="low_confidence_id",
                        severity="medium",
                        reason=(
                            f"Pigeon {pid} average confidence "
                            f"{avg:.2f} below threshold"
                        ),
                    ))

        return flags

    def summarize_flags(self, flags: list[QCFlag]) -> dict[str, int]:
        """Return a compact rule-name count for logging and diagnostics."""
        return dict(Counter(flag.rule_name for flag in flags))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detection_density_flags(
        self,
        frame_counts: Counter,
        total_frames: int | None,
    ) -> list[QCFlag]:
        if self._expected <= 0 or total_frames is None or total_frames <= 0:
            return []

        frames_with_detections = len(frame_counts)
        if frames_with_detections == 0:
            return [
                QCFlag(
                    rule_name="no_detections",
                    severity="high",
                    reason=(
                        f"No pigeons detected in this {total_frames}-frame chunk. "
                        "Check scene visibility, text prompt, and camera contrast."
                    ),
                )
            ]

        low_count_frames = sum(
            1
            for frame_idx in range(total_frames)
            if frame_counts.get(frame_idx, 0) < self._expected
        )
        low_rate = low_count_frames / total_frames
        if low_rate < 0.20:
            return []

        average_count = sum(frame_counts.values()) / total_frames
        severity = "high" if low_rate >= 0.60 else "medium"
        return [
            QCFlag(
                rule_name="low_detection_density",
                severity=severity,
                reason=(
                    f"{low_count_frames}/{total_frames} frames "
                    f"({low_rate * 100:.1f}%) had fewer than "
                    f"{self._expected} detections; average detections/frame "
                    f"{average_count:.2f}"
                ),
            )
        ]

    @staticmethod
    def _resolve_total_frames(
        all_features: list[dict],
        total_frames: int | None,
    ) -> int | None:
        if total_frames is not None:
            try:
                return max(0, int(total_frames))
            except (TypeError, ValueError):
                return None
        frame_values = [
            int(f["frame_idx"])
            for f in all_features
            if f.get("frame_idx") is not None
        ]
        return max(frame_values) + 1 if frame_values else None

    @staticmethod
    def _fps_scaled_gap_threshold(fps: float | None) -> int:
        if fps is None or fps <= 0:
            fps = 30.0
        # Preserve the original one-second intent of the 30-frame rule.
        return max(5, int(round(float(fps))))

    @staticmethod
    def _fps_scaled_velocity_threshold(fps: float | None) -> float:
        if fps is None or fps <= 0:
            fps = 30.0
        # Lower-fps footage has larger frame-to-frame jumps and noisier velocity
        # estimates. Scale the physical threshold up as fps drops.
        return max(500.0, min(1500.0, 500.0 * (30.0 / float(fps))))

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def flags_to_db_rows(
        self, flags: list[QCFlag], video_id: int,
    ) -> list[dict]:
        """Convert QC flags to dicts matching the ``qc_flags`` table columns.

        Args:
            flags: List of :class:`QCFlag` instances.
            video_id: Database video ID.

        Returns:
            List of dicts with keys: ``video_id``, ``frame_idx``,
            ``rule_name``, ``severity``, ``reason``, ``review_status``.
        """
        return [
            {
                "video_id": video_id,
                "frame_idx": f.frame_idx,
                "rule_name": f.rule_name,
                "severity": f.severity,
                "reason": f.reason,
                "review_status": "pending",
            }
            for f in flags
        ]
