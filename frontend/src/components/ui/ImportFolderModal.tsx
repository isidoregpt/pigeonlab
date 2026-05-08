import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  Check,
  FolderInput,
  Loader2,
  Scissors,
  X,
} from "lucide-react";
import {
  getFfmpegStatus,
  importVideoFolder,
  type ImportFolderResult,
} from "../../api/videos";

interface ImportFolderModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export default function ImportFolderModal({ onClose, onSuccess }: ImportFolderModalProps) {
  const queryClient = useQueryClient();
  const overlayRef = useRef<HTMLDivElement>(null);
  const firstInputRef = useRef<HTMLInputElement>(null);
  const [hydrated, setHydrated] = useState(false);
  const [inputDir, setInputDir] = useState("");
  const [outputDir, setOutputDir] = useState("");
  const [archiveDir, setArchiveDir] = useState("");
  const [chunkMinutes, setChunkMinutes] = useState(5);
  const [maxVideos, setMaxVideos] = useState(10);
  const [archiveOriginals, setArchiveOriginals] = useState(false);
  const [processNow, setProcessNow] = useState(true);
  const [pigeonCount, setPigeonCount] = useState(4);
  const [textPrompt, setTextPrompt] = useState("pigeon");
  const [sessionPrefix, setSessionPrefix] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportFolderResult | null>(null);

  const { data: status, isLoading } = useQuery({
    queryKey: ["ffmpeg-status"],
    queryFn: getFfmpegStatus,
  });

  useEffect(() => {
    if (!status || hydrated) return;
    setInputDir(status.default_input_dir);
    setOutputDir(status.default_output_dir);
    setArchiveDir(status.default_archive_dir);
    setChunkMinutes(Math.max(1, Math.round(status.chunk_seconds / 60)));
    setHydrated(true);
  }, [status, hydrated]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
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
    };
    document.addEventListener("keydown", handleKeyDown);
    firstInputRef.current?.focus();
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const canSubmit =
    !submitting &&
    !isLoading &&
    status?.available === true &&
    inputDir.trim().length > 0 &&
    outputDir.trim().length > 0;

  const handleImport = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const response = await importVideoFolder({
        input_dir: inputDir.trim() || undefined,
        output_dir: outputDir.trim() || undefined,
        archive_dir: archiveDir.trim() || undefined,
        chunk_seconds: Math.max(30, Math.round(chunkMinutes * 60)),
        archive_originals: archiveOriginals,
        process_now: processNow,
        expected_pigeon_count: pigeonCount,
        text_prompt: textPrompt.trim() || "pigeon",
        session_prefix: sessionPrefix.trim() || undefined,
        limit: maxVideos > 0 ? maxVideos : undefined,
      });
      setResult(response);
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      queryClient.invalidateQueries({ queryKey: ["stats-today"] });
      onSuccess();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Folder import failed. Check FFmpeg, SAM3, and the folder paths.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Import Folder"
    >
      <div className="bg-surface rounded-2xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <FolderInput size={18} className="text-accent" />
            <h2 className="text-base font-semibold text-text-primary">Import Folder</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-bg transition-colors text-text-secondary"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-5 max-h-[70vh] overflow-y-auto">
          {result ? (
            <ImportResult result={result} processNow={processNow} />
          ) : (
            <>
              <FfmpegBanner statusAvailable={status?.available} errors={status?.errors ?? []} />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <TextField
                  label="Input folder"
                  value={inputDir}
                  onChange={setInputDir}
                  placeholder="E:/PigeonLab/input"
                  inputRef={firstInputRef}
                />
                <TextField
                  label="Output folder"
                  value={outputDir}
                  onChange={setOutputDir}
                  placeholder="E:/PigeonLab/output"
                />
                <TextField
                  label="Archive folder"
                  value={archiveDir}
                  onChange={setArchiveDir}
                  placeholder="E:/PigeonLab/archive"
                />
                <TextField
                  label="Session prefix"
                  value={sessionPrefix}
                  onChange={setSessionPrefix}
                  placeholder="may_08_batch"
                />
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <NumberField
                  label="Chunk minutes"
                  value={chunkMinutes}
                  min={1}
                  max={60}
                  onChange={setChunkMinutes}
                />
                <NumberField
                  label="Max videos"
                  value={maxVideos}
                  min={0}
                  max={500}
                  onChange={setMaxVideos}
                />
                <NumberField
                  label="Pigeons"
                  value={pigeonCount}
                  min={0}
                  max={100}
                  onChange={setPigeonCount}
                />
                <TextField
                  label="Text prompt"
                  value={textPrompt}
                  onChange={setTextPrompt}
                  placeholder="pigeon"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <ToggleRow
                  checked={processNow}
                  onChange={setProcessNow}
                  icon={<Scissors size={16} />}
                  label="Queue chunks for SAM3"
                />
                <ToggleRow
                  checked={archiveOriginals}
                  onChange={setArchiveOriginals}
                  icon={<Archive size={16} />}
                  label="Archive originals after split"
                />
              </div>

              {error && <p className="text-sm text-error">{error}</p>}
            </>
          )}
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-border">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            {result ? "Close" : "Cancel"}
          </button>
          {!result && (
            <button
              onClick={handleImport}
              disabled={!canSubmit}
              className="flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {submitting ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Importing...
                </>
              ) : (
                <>
                  <FolderInput size={14} />
                  Import
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  inputRef,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  inputRef?: RefObject<HTMLInputElement | null>;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-text-primary mb-1.5">{label}</span>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
      />
    </label>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-text-primary mb-1.5">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => {
          const next = Number(e.target.value);
          onChange(Number.isFinite(next) ? Math.max(min, Math.min(max, next)) : min);
        }}
        className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
      />
    </label>
  );
}

function ToggleRow({
  checked,
  onChange,
  icon,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  icon: ReactNode;
  label: string;
}) {
  return (
    <label className="flex items-center justify-between gap-3 px-3 py-2.5 bg-bg border border-border rounded-lg">
      <span className="flex items-center gap-2 text-sm font-medium text-text-primary">
        <span className="text-text-secondary">{icon}</span>
        {label}
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="w-4 h-4 accent-accent"
      />
    </label>
  );
}

function FfmpegBanner({
  statusAvailable,
  errors,
}: {
  statusAvailable?: boolean;
  errors: string[];
}) {
  if (statusAvailable === undefined) {
    return (
      <div className="flex items-center gap-2 text-sm text-text-secondary">
        <Loader2 size={14} className="animate-spin" />
        Checking FFmpeg...
      </div>
    );
  }
  if (statusAvailable) {
    return (
      <div className="flex items-center gap-2 text-sm text-success">
        <Check size={15} />
        FFmpeg ready
      </div>
    );
  }
  return (
    <div className="flex items-start gap-2 text-sm text-error">
      <AlertTriangle size={15} className="mt-0.5 shrink-0" />
      <span>{errors.join(" ") || "FFmpeg is not available."}</span>
    </div>
  );
}

function ImportResult({
  result,
  processNow,
}: {
  result: ImportFolderResult;
  processNow: boolean;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-success/10 flex items-center justify-center">
          <Check size={20} className="text-success" />
        </div>
        <div>
          <p className="text-sm font-medium text-text-primary">
            {processNow ? "Folder import queued" : "Folder import complete"}
          </p>
          <p className="text-[12px] text-text-secondary">
            {result.chunks_created} chunk{result.chunks_created === 1 ? "" : "s"} from{" "}
            {result.videos_imported} video{result.videos_imported === 1 ? "" : "s"}.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label="Found" value={result.videos_found} />
        <Metric label="Imported" value={result.videos_imported} />
        <Metric label="Chunks" value={result.chunks_created} />
        <Metric label="Queued" value={result.videos_queued} />
      </div>

      <div className="text-[12px] text-text-secondary break-all">
        Output: {result.output_dir}
      </div>

      {result.errors.length > 0 && (
        <div className="space-y-1">
          <p className="text-sm font-medium text-warning">
            {result.errors.length} video{result.errors.length === 1 ? "" : "s"} failed
          </p>
          {result.errors.slice(0, 3).map((item) => (
            <p key={item.source_path} className="text-[12px] text-text-secondary break-all">
              {item.source_path}: {item.error}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-bg border border-border rounded-lg px-3 py-2">
      <p className="text-[11px] uppercase tracking-wider text-text-secondary">{label}</p>
      <p className="text-lg font-semibold tabular-nums text-text-primary">{value}</p>
    </div>
  );
}
