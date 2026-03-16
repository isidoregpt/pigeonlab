"""
Seed sample data into PigeonLab for development.

Run:  python backend/seed_data.py
"""

import sys
import random
from pathlib import Path
from datetime import datetime, timedelta

# Ensure backend modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import init_db, get_connection

ZONES = ["Center", "North", "South", "East", "West", "NW Corner", "SE Corner"]
BEHAVIORS = ["Feeding", "Resting", "Walking", "Preening", "Courtship"]


def seed():
    # Initialize DB (creates tables if missing)
    init_db()
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)

    # --------------------------------------------------
    # Pigeons
    # --------------------------------------------------
    pigeons = [
        ("Alpha", "Red band, left leg", "Center", "Dominant male, often near feeder"),
        ("Beta", "Blue band, left leg", "North", "Tends to stay along north wall"),
        ("Gamma", "Green band, right leg", "South", "Frequently preens near south corner"),
        ("Delta", None, "East", "No physical marker — identified by appearance"),
    ]

    for pigeon_id, markers, zone, notes in pigeons:
        cur.execute(
            """INSERT OR IGNORE INTO pigeons
               (pigeon_id, physical_markers, preferred_zones, total_frames_observed,
                first_seen, last_seen, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pigeon_id, markers, zone, random.randint(800, 3000),
             yesterday.isoformat(), now.isoformat(), notes),
        )

    print(f"  Inserted {len(pigeons)} pigeons")

    # --------------------------------------------------
    # Videos
    # --------------------------------------------------
    videos = [
        {
            "video_name": "session_001_overhead.mp4",
            "session_id": "session_001",
            "camera_type": "Overhead",
            "total_frames": 1800,
            "fps": 30.0,
            "processed_at": yesterday.isoformat(),
            "review_status": "raw",
            "processing_status": "completed",
            "model_version": "v20260101_000000",
        },
        {
            "video_name": "session_002_side.mp4",
            "session_id": "session_002",
            "camera_type": "Side",
            "total_frames": 2400,
            "fps": 30.0,
            "processed_at": now.isoformat(),
            "review_status": "raw",
            "processing_status": "completed",
            "model_version": "v20260101_000000",
        },
    ]

    video_ids = []
    for v in videos:
        cur.execute(
            """INSERT INTO videos
               (video_name, session_id, camera_type, total_frames, fps,
                processed_at, review_status, processing_status, model_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (v["video_name"], v["session_id"], v["camera_type"],
             v["total_frames"], v["fps"], v["processed_at"],
             v["review_status"], v["processing_status"], v["model_version"]),
        )
        video_ids.append(cur.lastrowid)

    print(f"  Inserted {len(videos)} videos")

    # --------------------------------------------------
    # Video assignments (one per pigeon per video)
    # --------------------------------------------------
    assignment_count = 0
    for vid_id in video_ids:
        for obj_idx, (pigeon_id, _, _, _) in enumerate(pigeons):
            cur.execute(
                """INSERT INTO video_assignments
                   (video_id, video_obj_id, pigeon_id, confidence, match_method,
                    review_status, assigned_at)
                   VALUES (?, ?, ?, ?, ?, 'raw', ?)""",
                (vid_id, obj_idx, pigeon_id,
                 round(random.uniform(0.65, 0.98), 3),
                 random.choice(["marker", "appearance", "spatial"]),
                 now.isoformat()),
            )
            assignment_count += 1

    print(f"  Inserted {assignment_count} video assignments")

    # --------------------------------------------------
    # QC flags (2 sample flags)
    # --------------------------------------------------
    qc_flags = [
        {
            "video_id": video_ids[0],
            "frame_idx": 120,
            "rule_name": "id_swap_detected",
            "severity": "high",
            "reason": "Alpha and Beta tracks appear to swap at frame 120",
            "review_status": "pending",
        },
        {
            "video_id": video_ids[1],
            "frame_idx": 800,
            "rule_name": "low_confidence_id",
            "severity": "medium",
            "reason": "Delta identification confidence dropped below 0.5",
            "review_status": "pending",
        },
    ]

    for flag in qc_flags:
        cur.execute(
            """INSERT INTO qc_flags
               (video_id, frame_idx, rule_name, severity, reason, review_status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (flag["video_id"], flag["frame_idx"], flag["rule_name"],
             flag["severity"], flag["reason"], flag["review_status"]),
        )

    print(f"  Inserted {len(qc_flags)} QC flags")

    # --------------------------------------------------
    # Features (10 frames per video, all 4 pigeons)
    # --------------------------------------------------
    feature_count = 0
    for vid_idx, vid_id in enumerate(video_ids):
        total_frames = videos[vid_idx]["total_frames"]
        sample_frames = [int(total_frames * i / 10) for i in range(10)]

        for frame_idx in sample_frames:
            for pigeon_id, _, pref_zone, _ in pigeons:
                zone = random.choice([pref_zone, random.choice(ZONES)])
                velocity = round(random.uniform(0, 25), 2)
                cur.execute(
                    """INSERT INTO features
                       (video_id, frame_idx, pigeon_id,
                        centroid_x, centroid_y,
                        centroid_mm_x, centroid_mm_y,
                        area_px, area_mm2,
                        velocity_px, velocity_mm_s,
                        heading_deg, current_zone,
                        distance_to_nearest_wall_px, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (vid_id, frame_idx, pigeon_id,
                     round(random.uniform(50, 600), 1),
                     round(random.uniform(50, 400), 1),
                     round(random.uniform(10, 300), 1),
                     round(random.uniform(10, 200), 1),
                     round(random.uniform(500, 3000), 0),
                     round(random.uniform(50, 300), 1),
                     round(velocity * 0.8, 2),
                     velocity,
                     round(random.uniform(0, 360), 1),
                     zone,
                     round(random.uniform(10, 200), 1),
                     round(random.uniform(0.7, 1.0), 3)),
                )
                feature_count += 1

    print(f"  Inserted {feature_count} feature rows")

    # --------------------------------------------------
    # Behaviors (sample entries)
    # --------------------------------------------------
    behavior_count = 0
    for vid_id in video_ids:
        for pigeon_id, _, _, _ in pigeons:
            behavior = random.choice(BEHAVIORS)
            start_f = random.randint(0, 500)
            end_f = start_f + random.randint(30, 300)
            cur.execute(
                """INSERT INTO behaviors
                   (video_id, pigeon_id, behavior, source, start_frame, end_frame,
                    duration_seconds, confidence, zone, review_status)
                   VALUES (?, ?, ?, 'model', ?, ?, ?, ?, ?, 'raw')""",
                (vid_id, pigeon_id, behavior, start_f, end_f,
                 round((end_f - start_f) / 30.0, 2),
                 round(random.uniform(0.6, 0.95), 3),
                 random.choice(ZONES)),
            )
            behavior_count += 1

    print(f"  Inserted {behavior_count} behavior records")

    # --------------------------------------------------
    # Pairwise proximity (sample entries)
    # --------------------------------------------------
    pairwise_count = 0
    pairs = [("Alpha", "Beta"), ("Alpha", "Gamma"), ("Beta", "Delta"), ("Gamma", "Delta")]
    for vid_id in video_ids:
        for pigeon_a, pigeon_b in pairs:
            frame_idx = random.randint(0, 1000)
            cur.execute(
                """INSERT INTO pairwise
                   (video_id, frame_idx, pigeon_a, pigeon_b, distance_px, distance_mm, overlap_iou)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (vid_id, frame_idx, pigeon_a, pigeon_b,
                 round(random.uniform(20, 400), 1),
                 round(random.uniform(10, 200), 1),
                 round(random.uniform(0, 0.3), 3)),
            )
            pairwise_count += 1

    print(f"  Inserted {pairwise_count} pairwise records")

    # --------------------------------------------------
    # Commit
    # --------------------------------------------------
    conn.commit()
    conn.close()

    print()
    print("  Seed data loaded successfully!")
    print(f"  Database: {Path(__file__).resolve().parent.parent / 'data' / 'pigeonlab.db'}")
    print()


if __name__ == "__main__":
    print()
    print("  Seeding PigeonLab development data...")
    print()
    seed()
