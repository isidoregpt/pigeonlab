import { apiFetch } from "./client";

export function fetchReview() {
  return apiFetch("/review");
}
