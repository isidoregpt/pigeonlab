import { get, post } from "./client";

// --- Heatmap ---

interface HeatmapResponse {
  grid: number[][];
  width: number;
  height: number;
}

export function getInsightsHeatmap(pigeons = "all", period = "week") {
  return get<HeatmapResponse>(`/insights/heatmap?pigeons=${pigeons}&period=${period}`);
}

// --- Behaviors ---

interface BehaviorSummary {
  duration_seconds: number;
  event_count: number;
}

export function getInsightsBehaviors(period = "week") {
  return get<{ pigeons: Record<string, Record<string, BehaviorSummary>> }>(
    `/insights/behaviors?period=${period}`,
  );
}

// --- Pairwise ---

interface PairwiseEntry {
  pigeon_a: string;
  pigeon_b: string;
  avg_distance_mm: number;
  proximity_events: number;
  total_duration_seconds: number;
}

export function getInsightsPairwise(period = "week") {
  return get<{ pairs: PairwiseEntry[] }>(`/insights/pairwise?period=${period}`);
}

// --- Droppings ---

interface DroppingsSummary {
  total: number;
  by_zone: Record<string, number>;
  grid: number[][];
}

export function getInsightsDroppings(period = "week") {
  return get<DroppingsSummary>(`/insights/droppings?period=${period}`);
}

// --- Compare ---

interface SessionComparison {
  session_a: string;
  session_b: string;
  zone_occupancy_diff: Record<string, Record<string, number>>;
  behavior_diff: Record<string, Record<string, { duration_diff: number; count_diff: number }>>;
  identity_changes: { only_in_a: string[]; only_in_b: string[]; in_both: string[] };
}

export function compareSessionsInsight(sessionA: string, sessionB: string) {
  return get<SessionComparison>(`/insights/compare?a=${sessionA}&b=${sessionB}`);
}

// --- Export ---

interface ExportPayload {
  format?: string;
  include?: string[];
  filters?: Record<string, unknown>;
  include_manifest?: boolean;
}

interface ExportResponse {
  download_url: string | null;
  files_included: string[];
  rows_exported: number;
}

export function createExport(payload: ExportPayload) {
  return post<ExportResponse>("/export", payload);
}

export function getExportDownloadUrl(filename: string) {
  return `/api/export/download/${filename}`;
}
