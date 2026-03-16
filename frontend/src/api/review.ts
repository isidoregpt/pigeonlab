import { get, post } from "./client";
import type { VideoAssignment, QCFlag, Behavior, DroppingDetection } from "../types";

// --- Identity ---

export function getNextVideoForIdentityReview() {
  return get<{ video_id: number | null }>("/review/identities/next-video");
}

export function getUnconfirmedIdentities(videoId: number) {
  return get<VideoAssignment[]>(`/review/identities?video_id=${videoId}`);
}

interface IdentityReviewPayload {
  assignment_id: number;
  action: "confirm" | "reject" | "reassign";
  pigeon_id?: string;
  old_pigeon_id?: string;
  new_pigeon_id?: string;
  reviewer?: string;
}

export function reviewIdentity(payload: IdentityReviewPayload) {
  return post<VideoAssignment>("/review/identity", payload);
}

// --- QC Flags ---

export function getQCFlags(status = "pending", videoId?: number) {
  let url = `/review/qc-flags?status=${status}`;
  if (videoId != null) url += `&video_id=${videoId}`;
  return get<QCFlag[]>(url);
}

interface QCFlagReviewPayload {
  flag_id: number;
  action: string;
  resolved_action?: string;
  reviewer?: string;
  notes?: string;
}

export function reviewQCFlag(payload: QCFlagReviewPayload) {
  return post<QCFlag>("/review/qc-flag", payload);
}

// --- Droppings List ---

export function getDroppingsForReview(status = "raw", limit = 50) {
  return get<DroppingDetection[]>(`/review/droppings?status=${status}&limit=${limit}`);
}

// --- Mask Edit ---

interface MaskEditPayload {
  video_id: number;
  frame_idx: number;
  pigeon_id?: string;
  edit_type?: string;
  mask_data?: string;
  editor?: string;
  details?: string;
}

export function submitMaskEdit(payload: MaskEditPayload) {
  return post<{ edit_id: number; saved: boolean }>("/review/mask-edit", payload);
}

// --- Track Merge ---

interface TrackMergePayload {
  video_id: number;
  source_obj_id: number;
  target_obj_id: number;
  from_frame?: number;
  editor?: string;
  notes?: string;
}

export function mergeTrack(payload: TrackMergePayload) {
  return post<{ edit_id: number; merged: boolean; frames_affected: number }>(
    "/review/track-merge",
    payload,
  );
}

// --- Track Split ---

interface TrackSplitPayload {
  video_id: number;
  obj_id: number;
  at_frame: number;
  editor?: string;
  notes?: string;
}

export function splitTrack(payload: TrackSplitPayload) {
  return post<{ edit_id: number; original_obj_id: number; new_obj_id: number; split_at_frame: number }>(
    "/review/track-split",
    payload,
  );
}

// --- Behavior Review ---

export function reviewBehavior(payload: { behavior_id: number; action: "confirm" | "reject"; reviewer?: string }) {
  return post<Behavior>("/review/behavior", payload);
}

// --- Dropping Review ---

export function reviewDropping(payload: { dropping_id: number; action: "confirm" | "reject"; reviewer?: string }) {
  return post<DroppingDetection>("/review/dropping", payload);
}
