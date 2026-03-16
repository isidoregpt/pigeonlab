import { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning" | "default";
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

const variantStyles = {
  danger: {
    confirm:
      "bg-error text-white hover:bg-error/90 focus:ring-error/30",
    icon: "bg-error/10 text-error",
  },
  warning: {
    confirm:
      "bg-amber-500 text-white hover:bg-amber-600 focus:ring-amber-500/30",
    icon: "bg-amber-500/10 text-amber-500",
  },
  default: {
    confirm:
      "bg-accent text-white hover:bg-accent/90 focus:ring-accent/30",
    icon: "bg-accent/10 text-accent",
  },
};

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  onConfirm,
  onCancel,
  loading = false,
}: ConfirmDialogProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const styles = variantStyles[variant];

  // Focus confirm button on open; handle ESC and focus trapping
  useEffect(() => {
    if (!open) return;

    // Focus the confirm button when the dialog opens
    confirmRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
        return;
      }
      if (e.key === "Tab") {
        const overlay = overlayRef.current;
        if (!overlay) return;
        const focusable = overlay.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div className="bg-surface rounded-2xl shadow-xl w-full max-w-sm mx-4 overflow-hidden">
        <div className="px-6 pt-6 pb-4 space-y-3">
          <h2 className="text-base font-semibold text-text-primary">{title}</h2>
          <p className="text-sm text-text-secondary leading-relaxed">{message}</p>
        </div>

        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary border border-border rounded-lg hover:bg-bg transition-colors disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            disabled={loading}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${styles.confirm}`}
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
