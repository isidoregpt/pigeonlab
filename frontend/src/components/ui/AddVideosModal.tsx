import { useState, useEffect, useCallback, useRef } from "react";
import { X, FolderOpen, ChevronRight, Check, Loader2 } from "lucide-react";
import { processVideos } from "../../api/videos";

interface AddVideosModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

const CAMERA_OPTIONS = ["Overhead", "Side", "Corner", "Other"] as const;

const STEPS = ["Select Files", "Camera Setup", "Processing Options"] as const;

export default function AddVideosModal({ onClose, onSuccess }: AddVideosModalProps) {
  const [step, setStep] = useState(0);
  const [paths, setPaths] = useState<string[]>([""]);
  const [cameraAssignments, setCameraAssignments] = useState<Record<string, string>>({});
  const [pigeonCount, setPigeonCount] = useState<number>(1);
  const [textPrompt, setTextPrompt] = useState("pigeon");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);
  const firstInputRef = useRef<HTMLInputElement>(null);

  // Focus trap & ESC to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab") {
        const overlay = overlayRef.current;
        if (!overlay) return;
        const focusable = overlay.querySelectorAll<HTMLElement>(
          'button, input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    firstInputRef.current?.focus();
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const validPaths = paths.filter((p) => p.trim() !== "");

  const addPath = () => setPaths((prev) => [...prev, ""]);
  const updatePath = (idx: number, val: string) =>
    setPaths((prev) => prev.map((p, i) => (i === idx ? val : p)));
  const removePath = (idx: number) =>
    setPaths((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== idx)));

  const handleProcess = useCallback(async () => {
    setError(null);
    setSubmitting(true);
    try {
      const cameraMap: Record<string, string> = {};
      for (const p of validPaths) {
        if (cameraAssignments[p]) {
          cameraMap[p] = cameraAssignments[p];
        }
      }
      await processVideos({
        video_paths: validPaths,
        camera_assignments: Object.keys(cameraMap).length > 0 ? cameraMap : undefined,
        expected_pigeon_count: pigeonCount,
        text_prompt: textPrompt.trim() || "pigeon",
      });
      setSuccess(true);
      setTimeout(() => onSuccess(), 1500);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to start processing. Please check the file paths and try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }, [validPaths, cameraAssignments, pigeonCount, textPrompt, onSuccess]);

  const canAdvance =
    step === 0 ? validPaths.length > 0 : step === 1 ? true : true;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Add Videos"
    >
      <div className="bg-surface rounded-2xl shadow-xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-base font-semibold text-text-primary">Add Videos</h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-bg transition-colors text-text-secondary"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-2 px-6 pt-4">
          {STEPS.map((label, i) => (
            <div key={label} className="flex items-center gap-2">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-semibold ${
                  i < step
                    ? "bg-accent text-white"
                    : i === step
                      ? "bg-accent text-white"
                      : "bg-border/50 text-text-secondary"
                }`}
              >
                {i < step ? <Check size={12} strokeWidth={3} /> : i + 1}
              </div>
              <span
                className={`text-[12px] ${i === step ? "text-text-primary font-medium" : "text-text-secondary"}`}
              >
                {label}
              </span>
              {i < STEPS.length - 1 && (
                <ChevronRight size={12} className="text-text-secondary/40 mx-1" />
              )}
            </div>
          ))}
        </div>

        {/* Body */}
        <div className="px-6 py-5 min-h-[240px]">
          {success ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="w-12 h-12 rounded-full bg-success/10 flex items-center justify-center mb-3">
                <Check size={24} className="text-success" />
              </div>
              <p className="text-sm font-medium text-text-primary">
                Processing started!
              </p>
              <p className="text-[12px] text-text-secondary mt-1">
                {validPaths.length} video{validPaths.length !== 1 ? "s" : ""} queued for processing.
              </p>
            </div>
          ) : step === 0 ? (
            <Step1
              paths={paths}
              updatePath={updatePath}
              removePath={removePath}
              addPath={addPath}
              firstInputRef={firstInputRef}
            />
          ) : step === 1 ? (
            <Step2
              paths={validPaths}
              cameraAssignments={cameraAssignments}
              setCameraAssignments={setCameraAssignments}
            />
          ) : (
            <Step3
              pigeonCount={pigeonCount}
              setPigeonCount={setPigeonCount}
              textPrompt={textPrompt}
              setTextPrompt={setTextPrompt}
            />
          )}

          {error && (
            <p className="mt-3 text-sm text-error">{error}</p>
          )}
        </div>

        {/* Footer */}
        {!success && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-border">
            <button
              onClick={step === 0 ? onClose : () => setStep((s) => s - 1)}
              className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
            >
              {step === 0 ? "Cancel" : "Back"}
            </button>

            {step < 2 ? (
              <button
                onClick={() => setStep((s) => s + 1)}
                disabled={!canAdvance}
                className="flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next
                <ChevronRight size={14} />
              </button>
            ) : (
              <button
                onClick={handleProcess}
                disabled={submitting || validPaths.length === 0}
                className="flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {submitting ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Processing…
                  </>
                ) : (
                  "Process Videos →"
                )}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- Step 1: File paths ---------- */

const VALID_VIDEO_EXT = /\.(mp4|avi|mov)$/i;

function hasUnexpectedExtension(path: string): boolean {
  const trimmed = path.trim();
  return trimmed.length > 0 && !VALID_VIDEO_EXT.test(trimmed);
}

function Step1({
  paths,
  updatePath,
  removePath,
  addPath,
  firstInputRef,
}: {
  paths: string[];
  updatePath: (i: number, v: string) => void;
  removePath: (i: number) => void;
  addPath: () => void;
  firstInputRef: React.RefObject<HTMLInputElement | null>;
}) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-text-secondary">
        Enter the file paths to your video files. These should be the full paths on your local machine.
      </p>
      {paths.map((p, i) => (
        <div key={i}>
          <div className="flex items-center gap-2">
            <input
              ref={i === 0 ? firstInputRef : undefined}
              type="text"
              value={p}
              onChange={(e) => updatePath(i, e.target.value)}
              placeholder="C:\Videos\session_01\overhead.mp4"
              className={`flex-1 px-3 py-2 bg-bg border rounded-lg text-sm text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:ring-2 transition-colors ${
                hasUnexpectedExtension(p)
                  ? "border-warning focus:ring-warning/30 focus:border-warning"
                  : "border-border focus:ring-accent/30 focus:border-accent"
              }`}
            />
            <button
              type="button"
              className="px-2.5 py-2 border border-border rounded-lg text-text-secondary hover:bg-bg transition-colors"
              title="Browse (placeholder)"
              aria-label="Browse files"
            >
              <FolderOpen size={16} />
            </button>
            {paths.length > 1 && (
              <button
                onClick={() => removePath(i)}
                className="p-2 text-text-secondary hover:text-error transition-colors"
                aria-label="Remove path"
              >
                <X size={14} />
              </button>
            )}
          </div>
          {hasUnexpectedExtension(p) && (
            <p className="text-[12px] text-warning mt-1">
              Unexpected extension. Supported formats: .mp4, .avi, .mov
            </p>
          )}
        </div>
      ))}
      <button
        onClick={addPath}
        className="text-sm text-accent hover:text-accent/80 font-medium transition-colors"
      >
        + Add another file
      </button>
    </div>
  );
}

/* ---------- Step 2: Camera assignment ---------- */

function Step2({
  paths,
  cameraAssignments,
  setCameraAssignments,
}: {
  paths: string[];
  cameraAssignments: Record<string, string>;
  setCameraAssignments: React.Dispatch<React.SetStateAction<Record<string, string>>>;
}) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-text-secondary">
        Assign a camera angle for each video. This helps the system choose the right tracking model.
      </p>
      {paths.map((p) => {
        const filename = p.split(/[/\\]/).pop() || p;
        return (
          <div
            key={p}
            className="flex items-center justify-between gap-3 py-2"
          >
            <span className="text-sm text-text-primary truncate flex-1">
              {filename}
            </span>
            <select
              value={cameraAssignments[p] ?? "Overhead"}
              onChange={(e) =>
                setCameraAssignments((prev) => ({ ...prev, [p]: e.target.value }))
              }
              className="px-3 py-1.5 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            >
              {CAMERA_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        );
      })}
    </div>
  );
}

/* ---------- Step 3: Processing options ---------- */

function Step3({
  pigeonCount,
  setPigeonCount,
  textPrompt,
  setTextPrompt,
}: {
  pigeonCount: number;
  setPigeonCount: (n: number) => void;
  textPrompt: string;
  setTextPrompt: (s: string) => void;
}) {
  return (
    <div className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-text-primary mb-1.5">
          Expected number of pigeons
        </label>
        <input
          type="number"
          min={1}
          max={100}
          value={pigeonCount}
          onChange={(e) => setPigeonCount(Math.max(1, Number(e.target.value) || 1))}
          className="w-24 px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
        />
        <p className="text-[12px] text-text-secondary mt-1">
          How many pigeons should the model look for in the video?
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-text-primary mb-1.5">
          Text prompt
        </label>
        <input
          type="text"
          value={textPrompt}
          onChange={(e) => setTextPrompt(e.target.value)}
          placeholder="pigeon"
          className="w-full max-w-xs px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
        />
        <p className="text-[12px] text-text-secondary mt-1">
          The object label the detection model will search for.
        </p>
      </div>
    </div>
  );
}
