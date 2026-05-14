"""Multi-pigeon tracker for PigeonLab.

Links per-frame SAM 3 detections into persistent tracks across frames
using greedy centroid-distance matching.  No external tracking libraries
required — only NumPy.
"""

import logging
import os
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """A single tracked object (pigeon) across multiple frames."""

    obj_id: int
    pigeon_id: str = "unknown"
    first_seen_frame: int = 0
    last_seen_frame: int = 0
    centroid_history: list[tuple[float, float]] = field(default_factory=list)
    confidence_history: list[float] = field(default_factory=list)
    frame_history: list[int] = field(default_factory=list)
    bbox_history: list[list[float]] = field(default_factory=list)
    appearance_history: list[np.ndarray] = field(default_factory=list)
    active: bool = True
    frames_lost: int = 0


class PigeonTracker:
    """Greedy nearest-centroid multi-object tracker.

    Usage::

        tracker = PigeonTracker()
        for frame_idx, detections in enumerate(all_detections):
            tracked = tracker.update(frame_idx, detections)
    """

    def __init__(
        self,
        max_lost_frames: int = 30,
        max_match_distance: float = 80.0,
        reid_enabled: bool | None = None,
        reid_appearance_threshold: float | None = None,
        reid_gap_frames: int | None = None,
        reid_spatial_threshold_px: float | None = None,
    ) -> None:
        """Initialise the tracker.

        Args:
            max_lost_frames: Deactivate a track after this many consecutive
                frames without a matching detection.
            max_match_distance: Maximum pixel distance between a detection
                centroid and an existing track centroid to allow a match.
                Detections farther than this start a new track.
        """
        self._max_lost_frames = max_lost_frames
        self._max_match_distance = max_match_distance
        self._tracks: list[Track] = []
        self._next_id: int = 0
        self._aliases: dict[int, int] = {}
        self.reid_enabled = (
            self._env_bool("PIGEONLAB_REID_ENABLED", True)
            if reid_enabled is None else reid_enabled
        )
        self._reid_appearance_threshold = (
            self._env_float("PIGEONLAB_REID_APPEARANCE_THRESHOLD", 0.55)
            if reid_appearance_threshold is None else reid_appearance_threshold
        )
        self._reid_gap_frames = (
            self._env_int("PIGEONLAB_REID_GAP_FRAMES", 90)
            if reid_gap_frames is None else reid_gap_frames
        )
        self._reid_spatial_threshold_px = (
            self._env_float("PIGEONLAB_REID_SPATIAL_THRESHOLD_PX", 240.0)
            if reid_spatial_threshold_px is None else reid_spatial_threshold_px
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self,
        frame_idx: int,
        detections: list[dict],
        frame_bgr: np.ndarray | None = None,
    ) -> list[dict]:
        """Assign persistent track IDs to a new set of detections.

        Args:
            frame_idx: Zero-based frame index.
            detections: List of detection dicts from SAM3Wrapper
                (keys: ``mask``, ``bbox``, ``confidence``, ``obj_id``).
            frame_bgr: Optional frame pixels used to collect simple
                appearance histograms for fragment re-identification.

        Returns:
            New list of dicts — same as input but with an added
            ``track_id`` key containing the persistent track ID.
        """
        active_tracks = self.get_active_tracks()

        matched_pairs, unmatched_tracks, unmatched_dets = (
            self._match_detections(active_tracks, detections)
        )

        # Update matched tracks
        for track, det in matched_pairs:
            cx, cy = self._compute_centroid(det["bbox"])
            track.last_seen_frame = frame_idx
            self._record_detection(track, frame_idx, det, (cx, cy), frame_bgr)
            track.frames_lost = 0

        # Handle unmatched existing tracks
        for track in unmatched_tracks:
            track.frames_lost += 1
            if track.frames_lost > self._max_lost_frames:
                track.active = False
                logger.debug(
                    "Track %d deactivated after %d lost frames",
                    track.obj_id, track.frames_lost,
                )

        # Create new tracks for unmatched detections
        for det in unmatched_dets:
            cx, cy = self._compute_centroid(det["bbox"])
            new_track = Track(
                obj_id=self._next_id,
                first_seen_frame=frame_idx,
                last_seen_frame=frame_idx,
            )
            self._record_detection(new_track, frame_idx, det, (cx, cy), frame_bgr)
            self._tracks.append(new_track)
            self._next_id += 1
            logger.debug("New track %d created at frame %d", new_track.obj_id, frame_idx)

        # Build output: attach track_id to each detection
        results: list[dict] = []
        for track, det in matched_pairs:
            results.append({**det, "track_id": track.obj_id})

        for det in unmatched_dets:
            cx, cy = self._compute_centroid(det["bbox"])
            # Find the track we just created for this detection
            for t in reversed(self._tracks):
                if t.centroid_history and t.centroid_history[-1] == (cx, cy):
                    results.append({**det, "track_id": t.obj_id})
                    break

        return results

    def merge_fragmented_tracks(self) -> dict[int, int]:
        """Merge short-gap track fragments using appearance and position.

        Returns:
            Mapping of ``source_track_id -> target_track_id`` for fragments
            that should be treated as the same physical pigeon.
        """
        if not self.reid_enabled:
            return {}

        mapping: dict[int, int] = {}
        tracks = sorted(self._tracks, key=lambda track: track.first_seen_frame)
        candidates_evaluated = 0
        for current in tracks:
            if not current.centroid_history:
                continue

            best: tuple[float, Track] | None = None
            for previous in tracks:
                if previous.obj_id == current.obj_id or not previous.centroid_history:
                    continue
                if previous.last_seen_frame >= current.first_seen_frame:
                    continue

                gap = current.first_seen_frame - previous.last_seen_frame
                if gap > self._reid_gap_frames:
                    continue

                spatial_distance = self._centroid_distance(
                    previous.centroid_history[-1],
                    current.centroid_history[0],
                )

                appearance_distance = self._track_appearance_distance(previous, current)
                candidates_evaluated += 1
                if appearance_distance > self._reid_appearance_threshold:
                    continue

                # A very close appearance match can rescue fragments that re-enter
                # farther away, while weaker matches still need spatial support.
                strong_appearance = appearance_distance <= max(
                    0.12,
                    self._reid_appearance_threshold * 0.55,
                )
                if spatial_distance > self._reid_spatial_threshold_px and not strong_appearance:
                    continue

                area_ratio = self._track_area_ratio(previous, current)
                if area_ratio is not None and not 0.2 <= area_ratio <= 5.0:
                    continue

                spatial_score = spatial_distance / max(self._reid_spatial_threshold_px, 1.0)
                if strong_appearance:
                    spatial_score *= 0.25
                gap_score = gap / max(self._reid_gap_frames, 1)
                score = (appearance_distance * 2.0) + spatial_score + (gap_score * 0.25)
                if best is None or score < best[0]:
                    best = (score, previous)

            if best is None:
                continue

            target = self._canonical_id(best[1].obj_id)
            source = self._canonical_id(current.obj_id)
            if source == target:
                continue
            mapping[current.obj_id] = target
            self._aliases[current.obj_id] = target

        if mapping:
            logger.info(
                "Re-ID merged %d fragmented track(s): %s",
                len(mapping),
                mapping,
            )
        elif candidates_evaluated:
            logger.info(
                "Re-ID evaluated %d candidate track link(s); no safe merges",
                candidates_evaluated,
            )
        return dict(mapping)

    def get_active_tracks(self) -> list[Track]:
        """Return all currently active tracks."""
        return [t for t in self._tracks if t.active]

    def get_all_tracks(self) -> list[Track]:
        """Return all tracks (active and inactive)."""
        return list(self._tracks)

    def assign_pigeon_id(self, track_id: int, pigeon_id: str) -> bool:
        """Assign a pigeon identity to a track.

        Args:
            track_id: The track's ``obj_id``.
            pigeon_id: The pigeon identity string.

        Returns:
            ``True`` if the track was found, ``False`` otherwise.
        """
        for track in self._tracks:
            if track.obj_id == track_id:
                track.pigeon_id = pigeon_id
                return True
        return False

    def reset(self) -> None:
        """Clear all tracks and reset the ID counter."""
        self._tracks.clear()
        self._aliases.clear()
        self._next_id = 0

    def average_confidence(self, track_id: int) -> float:
        """Return the mean confidence for a track, or 0.0 if not found."""
        confidences: list[float] = []
        for track in self._tracks:
            if self._canonical_id(track.obj_id) == track_id:
                confidences.extend(track.confidence_history)
        if confidences:
            return float(np.mean(confidences))
        return 0.0

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _compute_centroid(self, bbox: list) -> tuple[float, float]:
        """Compute the centre point of a bounding box.

        Args:
            bbox: ``[x1, y1, x2, y2]``

        Returns:
            ``(cx, cy)``
        """
        return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)

    def _record_detection(
        self,
        track: Track,
        frame_idx: int,
        det: dict,
        centroid: tuple[float, float],
        frame_bgr: np.ndarray | None,
    ) -> None:
        track.centroid_history.append(centroid)
        track.confidence_history.append(det.get("confidence", 1.0))
        track.frame_history.append(frame_idx)
        track.bbox_history.append([float(v) for v in det.get("bbox", [0, 0, 0, 0])])
        embedding = self._appearance_embedding(det, frame_bgr)
        if embedding is not None:
            track.appearance_history.append(embedding)

    def _appearance_embedding(
        self,
        det: dict,
        frame_bgr: np.ndarray | None,
    ) -> np.ndarray | None:
        if frame_bgr is None:
            return None
        bbox = det.get("bbox")
        if not bbox or len(bbox) != 4:
            return None

        height, width = frame_bgr.shape[:2]
        x1 = max(0, min(width - 1, int(round(bbox[0]))))
        y1 = max(0, min(height - 1, int(round(bbox[1]))))
        x2 = max(x1 + 1, min(width, int(round(bbox[2]))))
        y2 = max(y1 + 1, min(height, int(round(bbox[3]))))
        crop = frame_bgr[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        mask = det.get("mask")
        pixels = crop.reshape(-1, 3)
        if mask is not None:
            mask_arr = np.asarray(mask)
            if mask_arr.shape[:2] == frame_bgr.shape[:2]:
                mask_crop = mask_arr[y1:y2, x1:x2].astype(bool)
                masked = crop[mask_crop]
                if masked.size > 0:
                    pixels = masked.reshape(-1, 3)

        hist, _edges = np.histogramdd(
            pixels.astype(np.float32),
            bins=(4, 4, 4),
            range=((0, 256), (0, 256), (0, 256)),
        )
        embedding = hist.astype(np.float32).reshape(-1)
        total = float(embedding.sum())
        if total <= 0.0:
            return None
        return embedding / total

    def _track_appearance_distance(self, previous: Track, current: Track) -> float:
        if not previous.appearance_history or not current.appearance_history:
            return 1.0
        prev_embedding = previous.appearance_history[-1]
        curr_embedding = current.appearance_history[0]
        coefficient = float(np.sqrt(prev_embedding * curr_embedding).sum())
        return float(np.sqrt(max(0.0, 1.0 - min(1.0, coefficient))))

    def _track_area_ratio(self, previous: Track, current: Track) -> float | None:
        if not previous.bbox_history or not current.bbox_history:
            return None
        previous_area = self._bbox_area(previous.bbox_history[-1])
        current_area = self._bbox_area(current.bbox_history[0])
        if previous_area <= 0.0 or current_area <= 0.0:
            return None
        return current_area / previous_area

    @staticmethod
    def _bbox_area(bbox: list[float]) -> float:
        return max(0.0, float(bbox[2]) - float(bbox[0])) * max(
            0.0,
            float(bbox[3]) - float(bbox[1]),
        )

    def _canonical_id(self, track_id: int) -> int:
        seen: set[int] = set()
        current = track_id
        while current in self._aliases and current not in seen:
            seen.add(current)
            current = self._aliases[current]
        return current

    @staticmethod
    def _centroid_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        return float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except (TypeError, ValueError):
            return default

    def _match_detections(
        self,
        active_tracks: list[Track],
        detections: list[dict],
    ) -> tuple[list[tuple], list[Track], list[dict]]:
        """Greedy nearest-centroid matching.

        Args:
            active_tracks: Currently active tracks.
            detections: New frame detections.

        Returns:
            ``(matched_pairs, unmatched_tracks, unmatched_detections)``
            where ``matched_pairs`` is a list of ``(Track, det_dict)`` tuples.
        """
        if not active_tracks or not detections:
            return ([], list(active_tracks), list(detections))

        # Build centroid arrays
        track_centroids = np.array(
            [t.centroid_history[-1] for t in active_tracks], dtype=np.float64,
        )
        det_centroids = np.array(
            [self._compute_centroid(d["bbox"]) for d in detections],
            dtype=np.float64,
        )

        # Compute pairwise distance matrix (tracks x detections)
        diff = track_centroids[:, None, :] - det_centroids[None, :, :]
        dist_matrix = np.sqrt((diff ** 2).sum(axis=2))

        matched_pairs: list[tuple] = []
        matched_track_idxs: set[int] = set()
        matched_det_idxs: set[int] = set()

        # Greedy: pick smallest distance first
        num_tracks, num_dets = dist_matrix.shape
        flat_indices = np.argsort(dist_matrix, axis=None)

        for flat_idx in flat_indices:
            t_idx = int(flat_idx // num_dets)
            d_idx = int(flat_idx % num_dets)

            if t_idx in matched_track_idxs or d_idx in matched_det_idxs:
                continue

            if dist_matrix[t_idx, d_idx] > self._max_match_distance:
                break

            matched_pairs.append((active_tracks[t_idx], detections[d_idx]))
            matched_track_idxs.add(t_idx)
            matched_det_idxs.add(d_idx)

        unmatched_tracks = [
            active_tracks[i] for i in range(num_tracks)
            if i not in matched_track_idxs
        ]
        unmatched_dets = [
            detections[i] for i in range(num_dets)
            if i not in matched_det_idxs
        ]

        return (matched_pairs, unmatched_tracks, unmatched_dets)
