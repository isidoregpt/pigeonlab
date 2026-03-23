import { useState, useEffect, useRef } from "react";
import { X, Loader2 } from "lucide-react";
import { createPigeon } from "../../api/pigeons";

interface RegisterPigeonModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export default function RegisterPigeonModal({ onClose, onSuccess }: RegisterPigeonModalProps) {
  const [name, setName] = useState("");
  const [markers, setMarkers] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    nameRef.current?.focus();
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const overlay = overlayRef.current;
        if (!overlay) return;
        const focusable = overlay.querySelectorAll<HTMLElement>(
          'button, input, textarea, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0]!;
        const last = focusable[focusable.length - 1]!;
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const PIGEON_ID_RE = /^[a-zA-Z0-9_-]+$/;
  const nameError =
    name.length > 0 && !PIGEON_ID_RE.test(name.trim())
      ? "Only letters, numbers, hyphens, and underscores allowed."
      : null;
  const canSubmit = name.trim().length > 0 && !nameError && !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setSubmitting(true);
    try {
      await createPigeon({
        pigeon_id: name.trim(),
        physical_markers: markers.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onSuccess();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to register pigeon. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      role="dialog"
      aria-modal="true"
      aria-label="Register New Pigeon"
    >
      <form
        onSubmit={handleSubmit}
        className="bg-surface rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-base font-semibold text-text-primary">Register New Pigeon</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-bg transition-colors text-text-secondary"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              Name <span className="text-error">*</span>
            </label>
            <input
              ref={nameRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. P-01, Blue-Band"
              className={`w-full px-3 py-2 bg-bg border rounded-lg text-sm text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:ring-2 transition-colors ${
                nameError
                  ? "border-error focus:ring-error/30 focus:border-error"
                  : "border-border focus:ring-accent/30 focus:border-accent"
              }`}
            />
            {nameError && (
              <p className="text-[12px] text-error mt-1">{nameError}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              Physical Markers
            </label>
            <input
              type="text"
              value={markers}
              onChange={(e) => setMarkers(e.target.value)}
              placeholder="e.g. Blue leg band, white chest patch"
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">
              Notes
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Any additional notes..."
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors resize-none"
            />
          </div>

          {error && <p className="text-sm text-error">{error}</p>}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className="flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Register
          </button>
        </div>
      </form>
    </div>
  );
}
