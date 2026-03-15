import { apiFetch } from "./client";

export function fetchInsights() {
  return apiFetch("/insights");
}
