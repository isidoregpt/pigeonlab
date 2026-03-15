interface StatusBadgeProps {
  status: string;
}

const colorMap: Record<string, string> = {
  raw: "bg-gray-100 text-gray-600",
  pending: "bg-warning/10 text-warning",
  approved: "bg-success/10 text-success",
  rejected: "bg-error/10 text-error",
  processing: "bg-accent/10 text-accent",
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const colors = colorMap[status] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors}`}>
      {status}
    </span>
  );
}
