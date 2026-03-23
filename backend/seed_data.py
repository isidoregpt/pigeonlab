"""
Seed sample data into PigeonLab for development.

Run:  python backend/seed_data.py
"""

import sys
import random
import json
from pathlib import Path
from datetime import datetime, timedelta

# Ensure backend modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import init_db, get_connection, DB_PATH  # noqa: E402

ZONES = ["Center", "North", "South", "East", "West", "NW Corner", "SE Corner"]
BEHAVIORS = ["Feeding", "Resting", "Walking", "Preening", "Courtship"]


def seed():
    # Initialize DB (creates tables if missing)
    init_db()
    conn = get_connection()
    cur = conn.cursor()

    # Idempotency check
    count = cur.execute("SELECT COUNT(*) FROM pigeons").fetchone()[0]
    if count > 0:
        conn.close()
        print("  Data already seeded. Delete data/pigeonlab.db to re-seed,")
        print("  or run with --force to drop and recreate.")
        return

    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)

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
             two_days_ago.isoformat(), now.isoformat(), notes),
        )

    print(f"  Inserted {len(pigeons)} pigeons")

    # --------------------------------------------------
    # Videos (4 videos across 2 sessions)
    # --------------------------------------------------
    videos = [
        {
            "video_name": "session_001_overhead.mp4",
            "session_id": "session_001",
            "camera_type": "Overhead",
            "total_frames": 1800,
            "fps": 30.0,
            "processed_at": two_days_ago.isoformat(),
            "review_status": "raw",
            "processing_status": "completed",
            "model_version": "v20260101_000000",
        },
        {
            "video_name": "session_001_side.mp4",
            "session_id": "session_001",
            "camera_type": "Side",
            "total_frames": 1800,
            "fps": 30.0,
            "processed_at": two_days_ago.isoformat(),
            "review_status": "raw",
            "processing_status": "completed",
            "model_version": "v20260101_000000",
        },
        {
            "video_name": "session_002_overhead.mp4",
            "session_id": "session_002",
            "camera_type": "Overhead",
            "total_frames": 2400,
            "fps": 30.0,
            "processed_at": yesterday.isoformat(),
            "review_status": "raw",
            "processing_status": "completed",
            "model_version": "v20260101_000000",
        },
        {
            "video_name": "session_002_corner.mp4",
            "session_id": "session_002",
            "camera_type": "Corner",
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
                    review_status, assigned_at, created_at)
                   VALUES (?, ?, ?, ?, ?, 'raw', ?, ?)""",
                (vid_id, obj_idx, pigeon_id,
                 round(random.uniform(0.65, 0.98), 3),
                 random.choice(["marker", "appearance", "spatial"]),
                 now.isoformat(), now.isoformat()),
            )
            assignment_count += 1

    print(f"  Inserted {assignment_count} video assignments")

    # --------------------------------------------------
    # QC flags (sample flags across videos)
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
            "frame_idx": 450,
            "rule_name": "track_lost",
            "severity": "medium",
            "reason": "Gamma track lost for 30+ frames near south wall",
            "review_status": "pending",
        },
        {
            "video_id": video_ids[2],
            "frame_idx": 800,
            "rule_name": "low_confidence_id",
            "severity": "medium",
            "reason": "Delta identification confidence dropped below 0.5",
            "review_status": "pending",
        },
        {
            "video_id": video_ids[3],
            "frame_idx": 1600,
            "rule_name": "overlapping_bboxes",
            "severity": "low",
            "reason": "Alpha and Gamma bounding boxes overlap >60% at frame 1600",
            "review_status": "pending",
        },
    ]

    for flag in qc_flags:
        cur.execute(
            """INSERT INTO qc_flags
               (video_id, frame_idx, rule_name, severity, reason, review_status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (flag["video_id"], flag["frame_idx"], flag["rule_name"],
             flag["severity"], flag["reason"], flag["review_status"],
             now.isoformat()),
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
    # Behaviors (diverse: all 5 types represented per video)
    # --------------------------------------------------
    behavior_count = 0
    for vid_idx, vid_id in enumerate(video_ids):
        total_frames = videos[vid_idx]["total_frames"]
        for pigeon_id, _, _, _ in pigeons:
            # Ensure every behavior type appears at least once per pigeon
            # across the full dataset; give each pigeon 2-3 behaviors per video
            num_behaviors = random.randint(2, 3)
            chosen = random.sample(BEHAVIORS, num_behaviors)
            for behavior in chosen:
                start_f = random.randint(0, max(1, total_frames - 400))
                duration_frames = random.randint(30, 360)
                end_f = min(start_f + duration_frames, total_frames)
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
    # Pairwise proximity (2-3 per video with realistic distances)
    # --------------------------------------------------
    pairwise_count = 0
    all_pairs = [
        ("Alpha", "Beta"),
        ("Alpha", "Gamma"),
        ("Alpha", "Delta"),
        ("Beta", "Gamma"),
        ("Beta", "Delta"),
        ("Gamma", "Delta"),
    ]
    for vid_idx, vid_id in enumerate(video_ids):
        total_frames = videos[vid_idx]["total_frames"]
        # Pick 3 pairs per video with multiple proximity events each
        selected_pairs = random.sample(all_pairs, 3)
        for pigeon_a, pigeon_b in selected_pairs:
            # 2-3 proximity events per pair per video
            for _ in range(random.randint(2, 3)):
                frame_idx = random.randint(0, total_frames - 1)
                dist_mm = round(random.uniform(5, 250), 1)
                cur.execute(
                    """INSERT INTO pairwise
                       (video_id, frame_idx, pigeon_a, pigeon_b, distance_px, distance_mm, overlap_iou)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (vid_id, frame_idx, pigeon_a, pigeon_b,
                     round(dist_mm * random.uniform(1.5, 3.0), 1),
                     dist_mm,
                     round(random.uniform(0, 0.35) if dist_mm < 80 else 0.0, 3)),
                )
                pairwise_count += 1

    print(f"  Inserted {pairwise_count} pairwise records")

    # --------------------------------------------------
    # Droppings (15-20 across videos)
    # --------------------------------------------------
    droppings_count = random.randint(15, 20)
    for _ in range(droppings_count):
        vid_idx = random.randint(0, len(video_ids) - 1)
        vid_id = video_ids[vid_idx]
        total_frames = videos[vid_idx]["total_frames"]
        cur.execute(
            """INSERT INTO droppings
               (video_id, frame_idx, centroid_x, centroid_y, area_px,
                zone, confidence, detection_method, review_status, deduplicated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (vid_id,
             random.randint(0, total_frames - 1),
             round(random.uniform(50, 600), 1),
             round(random.uniform(50, 400), 1),
             round(random.uniform(20, 200), 1),
             random.choice(ZONES),
             round(random.uniform(0.4, 0.98), 3),
             random.choice(["color_threshold", "model_v1", "contour"]),
             random.choice(["raw", "raw", "raw", "confirmed"]),
             0),
        )

    print(f"  Inserted {droppings_count} droppings")

    # --------------------------------------------------
    # Clip library (10 clips with varying properties)
    # --------------------------------------------------
    extraction_reasons = [
        "High velocity burst detected",
        "Behavior transition boundary",
        "Close proximity event",
        "Rare zone visit",
        "Low-confidence detection segment",
        "Extended resting period",
        "Courtship display candidate",
        "Aggression event candidate",
        "Unusual heading change",
        "Feeding bout boundary",
    ]

    clip_ids = []
    for i in range(10):
        vid_idx = i % len(video_ids)
        vid_id = video_ids[vid_idx]
        total_frames = videos[vid_idx]["total_frames"]
        pigeon_id = pigeons[i % len(pigeons)][0]
        start_f = random.randint(0, max(1, total_frames - 200))
        dur_frames = random.randint(30, 180)
        end_f = min(start_f + dur_frames, total_frames)
        cur.execute(
            """INSERT INTO clip_library
               (video_id, pigeon_id, start_frame, end_frame, duration_seconds,
                clip_path, mask_overlay, zone, velocity_context,
                pairwise_context, extraction_reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (vid_id, pigeon_id, start_f, end_f,
             round((end_f - start_f) / 30.0, 2),
             f"clips/{pigeon_id.lower()}_clip_{i+1:03d}.mp4",
             1,
             random.choice(ZONES),
             f"{round(random.uniform(2, 20), 1)} mm/s avg",
             random.choice([None, "Near Beta (45mm)", "Near Gamma (62mm)", None]),
             extraction_reasons[i],
             (now - timedelta(hours=random.randint(1, 48))).isoformat()),
        )
        clip_ids.append(cur.lastrowid)

    print(f"  Inserted {len(clip_ids)} clips")

    # --------------------------------------------------
    # Behavior labels (5 of the 10 clips labeled)
    # --------------------------------------------------
    labeled_behaviors = ["Feeding", "Resting", "Walking", "Preening", "Courtship"]
    for i in range(5):
        cur.execute(
            """INSERT INTO behavior_labels
               (clip_id, behavior_class, labeler, labeled_at, split, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (clip_ids[i],
             labeled_behaviors[i],
             "lab_user",
             (now - timedelta(hours=random.randint(1, 24))).isoformat(),
             random.choice(["train", "train", "train", "val"]),
             None),
        )

    print("  Inserted 5 behavior labels")

    # --------------------------------------------------
    # Model registry (1 inactive trained model)
    # --------------------------------------------------
    cur.execute(
        """INSERT INTO model_registry
           (model_name, model_type, version, checkpoint_path,
            training_config, training_clips,
            train_accuracy, val_accuracy, test_accuracy,
            created_at, notes, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("behavior_classifier", "r3d_18", "v0.1.0",
         "models/behavior_r3d18_v0.1.0.pt",
         json.dumps({
             "backbone": "r3d_18",
             "epochs": 50,
             "batch_size": 16,
             "learning_rate": 0.001,
             "freeze_backbone": False,
             "behavior_classes": labeled_behaviors,
         }),
         120,
         0.87, 0.82, 0.79,
         (now - timedelta(days=1)).isoformat(),
         "First baseline model trained on initial labeled clips",
         0),
    )

    print("  Inserted 1 model registry entry")

    # --------------------------------------------------
    # Commit
    # --------------------------------------------------
    conn.commit()

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------
    tables = [
        "pigeons", "videos", "video_assignments", "qc_flags",
        "features", "behaviors", "pairwise", "droppings",
        "clip_library", "behavior_labels", "model_registry",
    ]
    print()
    print("  Seed complete! Summary:")
    for table in tables:
        cnt = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"    {table:24s} {cnt:>5}")

    conn.close()

    print()
    print(f"  Database: {DB_PATH}")
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed PigeonLab development data")
    parser.add_argument("--force", action="store_true", help="Delete existing DB and re-seed")
    args = parser.parse_args()

    print()
    print("  Seeding PigeonLab development data...")
    print()

    if args.force:
        DB_PATH.unlink(missing_ok=True)
        print("  Deleted existing database (--force)")
        print()

    seed()
