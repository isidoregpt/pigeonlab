import { get } from "./client";

export function getZones() {
  return get<{ zones: string[] }>("/settings/zones");
}

export interface SystemInfo {
  database_path: string;
  database_size_mb: number;
  total_videos: number;
  total_pigeons: number;
  total_features: number;
  total_behaviors: number;
  total_clips: number;
  model_count: number;
}

export function getSystemInfo() {
  return get<SystemInfo>("/settings/info");
}
