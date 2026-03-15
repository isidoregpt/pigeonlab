# PigeonLab: Complete Pigeon Research Platform

## Architecture & Implementation Specification

### Platform: Windows 11 + NVIDIA A6000 | SAM 3 + Claude

### Version: This document supersedes all previous pipeline and application documents.

---

## What PigeonLab Is

PigeonLab is a **pigeon-specialized research application** — not a wrapper around third-party tools. It replaces the combined EZannot + LabGym stack with a single system purpose-built for pigeon behavioral research.

### What It Replaces

| Was | Becomes | How |
|-----|---------|-----|
| EZannot | PigeonLab review workflow | Native mask/track/identity review tools with QC-driven queues |
| LabGym detection/tracking | PigeonLab Layer 1 (SAM3) | Text-prompted detection, video propagation, multi-camera support |
| LabGym behavior quantification | PigeonLab Layers 4A + 4B | Rule-based behaviors immediately, learned behaviors via native training pipeline |
| LabGym classifier training | PigeonLab clip extraction + training pipeline | Extract clips, label in-app, train classifiers, version models, re-infer across archive |
| External annotation tools | PigeonLab review UI | Seed review, track correction, identity confirmation, behavior label review |

### What It Does NOT Try to Be

- Not a generic multi-animal platform — pigeon-specific quality comes first
- Not a real-time monitoring system (batch processing; real-time is a future consideration)
- Not a LabGym clone — absorbs the valuable concepts, leaves out the generic-animal abstractions

---

## System Layers (Enhanced)

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 7: WEB APPLICATION                                        │
│  Ingestion, review, analysis, training, export                   │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 6: BENCHMARKING & EVALUATION                              │
│  Segmentation, tracking, identity, behavior, droppings metrics   │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 5: LEARNED BEHAVIOR ENGINE (Track B)                      │
│  Clip extraction, labeling, training, versioned models           │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 4: RULE-BASED BEHAVIOR ENGINE (Track A)                   │
│  Stationary, feeding, resting, locomotion, social proximity      │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3: SPATIAL & KINEMATIC FEATURES                           │
│  Zones, heatmaps, heading proxy, velocity, pairwise, dwell time │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: TRACKING & PERSISTENT IDENTITY                         │
│  Masks → tracks → within-video IDs → cross-session identity      │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 1: SAM3 DETECTION & SEGMENTATION                          │
│  Text-prompted detection, video propagation, droppings candidates │
├─────────────────────────────────────────────────────────────────┤
│  FOUNDATION: DATABASE + REVIEW + DROPPINGS SUBSYSTEM             │
│  Truth states, audit trail, review queues, droppings mapping     │
└─────────────────────────────────────────────────────────────────┘
```

### What Is New vs Previous Spec

| Component | Previous Spec | This Spec |
|-----------|--------------|-----------|
| Layer 5 (Learned Behaviors) | "Deferred to Phase 5, ongoing" | Fully specified: clip extraction, label manager, training pipeline, model registry |
| Layer 6 (Benchmarking) | Not present | New: benchmark modules for every subsystem with precision/recall/F1 |
| Layer 7 (Web App) | "Phase 4, build later" | Fully specified: 5 sections (Ingestion, Review, Analysis, Training, Export) |
| Review Workflow | "Flagged frame review bundle" | Full EZannot replacement: mask correction, track merge/split, identity confirmation |
| Database | Results storage | Lifecycle-aware: raw → reviewed → approved states, audit trail, model versioning |
| Droppings | Subsystem with fallback ladder | Formal subsystem with benchmark workflow, deduplication, review queue |
| Clip Extraction | Not present | New: LabGym replacement — extract, label, train, version, re-infer |

---

## Technology Stack (Unchanged)

| Layer | Technology | Version |
|-------|-----------|---------|
| OS | Windows 11 | 64-bit |
| Python | 3.12+ | 3.12.10 |
| CUDA | 12.6+ | |
| PyTorch | 2.7+ | |
| SAM3 | Latest from GitHub | Editable install |
| Claude API | claude-sonnet-4-6 | Instruction parsing, reporting, triage |
| FFmpeg | 8.0.1 (stable) | Frame extraction |
| HuggingFace Hub | Latest | SAM3 checkpoint access |
| FastAPI | 0.100+ | Web application backend (Phase 4) |
| SQLite | Built into Python | Central database |

---

## Foundation: Enhanced Database

The database is the backbone of PigeonLab. Every layer writes to it. Every review action updates it. Every report reads from it. It must distinguish what the model guessed, what the human confirmed, and what downstream analytics are allowed to trust.

### Truth States

Every important output has a lifecycle:

```
RAW (model output) → REVIEWED (human looked at it) → APPROVED (human confirmed it)
```

Placeholder identities, unreviewed behavior events, and unbenchmarked droppings detections are all **RAW** until explicitly reviewed.

### Schema

```sql
-- ═══════════════════════════════════════════════════════════════
-- CORE TABLES
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE videos (
    video_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    video_name      TEXT NOT NULL UNIQUE,
    session_id      TEXT,
    camera_type     TEXT,
    total_frames    INTEGER,
    fps             REAL,
    processed_at    TEXT,
    review_status   TEXT DEFAULT 'raw',        -- raw | reviewed | approved
    model_version   TEXT,                       -- SAM3 version used
    config_hash     TEXT,                       -- Hash of config used for reproducibility
    notes           TEXT DEFAULT ''
);

CREATE TABLE pigeons (
    pigeon_id           TEXT PRIMARY KEY,
    physical_markers    TEXT,
    appearance_embedding TEXT,
    preferred_zones     TEXT,                   -- JSON
    total_frames_observed INTEGER DEFAULT 0,
    first_seen          TEXT,
    last_seen           TEXT,
    notes               TEXT DEFAULT ''
);

-- ═══════════════════════════════════════════════════════════════
-- IDENTITY & TRACKING
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE video_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        INTEGER NOT NULL,
    video_obj_id    INTEGER NOT NULL,
    pigeon_id       TEXT NOT NULL,
    confidence      REAL,
    match_method    TEXT,                       -- marker | appearance | spatial | manual | placeholder
    review_status   TEXT DEFAULT 'raw',         -- raw | reviewed | approved
    assigned_at     TEXT,
    reviewed_at     TEXT,
    reviewed_by     TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(video_id),
    FOREIGN KEY (pigeon_id) REFERENCES pigeons(pigeon_id)
);

CREATE TABLE identity_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id   INTEGER NOT NULL,
    action          TEXT NOT NULL,              -- confirm | reject | reassign
    old_pigeon_id   TEXT,
    new_pigeon_id   TEXT,
    reviewer        TEXT,
    reviewed_at     TEXT,
    notes           TEXT,
    FOREIGN KEY (assignment_id) REFERENCES video_assignments(id)
);

CREATE TABLE track_edits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        INTEGER NOT NULL,
    frame_idx       INTEGER,
    edit_type       TEXT,                       -- merge | split | delete | correct_mask
    old_obj_id      INTEGER,
    new_obj_id      INTEGER,
    editor          TEXT,
    edited_at       TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

-- ═══════════════════════════════════════════════════════════════
-- SPATIAL FEATURES
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE features (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        INTEGER,
    frame_idx       INTEGER,
    pigeon_id       TEXT,
    centroid_x      REAL,
    centroid_y      REAL,
    centroid_mm_x   REAL,
    centroid_mm_y   REAL,
    area_px         INTEGER,
    area_mm2        REAL,
    velocity_px     REAL,
    velocity_mm_s   REAL,
    heading_deg     REAL,                      -- Estimated proxy, not anatomical facing
    current_zone    TEXT,
    distance_to_nearest_wall_px REAL,
    confidence      REAL DEFAULT 1.0,          -- Allows exclusion of bad frames
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE TABLE pairwise (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        INTEGER,
    frame_idx       INTEGER,
    pigeon_a        TEXT,
    pigeon_b        TEXT,
    distance_px     REAL,
    distance_mm     REAL,
    overlap_iou     REAL DEFAULT 0.0,          -- True mask IoU when bboxes overlap
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

-- ═══════════════════════════════════════════════════════════════
-- BEHAVIORS
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE behaviors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        INTEGER,
    pigeon_id       TEXT,
    behavior        TEXT,
    source          TEXT NOT NULL,              -- rule_engine | learned_model
    model_version   TEXT,                       -- NULL for rule_engine, version string for learned
    start_frame     INTEGER,
    end_frame       INTEGER,
    duration_seconds REAL,
    confidence      REAL,
    zone            TEXT,
    interacting_with TEXT,
    review_status   TEXT DEFAULT 'raw',
    details         TEXT,                       -- JSON
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE TABLE behavior_labels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    clip_id         INTEGER NOT NULL,
    behavior_class  TEXT NOT NULL,
    labeler         TEXT,
    labeled_at      TEXT,
    split           TEXT DEFAULT 'train',       -- train | val | test
    notes           TEXT,
    FOREIGN KEY (clip_id) REFERENCES clip_library(id)
);

-- ═══════════════════════════════════════════════════════════════
-- CLIP LIBRARY (LabGym replacement core)
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE clip_library (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        INTEGER,
    pigeon_id       TEXT,
    start_frame     INTEGER,
    end_frame       INTEGER,
    duration_seconds REAL,
    clip_path       TEXT,                       -- Path to extracted clip file
    mask_overlay    BOOLEAN DEFAULT 1,          -- Whether mask is burned into clip
    zone            TEXT,
    velocity_context REAL,                      -- Average velocity during clip
    pairwise_context TEXT,                      -- JSON: nearby pigeons and distances
    extraction_reason TEXT,                     -- candidate_behavior | manual | random
    created_at      TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

-- ═══════════════════════════════════════════════════════════════
-- MODEL REGISTRY
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE model_registry (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name      TEXT NOT NULL,
    model_type      TEXT NOT NULL,              -- behavior_classifier | droppings_detector | etc.
    version         TEXT NOT NULL,
    checkpoint_path TEXT,
    training_config TEXT,                       -- JSON
    training_clips  INTEGER,                    -- Number of clips used
    train_accuracy  REAL,
    val_accuracy    REAL,
    test_accuracy   REAL,
    created_at      TEXT,
    notes           TEXT,
    is_active       BOOLEAN DEFAULT 0           -- Which version is currently used for inference
);

-- ═══════════════════════════════════════════════════════════════
-- DROPPINGS
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE droppings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        INTEGER,
    frame_idx       INTEGER,
    centroid_x      REAL,
    centroid_y      REAL,
    area_px         INTEGER,
    zone            TEXT,
    confidence      REAL,
    detection_method TEXT,                      -- sam3_text | finetuned | background_diff | manual
    review_status   TEXT DEFAULT 'raw',
    deduplicated    BOOLEAN DEFAULT 0,          -- Whether this has been dedup'd against adjacent frames
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE TABLE droppings_reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dropping_id     INTEGER NOT NULL,
    action          TEXT NOT NULL,              -- confirm | reject
    reviewer        TEXT,
    reviewed_at     TEXT,
    FOREIGN KEY (dropping_id) REFERENCES droppings(id)
);

-- ═══════════════════════════════════════════════════════════════
-- QC & REVIEW
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE qc_flags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        INTEGER,
    frame_idx       INTEGER,
    rule_name       TEXT,
    severity        TEXT,
    reason          TEXT,
    review_status   TEXT DEFAULT 'pending',     -- pending | acknowledged | resolved
    resolved_action TEXT,                       -- accepted | corrected | ignored
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE TABLE review_tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type       TEXT NOT NULL,              -- identity | track | mask | behavior | dropping | qc_flag
    reference_id    INTEGER,                    -- ID in the relevant table
    video_id        INTEGER,
    priority        TEXT DEFAULT 'normal',      -- low | normal | high | critical
    status          TEXT DEFAULT 'pending',     -- pending | in_progress | completed
    assigned_to     TEXT,
    created_at      TEXT,
    completed_at    TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

-- ═══════════════════════════════════════════════════════════════
-- BENCHMARKS
-- ═══════════════════════════════════════════════════════════════

CREATE TABLE benchmark_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subsystem       TEXT NOT NULL,              -- segmentation | tracking | identity | behavior | droppings
    benchmark_name  TEXT,
    model_version   TEXT,
    metric_name     TEXT,                       -- precision | recall | f1 | iou | fragmentation | etc
    metric_value    REAL,
    sample_size     INTEGER,
    run_at          TEXT,
    config_used     TEXT                        -- JSON
);

-- ═══════════════════════════════════════════════════════════════
-- INDEXES
-- ═══════════════════════════════════════════════════════════════

CREATE INDEX idx_features_video ON features(video_id);
CREATE INDEX idx_features_pigeon ON features(pigeon_id);
CREATE INDEX idx_features_zone ON features(current_zone);
CREATE INDEX idx_behaviors_video ON behaviors(video_id);
CREATE INDEX idx_behaviors_pigeon ON behaviors(pigeon_id);
CREATE INDEX idx_behaviors_type ON behaviors(behavior);
CREATE INDEX idx_behaviors_source ON behaviors(source);
CREATE INDEX idx_behaviors_review ON behaviors(review_status);
CREATE INDEX idx_droppings_zone ON droppings(zone);
CREATE INDEX idx_droppings_review ON droppings(review_status);
CREATE INDEX idx_assignments_review ON video_assignments(review_status);
CREATE INDEX idx_clips_pigeon ON clip_library(pigeon_id);
CREATE INDEX idx_labels_class ON behavior_labels(behavior_class);
CREATE INDEX idx_labels_split ON behavior_labels(split);
CREATE INDEX idx_review_tasks_status ON review_tasks(status);
CREATE INDEX idx_review_tasks_type ON review_tasks(task_type);
```

### Key Design Principle

Every table that stores model outputs includes:
- `review_status` (raw → reviewed → approved)
- `confidence` or equivalent quality signal
- Foreign key to the source video

Every table that stores human decisions includes:
- `reviewer` / `editor` / `labeler` identity
- Timestamp
- The action taken

This means any downstream report can filter to only approved data, and every result has provenance.

---

## Layer 5: Learned Behavior Engine (New — LabGym Replacement Core)

This is the most important new layer. It is what makes LabGym unnecessary.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                LEARNED BEHAVIOR ENGINE                    │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │   Clip   │───►│  Label   │───►│  Train / Eval    │   │
│  │ Extractor│    │  Manager │    │  Pipeline        │   │
│  └──────────┘    └──────────┘    └────────┬─────────┘   │
│       ▲                                    │             │
│       │               ┌────────────────────┘             │
│       │               ▼                                  │
│  ┌──────────┐    ┌──────────────────┐                   │
│  │  Video   │    │  Model Registry  │                   │
│  │  Archive │    │  + Re-inference  │                   │
│  └──────────┘    └──────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

### Clip Extraction

```python
# src/behavior/clip_extractor.py

"""
Clip Extractor: Extracts short video clips centered on individual pigeons
for behavior labeling and classifier training.

This is the core of the LabGym replacement. LabGym's real value was not
just behavior inference — it was the workflow around building a custom
classifier from labeled examples. PigeonLab must own this workflow.
"""

import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class ClipSpec:
    """Specification for a clip to extract."""
    video_id: int
    pigeon_id: str
    center_frame: int
    duration_frames: int           # Total frames in clip
    include_mask_overlay: bool
    include_neighbors: bool        # Show nearby pigeons
    extraction_reason: str         # "candidate_behavior" | "manual" | "random"


@dataclass
class ExtractedClip:
    """A successfully extracted clip."""
    clip_path: Path
    video_id: int
    pigeon_id: str
    start_frame: int
    end_frame: int
    duration_seconds: float
    zone: Optional[str]
    velocity_context: float
    pairwise_context: dict


class ClipExtractor:
    """
    Extracts pigeon-centered video clips for behavior labeling.

    Each clip:
    - Is centered on a single tracked pigeon
    - Has the pigeon's mask overlaid (optional)
    - Is cropped to a region around the pigeon (not full frame)
    - Includes metadata: zone, velocity, nearby pigeons
    - Is saved as a short MP4 file in the clip library
    """

    def __init__(self, clip_dir: str = "data/clips", crop_padding: float = 1.5):
        self.clip_dir = Path(clip_dir)
        self.clip_dir.mkdir(parents=True, exist_ok=True)
        self.crop_padding = crop_padding  # Multiplier on bbox size for crop region

    def extract_clip(
        self,
        spec: ClipSpec,
        frame_dir: Path,
        tracked_masks: dict,        # {frame_idx: {pigeon_id: mask}}
        features: dict,             # {frame_idx: [FrameFeatures]}
        fps: int = 6
    ) -> Optional[ExtractedClip]:
        """
        Extract a single clip centered on a pigeon.

        Args:
            spec: What to extract
            frame_dir: Directory of JPEG frames
            tracked_masks: All masks for this video
            features: Spatial features for context metadata
            fps: Frame rate for the output clip

        Returns:
            ExtractedClip if successful, None if pigeon not present in enough frames
        """
        frame_paths = sorted(frame_dir.glob("*.jpg"))
        half = spec.duration_frames // 2
        start = max(0, spec.center_frame - half)
        end = min(len(frame_paths) - 1, spec.center_frame + half)

        # Verify pigeon is present in most of the clip frames
        present_count = 0
        for fi in range(start, end + 1):
            if fi in tracked_masks and spec.pigeon_id in tracked_masks[fi]:
                present_count += 1
        if present_count < (end - start + 1) * 0.7:
            return None  # Pigeon not visible in enough frames

        # Determine crop region from the pigeon's bounding box
        crop_bbox = self._compute_crop_region(
            tracked_masks, spec.pigeon_id, start, end, frame_paths[0]
        )

        # Extract and write clip
        clip_name = f"{spec.pigeon_id}_{spec.video_id}_f{start}-{end}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
        clip_path = self.clip_dir / clip_name

        x1, y1, x2, y2 = crop_bbox
        crop_w, crop_h = x2 - x1, y2 - y1

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(clip_path), fourcc, fps, (crop_w, crop_h))

        for fi in range(start, end + 1):
            frame = cv2.imread(str(frame_paths[fi]))
            cropped = frame[y1:y2, x1:x2].copy()

            # Overlay mask if requested
            if spec.include_mask_overlay and fi in tracked_masks:
                mask = tracked_masks[fi].get(spec.pigeon_id)
                if mask is not None:
                    mask_crop = mask[y1:y2, x1:x2]
                    overlay = cropped.copy()
                    overlay[mask_crop > 0] = (overlay[mask_crop > 0] * 0.5 +
                                               np.array([0, 255, 0]) * 0.5).astype(np.uint8)
                    cropped = overlay

            writer.write(cropped)

        writer.release()

        # Compute context metadata
        velocity_ctx = self._avg_velocity(features, spec.pigeon_id, start, end)
        pairwise_ctx = self._pairwise_context(features, spec.pigeon_id, spec.center_frame)
        zone = self._get_zone(features, spec.pigeon_id, spec.center_frame)

        return ExtractedClip(
            clip_path=clip_path,
            video_id=spec.video_id,
            pigeon_id=spec.pigeon_id,
            start_frame=start,
            end_frame=end,
            duration_seconds=(end - start + 1) / fps,
            zone=zone,
            velocity_context=velocity_ctx,
            pairwise_context=pairwise_ctx
        )

    def extract_candidates(
        self,
        video_id: int,
        behavior_events: list,      # BehaviorEvent list from rule engine
        frame_dir: Path,
        tracked_masks: dict,
        features: dict,
        clip_duration_frames: int = 30,
        fps: int = 6
    ) -> list[ExtractedClip]:
        """
        Auto-extract clips around detected behavior events.
        These become candidates for human labeling of advanced behaviors.
        """
        clips = []
        for event in behavior_events:
            center = (event.start_frame + event.end_frame) // 2
            spec = ClipSpec(
                video_id=video_id,
                pigeon_id=event.pigeon_id,
                center_frame=center,
                duration_frames=clip_duration_frames,
                include_mask_overlay=True,
                include_neighbors=True,
                extraction_reason="candidate_behavior"
            )
            clip = self.extract_clip(spec, frame_dir, tracked_masks, features, fps)
            if clip:
                clips.append(clip)
        return clips

    def _compute_crop_region(self, tracked_masks, pigeon_id, start, end, sample_frame_path):
        """Compute a stable crop bbox that covers the pigeon across all clip frames."""
        all_xs, all_ys = [], []
        for fi in range(start, end + 1):
            if fi in tracked_masks and pigeon_id in tracked_masks[fi]:
                mask = tracked_masks[fi][pigeon_id]
                ys, xs = np.where(mask)
                if len(xs) > 0:
                    all_xs.extend([xs.min(), xs.max()])
                    all_ys.extend([ys.min(), ys.max()])

        if not all_xs:
            img = cv2.imread(str(sample_frame_path))
            h, w = img.shape[:2]
            return (0, 0, w, h)

        x1, x2 = min(all_xs), max(all_xs)
        y1, y2 = min(all_ys), max(all_ys)

        # Add padding
        w, h = x2 - x1, y2 - y1
        pad_w = int(w * (self.crop_padding - 1) / 2)
        pad_h = int(h * (self.crop_padding - 1) / 2)

        img = cv2.imread(str(sample_frame_path))
        img_h, img_w = img.shape[:2]

        x1 = max(0, x1 - pad_w)
        y1 = max(0, y1 - pad_h)
        x2 = min(img_w, x2 + pad_w)
        y2 = min(img_h, y2 + pad_h)

        return (x1, y1, x2, y2)

    def _avg_velocity(self, features, pigeon_id, start, end):
        vels = []
        for fi in range(start, end + 1):
            if fi in features:
                for f in features[fi]:
                    if f.pigeon_id == pigeon_id and f.velocity_mm_s is not None:
                        vels.append(f.velocity_mm_s)
        return float(np.mean(vels)) if vels else 0.0

    def _pairwise_context(self, features, pigeon_id, frame_idx):
        # Simplified: return distances to other pigeons at center frame
        return {}

    def _get_zone(self, features, pigeon_id, frame_idx):
        if frame_idx in features:
            for f in features[frame_idx]:
                if f.pigeon_id == pigeon_id:
                    return f.current_zone
        return None
```

### Behavior Training Pipeline

```python
# src/behavior/training.py

"""
Behavior Training Pipeline: Trains classifiers on labeled pigeon clips.

This is what makes LabGym unnecessary. PigeonLab produces its own training
data from its own review process, trains its own classifiers, and stores
versioned models in its own registry.

Design rule: Make it work well for pigeons first. Do not make it
generic-animal-first.
"""

import json
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TrainingConfig:
    """Configuration for a behavior training run."""
    behavior_classes: list[str]     # ["preening", "courtship", "resting", "locomotion"]
    clip_duration_seconds: float
    train_split: float              # 0.7
    val_split: float                # 0.15
    test_split: float               # 0.15
    epochs: int
    batch_size: int
    learning_rate: float
    backbone: str                   # "r3d_18" | "slowfast" | "x3d_s"
    freeze_backbone: bool
    augmentations: list[str]        # ["horizontal_flip", "color_jitter", "time_crop"]


@dataclass
class TrainingResult:
    """Results from a training run."""
    model_version: str
    checkpoint_path: str
    train_accuracy: float
    val_accuracy: float
    test_accuracy: float
    per_class_metrics: dict         # {class: {precision, recall, f1}}
    confusion_matrix: list[list]
    training_clips: int
    training_config: dict


class BehaviorTrainer:
    """
    Trains behavior classifiers from labeled clips.

    Workflow:
    1. Query labeled clips from clip_library + behavior_labels
    2. Split into train/val/test
    3. Train a video classification model
    4. Evaluate and store metrics
    5. Register model in model_registry
    6. Optionally run re-inference across video archive
    """

    def __init__(self, db_path: str = "data/pigeonlab.db",
                 model_dir: str = "data/models/behavior"):
        self.db_path = db_path
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def get_labeled_clip_counts(self) -> dict[str, int]:
        """Check how many labeled clips exist per behavior class."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT bl.behavior_class, COUNT(*) "
            "FROM behavior_labels bl "
            "JOIN clip_library cl ON bl.clip_id = cl.id "
            "GROUP BY bl.behavior_class"
        ).fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}

    def check_readiness(self, min_clips_per_class: int = 20) -> dict:
        """
        Check if there are enough labeled clips to train.

        Returns readiness report with per-class status.
        """
        counts = self.get_labeled_clip_counts()
        report = {
            "ready": all(c >= min_clips_per_class for c in counts.values()) and len(counts) >= 2,
            "min_clips_required": min_clips_per_class,
            "classes": {
                cls: {
                    "count": count,
                    "ready": count >= min_clips_per_class,
                    "need": max(0, min_clips_per_class - count)
                }
                for cls, count in counts.items()
            }
        }
        return report

    def train(self, config: TrainingConfig) -> TrainingResult:
        """
        Train a behavior classifier.

        Implementation note: The actual model training uses PyTorch
        video classification models (torchvision). The specific
        implementation depends on clip format and model architecture.

        This method handles:
        1. Loading labeled clips from the database
        2. Creating train/val/test splits
        3. Training the model
        4. Evaluating on held-out test set
        5. Registering the trained model
        """
        # Load clips and labels
        conn = sqlite3.connect(self.db_path)
        clips = conn.execute(
            "SELECT cl.clip_path, bl.behavior_class, bl.split "
            "FROM behavior_labels bl "
            "JOIN clip_library cl ON bl.clip_id = cl.id "
            "WHERE bl.behavior_class IN ({})".format(
                ",".join("?" * len(config.behavior_classes))
            ),
            config.behavior_classes
        ).fetchall()
        conn.close()

        if len(clips) < 10:
            raise ValueError(f"Not enough labeled clips ({len(clips)}). Need at least 10.")

        # Split data
        train_clips = [(p, c) for p, c, s in clips if s == "train"]
        val_clips = [(p, c) for p, c, s in clips if s == "val"]
        test_clips = [(p, c) for p, c, s in clips if s == "test"]

        # ─── TRAINING LOOP PLACEHOLDER ─────────────────────────────
        # The actual training implementation depends on chosen architecture.
        # For pigeon behavior classification, recommended starting point:
        #
        # - Backbone: torchvision.models.video.r3d_18 (pretrained)
        # - Fine-tune final FC layer on pigeon behavior classes
        # - Input: 16-frame clips at 6 FPS (~2.7 seconds)
        # - Augmentation: horizontal flip, color jitter, temporal crop
        #
        # This is a standard PyTorch training loop — the key PigeonLab
        # value is not the training code itself but the clip extraction,
        # labeling, versioning, and re-inference workflow around it.
        # ────────────────────────────────────────────────────────────

        version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        checkpoint_path = str(self.model_dir / f"behavior_{version}.pt")

        # Placeholder metrics (replace with actual training results)
        result = TrainingResult(
            model_version=version,
            checkpoint_path=checkpoint_path,
            train_accuracy=0.0,
            val_accuracy=0.0,
            test_accuracy=0.0,
            per_class_metrics={},
            confusion_matrix=[],
            training_clips=len(train_clips),
            training_config=vars(config)
        )

        # Register in model registry
        self._register_model(result)

        return result

    def _register_model(self, result: TrainingResult):
        """Save trained model to the registry."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO model_registry "
            "(model_name, model_type, version, checkpoint_path, training_config, "
            "training_clips, train_accuracy, val_accuracy, test_accuracy, created_at, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("pigeon_behavior", "behavior_classifier", result.model_version,
             result.checkpoint_path, json.dumps(result.training_config),
             result.training_clips, result.train_accuracy, result.val_accuracy,
             result.test_accuracy, datetime.now().isoformat(), 0)
        )
        conn.commit()
        conn.close()

    def set_active_model(self, version: str):
        """Set which model version is used for inference."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE model_registry SET is_active = 0 WHERE model_type = 'behavior_classifier'")
        conn.execute("UPDATE model_registry SET is_active = 1 WHERE version = ?", (version,))
        conn.commit()
        conn.close()

    def reinfer_archive(self, version: str):
        """
        Run a trained classifier across all processed videos.
        Stores results as new behavior predictions with source='learned_model'.

        This is what closes the loop: label → train → apply to archive.
        """
        conn = sqlite3.connect(self.db_path)
        model = conn.execute(
            "SELECT checkpoint_path FROM model_registry WHERE version = ?", (version,)
        ).fetchone()
        conn.close()

        if not model:
            raise ValueError(f"Model version {version} not found")

        # Load model and run inference on all clips in clip_library
        # Store predictions in behaviors table with source='learned_model'
        # and model_version=version
        pass  # Implementation depends on model architecture
```

---

## Layer 6: Benchmarking & Evaluation (New)

```python
# src/benchmark/runner.py

"""
Benchmark Runner: Measures quality of every major subsystem.

To replace LabGym credibly, PigeonLab must not just produce outputs —
it must measure whether those outputs are good.

Each subsystem has its own benchmark module. All benchmarks:
- Run against manually labeled ground-truth subsets
- Report precision, recall, F1, and subsystem-specific metrics
- Store results in the benchmark_results table
- Are runnable from CLI: python scripts/run_benchmark.py --subsystem tracking
"""

import sqlite3
import json
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class BenchmarkResult:
    subsystem: str
    benchmark_name: str
    metrics: dict[str, float]       # {metric_name: value}
    sample_size: int
    model_version: Optional[str]


class BenchmarkRunner:
    """Runs and stores benchmark results."""

    def __init__(self, db_path: str = "data/pigeonlab.db"):
        self.db_path = db_path

    def store_result(self, result: BenchmarkResult):
        conn = sqlite3.connect(self.db_path)
        for metric_name, metric_value in result.metrics.items():
            conn.execute(
                "INSERT INTO benchmark_results "
                "(subsystem, benchmark_name, model_version, metric_name, metric_value, sample_size, run_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (result.subsystem, result.benchmark_name, result.model_version,
                 metric_name, metric_value, result.sample_size,
                 datetime.now().isoformat())
            )
        conn.commit()
        conn.close()

    def get_latest_results(self, subsystem: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT metric_name, metric_value, run_at FROM benchmark_results "
            "WHERE subsystem = ? ORDER BY run_at DESC LIMIT 20",
            (subsystem,)
        ).fetchall()
        conn.close()
        return {r[0]: {"value": r[1], "run_at": r[2]} for r in rows}


# ─── Subsystem Benchmarks ─────────────────────────────────────────

class SegmentationBenchmark:
    """Compare SAM3 masks against manually annotated ground truth."""

    def run(self, ground_truth_dir: str, predictions: dict) -> BenchmarkResult:
        # Compare predicted masks against ground truth masks
        # Compute: mask IoU, precision, recall
        # This requires a small set of manually annotated frames
        return BenchmarkResult(
            subsystem="segmentation",
            benchmark_name="mask_iou",
            metrics={"mean_iou": 0.0, "precision": 0.0, "recall": 0.0},
            sample_size=0,
            model_version="sam3"
        )


class TrackingBenchmark:
    """Measure track continuity and fragmentation."""

    def run(self, ground_truth_tracks: dict, predicted_tracks: dict) -> BenchmarkResult:
        # Metrics: track fragmentation rate, ID switches, MOTA
        return BenchmarkResult(
            subsystem="tracking",
            benchmark_name="track_continuity",
            metrics={"fragmentation_rate": 0.0, "id_switches": 0, "mota": 0.0},
            sample_size=0,
            model_version=None
        )


class IdentityBenchmark:
    """Measure cross-session identity consistency."""

    def run(self, confirmed_assignments: dict, proposed_assignments: dict) -> BenchmarkResult:
        # Metrics: identity accuracy, false merge rate
        return BenchmarkResult(
            subsystem="identity",
            benchmark_name="cross_session_accuracy",
            metrics={"accuracy": 0.0, "false_merge_rate": 0.0},
            sample_size=0,
            model_version=None
        )


class BehaviorBenchmark:
    """Evaluate behavior classifier against labeled test set."""

    def run(self, test_predictions: list, test_labels: list, classes: list) -> BenchmarkResult:
        # Metrics: per-class precision, recall, F1, overall accuracy
        return BenchmarkResult(
            subsystem="behavior",
            benchmark_name="classifier_accuracy",
            metrics={"accuracy": 0.0, "macro_f1": 0.0},
            sample_size=len(test_labels),
            model_version=None
        )


class DroppingsBenchmark:
    """Evaluate droppings detection against manually confirmed samples."""

    def run(self, confirmed: list, detected: list) -> BenchmarkResult:
        # Metrics: precision, recall, F1 for droppings detection
        return BenchmarkResult(
            subsystem="droppings",
            benchmark_name="detection_accuracy",
            metrics={"precision": 0.0, "recall": 0.0, "f1": 0.0},
            sample_size=len(confirmed),
            model_version=None
        )
```

---

## Layer 7: Web Application (Specification)

The web UI replaces external tools. It must do real work, not just display dashboards.

### Technology Choice

| Component | Technology | Why |
|-----------|-----------|-----|
| Backend | FastAPI | Async Python, easy SQLite integration, API-first |
| Frontend | React + Tailwind | Standard, rich ecosystem for interactive UIs |
| Video Player | Video.js or custom HTML5 | Frame scrubbing, overlay support |
| Charts | Recharts or Plotly | Heatmaps, timelines, interactive plots |
| State | React Query + SQLite via API | Simple, no external database server |

### Application Sections

#### A. Ingestion

| Feature | Description |
|---------|-------------|
| Add videos | Upload or specify directory path |
| Batch queue | Show processing status for all queued videos |
| Session grouping | Auto-group videos by session ID and camera |
| Camera assignment | Verify/correct camera type per video |
| Processing log | Show per-video processing output and errors |

#### B. Review (EZannot Replacement)

| Feature | Description |
|---------|-------------|
| QC flag queue | List all flagged frames, sortable by severity |
| Frame viewer | Show frame with mask overlays, scrub through video |
| Mask correction | Draw/erase mask regions, accept/reject masks |
| Track merge/split | Merge two tracks into one, split a track at a frame |
| Identity confirmation | Approve or reassign placeholder identities |
| Behavior event review | Accept/reject detected behavior events |
| Droppings review | Confirm/reject droppings detections |
| Approval workflow | Mark video as reviewed → approved |

#### C. Analysis

| Feature | Description |
|---------|-------------|
| Per-pigeon summary | Zone preferences, behavior counts, total observation time |
| Per-session summary | All pigeons in one session, comparative stats |
| Heatmaps | Per-pigeon and combined position heatmaps |
| Behavior timelines | Gantt-style view of behaviors over time per pigeon |
| Pairwise interaction | Distance plots, proximity events between pairs |
| Droppings maps | Spatial heatmap of droppings with zone overlay |
| Session comparison | Compare metrics across sessions/dates |

#### D. Training (LabGym Replacement)

| Feature | Description |
|---------|-------------|
| Clip library | Browse all extracted clips with metadata |
| Label clips | Assign behavior class to clips, drag-and-drop |
| Manage classes | Add/remove behavior categories |
| Training readiness | Show per-class clip counts vs minimum required |
| Launch training | Configure and start training run |
| Training history | View all training runs with metrics |
| Model comparison | Compare accuracy across model versions |
| Set active model | Choose which model version to use for inference |
| Re-inference | Apply a model to the full video archive |

#### E. Export

| Feature | Description |
|---------|-------------|
| CSV summaries | Per-pigeon, per-session, per-behavior |
| COCO masks | Standard annotation format |
| Event logs | All behavior events with timestamps |
| Trajectory JSON | Per-pigeon position time series |
| Heatmap images | PNG exports of spatial heatmaps |
| Overlay videos | Videos with mask and ID overlays |
| Clip datasets | Labeled clips for external training |
| Benchmark reports | Latest benchmark results per subsystem |
| Reproducibility manifest | Config, model versions, thresholds, review state |

---

## Development Phases (Concrete Checklist)

### Phase 1: Make PigeonLab Operational Without Outside Tools

This phase replaces EZannot.

- [ ] Harden SAM3 wrappers with retry/failure handling
- [ ] Add contract tests for SAM3 responses
- [ ] Finish batch ingestion with multi-camera awareness
- [ ] Build enhanced database with truth states
- [ ] Build QC flag review queue (CLI first, web later)
- [ ] Build mask/track review tools (CLI first)
- [ ] Build identity confirmation workflow
- [ ] Store raw vs reviewed vs approved outputs separately
- [ ] Support placeholder identities with downstream filtering
- [ ] Export corrected outputs (COCO, CSV)

**Done when:** A user can process pigeon videos, review results, and export corrected annotations without EZannot.

### Phase 2: Make Pigeon Analytics Genuinely Useful

- [ ] Add `distance_to_walls` computation
- [ ] Add pairwise `overlap_iou` (true mask IoU)
- [ ] Finalize zone occupancy and dwell reporting
- [ ] Add per-pigeon and per-session heatmaps
- [ ] Benchmark droppings detection on actual footage
- [ ] Add fallback droppings detection (background subtraction)
- [ ] Add droppings deduplication across adjacent frames
- [ ] Add droppings review queue
- [ ] Add session comparison summaries
- [ ] Normalize features across cameras/arena configs

**Done when:** Spatial reports are useful on their own even before advanced behavior models exist.

### Phase 3: Replace the Best Remaining Part of LabGym

- [ ] Build clip extraction module
- [ ] Build behavior label manager
- [ ] Build appearance matching module for identity
- [ ] Build identity confidence scoring
- [ ] Build human confirmation workflow for identity matches
- [ ] Build behavior training pipeline (PyTorch video classification)
- [ ] Build classifier evaluation with per-class metrics and confusion matrix
- [ ] Build model registry with versioning
- [ ] Build re-inference across archived videos
- [ ] Store learned behavior predictions with model version tag

**Done when:** A user can label behavior clips, train a classifier, apply it to the archive, and inspect results — all inside PigeonLab. LabGym is no longer needed.

### Phase 4: Build the Web Application

- [ ] FastAPI backend with all database queries as API endpoints
- [ ] Ingestion section (upload, queue, status)
- [ ] Review section (QC flags, masks, tracks, identities, behaviors, droppings)
- [ ] Analysis section (summaries, heatmaps, timelines, pairwise, droppings maps)
- [ ] Training section (clip library, labeling, training, model comparison)
- [ ] Export section (CSV, COCO, JSON, overlays, manifests)
- [ ] Benchmark reporting pages

**Done when:** A researcher can do daily work entirely inside PigeonLab.

### Phase 5: Ongoing

- [ ] Collect labeled data for Tier 2 behaviors (preening, courtship, aggression)
- [ ] Train and iterate behavior classifiers
- [ ] Add benchmark suites as ground-truth data grows
- [ ] Consider cross-camera fusion if calibration data becomes available
- [ ] Consider real-time monitoring mode

---

## Definition of Success

PigeonLab has successfully replaced LabGym and EZannot when all of the following are true:

1. A user can process pigeon videos without external tools
2. A user can review and correct tracks and identities inside PigeonLab
3. A user can generate spatial and behavior outputs inside PigeonLab
4. A user can label advanced behavior clips inside PigeonLab
5. A user can train and evaluate a learned behavior classifier inside PigeonLab
6. A user can re-run that classifier on the archive inside PigeonLab
7. All outputs are reviewable, versioned, and exportable
8. LabGym is no longer needed for any normal pigeon workflow

---

## What PigeonLab Does Not Copy from LabGym

- Generic multi-animal abstractions that weaken pigeon-specific quality
- Broad support for unrelated species before pigeons are complete
- Premature real-time support
- Fancy generic training GUIs before the pigeon clip-labeling loop is solid
- External-tool-dependent workflows

The goal is not to become "LabGym but bigger." The goal is to become **better for pigeons**.
