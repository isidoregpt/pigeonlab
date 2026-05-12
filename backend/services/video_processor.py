"""Video processing orchestrator for PigeonLab.

Ties together frame extraction, SAM 3 detection, tracking, feature
extraction, and QC flagging into a single end-to-end pipeline that
processes a video and populates all database tables.

All database operations use ``aiosqlite`` for async I/O.
"""

import logging
import os
from datetime import datetime
from typing import Callable

import aiosqlite

from database import get_db_path
from services.feature_extractor import FeatureExtractor
from services.frame_extractor import FrameExtractor
from services.gemma_reviewer import GemmaReviewer
from services.qc_rules import QCRulesEngine
from services.sam3 import get_sam3
from services.tracker import PigeonTracker

logger = logging.getLogger(__name__)


class ProcessingCancelled(Exception):
    """Raised when a user cancels an in-progress video job."""


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class VideoProcessor:
    """End-to-end video processing pipeline.

    Usage::

        processor = VideoProcessor()
        result = await processor.process_video(video_id, video_path)
    """

    def __init__(
        self,
        sam3_checkpoint: str | None = None,
        frames_dir: str = "data/frames",
    ) -> None:
        """Initialise the processor.

        Args:
            sam3_checkpoint: Optional path to the SAM 3 checkpoint.
            frames_dir: Root directory for extracted frames.
        """
        self._sam3_checkpoint = sam3_checkpoint
        self._frames_dir = frames_dir
        self._sam3 = None

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    async def process_video(
        self,
        video_id: int,
        video_path: str,
        text_prompt: str = "pigeon",
        expected_pigeon_count: int = 4,
        use_video_api: bool = True,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict:
        """Process a single video end-to-end.

        Args:
            video_id: Database video ID.
            video_path: Path to the video file on disk.
            text_prompt: SAM 3 text prompt for detection.
            expected_pigeon_count: Expected pigeon count (for QC).
            use_video_api: If ``True``, use SAM 3's video API for
                temporally-consistent tracking. Falls back to the
                per-frame image API when ``False``.

        Returns:
            Summary dict with ``video_id``, ``status``, ``total_frames``,
            ``pigeons_found``, ``features_extracted``, ``qc_flags_created``.

        Raises:
            Exception: Re-raised after marking the video as failed.
        """
        db_path = get_db_path()

        def raise_if_cancelled() -> None:
            if cancel_check is not None and cancel_check():
                raise ProcessingCancelled(f"Processing cancelled for video {video_id}")

        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            try:
                raise_if_cancelled()
                # 1. Mark processing
                await self._update_status(conn, video_id, "processing", error=None)
                await conn.commit()

                # 2. Extract frames
                logger.info("Extracting frames for video %d …", video_id)
                frame_extractor = FrameExtractor(self._frames_dir)
                extraction = frame_extractor.extract_frames(video_path, video_id)
                raise_if_cancelled()
                total_frames = extraction["total_frames"]
                fps = extraction["fps"]

                await conn.execute(
                    "UPDATE videos SET total_frames = ?, fps = ? WHERE video_id = ?",
                    (total_frames, fps, video_id),
                )
                await conn.commit()

                # 3. Lazy-load SAM 3
                if self._sam3 is None:
                    logger.info("Loading SAM 3 model …")
                    self._sam3 = get_sam3(checkpoint_path=self._sam3_checkpoint)
                raise_if_cancelled()

                # 4. Determine frame shape from first frame
                first_frame = frame_extractor.get_frame(video_id, 0)
                frame_shape = (
                    first_frame.shape[:2] if first_frame is not None
                    else (720, 1280)
                )

                # 5. Run detection + tracking
                tracker = PigeonTracker()
                feature_extractor = FeatureExtractor()
                qc_engine = QCRulesEngine(expected_pigeon_count=expected_pigeon_count)

                all_features: list[dict] = []
                all_pairwise: list[dict] = []
                all_qc_flags: list[dict] = []
                prev_features: list[dict] | None = None
                prev_tracked: list[dict] | None = None
                session_id: str | None = None

                if use_video_api:
                    raise_if_cancelled()
                    session_id = self._sam3.start_video_session(video_path)
                    logger.info(
                        "SAM 3 video session %s started for video %d",
                        session_id, video_id,
                    )

                    try:
                        logger.info(
                            "Running SAM 3 video propagation on %d frames…",
                            total_frames,
                        )
                        all_detections = self._sam3.propagate_video(
                            session_id=session_id,
                            text_prompt=text_prompt,
                            max_frames=total_frames,
                            cancel_check=raise_if_cancelled,
                        )
                        raise_if_cancelled()
                        logger.info(
                            "SAM 3 returned detections for %d frames",
                            len(all_detections),
                        )

                        for frame_num in range(total_frames):
                            raise_if_cancelled()
                            detections = all_detections.get(frame_num, [])
                            tracked = tracker.update(frame_num, detections)
                            features = feature_extractor.compute_features(
                                frame_idx=frame_num,
                                video_id=video_id,
                                tracked_detections=tracked,
                                frame_shape=frame_shape,
                                prev_detections=prev_tracked,
                                fps=fps,
                            )
                            pairwise = feature_extractor.compute_pairwise(
                                frame_idx=frame_num,
                                video_id=video_id,
                                features=features,
                            )

                            frame_flags = qc_engine.check_frame(
                                frame_num, features, prev_features,
                            )
                            qc_rows = qc_engine.flags_to_db_rows(frame_flags, video_id)

                            all_features.extend(features)
                            all_pairwise.extend(pairwise)
                            all_qc_flags.extend(qc_rows)
                            prev_features = features
                            prev_tracked = tracked

                        self._sam3.close_video_session(session_id)
                        session_id = None

                    except Exception as exc:
                        self._sam3.close_video_session(session_id)
                        session_id = None
                        if isinstance(exc, ProcessingCancelled):
                            raise
                        if not _env_bool("PIGEONLAB_SAM3_FALLBACK_PER_FRAME", False):
                            logger.exception("Video propagation failed and per-frame fallback is disabled")
                            raise RuntimeError(
                                "SAM3 video propagation failed before completion. "
                                "PigeonLab now auto-chunks long videos before processing; "
                                "if this still happens, use a shorter chunk length or retry "
                                "this video after restarting the backend."
                            ) from exc
                        logger.warning(
                            "Video propagation failed (%s), falling back to "
                            "per-frame prediction",
                            exc,
                        )
                        tracker.reset()
                        all_features.clear()
                        all_pairwise.clear()
                        all_qc_flags.clear()
                        prev_features = None
                        prev_tracked = None
                        use_video_api = False  # fall through to per-frame below

                if not use_video_api:
                    for frame_num in range(total_frames):
                        raise_if_cancelled()
                        frame_bgr = frame_extractor.get_frame(video_id, frame_num)
                        if frame_bgr is None:
                            continue

                        detections = self._sam3.predict_frame(
                            frame_bgr, text_prompt,
                        )
                        tracked = tracker.update(frame_num, detections)

                        features = feature_extractor.compute_features(
                            frame_idx=frame_num,
                                video_id=video_id,
                                tracked_detections=tracked,
                                frame_shape=frame_shape,
                                prev_detections=prev_tracked,
                                fps=fps,
                            )
                        pairwise = feature_extractor.compute_pairwise(
                            frame_idx=frame_num,
                            video_id=video_id,
                            features=features,
                        )

                        frame_flags = qc_engine.check_frame(
                            frame_num, features, prev_features,
                        )
                        qc_rows = qc_engine.flags_to_db_rows(frame_flags, video_id)

                        all_features.extend(features)
                        all_pairwise.extend(pairwise)
                        all_qc_flags.extend(qc_rows)
                        prev_features = features
                        prev_tracked = tracked

                        if frame_num % 100 == 0:
                            logger.debug(
                                "Video %d: processed frame %d/%d",
                                video_id, frame_num, total_frames,
                            )

                logger.info(
                    "Video %d: detection complete — %d features, %d pairwise rows",
                    video_id, len(all_features), len(all_pairwise),
                )
                raise_if_cancelled()

                # 6. Ensure placeholder pigeons exist before feature inserts
                track_labels = sorted({f["pigeon_id"] for f in all_features})
                for label in track_labels:
                    await conn.execute(
                        """INSERT OR IGNORE INTO pigeons (pigeon_id, first_seen, last_seen)
                           VALUES (?, ?, ?)""",
                        (label, datetime.now().isoformat(), datetime.now().isoformat()),
                    )
                if track_labels:
                    await conn.commit()

                # 7. Batch insert features
                if all_features:
                    await conn.executemany(
                        """INSERT INTO features (
                            video_id, frame_idx, pigeon_id,
                            centroid_x, centroid_y, centroid_mm_x, centroid_mm_y,
                            area_px, area_mm2, velocity_px, velocity_mm_s,
                            heading_deg, current_zone, distance_to_nearest_wall_px,
                            confidence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        [
                            (
                                f["video_id"], f["frame_idx"], f["pigeon_id"],
                                f["centroid_x"], f["centroid_y"],
                                f["centroid_mm_x"], f["centroid_mm_y"],
                                f["area_px"], f["area_mm2"],
                                f["velocity_px"], f["velocity_mm_s"],
                                f["heading_deg"], f["current_zone"],
                                f["distance_to_nearest_wall_px"],
                                f["confidence"],
                            )
                            for f in all_features
                        ],
                    )
                    await conn.commit()

                # 8. Batch insert pairwise
                if all_pairwise:
                    await conn.executemany(
                        """INSERT INTO pairwise (
                            video_id, frame_idx, pigeon_a, pigeon_b,
                            distance_px, distance_mm, overlap_iou
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        [
                            (
                                p["video_id"], p["frame_idx"],
                                p["pigeon_a"], p["pigeon_b"],
                                p["distance_px"], p["distance_mm"],
                                p["overlap_iou"],
                            )
                            for p in all_pairwise
                        ],
                    )
                    await conn.commit()

                # 9. Video-level QC + batch insert
                video_qc = qc_engine.check_video(all_features)
                video_qc_rows = qc_engine.flags_to_db_rows(video_qc, video_id)
                all_qc_flags.extend(video_qc_rows)

                if all_qc_flags:
                    await conn.executemany(
                        """INSERT INTO qc_flags (
                            video_id, frame_idx, rule_name, severity,
                            reason, review_status
                        ) VALUES (?, ?, ?, ?, ?, ?)""",
                        [
                            (
                                q["video_id"], q["frame_idx"],
                                q["rule_name"], q["severity"],
                                q["reason"], q["review_status"],
                            )
                            for q in all_qc_flags
                        ],
                    )
                    await conn.commit()

                # 10. Video assignments
                unique_track_ids: set[int] = set()
                for f in all_features:
                    raw_id = str(f["pigeon_id"])
                    try:
                        unique_track_ids.add(int(raw_id.replace("unknown_", "", 1)))
                    except (ValueError, TypeError):
                        pass

                now_iso = datetime.now().isoformat()
                for tid in unique_track_ids:
                    await conn.execute(
                        """INSERT INTO video_assignments (
                            video_id, video_obj_id, pigeon_id, confidence,
                            match_method, review_status, assigned_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            video_id, tid,
                            f"unknown_{tid}",
                            tracker.average_confidence(tid),
                            "placeholder", "raw", now_iso,
                        ),
                    )

                await conn.commit()

                # 11. Optional Gemma reviewer pass
                gemma_review = {"status": "skipped"}
                try:
                    reviewer = GemmaReviewer(frames_dir=self._frames_dir)
                    gemma_review = await reviewer.review_video(
                        conn=conn,
                        video_id=video_id,
                        total_frames=total_frames,
                        fps=fps,
                    )
                    await conn.commit()
                    logger.info(
                        "Video %d Gemma review result: %s",
                        video_id,
                        gemma_review,
                    )
                except Exception as exc:
                    logger.exception("Gemma reviewer failed for video %d", video_id)
                    gemma_review = {"status": "failed", "error": str(exc)}

                # 12. Mark completed. A zero-detection chunk completed the
                # pipeline, but should be visible as "no data" in the UI/report.
                model_version = getattr(self._sam3, "version", "sam3")
                final_status = (
                    "completed_no_detections"
                    if len(unique_track_ids) == 0 and len(all_features) == 0
                    else "completed"
                )
                await conn.execute(
                    """UPDATE videos
                       SET processing_status = ?,
                           processed_at = ?,
                           processing_error = NULL,
                           model_version = ?
                       WHERE video_id = ?""",
                    (final_status, datetime.now().isoformat(), model_version, video_id),
                )
                await conn.commit()

                # 13. Return summary
                result = {
                    "video_id": video_id,
                    "status": final_status,
                    "total_frames": total_frames,
                    "pigeons_found": len(unique_track_ids),
                    "features_extracted": len(all_features),
                    "qc_flags_created": len(all_qc_flags),
                    "gemma_review": gemma_review,
                }
                logger.info("Video %d processing complete: %s", video_id, result)
                return result

            except ProcessingCancelled as exc:
                logger.info("Processing cancelled for video %d", video_id)
                await self._discard_partial_results(conn, video_id)
                await self._update_status(conn, video_id, "cancelled", error=str(exc))
                await conn.commit()
                return {
                    "video_id": video_id,
                    "status": "cancelled",
                    "total_frames": 0,
                    "pigeons_found": 0,
                    "features_extracted": 0,
                    "qc_flags_created": 0,
                }
            except Exception as exc:
                logger.exception("Processing failed for video %d", video_id)
                await self._update_status(conn, video_id, "failed", error=str(exc))
                await conn.commit()
                raise
            finally:
                if session_id is not None:
                    self._sam3.close_video_session(session_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _update_status(
        self,
        conn: aiosqlite.Connection,
        video_id: int,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update a video's processing status."""
        if error is None:
            await conn.execute(
                "UPDATE videos SET processing_status = ?, processing_error = NULL WHERE video_id = ?",
                (status, video_id),
            )
        else:
            await conn.execute(
                """UPDATE videos
                   SET processing_status = ?,
                       processing_error = ?,
                       processed_at = ?
                   WHERE video_id = ?""",
                (status, error[:1000], datetime.now().isoformat(), video_id),
            )

    async def _discard_partial_results(self, conn: aiosqlite.Connection, video_id: int) -> None:
        """Remove any derived rows/frames from an aborted processing attempt."""
        for table in [
            "features",
            "pairwise",
            "behaviors",
            "clip_library",
            "droppings",
            "qc_flags",
            "review_tasks",
            "ai_observations",
            "video_assignments",
            "track_edits",
        ]:
            await conn.execute(f"DELETE FROM {table} WHERE video_id = ?", (video_id,))
        FrameExtractor(self._frames_dir).cleanup_frames(video_id)
