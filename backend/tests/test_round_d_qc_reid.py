"""Round D QC and within-chunk re-ID regression checks.

These tests stay CPU-only. They verify the logic that reduces review spam and
track fragmentation before the A6000 workstation runs the full SAM3 pipeline.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.qc_rules import QCRulesEngine  # noqa: E402

try:
    import numpy as np  # noqa: E402
except Exception:
    np = None

try:
    from services.tracker import PigeonTracker  # noqa: E402
except Exception:
    PigeonTracker = None

try:
    from services.video_processor import VideoProcessor  # noqa: E402
except Exception:
    VideoProcessor = None


class RoundDQCRegressionTests(unittest.TestCase):
    def test_sparse_detection_density_emits_one_chunk_level_flag(self) -> None:
        engine = QCRulesEngine(expected_pigeon_count=4)
        all_features = []
        for frame_idx in range(100):
            for track_id in range(4):
                all_features.append({
                    "frame_idx": frame_idx,
                    "pigeon_id": f"unknown_{track_id}",
                    "centroid_x": track_id * 100,
                    "centroid_y": track_id * 100,
                    "confidence": 0.9,
                })

        frame_flags = engine.check_frame(10, all_features[:2], [], fps=15.0)
        video_flags = engine.check_video(all_features, total_frames=900, fps=15.0)

        self.assertEqual(frame_flags, [])
        self.assertEqual([flag.rule_name for flag in video_flags], ["low_detection_density"])
        self.assertIn("800/900", video_flags[0].reason)

    def test_no_detections_emits_one_high_level_flag(self) -> None:
        engine = QCRulesEngine(expected_pigeon_count=4)
        flags = engine.check_video([], total_frames=425, fps=15.0)

        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0].rule_name, "no_detections")
        self.assertEqual(flags[0].severity, "high")

    def test_velocity_spike_threshold_scales_for_low_fps(self) -> None:
        engine = QCRulesEngine(expected_pigeon_count=4)
        feature = {"pigeon_id": "unknown_0", "velocity_mm_s": 750.0}

        self.assertEqual(engine.check_frame(1, [feature], fps=15.0), [])
        self.assertEqual(
            engine.check_frame(1, [feature], fps=30.0)[0].rule_name,
            "velocity_spike",
        )


class RoundDReIDRegressionTests(unittest.TestCase):
    @unittest.skipIf(PigeonTracker is None or np is None, "NumPy not installed in this Python")
    def test_reid_merges_short_gap_fragments_with_matching_appearance(self) -> None:
        assert PigeonTracker is not None
        assert np is not None
        tracker = PigeonTracker(
            max_lost_frames=0,
            reid_enabled=True,
            reid_appearance_threshold=0.3,
            reid_gap_frames=5,
            reid_spatial_threshold_px=50.0,
        )
        red_frame = np.zeros((64, 64, 3), dtype=np.uint8)
        red_frame[:, :] = [0, 0, 220]

        first = [{"bbox": [10, 10, 30, 30], "confidence": 0.95}]
        second = [{"bbox": [14, 12, 34, 32], "confidence": 0.91}]

        tracker.update(0, first, frame_bgr=red_frame)
        tracker.update(1, [], frame_bgr=red_frame)
        tracker.update(3, second, frame_bgr=red_frame)
        mapping = tracker.merge_fragmented_tracks()

        self.assertEqual(mapping, {1: 0})
        self.assertGreater(tracker.average_confidence(0), 0.9)

    @unittest.skipIf(VideoProcessor is None, "VideoProcessor dependencies not installed in this Python")
    def test_video_processor_rewrites_feature_and_pairwise_labels(self) -> None:
        assert VideoProcessor is not None
        features = [
            {"track_id": 1, "pigeon_id": "unknown_1", "frame_idx": 10},
            {"track_id": 0, "pigeon_id": "unknown_0", "frame_idx": 10},
        ]
        pairwise = [
            {"frame_idx": 10, "pigeon_a": "unknown_1", "pigeon_b": "unknown_2"},
            {"frame_idx": 10, "pigeon_a": "unknown_1", "pigeon_b": "unknown_0"},
        ]

        VideoProcessor._apply_track_id_mapping(features, pairwise, {1: 0})

        self.assertEqual(features[0]["track_id"], 0)
        self.assertEqual(features[0]["pigeon_id"], "unknown_0")
        self.assertEqual(pairwise, [
            {"frame_idx": 10, "pigeon_a": "unknown_0", "pigeon_b": "unknown_2"},
        ])


if __name__ == "__main__":
    unittest.main()
