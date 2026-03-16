import { get, post, put } from "./client";
import type { Pigeon } from "../types";

interface PigeonListItem extends Pigeon {
  session_count: number;
  top_zone: string | null;
}

interface PigeonProfile extends Pigeon {
  session_count: number;
  top_zone: string | null;
  avg_velocity_mm_s: number;
  behavior_summary: Record<string, number>;
}

interface HeatmapResponse {
  grid: number[][];
  width: number;
  height: number;
  pigeon_id: string;
}

interface BehaviorsResponse {
  behaviors: Record<string, { duration_seconds: number; event_count: number }>;
}

interface IdentityStatusResponse {
  confirmed_sessions: number;
  unconfirmed_sessions: number;
  total_sessions: number;
}

export function getPigeons() {
  return get<PigeonListItem[]>("/pigeons");
}

export function getPigeon(id: string) {
  return get<PigeonProfile>(`/pigeons/${id}`);
}

export function getPigeonHeatmap(id: string, period = "week") {
  return get<HeatmapResponse>(`/pigeons/${id}/heatmap?period=${period}`);
}

export function getPigeonBehaviors(id: string, period = "week") {
  return get<BehaviorsResponse>(`/pigeons/${id}/behaviors?period=${period}`);
}

export function getPigeonIdentityStatus(id: string) {
  return get<IdentityStatusResponse>(`/pigeons/${id}/identity-status`);
}

export function createPigeon(payload: { pigeon_id: string; physical_markers?: string; notes?: string }) {
  return post<{ pigeon_id: string; status: string }>("/pigeons", payload);
}

export function updatePigeon(id: string, payload: { physical_markers?: string; preferred_zones?: string; notes?: string }) {
  return put<{ pigeon_id: string; status: string }>(`/pigeons/${id}`, payload);
}
