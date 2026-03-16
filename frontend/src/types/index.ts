// --- Status unions ---

export type ReviewStatus = "raw" | "reviewed" | "approved" | "rejected";
export type ProcessingStatus = "queued" | "processing" | "completed" | "failed";
export type QCFlagStatus = "pending" | "acknowledged" | "resolved";
export type MatchMethod = "marker" | "appearance" | "spatial" | "manual" | "placeholder";
export type QCSeverity = "low" | "medium" | "high" | "critical";

// --- Data interfaces ---

export interface Video {
  video_id: number;
  video_name: string;
  session_id: string | null;
  camera_type: string | null;
  total_frames: number | null;
  fps: number | null;
  processed_at: string | null;
  review_status: ReviewStatus;
  processing_status: ProcessingStatus;
  model_version: string | null;
  config_hash: string | null;
  notes: string | null;
}

export interface Pigeon {
  pigeon_id: string;
  physical_markers: string | null;
  appearance_embedding: string | null;
  preferred_zones: string | null;
  total_frames_observed: number;
  first_seen: string | null;
  last_seen: string | null;
  notes: string | null;
}

export interface VideoAssignment {
  id: number;
  video_id: number;
  video_obj_id: number;
  pigeon_id: string;
  confidence: number | null;
  match_method: MatchMethod | null;
  review_status: ReviewStatus;
  assigned_at: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
}

export interface Feature {
  id: number;
  video_id: number;
  frame_idx: number;
  pigeon_id: string;
  centroid_x: number | null;
  centroid_y: number | null;
  centroid_mm_x: number | null;
  centroid_mm_y: number | null;
  area_px: number | null;
  area_mm2: number | null;
  velocity_px: number | null;
  velocity_mm_s: number | null;
  heading_deg: number | null;
  current_zone: string | null;
  distance_to_nearest_wall_px: number | null;
  confidence: number;
}

export interface Behavior {
  id: number;
  video_id: number;
  pigeon_id: string;
  behavior: string;
  source: string | null;
  model_version: string | null;
  start_frame: number | null;
  end_frame: number | null;
  duration_seconds: number | null;
  confidence: number | null;
  zone: string | null;
  interacting_with: string | null;
  review_status: ReviewStatus;
  details: string | null;
}

export interface ClipLibraryItem {
  id: number;
  video_id: number;
  pigeon_id: string | null;
  start_frame: number;
  end_frame: number;
  duration_seconds: number | null;
  clip_path: string | null;
  mask_overlay: boolean;
  zone: string | null;
  velocity_context: string | null;
  pairwise_context: string | null;
  extraction_reason: string | null;
  created_at: string | null;
}

export interface DroppingDetection {
  id: number;
  video_id: number;
  frame_idx: number;
  centroid_x: number | null;
  centroid_y: number | null;
  area_px: number | null;
  zone: string | null;
  confidence: number | null;
  detection_method: string | null;
  review_status: ReviewStatus;
  deduplicated: boolean;
}

export interface QCFlag {
  id: number;
  video_id: number;
  frame_idx: number | null;
  rule_name: string;
  severity: QCSeverity | null;
  reason: string | null;
  review_status: QCFlagStatus;
  resolved_action: string | null;
}

export interface ReviewTask {
  id: number;
  task_type: string;
  reference_id: number | null;
  video_id: number | null;
  priority: "low" | "normal" | "high" | "urgent";
  status: "pending" | "in_progress" | "completed" | "skipped";
  assigned_to: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface ModelRegistryEntry {
  id: number;
  model_name: string;
  model_type: string;
  version: string | null;
  checkpoint_path: string | null;
  training_config: string | null;
  training_clips: number | null;
  train_accuracy: number | null;
  val_accuracy: number | null;
  test_accuracy: number | null;
  created_at: string | null;
  notes: string | null;
  is_active: boolean;
}

export interface BenchmarkResult {
  id: number;
  subsystem: string;
  benchmark_name: string;
  model_version: string | null;
  metric_name: string;
  metric_value: number | null;
  sample_size: number | null;
  run_at: string | null;
  config_used: string | null;
}

export interface AttentionItem {
  type: string;
  description: string;
  link: string;
  severity: QCSeverity;
  count: number;
}

export interface StatsToday {
  videos_processed: number;
  pigeons_tracked: number;
}

export interface StatsSummary {
  zone_occupancy: Record<string, Record<string, number>>;
}
