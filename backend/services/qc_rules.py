"""Quality control rules engine for PigeonLab.

Runs automated QC checks on processed video data and generates entries
for the ``qc_flags`` database table.  Uses only the standard library.
"""

import logging
from collections import defaultdict
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
        video_flags = engine.check_video(all_features)
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
    ) -> list[QCFlag]:
        """Run per-frame QC checks.

        Args:
            frame_idx: Zero-based frame index.
            features: Feature dicts for the current frame.
            prev_features: Feature dicts for the previous frame, or ``None``.

        Returns:
            List of :class:`QCFlag` instances for any issues found.
        """
        flags: list[QCFlag] = []

        # count_mismatch
        if self._expected > 0 and len(features) != self._expected:
            flags.append(QCFlag(
                rule_name="count_mismatch",
                severity="high",
                reason=(
                    f"Expected {self._expected} pigeons, "
                    f"found {len(features)}"
                ),
                frame_idx=frame_idx,
            ))

        # mask_disappearance
        if prev_features is not None:
            prev_ids = {f["pigeon_id"] for f in prev_features}
            curr_ids = {f["pigeon_id"] for f in features}
            for pid in prev_ids - curr_ids:
                flags.append(QCFlag(
                    rule_name="mask_disappearance",
                    severity="high",
                    reason=f"Pigeon {pid} disappeared at frame {frame_idx}",
                    frame_idx=frame_idx,
                ))

        # velocity_spike
        for feat in features:
            v = feat.get("velocity_mm_s", 0.0)
            if v is not None and v > 500.0:
                pid = feat.get("pigeon_id", "?")
                flags.append(QCFlag(
                    rule_name="velocity_spike",
                    severity="medium",
                    reason=(
                        f"Pigeon {pid} velocity {v:.1f} mm/s "
                        f"exceeds physical limit"
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

    def check_video(self, all_features: list[dict]) -> list[QCFlag]:
        """Run video-level QC checks across all frames.

        Args:
            all_features: All feature dicts for the entire video.

        Returns:
            List of :class:`QCFlag` instances for any issues found.
        """
        flags: list[QCFlag] = []

        # Group features by pigeon_id
        by_pigeon: dict[str, list[dict]] = defaultdict(list)
        for feat in all_features:
            pid = feat.get("pigeon_id", "?")
            by_pigeon[pid].append(feat)

        for pid, feats in by_pigeon.items():
            frames = sorted(f["frame_idx"] for f in feats)

            # track_gap: pigeon disappears for >30 frames then reappears
            for k in range(1, len(frames)):
                gap = frames[k] - frames[k - 1]
                if gap > 30:
                    start = frames[k - 1]
                    end = frames[k]
                    flags.append(QCFlag(
                        rule_name="track_gap",
                        severity="medium",
                        reason=(
                            f"Pigeon {pid} missing frames "
                            f"{start}-{end} ({gap} frames)"
                        ),
                        frame_idx=start,
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
