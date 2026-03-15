import { apiFetch } from "./client";

export function fetchPigeons() {
  return apiFetch("/pigeons");
}
