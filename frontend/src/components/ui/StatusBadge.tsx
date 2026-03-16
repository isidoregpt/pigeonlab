import { getStatusLabel, getStatusColor, getStatusDotColor } from "../../statusUtils";
import type { AnyStatus } from "../../statusUtils";

interface StatusBadgeProps {
  status: AnyStatus;
  size?: "sm" | "md";
}

export default function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const sizeClasses = size === "md"
    ? "px-2.5 py-1 text-xs"
    : "px-2 py-0.5 text-[11px]";

  const dotSize = size === "md" ? "w-2 h-2" : "w-1.5 h-1.5";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${getStatusColor(status)} ${sizeClasses}`}
    >
      <span className={`${dotSize} rounded-full shrink-0 ${getStatusDotColor(status)}`} />
      {getStatusLabel(status)}
    </span>
  );
}
