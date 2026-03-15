import { apiFetch } from "./client";

export function fetchStats() {
  return apiFetch("/stats");
}
