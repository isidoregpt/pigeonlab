import type { ReviewStatus, ProcessingStatus, QCFlagStatus } from "./types";

type AnyStatus = ReviewStatus | ProcessingStatus | QCFlagStatus | string;

const statusLabels: Record<string, string> = {
  raw: "Raw",
  reviewed: "Reviewed",
  approved: "Approved",
  rejected: "Rejected",
  queued: "Queued",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
  pending: "Pending",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
};

export function getStatusLabel(status: AnyStatus): string {
  return statusLabels[status] ?? status;
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
