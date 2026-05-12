import { del, get, post, postForm, put } from "./client";
import type { Video } from "../types";

interface VideosResponse {
  videos: Video[];
  total: number;
  page: number;
  per_page: number;
}

export function getSessions() {
  return get<string[]>("/videos/sessions");
}

export function getVideos(sort = "date", page = 1, perPage = 20) {
  return get<VideosResponse>(`/videos?sort=${sort}&page=${page}&per_page=${perPage}`);
}

export function getVideo(id: number) {
  return get<Video & { pigeon_count: number }>(`/videos/${id}`);
}

interface ProcessPayload {
  video_paths: string[];
  camera_assignments?: Record<string, string>;
  text_prompt?: string;
  expected_pigeon_count?: number;
  session_id?: string;
}

export function processVideos(payload: ProcessPayload) {
  return post<{ job_id: string; videos_queued: number; status: string }>(
    "/videos/process",
    payload,
  );
}

interface UploadVideosPayload {
  files: File[];
  camera_assignments?: Record<string, string>;
  text_prompt?: string;
  expected_pigeon_count?: number;
  session_id?: string;
  process_now?: boolean;
}

export interface UploadVideosResult {
  job_id: string | null;
  status: string;
  videos_uploaded: number;
  videos_queued: number;
}

export function uploadVideos(payload: UploadVideosPayload) {
  const form = new FormData();
  for (const file of payload.files) {
    form.append("files", file, file.name);
  }
  form.append("process_now", String(payload.process_now ?? true));
  if (payload.camera_assignments) {
    form.append("camera_assignments", JSON.stringify(payload.camera_assignments));
  }
  if (payload.text_prompt) form.append("text_prompt", payload.text_prompt);
  if (payload.expected_pigeon_count !== undefined) {
    form.append("expected_pigeon_count", String(payload.expected_pigeon_count));
  }
  if (payload.session_id) form.append("session_id", payload.session_id);
  return postForm<UploadVideosResult>("/videos/upload", form);
}

export interface FfmpegStatus {
  available: boolean;
  ffmpeg_path: string | null;
  ffprobe_path: string | null;
  default_input_dir: string;
  default_output_dir: string;
  default_archive_dir: string;
  chunk_seconds: number;
  errors: string[];
}

export interface ImportFolderPayload {
  input_dir?: string;
  output_dir?: string;
  archive_dir?: string;
  chunk_seconds?: number;
  archive_originals?: boolean;
  process_now?: boolean;
  expected_pigeon_count?: number;
  text_prompt?: string;
  session_prefix?: string;
  limit?: number;
}

export interface ImportFolderResult {
  input_dir: string;
  output_dir: string;
  archive_dir: string;
  chunk_seconds: number;
  videos_found: number;
  videos_imported: number;
  chunks_created: number;
  videos_queued: number;
  job_id: string | null;
  status: string;
  errors: Array<{ source_path: string; error: string }>;
}

export function getFfmpegStatus() {
  return get<FfmpegStatus>("/videos/ffmpeg/status");
}

export function importVideoFolder(payload: ImportFolderPayload) {
  return post<ImportFolderResult>("/videos/import-folder", payload);
}

export function getVideoStatus(id: number) {
  return get<{
    status: string;
    progress: number;
    error?: string | null;
    chunk_group_status?: string | null;
    chunk_group_status_label?: string | null;
    chunk_group_total?: number | null;
    chunk_group_completed?: number | null;
    chunk_group_failed?: number | null;
    chunk_group_cancelled?: number | null;
  }>(`/videos/${id}/status`);
}

export function retryVideo(id: number) {
  return post<{ job_id: string; video_id: number; status: string }>(
    `/videos/${id}/retry`,
    {},
  );
}

export function cancelVideo(id: number) {
  return post<{
    video_id: number;
    status: string;
    cancelled: boolean;
    cancelled_video_ids?: number[];
    message?: string;
  }>(`/videos/${id}/cancel`, {});
}

export function retryFailedChunkGroup(chunkGroupId: string) {
  return post<{ job_id: string; chunk_group_id: string; chunks_queued: number; status: string }>(
    `/videos/chunk-groups/${encodeURIComponent(chunkGroupId)}/retry-failed`,
    {},
  );
}

export function deleteVideo(id: number) {
  return del<{ video_id: number; deleted: boolean; rows_deleted: Record<string, number> }>(
    `/videos/${id}`,
  );
}

export function updateVideoReview(id: number, payload: { review_status: string; reviewer: string }) {
  return put<{ video_id: number; review_status: string; reviewer: string }>(
    `/videos/${id}/review`,
    payload,
  );
}

export function getFrameUrl(videoId: number, frameNum: number, overlay?: boolean) {
  const params = overlay ? "?overlay=true" : "";
  return `/api/videos/${videoId}/frame/${frameNum}${params}`;
}

export function getVideoFeatures(videoId: number, frameIdx: number) {
  return get<import("../types").Feature[]>(
    `/videos/${videoId}/features?frame_idx=${frameIdx}`,
  );
}

export function getVideoAIObservations(videoId: number, frameIdx?: number) {
  const params = frameIdx === undefined ? "" : `?frame_idx=${frameIdx}`;
  return get<import("../types").AIObservation[]>(
    `/videos/${videoId}/ai-observations${params}`,
  );
}

export interface TrackEdit {
  edit_id: number;
  edit_type: string;
  editor: string | null;
  details: string | null;
  created_at: string | null;
}

export function getVideoTrackEdits(videoId: number) {
  return get<TrackEdit[]>(`/videos/${videoId}/track-edits`);
}
