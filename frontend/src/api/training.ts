import { get, post } from "./client";
import type { ClipLibraryItem, ModelRegistryEntry } from "../types";

// --- Clips ---

export interface ClipWithLabel extends ClipLibraryItem {
  label_id: number | null;
  label: string | null;
  labeler: string | null;
  labeled_at: string | null;
  split: string | null;
}

interface ClipsResponse {
  clips: ClipWithLabel[];
  total: number;
  page: number;
  per_page: number;
}

export function getClips(pigeon?: string, labeled?: string, page = 1, perPage = 50) {
  const params = new URLSearchParams();
  if (pigeon && pigeon !== "all") params.set("pigeon", pigeon);
  if (labeled && labeled !== "all") params.set("labeled", labeled);
  params.set("page", String(page));
  params.set("per_page", String(perPage));
  return get<ClipsResponse>(`/training/clips?${params.toString()}`);
}

// --- Label ---

export function labelClip(clipId: number, behaviorClass: string) {
  return post<{
    id: number;
    clip_id: number;
    behavior_class: string;
    labeler: string;
    labeled_at: string;
    split: string;
  }>("/training/label", { clip_id: clipId, behavior_class: behaviorClass });
}

// --- Readiness ---

export interface ReadinessClass {
  count: number;
  minimum: number;
  ready: boolean;
  needed: number;
}

export interface ReadinessReport {
  classes: Record<string, ReadinessClass>;
  total_labeled_clips: number;
  min_per_class: number;
  all_ready: boolean;
  num_classes: number;
}

export function getReadiness() {
  return get<ReadinessReport>("/training/readiness");
}

// --- Class counts (backward compat) ---

export function getClassCounts() {
  return get<Record<string, number>>("/training/class-counts");
}

// --- Train ---

export interface TrainConfig {
  backbone: string;
  epochs: number;
  batch_size: number;
  learning_rate: number;
  freeze_backbone: boolean;
  behavior_classes: string[];
}

export function startTraining(config: TrainConfig) {
  return post<{
    job_id: string;
    model_id: number;
    version: string;
    status: string;
    estimated_duration_minutes: number | null;
    training_clips: number;
    config: TrainConfig;
  }>("/training/start", config);
}

export function getTrainingStatus(jobId: string) {
  return get<{
    job_id: string;
    status: string;
    epoch: number;
    total_epochs: number;
    loss: number | null;
    val_acc: number | null;
    progress: number;
  }>(`/training/status/${jobId}`);
}

// --- Models ---

export function getModels() {
  return get<ModelRegistryEntry[]>("/training/models");
}

export function activateModel(modelId: number) {
  return post<{ model_id: number; model_type: string; is_active: boolean }>(
    `/training/models/${modelId}/activate`,
    {},
  );
}

// --- Reinfer ---

export interface ReinferPayload {
  model_version?: string;
  scope?: string;
  skip_already_inferred?: boolean;
  only_approved_videos?: boolean;
}

export function reinferVideos(payload: ReinferPayload = {}) {
  return post<{
    job_id: string;
    model_version: string;
    videos_eligible: number;
    videos_skipped: number;
    status: string;
  }>("/training/reinfer", payload);
}
