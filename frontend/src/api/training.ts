import { get, post } from "./client";
import type { ClipLibraryItem, ModelRegistryEntry } from "../types";

// --- Clips ---

export interface ClipWithLabel extends ClipLibraryItem {
  label: string | null;
  labeler: string | null;
}

export function getClips(pigeon?: string, labeled?: string) {
  const params = new URLSearchParams();
  if (pigeon && pigeon !== "all") params.set("pigeon", pigeon);
  if (labeled && labeled !== "all") params.set("labeled", labeled);
  const qs = params.toString();
  return get<ClipWithLabel[]>(`/training/clips${qs ? `?${qs}` : ""}`);
}

// --- Label ---

export function labelClip(clipId: number, behaviorClass: string) {
  return post<{ clip_id: number; behavior_class: string; status: string }>(
    "/training/label",
    { clip_id: clipId, behavior_class: behaviorClass },
  );
}

// --- Class counts ---

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
  return post<{ job_id: string; status: string; config: TrainConfig }>(
    "/training/start",
    config,
  );
}

export function getTrainingStatus(jobId: string) {
  return get<{
    job_id: string;
    status: string;
    epoch: number;
    total_epochs: number;
    progress: number;
  }>(`/training/status/${jobId}`);
}

// --- Models ---

export function getModels() {
  return get<ModelRegistryEntry[]>("/training/models");
}

export function activateModel(modelId: number) {
  return post<{ model_id: number; is_active: boolean }>(
    `/training/models/${modelId}/activate`,
    {},
  );
}

// --- Reinfer ---

export function reinferAll() {
  return post<{ status: string; job_id: string; message: string }>(
    "/training/reinfer",
    {},
  );
}
