"""Multi-pigeon tracker for PigeonLab.

Links per-frame SAM 3 detections into persistent tracks across frames
using greedy centroid-distance matching.  No external tracking libraries
required — only NumPy.
"""

import logging
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, frame_idx: int, detections: list[dict]) -> list[dict]:
        """Assign persistent track IDs to a new set of detections.

        Args:
            frame_idx: Zero-based frame index.
            detections: List of detection dicts from SAM3Wrapper
                (keys: ``mask``, ``bbox``, ``confidence``, ``obj_id``).

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
            track.centroid_history.append((cx, cy))
            track.confidence_history.append(det.get("confidence", 1.0))
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
                centroid_history=[(cx, cy)],
                confidence_history=[det.get("confidence", 1.0)],
            )
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
        self._next_id = 0

    def average_confidence(self, track_id: int) -> float:
        """Return the mean confidence for a track, or 0.0 if not found."""
        for track in self._tracks:
            if track.obj_id == track_id:
                if not track.confidence_history:
                    return 0.0
                return float(np.mean(track.confidence_history))
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
