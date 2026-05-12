import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "pigeonlab.db"


def get_db_path() -> str:
    """Return the database file path as a string (used by aiosqlite routers)."""
    return str(DB_PATH)


def get_connection() -> sqlite3.Connection:
    try:
        conn = sqlite3.connect(str(DB_PATH))
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"Failed to open database at {DB_PATH}: {exc}"
        ) from exc
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    """Context manager that yields a connection and guarantees close on exit."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS videos (
            video_id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_name TEXT NOT NULL,
            source_path TEXT,
            session_id TEXT,
            camera_type TEXT,
            total_frames INTEGER,
            fps REAL,
            processed_at TEXT,
            review_status TEXT DEFAULT 'raw',
            processing_status TEXT DEFAULT 'queued',
            processing_error TEXT,
            model_version TEXT,
            config_hash TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS pigeons (
            pigeon_id TEXT PRIMARY KEY,
            physical_markers TEXT,
            appearance_embedding BLOB,
            preferred_zones TEXT,
            total_frames_observed INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS video_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL REFERENCES videos(video_id),
            video_obj_id INTEGER NOT NULL,
            pigeon_id TEXT NOT NULL REFERENCES pigeons(pigeon_id),
            confidence REAL,
            match_method TEXT,
            review_status TEXT DEFAULT 'raw',
            assigned_at TEXT DEFAULT (datetime('now')),
            reviewed_at TEXT,
            reviewed_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS identity_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL REFERENCES video_assignments(id),
            action TEXT NOT NULL,
            old_pigeon_id TEXT,
            new_pigeon_id TEXT,
            reviewer TEXT,
            reviewed_at TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS track_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL REFERENCES videos(video_id),
            frame_idx INTEGER NOT NULL,
            edit_type TEXT NOT NULL,
            old_obj_id INTEGER,
            new_obj_id INTEGER,
            editor TEXT,
            edited_at TEXT,
            details TEXT
        );

        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL REFERENCES videos(video_id),
            frame_idx INTEGER NOT NULL,
            pigeon_id TEXT NOT NULL REFERENCES pigeons(pigeon_id),
            centroid_x REAL,
            centroid_y REAL,
            centroid_mm_x REAL,
            centroid_mm_y REAL,
            area_px REAL,
            area_mm2 REAL,
            velocity_px REAL,
            velocity_mm_s REAL,
            heading_deg REAL,
            current_zone TEXT,
            distance_to_nearest_wall_px REAL,
            confidence REAL DEFAULT 1.0
        );

        CREATE TABLE IF NOT EXISTS pairwise (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL REFERENCES videos(video_id),
            frame_idx INTEGER NOT NULL,
            pigeon_a TEXT NOT NULL REFERENCES pigeons(pigeon_id),
            pigeon_b TEXT NOT NULL REFERENCES pigeons(pigeon_id),
            distance_px REAL,
            distance_mm REAL,
            overlap_iou REAL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS behaviors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL REFERENCES videos(video_id),
            pigeon_id TEXT NOT NULL REFERENCES pigeons(pigeon_id),
            behavior TEXT NOT NULL,
            source TEXT,
            model_version TEXT,
            start_frame INTEGER,
            end_frame INTEGER,
            duration_seconds REAL,
            confidence REAL,
            zone TEXT,
            interacting_with TEXT,
            review_status TEXT DEFAULT 'raw',
            details TEXT
        );

        CREATE TABLE IF NOT EXISTS behavior_labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clip_id INTEGER NOT NULL REFERENCES clip_library(id),
            behavior_class TEXT NOT NULL,
            labeler TEXT,
            labeled_at TEXT,
            split TEXT DEFAULT 'train',
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS clip_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL REFERENCES videos(video_id),
            pigeon_id TEXT REFERENCES pigeons(pigeon_id),
            start_frame INTEGER NOT NULL,
            end_frame INTEGER NOT NULL,
            duration_seconds REAL,
            clip_path TEXT,
            mask_overlay BOOLEAN DEFAULT 1,
            zone TEXT,
            velocity_context TEXT,
            pairwise_context TEXT,
            extraction_reason TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS model_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            model_type TEXT NOT NULL,
            version TEXT,
            checkpoint_path TEXT,
            training_config TEXT,
            training_clips INTEGER,
            train_accuracy REAL,
            val_accuracy REAL,
            test_accuracy REAL,
            created_at TEXT DEFAULT (datetime('now')),
            notes TEXT,
            is_active BOOLEAN DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS droppings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL REFERENCES videos(video_id),
            frame_idx INTEGER NOT NULL,
            centroid_x REAL,
            centroid_y REAL,
            area_px REAL,
            zone TEXT,
            confidence REAL,
            detection_method TEXT,
            review_status TEXT DEFAULT 'raw',
            deduplicated BOOLEAN DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS droppings_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dropping_id INTEGER NOT NULL REFERENCES droppings(id),
            action TEXT NOT NULL,
            reviewer TEXT,
            reviewed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS qc_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL REFERENCES videos(video_id),
            frame_idx INTEGER,
            rule_name TEXT NOT NULL,
            severity TEXT,
            reason TEXT,
            review_status TEXT DEFAULT 'pending',
            resolved_action TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS review_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            reference_id INTEGER,
            video_id INTEGER REFERENCES videos(video_id),
            priority TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'pending',
            assigned_to TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS ai_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL REFERENCES videos(video_id),
            frame_idx INTEGER,
            pigeon_id TEXT,
            observation_type TEXT NOT NULL,
            label TEXT,
            confidence REAL,
            zone TEXT,
            bbox_json TEXT,
            source_model TEXT,
            review_status TEXT DEFAULT 'raw',
            details TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS benchmark_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subsystem TEXT NOT NULL,
            benchmark_name TEXT NOT NULL,
            model_version TEXT,
            metric_name TEXT NOT NULL,
            metric_value REAL,
            sample_size INTEGER,
            run_at TEXT DEFAULT (datetime('now')),
            config_used TEXT
        );

        -- Indexes: videos
        CREATE INDEX IF NOT EXISTS idx_videos_session ON videos(session_id);
        CREATE INDEX IF NOT EXISTS idx_videos_review_status ON videos(review_status);
        CREATE INDEX IF NOT EXISTS idx_videos_processing_status ON videos(processing_status);
        CREATE INDEX IF NOT EXISTS idx_videos_processed_at ON videos(processed_at);

        -- Indexes: video_assignments
        CREATE INDEX IF NOT EXISTS idx_va_video ON video_assignments(video_id);
        CREATE INDEX IF NOT EXISTS idx_va_pigeon ON video_assignments(pigeon_id);
        CREATE INDEX IF NOT EXISTS idx_va_review_status ON video_assignments(review_status);

        -- Indexes: identity_reviews
        CREATE INDEX IF NOT EXISTS idx_ir_assignment ON identity_reviews(assignment_id);
        CREATE INDEX IF NOT EXISTS idx_ir_reviewed_at ON identity_reviews(reviewed_at);

        -- Indexes: track_edits
        CREATE INDEX IF NOT EXISTS idx_te_video_frame ON track_edits(video_id, frame_idx);

        -- Indexes: features
        CREATE INDEX IF NOT EXISTS idx_feat_video_frame ON features(video_id, frame_idx);
        CREATE INDEX IF NOT EXISTS idx_feat_pigeon ON features(pigeon_id);
        CREATE INDEX IF NOT EXISTS idx_feat_zone ON features(current_zone);

        -- Indexes: pairwise
        CREATE INDEX IF NOT EXISTS idx_pw_video_frame ON pairwise(video_id, frame_idx);
        CREATE INDEX IF NOT EXISTS idx_pw_pigeon_a ON pairwise(pigeon_a);
        CREATE INDEX IF NOT EXISTS idx_pw_pigeon_b ON pairwise(pigeon_b);

        -- Indexes: behaviors
        CREATE INDEX IF NOT EXISTS idx_beh_video ON behaviors(video_id);
        CREATE INDEX IF NOT EXISTS idx_beh_pigeon ON behaviors(pigeon_id);
        CREATE INDEX IF NOT EXISTS idx_beh_behavior ON behaviors(behavior);
        CREATE INDEX IF NOT EXISTS idx_beh_review_status ON behaviors(review_status);

        -- Indexes: behavior_labels
        CREATE INDEX IF NOT EXISTS idx_bl_clip ON behavior_labels(clip_id);
        CREATE INDEX IF NOT EXISTS idx_bl_split ON behavior_labels(split);

        -- Indexes: clip_library
        CREATE INDEX IF NOT EXISTS idx_cl_video ON clip_library(video_id);
        CREATE INDEX IF NOT EXISTS idx_cl_pigeon ON clip_library(pigeon_id);

        -- Indexes: model_registry
        CREATE INDEX IF NOT EXISTS idx_mr_type ON model_registry(model_type);
        CREATE INDEX IF NOT EXISTS idx_mr_active ON model_registry(is_active);

        -- Indexes: droppings
        CREATE INDEX IF NOT EXISTS idx_drop_video_frame ON droppings(video_id, frame_idx);
        CREATE INDEX IF NOT EXISTS idx_drop_zone ON droppings(zone);
        CREATE INDEX IF NOT EXISTS idx_drop_review_status ON droppings(review_status);

        -- Indexes: droppings_reviews
        CREATE INDEX IF NOT EXISTS idx_dr_dropping ON droppings_reviews(dropping_id);

        -- Indexes: qc_flags
        CREATE INDEX IF NOT EXISTS idx_qc_video ON qc_flags(video_id);
        CREATE INDEX IF NOT EXISTS idx_qc_review_status ON qc_flags(review_status);

        -- Indexes: review_tasks
        CREATE INDEX IF NOT EXISTS idx_rt_status ON review_tasks(status);
        CREATE INDEX IF NOT EXISTS idx_rt_video ON review_tasks(video_id);
        CREATE INDEX IF NOT EXISTS idx_rt_type ON review_tasks(task_type);

        -- Indexes: ai_observations
        CREATE INDEX IF NOT EXISTS idx_ai_obs_video_frame ON ai_observations(video_id, frame_idx);
        CREATE INDEX IF NOT EXISTS idx_ai_obs_pigeon ON ai_observations(pigeon_id);
        CREATE INDEX IF NOT EXISTS idx_ai_obs_type ON ai_observations(observation_type);
        CREATE INDEX IF NOT EXISTS idx_ai_obs_review ON ai_observations(review_status);

        -- Indexes: benchmark_results
        CREATE INDEX IF NOT EXISTS idx_bench_subsystem ON benchmark_results(subsystem);
        CREATE INDEX IF NOT EXISTS idx_bench_model ON benchmark_results(model_version);
    """)

    # Migrations for existing databases
    for stmt in [
        "ALTER TABLE qc_flags ADD COLUMN created_at TEXT",
        "ALTER TABLE video_assignments ADD COLUMN created_at TEXT",
        "ALTER TABLE videos ADD COLUMN processing_error TEXT",
        "ALTER TABLE videos ADD COLUMN source_path TEXT",
    ]:
        try:
            cur.execute(stmt)
        except Exception:
            pass  # column already exists

    default_settings = {
        "gemma_review_mode": os.getenv("PIGEONLAB_GEMMA_REVIEW_MODE", "off"),
        "gemma_model": os.getenv("PIGEONLAB_GEMMA_MODEL", "gemma4:e4b"),
        "gemma_base_url": os.getenv("PIGEONLAB_GEMMA_BASE_URL", "http://localhost:11434"),
        "gemma_sample_interval_seconds": os.getenv("PIGEONLAB_GEMMA_SAMPLE_SECONDS", "15"),
        "gemma_max_frames_per_video": os.getenv("PIGEONLAB_GEMMA_MAX_FRAMES", "20"),
        "gemma_confidence_threshold": os.getenv("PIGEONLAB_GEMMA_CONFIDENCE_THRESHOLD", "0.65"),
    }
    for key, value in default_settings.items():
        cur.execute(
            "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
            (key, value),
        )

    conn.commit()
    conn.close()
