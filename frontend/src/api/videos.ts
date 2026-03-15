import { apiFetch } from "./client";

export function fetchVideos() {
  return apiFetch("/videos");
}
