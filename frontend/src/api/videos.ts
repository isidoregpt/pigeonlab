import { get, post, put } from "./client";
import type { Video } from "../types";

interface VideosResponse {
  videos: Video[];
  total: number;
  page: number;
  per_page: number;
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

export function getVideoStatus(id: number) {
  return get<{ status: string; progress: number }>(`/videos/${id}/status`);
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
