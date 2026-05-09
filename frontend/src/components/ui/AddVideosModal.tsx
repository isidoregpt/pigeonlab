import { useState, useEffect, useCallback, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { X, FolderOpen, ChevronRight, Check, Loader2 } from "lucide-react";
import { processVideos, uploadVideos } from "../../api/videos";

interface AddVideosModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

const CAMERA_OPTIONS = ["Overhead", "Side", "Corner", "Other"] as const;

const STEPS = ["Select Files", "Camera Setup", "Processing Options"] as const;

interface CameraItem {
  key: string;
  label: string;
}

function fileKey(file: File): string {
  return `upload:${file.name}:${file.size}:${file.lastModified}`;
}

export default function AddVideosModal({ onClose, onSuccess }: AddVideosModalProps) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const [paths, setPaths] = useState<string[]>([""]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [cameraAssignments, setCameraAssignments] = useState<Record<string, string>>({});
  const [pigeonCount, setPigeonCount] = useState<number>(4);
  const [textPrompt, setTextPrompt] = useState("pigeon");
  const [sessionId, setSessionId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);
  const firstInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    document.addEventListener("keydown", handleKeyDown);
    firstInputRef.current?.focus();
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const validPaths = paths.map((p) => p.trim()).filter(Boolean);
  const cameraItems: CameraItem[] = [
    ...validPaths.map((path) => ({
      key: path,
      label: path.split(/[/\\]/).pop() || path,
    })),
    ...selectedFiles.map((file) => ({
      key: fileKey(file),
      label: file.name,
    })),
  ];
  const selectedCount = validPaths.length + selectedFiles.length;

  const addPath = () => setPaths((prev) => [...prev, ""]);
  const updatePath = (idx: number, val: string) =>
    setPaths((prev) => prev.map((p, i) => (i === idx ? val : p)));
  const removePath = (idx: number) =>
    setPaths((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== idx)));
  const addSelectedFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const incoming = Array.from(files);
    setSelectedFiles((prev) => {
      const seen = new Set(prev.map(fileKey));
      return [...prev, ...incoming.filter((file) => !seen.has(fileKey(file)))];
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };
  const removeSelectedFile = (key: string) => {
    setSelectedFiles((prev) => prev.filter((file) => fileKey(file) !== key));
    setCameraAssignments((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleProcess = useCallback(async () => {
    setError(null);
    setSubmitting(true);
    try {
      const pathCameraMap: Record<string, string> = {};
      for (const p of validPaths) {
        if (cameraAssignments[p]) {
          pathCameraMap[p] = cameraAssignments[p];
        }
      }
      const uploadCameraMap: Record<string, string> = {};
      for (const file of selectedFiles) {
        const key = fileKey(file);
        if (cameraAssignments[key]) {
          uploadCameraMap[file.name] = cameraAssignments[key];
        }
      }
      const sharedOptions = {
        expected_pigeon_count: pigeonCount,
        text_prompt: textPrompt.trim() || "pigeon",
        session_id: sessionId.trim() || undefined,
      };
      if (selectedFiles.length > 0) {
        await uploadVideos({
          files: selectedFiles,
          camera_assignments:
            Object.keys(uploadCameraMap).length > 0 ? uploadCameraMap : undefined,
          ...sharedOptions,
        });
      }
      if (validPaths.length > 0) {
        await processVideos({
          video_paths: validPaths,
          camera_assignments:
            Object.keys(pathCameraMap).length > 0 ? pathCameraMap : undefined,
          ...sharedOptions,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      queryClient.invalidateQueries({ queryKey: ["stats-today"] });
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
  }, [validPaths, selectedFiles, cameraAssignments, pigeonCount, textPrompt, sessionId, onSuccess]);

  const canAdvance =
    step === 0 ? selectedCount > 0 : step === 1 ? true : true;

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
                {selectedCount} video{selectedCount !== 1 ? "s" : ""} queued for processing.
              </p>
            </div>
          ) : step === 0 ? (
            <Step1
              paths={paths}
              selectedFiles={selectedFiles}
              updatePath={updatePath}
              removePath={removePath}
              removeSelectedFile={removeSelectedFile}
              addPath={addPath}
              firstInputRef={firstInputRef}
              fileInputRef={fileInputRef}
              addSelectedFiles={addSelectedFiles}
            />
          ) : step === 1 ? (
            <Step2
              items={cameraItems}
              cameraAssignments={cameraAssignments}
              setCameraAssignments={setCameraAssignments}
            />
          ) : (
            <Step3
              pigeonCount={pigeonCount}
              setPigeonCount={setPigeonCount}
              textPrompt={textPrompt}
              setTextPrompt={setTextPrompt}
              sessionId={sessionId}
              setSessionId={setSessionId}
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
                disabled={submitting || selectedCount === 0}
                className="flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {submitting ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Processing...
                  </>
                ) : (
                  "Process Videos ->"
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

const VALID_VIDEO_EXT = /\.(mp4|avi|mov|mkv)$/i;

function hasUnexpectedExtension(path: string): boolean {
  const trimmed = path.trim();
  return trimmed.length > 0 && !VALID_VIDEO_EXT.test(trimmed);
}

function Step1({
  paths,
  selectedFiles,
  updatePath,
  removePath,
  removeSelectedFile,
  addPath,
  firstInputRef,
  fileInputRef,
  addSelectedFiles,
}: {
  paths: string[];
  selectedFiles: File[];
  updatePath: (i: number, v: string) => void;
  removePath: (i: number) => void;
  removeSelectedFile: (key: string) => void;
  addPath: () => void;
  firstInputRef: React.RefObject<HTMLInputElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  addSelectedFiles: (files: FileList | null) => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-text-secondary">
        Choose video files or enter full file paths on this workstation.
      </p>
      <input
        ref={fileInputRef}
        type="file"
        accept=".mp4,.avi,.mov,.mkv,video/*"
        multiple
        className="hidden"
        onChange={(e) => addSelectedFiles(e.target.files)}
      />
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        className="inline-flex items-center gap-2 px-3 py-2 border border-border rounded-lg text-sm font-medium text-text-primary hover:bg-bg transition-colors"
      >
        <FolderOpen size={16} />
        Choose video files
      </button>
      {selectedFiles.length > 0 && (
        <div className="space-y-2">
          {selectedFiles.map((file) => {
            const key = fileKey(file);
            return (
              <div
                key={key}
                className="flex items-center justify-between gap-3 py-1.5 px-2 bg-bg rounded-lg"
              >
                <span className="text-sm text-text-primary truncate">{file.name}</span>
                <button
                  type="button"
                  onClick={() => removeSelectedFile(key)}
                  className="p-1 text-text-secondary hover:text-error transition-colors"
                  aria-label="Remove selected file"
                >
                  <X size={14} />
                </button>
              </div>
            );
          })}
        </div>
      )}
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
              onClick={() => fileInputRef.current?.click()}
              className="px-2.5 py-2 border border-border rounded-lg text-text-secondary hover:bg-bg transition-colors"
              title="Choose video files"
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
              Unexpected extension. Supported formats: .mp4, .avi, .mov, .mkv
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
  items,
  cameraAssignments,
  setCameraAssignments,
}: {
  items: CameraItem[];
  cameraAssignments: Record<string, string>;
  setCameraAssignments: React.Dispatch<React.SetStateAction<Record<string, string>>>;
}) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-text-secondary">
        Assign a camera angle for each video. This helps the system choose the right tracking model.
      </p>
      {items.map((item) => (
          <div
            key={item.key}
            className="flex items-center justify-between gap-3 py-2"
          >
            <span className="text-sm text-text-primary truncate flex-1">
              {item.label}
            </span>
            <select
              value={cameraAssignments[item.key] ?? "Overhead"}
              onChange={(e) =>
                setCameraAssignments((prev) => ({ ...prev, [item.key]: e.target.value }))
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
      ))}
    </div>
  );
}

/* ---------- Step 3: Processing options ---------- */

function Step3({
  pigeonCount,
  setPigeonCount,
  textPrompt,
  setTextPrompt,
  sessionId,
  setSessionId,
}: {
  pigeonCount: number;
  setPigeonCount: (n: number) => void;
  textPrompt: string;
  setTextPrompt: (s: string) => void;
  sessionId: string;
  setSessionId: (s: string) => void;
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

      <div>
        <label className="block text-sm font-medium text-text-primary mb-1.5">
          Session ID
          <span className="text-text-secondary font-normal ml-1">(optional)</span>
        </label>
        <input
          type="text"
          value={sessionId}
          onChange={(e) => setSessionId(e.target.value)}
          placeholder="session_013"
          className="w-full max-w-xs px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
        />
        <p className="text-[12px] text-text-secondary mt-1">
          Group these videos under a session for easier filtering.
        </p>
      </div>
    </div>
  );
}
