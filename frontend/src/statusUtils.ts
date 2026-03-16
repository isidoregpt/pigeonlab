import type { ReviewStatus, ProcessingStatus, QCFlagStatus } from "./types";

export type AnyStatus = ReviewStatus | ProcessingStatus | QCFlagStatus | string;

const statusLabels: Record<string, string> = {
  raw: "Not yet checked",
  reviewed: "Checked",
  approved: "Confirmed",
  rejected: "Rejected",
  queued: "Queued",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
  pending: "Needs attention",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
};

export function getStatusLabel(status: AnyStatus): string {
  return statusLabels[status] ?? status;
}

const videoStatusLabels: Record<string, string> = {
  ...statusLabels,
  approved: "Approved",
};

export function getVideoStatusLabel(status: AnyStatus): string {
  return videoStatusLabels[status] ?? status;
}

const statusColors: Record<string, string> = {
  raw: "bg-gray-100 text-gray-600",
  reviewed: "bg-accent/10 text-accent",
  approved: "bg-success/10 text-success",
  rejected: "bg-error/10 text-error",
  queued: "bg-gray-100 text-gray-600",
  processing: "bg-accent/10 text-accent",
  completed: "bg-success/10 text-success",
  failed: "bg-error/10 text-error",
  pending: "bg-warning/10 text-warning",
  acknowledged: "bg-accent/10 text-accent",
  resolved: "bg-success/10 text-success",
};

export function getStatusColor(status: AnyStatus): string {
  return statusColors[status] ?? "bg-gray-100 text-gray-600";
}

const dotColors: Record<string, string> = {
  raw: "bg-gray-400",
  reviewed: "bg-accent",
  approved: "bg-success",
  rejected: "bg-error",
  queued: "bg-gray-400",
  processing: "bg-accent",
  completed: "bg-success",
  failed: "bg-error",
  pending: "bg-warning",
  acknowledged: "bg-accent",
  resolved: "bg-success",
};

export function getStatusDotColor(status: AnyStatus): string {
  return dotColors[status] ?? "bg-gray-400";
}
