import { AlertTriangle } from "lucide-react";

interface SectionErrorProps {
  message: string;
  onRetry?: () => void;
}

export default function SectionError({ message, onRetry }: SectionErrorProps) {
  return (
    <div className="flex items-center justify-center gap-3 py-8 text-sm text-text-secondary">
      <AlertTriangle size={16} className="text-error shrink-0" />
      <span>{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-3 py-1 text-[12px] font-medium text-accent border border-accent/30 rounded-lg hover:bg-accent/5 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}
