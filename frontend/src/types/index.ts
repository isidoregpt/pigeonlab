export interface Video {
  video_id: number;
  video_name: string;
  session_id: string;
  camera_type: string;
  total_frames: number;
  fps: number;
  processed_at: string;
  review_status: string;
  processing_status: string;
  model_version: string;
  config_hash: string;
  notes: string;
}

export interface Pigeon {
  pigeon_id: string;
  physical_markers: string;
  preferred_zones: string;
  total_frames_observed: number;
  first_seen: string;
  last_seen: string;
  notes: string;
}
