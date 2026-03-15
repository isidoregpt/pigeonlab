import { apiFetch } from "./client";

export function fetchTraining() {
  return apiFetch("/training");
}
