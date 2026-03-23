import { get } from "./client";
import type { StatsToday, AttentionItem } from "../types";

export function getStatsToday() {
  return get<StatsToday>("/stats/today");
}

export function getStatsSummary(period = "week") {
  return get<{ pigeons: Record<string, Record<string, number>> }>(
    `/stats/summary?period=${period}`,
  );
}

export function getAttentionCount() {
  return get<{ total: number; identity: number; qc: number; droppings: number; behaviors: number }>(
    "/review/attention/count",
  );
}

export function getAttentionItems(limit = 5) {
  return get<(AttentionItem & { id: number; video_id: number; link: string })[]>(
    `/review/attention?limit=${limit}`,
  );
}

interface ActivityItem {
  timestamp: string;
  description: string;
  type: string;
  status: string;
}

export function getActivity(limit = 10) {
  return get<ActivityItem[]>(`/activity?limit=${limit}`);
}
