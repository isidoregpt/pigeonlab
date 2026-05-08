"""Gemma/Ollama reviewer for optional AI-assisted video annotation."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:  # pragma: no cover - setup_check reports this clearly
    httpx = None

from database import DB_PATH, get_db

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
VALID_MODES = {"off", "assist", "auto"}
KNOWN_BEHAVIORS = {
    "preening",
    "drinking",
    "eating",
    "bathing",
    "pooping_common_area",
    "pooping_uncommon_area",
    "wing_flapping",
    "walking",
    "resting",
}


@dataclass
class GemmaReviewerConfig:
    mode: str
    model: str
    base_url: str
    sample_interval_seconds: int
    max_frames_per_video: int
    confidence_threshold: float


def _env_default(key: str, fallback: str) -> str:
    return os.getenv(key, fallback)


DEFAULTS = {
    "gemma_review_mode": _env_default("PIGEONLAB_GEMMA_REVIEW_MODE", "off"),
    "gemma_model": _env_default("PIGEONLAB_GEMMA_MODEL", "gemma4:e4b"),
    "gemma_base_url": _env_default("PIGEONLAB_GEMMA_BASE_URL", "http://localhost:11434"),
    "gemma_sample_interval_seconds": _env_default("PIGEONLAB_GEMMA_SAMPLE_SECONDS", "15"),
    "gemma_max_frames_per_video": _env_default("PIGEONLAB_GEMMA_MAX_FRAMES", "20"),
    "gemma_confidence_threshold": _env_default("PIGEONLAB_GEMMA_CONFIDENCE_THRESHOLD", "0.65"),
}


def _clamp_int(value: str | int | None, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _clamp_float(value: str | float | None, default: float, low: float, high: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


def _normalise_mode(value: str | None) -> str:
    mode = (value or "off").strip().lower()
    return mode if mode in VALID_MODES else "off"


def _config_from_values(values: dict[str, str]) -> GemmaReviewerConfig:
    return GemmaReviewerConfig(
        mode=_normalise_mode(values.get("gemma_review_mode")),
        model=(values.get("gemma_model") or DEFAULTS["gemma_model"]).strip() or "gemma4:e4b",
        base_url=(values.get("gemma_base_url") or DEFAULTS["gemma_base_url"]).strip().rstrip("/"),
        sample_interval_seconds=_clamp_int(
            values.get("gemma_sample_interval_seconds"),
            15,
            1,
            300,
        ),
        max_frames_per_video=_clamp_int(
            values.get("gemma_max_frames_per_video"),
            20,
            1,
            200,
        ),
        confidence_threshold=_clamp_float(
            values.get("gemma_confidence_threshold"),
            0.65,
            0.0,
            1.0,
        ),
    )


def get_gemma_config() -> GemmaReviewerConfig:
    values = dict(DEFAULTS)
    try:
        if DB_PATH.exists():
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT key, value FROM app_settings WHERE key LIKE 'gemma_%'"
                ).fetchall()
                values.update({row["key"]: row["value"] for row in rows})
    except Exception:
        logger.debug("Using Gemma defaults because app_settings is unavailable", exc_info=True)
    return _config_from_values(values)


async def get_gemma_config_async(conn) -> GemmaReviewerConfig:
    values = dict(DEFAULTS)
    cursor = await conn.execute("SELECT key, value FROM app_settings WHERE key LIKE 'gemma_%'")
    rows = await cursor.fetchall()
    await cursor.close()
    values.update({row["key"]: row["value"] for row in rows})
    return _config_from_values(values)


def save_gemma_config(payload: dict[str, Any]) -> GemmaReviewerConfig:
    current = get_gemma_config()
    next_values = {
        "gemma_review_mode": _normalise_mode(payload.get("mode", current.mode)),
        "gemma_model": str(payload.get("model", current.model)).strip() or current.model,
        "gemma_base_url": str(payload.get("base_url", current.base_url)).strip().rstrip("/") or current.base_url,
        "gemma_sample_interval_seconds": str(
            _clamp_int(
                payload.get("sample_interval_seconds", current.sample_interval_seconds),
                current.sample_interval_seconds,
                1,
                300,
            )
        ),
        "gemma_max_frames_per_video": str(
            _clamp_int(
                payload.get("max_frames_per_video", current.max_frames_per_video),
                current.max_frames_per_video,
                1,
                200,
            )
        ),
        "gemma_confidence_threshold": str(
            _clamp_float(
                payload.get("confidence_threshold", current.confidence_threshold),
                current.confidence_threshold,
                0.0,
                1.0,
            )
        ),
    }
    with get_db() as conn:
        for key, value in next_values.items():
            conn.execute(
                """INSERT INTO app_settings (key, value, updated_at)
                   VALUES (?, ?, datetime('now'))
                   ON CONFLICT(key) DO UPDATE SET
                       value = excluded.value,
                       updated_at = datetime('now')""",
                (key, value),
            )
        conn.commit()
    return get_gemma_config()


async def get_gemma_status() -> dict:
    config = get_gemma_config()
    errors: list[str] = []
    warnings: list[str] = []
    installed_models: list[str] = []
    reachable = False
    model_available = False

    if httpx is None:
        if config.mode != "off":
            errors.append("Python package 'httpx' is not installed. Run: pip install httpx")
    else:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{config.base_url}/api/tags")
                response.raise_for_status()
                reachable = True
                data = response.json()
                installed_models = sorted(
                    item.get("name", "")
                    for item in data.get("models", [])
                    if item.get("name")
                )
                wanted_name = config.model.split(":", 1)[0]
                model_available = any(
                    name == config.model or name.split(":", 1)[0] == wanted_name
                    for name in installed_models
                )
        except Exception as exc:
            if config.mode != "off":
                errors.append(f"Ollama is not reachable at {config.base_url}: {exc}")

    if config.mode != "off" and reachable and not model_available:
        errors.append(
            f"Ollama is running, but model '{config.model}' is not installed. "
            f"Run: ollama pull {config.model}"
        )
    if config.mode == "off":
        warnings.append("Gemma reviewer is disabled; human review remains active.")
    return {
        "mode": config.mode,
        "enabled": config.mode != "off",
        "ready": config.mode != "off" and reachable and model_available,
        "reachable": reachable,
        "model_available": model_available,
        "model": config.model,
        "base_url": config.base_url,
        "sample_interval_seconds": config.sample_interval_seconds,
        "max_frames_per_video": config.max_frames_per_video,
        "confidence_threshold": config.confidence_threshold,
        "installed_models": installed_models,
        "errors": errors,
        "warnings": warnings,
    }


def _frame_path(frames_dir: str, video_id: int, frame_idx: int) -> Path:
    base = Path(frames_dir)
    if not base.is_absolute():
        base = PROJECT_ROOT / base
    return base / str(video_id) / f"{frame_idx:06d}.jpg"


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _extract_json(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        return {}
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"items": parsed}
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        parsed = json.loads(raw[start : end + 1])
        return parsed if isinstance(parsed, dict) else {"items": parsed}
    return {}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalise_behavior(value: Any) -> str:
    label = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "flapping": "wing_flapping",
        "wing_flap": "wing_flapping",
        "wings_flapping": "wing_flapping",
        "pooping": "pooping_uncommon_area",
        "defecating": "pooping_uncommon_area",
        "unknown": "",
        "none": "",
    }
    label = aliases.get(label, label)
    return label if label in KNOWN_BEHAVIORS else ""


def _review_status(mode: str, confidence: float, threshold: float) -> str:
    return "approved" if mode == "auto" and confidence >= threshold else "raw"


def _track_obj_id(track_id: Any) -> int | None:
    text = str(track_id or "")
    match = re.search(r"(\d+)$", text)
    return int(match.group(1)) if match else None


class GemmaReviewer:
    """Runs the optional Gemma reviewer over sampled processed frames."""

    def __init__(self, frames_dir: str = "data/frames") -> None:
        self._frames_dir = frames_dir

    async def review_video(
        self,
        conn,
        video_id: int,
        total_frames: int,
        fps: float,
    ) -> dict:
        config = await get_gemma_config_async(conn)
        if config.mode == "off":
            return {"status": "skipped", "reason": "Gemma reviewer disabled"}

        status = await get_gemma_status()
        if not status["ready"]:
            return {
                "status": "skipped",
                "reason": "Gemma reviewer is not ready",
                "errors": status["errors"],
            }

        frame_indices = self._sample_frames(total_frames, fps, config)
        known_pigeons = await self._known_pigeons(conn)
        counts = {
            "frames_reviewed": 0,
            "observations_created": 0,
            "behaviors_created": 0,
            "droppings_created": 0,
            "qc_flags_created": 0,
            "identity_updates": 0,
            "errors": [],
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            for frame_idx in frame_indices:
                image_path = _frame_path(self._frames_dir, video_id, frame_idx)
                if not image_path.is_file():
                    counts["errors"].append(f"Missing frame {frame_idx}")
                    continue

                features = await self._frame_features(conn, video_id, frame_idx)
                try:
                    analysis = await self._analyze_frame(
                        client=client,
                        config=config,
                        image_path=image_path,
                        video_id=video_id,
                        frame_idx=frame_idx,
                        fps=fps,
                        features=features,
                        known_pigeons=known_pigeons,
                    )
                    created = await self._persist_analysis(
                        conn=conn,
                        config=config,
                        video_id=video_id,
                        frame_idx=frame_idx,
                        fps=fps,
                        analysis=analysis,
                        known_pigeons=known_pigeons,
                    )
                    for key, value in created.items():
                        counts[key] += value
                    counts["frames_reviewed"] += 1
                except Exception as exc:
                    logger.exception("Gemma review failed for video_id=%s frame=%s", video_id, frame_idx)
                    counts["errors"].append(f"Frame {frame_idx}: {exc}")

        return {"status": "completed", "mode": config.mode, "model": config.model, **counts}

    def _sample_frames(
        self,
        total_frames: int,
        fps: float,
        config: GemmaReviewerConfig,
    ) -> list[int]:
        if total_frames <= 0:
            return []
        step = max(1, round(max(fps, 1.0) * config.sample_interval_seconds))
        frames = list(range(0, total_frames, step))
        if total_frames - 1 not in frames:
            frames.append(total_frames - 1)
        return sorted(set(frames))[: config.max_frames_per_video]

    async def _known_pigeons(self, conn) -> list[dict]:
        cursor = await conn.execute(
            """SELECT pigeon_id, physical_markers, preferred_zones, notes
               FROM pigeons
               WHERE pigeon_id NOT LIKE 'unknown_%'
               ORDER BY pigeon_id"""
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(row) for row in rows]

    async def _frame_features(self, conn, video_id: int, frame_idx: int) -> list[dict]:
        cursor = await conn.execute(
            """SELECT pigeon_id, centroid_x, centroid_y, heading_deg, current_zone,
                      velocity_mm_s, confidence
               FROM features
               WHERE video_id = ? AND frame_idx = ?
               ORDER BY pigeon_id""",
            (video_id, frame_idx),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [dict(row) for row in rows]

    async def _analyze_frame(
        self,
        client: httpx.AsyncClient,
        config: GemmaReviewerConfig,
        image_path: Path,
        video_id: int,
        frame_idx: int,
        fps: float,
        features: list[dict],
        known_pigeons: list[dict],
    ) -> dict:
        prompt = self._frame_prompt(video_id, frame_idx, fps, features, known_pigeons)
        response = await client.post(
            f"{config.base_url}/api/chat",
            json={
                "model": config.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are PigeonLab's AI reviewer. Analyze lab frames for pigeons, "
                            "objects, zones, facing direction, and pigeon behavior. Return only "
                            "valid JSON. Do not include markdown or explanatory prose."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [_encode_image(image_path)],
                    },
                ],
                "format": "json",
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.95,
                    "top_k": 64,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "")
        return _extract_json(content)

    def _frame_prompt(
        self,
        video_id: int,
        frame_idx: int,
        fps: float,
        features: list[dict],
        known_pigeons: list[dict],
    ) -> str:
        return json.dumps(
            {
                "task": "Analyze this pigeon lab frame and return structured annotations.",
                "video_id": video_id,
                "frame_idx": frame_idx,
                "timestamp_seconds": round(frame_idx / max(fps, 1.0), 2),
                "sam3_tracks": features,
                "known_pigeons": known_pigeons,
                "allowed_behaviors": sorted(KNOWN_BEHAVIORS),
                "facing_options": [
                    "north",
                    "south",
                    "east",
                    "west",
                    "upstage",
                    "downstage",
                    "left",
                    "right",
                    "toward_camera",
                    "away_from_camera",
                    "unknown",
                ],
                "coordinate_rules": (
                    "For object and dropping coordinates use a normalized 0-1000 image grid. "
                    "For boxes use [y1, x1, y2, x2]. Match pigeon observations to sam3_tracks "
                    "using pigeon_id when possible."
                ),
                "pooping_rules": (
                    "Use pooping_common_area only for a tray, bedding, litter, or obvious common "
                    "dropping zone. Use pooping_uncommon_area for food, water, perch, nest, or "
                    "open floor areas that are not an obvious dropping zone."
                ),
                "output_schema": {
                    "frame_summary": "short scene description",
                    "objects": [
                        {
                            "label": "waterer|feeder|bath|perch|nest|door|toy|other",
                            "box_2d": [0, 0, 0, 0],
                            "confidence": 0.0,
                            "notes": "",
                        }
                    ],
                    "pigeons": [
                        {
                            "track_id": "unknown_1",
                            "identity": "known pigeon_id or empty string",
                            "identity_confidence": 0.0,
                            "location": "zone or short location",
                            "facing": "direction",
                            "behavior": "one allowed behavior or empty string",
                            "confidence": 0.0,
                            "notes": "",
                        }
                    ],
                    "droppings": [
                        {
                            "x": 0,
                            "y": 0,
                            "zone": "",
                            "common_area": True,
                            "confidence": 0.0,
                            "notes": "",
                        }
                    ],
                    "qc_flags": [
                        {
                            "severity": "low|medium|high|critical",
                            "reason": "tracking, identity, object, or behavior uncertainty",
                        }
                    ],
                },
            },
            ensure_ascii=True,
        )

    async def _persist_analysis(
        self,
        conn,
        config: GemmaReviewerConfig,
        video_id: int,
        frame_idx: int,
        fps: float,
        analysis: dict,
        known_pigeons: list[dict],
    ) -> dict[str, int]:
        counts = {
            "observations_created": 0,
            "behaviors_created": 0,
            "droppings_created": 0,
            "qc_flags_created": 0,
            "identity_updates": 0,
        }
        source_model = f"ollama/{config.model}"
        review_status = "approved" if config.mode == "auto" else "raw"

        summary = analysis.get("frame_summary")
        if summary:
            await self._insert_observation(
                conn,
                video_id,
                frame_idx,
                None,
                "scene_summary",
                "summary",
                None,
                None,
                None,
                source_model,
                review_status,
                {"summary": summary},
            )
            counts["observations_created"] += 1

        for obj in analysis.get("objects") or []:
            if not isinstance(obj, dict):
                continue
            confidence = _to_float(obj.get("confidence"), 0.0)
            await self._insert_observation(
                conn,
                video_id,
                frame_idx,
                None,
                "object",
                str(obj.get("label") or "object"),
                confidence,
                None,
                obj.get("box_2d"),
                source_model,
                _review_status(config.mode, confidence, config.confidence_threshold),
                obj,
            )
            counts["observations_created"] += 1

        known_ids = {p["pigeon_id"] for p in known_pigeons}
        for pigeon in analysis.get("pigeons") or []:
            if not isinstance(pigeon, dict):
                continue
            track_id = str(pigeon.get("track_id") or "")
            confidence = _to_float(pigeon.get("confidence"), 0.0)
            zone = str(pigeon.get("location") or "")[:120] or None
            await self._insert_observation(
                conn,
                video_id,
                frame_idx,
                track_id or None,
                "pigeon_state",
                str(pigeon.get("facing") or "unknown"),
                confidence,
                zone,
                None,
                source_model,
                _review_status(config.mode, confidence, config.confidence_threshold),
                pigeon,
            )
            counts["observations_created"] += 1

            behavior = _normalise_behavior(pigeon.get("behavior"))
            if behavior and confidence >= config.confidence_threshold:
                behavior_pigeon = track_id or "unknown_0"
                await conn.execute(
                    "INSERT OR IGNORE INTO pigeons (pigeon_id, first_seen) VALUES (?, datetime('now'))",
                    (behavior_pigeon,),
                )
                await conn.execute(
                    """INSERT INTO behaviors (
                        video_id, pigeon_id, behavior, source, model_version,
                        start_frame, end_frame, duration_seconds, confidence,
                        zone, interacting_with, review_status, details
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        video_id,
                        behavior_pigeon,
                        behavior,
                        "gemma4",
                        source_model,
                        frame_idx,
                        frame_idx,
                        round(config.sample_interval_seconds, 2),
                        confidence,
                        zone,
                        None,
                        _review_status(config.mode, confidence, config.confidence_threshold),
                        json.dumps(pigeon, ensure_ascii=True),
                    ),
                )
                counts["behaviors_created"] += 1

            identity = str(pigeon.get("identity") or "").strip()
            identity_confidence = _to_float(pigeon.get("identity_confidence"), 0.0)
            if (
                config.mode == "auto"
                and identity
                and identity in known_ids
                and identity_confidence >= config.confidence_threshold
            ):
                updated = await self._apply_identity_update(
                    conn,
                    video_id,
                    track_id,
                    identity,
                    identity_confidence,
                )
                counts["identity_updates"] += updated

        for dropping in analysis.get("droppings") or []:
            if not isinstance(dropping, dict):
                continue
            confidence = _to_float(dropping.get("confidence"), 0.0)
            if confidence < config.confidence_threshold:
                continue
            await conn.execute(
                """INSERT INTO droppings (
                    video_id, frame_idx, centroid_x, centroid_y, area_px, zone,
                    confidence, detection_method, review_status, deduplicated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (
                    video_id,
                    frame_idx,
                    _to_int(dropping.get("x")),
                    _to_int(dropping.get("y")),
                    None,
                    str(dropping.get("zone") or "")[:120] or None,
                    confidence,
                    "gemma4",
                    _review_status(config.mode, confidence, config.confidence_threshold),
                ),
            )
            counts["droppings_created"] += 1

        for flag in analysis.get("qc_flags") or []:
            if not isinstance(flag, dict):
                continue
            reason = str(flag.get("reason") or "").strip()
            if not reason:
                continue
            severity = str(flag.get("severity") or "medium").lower()
            if severity not in {"low", "medium", "high", "critical"}:
                severity = "medium"
            await conn.execute(
                """INSERT INTO qc_flags (
                    video_id, frame_idx, rule_name, severity, reason, review_status
                ) VALUES (?, ?, 'gemma4_review', ?, ?, 'pending')""",
                (video_id, frame_idx, severity, reason[:1000]),
            )
            counts["qc_flags_created"] += 1

        return counts

    async def _insert_observation(
        self,
        conn,
        video_id: int,
        frame_idx: int,
        pigeon_id: str | None,
        observation_type: str,
        label: str | None,
        confidence: float | None,
        zone: str | None,
        bbox: Any,
        source_model: str,
        review_status: str,
        details: Any,
    ) -> None:
        await conn.execute(
            """INSERT INTO ai_observations (
                video_id, frame_idx, pigeon_id, observation_type, label,
                confidence, zone, bbox_json, source_model, review_status, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                video_id,
                frame_idx,
                pigeon_id,
                observation_type,
                label,
                confidence,
                zone,
                json.dumps(bbox, ensure_ascii=True) if bbox is not None else None,
                source_model,
                review_status,
                json.dumps(details, ensure_ascii=True),
            ),
        )

    async def _apply_identity_update(
        self,
        conn,
        video_id: int,
        track_id: str,
        identity: str,
        confidence: float,
    ) -> int:
        obj_id = _track_obj_id(track_id)
        if obj_id is None:
            return 0

        cursor = await conn.execute(
            """SELECT * FROM video_assignments
               WHERE video_id = ? AND video_obj_id = ?
               ORDER BY id DESC LIMIT 1""",
            (video_id, obj_id),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            return 0

        assignment = dict(row)
        old_pigeon = assignment["pigeon_id"]
        candidates = [old_pigeon, f"unknown_{obj_id}", str(obj_id)]
        deduped = []
        for item in candidates:
            if item and item not in deduped:
                deduped.append(item)
        placeholders = ",".join("?" for _ in deduped)

        await conn.execute(
            """UPDATE video_assignments
               SET pigeon_id = ?, confidence = ?, match_method = 'gemma4',
                   review_status = 'approved', reviewed_at = datetime('now'),
                   reviewed_by = 'gemma4'
               WHERE id = ?""",
            (identity, confidence, assignment["id"]),
        )
        await conn.execute(
            f"UPDATE features SET pigeon_id = ? WHERE video_id = ? AND pigeon_id IN ({placeholders})",
            [identity, video_id, *deduped],
        )
        await conn.execute(
            f"UPDATE behaviors SET pigeon_id = ? WHERE video_id = ? AND pigeon_id IN ({placeholders})",
            [identity, video_id, *deduped],
        )
        await conn.execute(
            f"UPDATE pairwise SET pigeon_a = ? WHERE video_id = ? AND pigeon_a IN ({placeholders})",
            [identity, video_id, *deduped],
        )
        await conn.execute(
            f"UPDATE pairwise SET pigeon_b = ? WHERE video_id = ? AND pigeon_b IN ({placeholders})",
            [identity, video_id, *deduped],
        )
        await conn.execute(
            """INSERT INTO identity_reviews (
                assignment_id, action, old_pigeon_id, new_pigeon_id, reviewer, reviewed_at, notes
            ) VALUES (?, 'reassign', ?, ?, 'gemma4', datetime('now'), ?)""",
            (
                assignment["id"],
                old_pigeon,
                identity,
                f"Gemma4 identity confidence {confidence:.2f}",
            ),
        )
        return 1
