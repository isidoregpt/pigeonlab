import { get, post, put, del } from "./client";

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

export interface FullHealthDiagnostics {
  model_loaded: boolean;
  sam3_version: string | null;
  sam3_backend: string | null;
  gpu_name: string | null;
  vram_total_gb: number | null;
  vram_used_gb: number | null;
  vram_free_gb: number | null;
  cuda_version: string | null;
  torch_version: string | null;
  python_version: string;
  hardware_profile: string;
  last_processing_error: { video_id: number; error: string; timestamp: string | null } | null;
  active_jobs: number;
  env_summary: Record<string, string>;
  ffmpeg_available: boolean;
  ffmpeg_path?: string | null;
  ollama_reachable: boolean;
  gemma_model_present: boolean;
  gemma_model: string;
  gemma_installed_models: string[];
  sam3_ready: boolean;
  sam3_errors: string[];
  sam3_warnings: string[];
  sam3_patches: Record<string, boolean>;
}

export function getFullHealthDiagnostics() {
  return get<FullHealthDiagnostics>("/health/full");
}

export interface Sam3Info {
  ready: boolean;
  loaded: boolean;
  version: string;
  backend: string | null;
  native_available: boolean;
  transformers_available: boolean;
  torch_available: boolean;
  torch_version: string | null;
  cuda_available: boolean;
  cuda_version: string | null;
  gpu_name: string | null;
  python_version: string;
  recommended_dtype: string;
  model_id: string;
  model_dir: string;
  checkpoint_path: string | null;
  config_path: string | null;
  config_model_type: string | null;
  config_architectures: string[] | null;
  allow_hf_download: boolean;
  errors: string[];
  warnings: string[];
  load_error: string | null;
}

export function getSam3Info() {
  return get<Sam3Info>("/settings/sam3");
}

export interface GemmaInfo {
  mode: "off" | "assist" | "auto";
  enabled: boolean;
  ready: boolean;
  reachable: boolean;
  model_available: boolean;
  model: string;
  base_url: string;
  sample_interval_seconds: number;
  max_frames_per_video: number;
  confidence_threshold: number;
  installed_models: string[];
  errors: string[];
  warnings: string[];
}

export interface GemmaSettingsPayload {
  mode: "off" | "assist" | "auto";
  model: string;
  base_url: string;
  sample_interval_seconds: number;
  max_frames_per_video: number;
  confidence_threshold: number;
}

export function getGemmaInfo() {
  return get<GemmaInfo>("/settings/gemma");
}

export function updateGemmaSettings(payload: GemmaSettingsPayload) {
  return put<GemmaInfo>("/settings/gemma", payload);
}

export function resetDatabase() {
  return del<{ status: string; message: string }>("/settings/reset");
}

export function seedDatabase() {
  return post<{ status: string; message: string }>("/settings/seed", {});
}
