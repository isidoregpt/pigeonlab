import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Play,
  Check,
  Loader2,
  AlertTriangle,
  ChevronDown,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  X,
} from "lucide-react";
import {
  getClips,
  labelClip,
  getReadiness,
  startTraining,
  getTrainingStatus,
  getModels,
  activateModel,
  reinferVideos,
} from "../api/training";
import type { ClipWithLabel, TrainConfig } from "../api/training";
import type { ModelRegistryEntry } from "../types";
import LoadingState from "../components/ui/LoadingState";
import EmptyState from "../components/ui/EmptyState";
import SectionError from "../components/ui/SectionError";
import { usePageTitle } from "../hooks/usePageTitle";

/* ================================================================ */
const TABS = ["Clip Library", "Label Clips", "Train Model", "Model History"] as const;
type Tab = (typeof TABS)[number];

const BEHAVIOR_CLASSES = [
  "Feeding",
  "Resting",
  "Walking",
  "Preening",
  "Courtship",
  "Aggression",
  "Other",
] as const;

const BEHAVIOR_KEYS: Record<string, string> = {
  "1": "Feeding",
  "2": "Resting",
  "3": "Walking",
  "4": "Preening",
  "5": "Courtship",
  "6": "Aggression",
  "7": "Other",
  "0": "Skip",
};

const MIN_CLIPS_PER_CLASS = 20;

/* ================================================================ */
export default function Training() {
  usePageTitle("Training");
  const [tab, setTab] = useState<Tab>("Clip Library");
  const [labelClipId, setLabelClipId] = useState<number | null>(null);

  function goToLabel(clipId?: number) {
    if (clipId != null) setLabelClipId(clipId);
    setTab("Label Clips");
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <h1 className="text-xl font-bold text-text-primary">🧠 Training</h1>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              t === tab
                ? "border-accent text-accent"
                : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "Clip Library" && <ClipLibraryTab onLabel={goToLabel} />}
      {tab === "Label Clips" && (
        <LabelClipsTab preselectedId={labelClipId} onClearPreselected={() => setLabelClipId(null)} />
      )}
      {tab === "Train Model" && <TrainModelTab />}
      {tab === "Model History" && <ModelHistoryTab />}
    </div>
  );
}

/* ================================================================
   Tab 1: Clip Library
   ================================================================ */
function ClipLibraryTab({ onLabel }: { onLabel: (id: number) => void }) {
  const [pigeonFilter, setPigeonFilter] = useState("all");
  const [labeledFilter, setLabeledFilter] = useState("all");

  const clipsQuery = useQuery({
    queryKey: ["training-clips", pigeonFilter, labeledFilter],
    queryFn: () => getClips(pigeonFilter, labeledFilter),
  });

  const clips = clipsQuery.data?.clips ?? [];

  // Unique pigeons
  const pigeonIds = [...new Set(clips.map((c) => c.pigeon_id).filter(Boolean))] as string[];

  if (clipsQuery.isLoading) return <LoadingState />;
  if (clipsQuery.isError) return <SectionError message="Failed to load clips." onRetry={() => clipsQuery.refetch()} />;

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <SelectFilter
          label="Pigeon"
          value={pigeonFilter}
          onChange={setPigeonFilter}
          options={[
            { value: "all", label: "All Pigeons" },
            ...pigeonIds.map((id) => ({ value: id, label: id })),
          ]}
        />
        <SelectFilter
          label="Status"
          value={labeledFilter}
          onChange={setLabeledFilter}
          options={[
            { value: "all", label: "All" },
            { value: "labeled", label: "Labeled" },
            { value: "unlabeled", label: "Unlabeled" },
          ]}
        />
      </div>

      {clips.length === 0 ? (
        <EmptyState
          icon="🎬"
          title="No clips yet"
          description="Process some videos to generate training clips."
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {clips.map((clip) => (
            <ClipCard key={clip.id} clip={clip} onLabel={() => onLabel(clip.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

function ClipCard({
  clip,
  onLabel,
}: {
  clip: ClipWithLabel;
  onLabel: () => void;
}) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-text-primary truncate">
            {clip.pigeon_id ?? "Unknown"}
          </p>
          <p className="text-[12px] text-text-secondary mt-0.5">
            {clip.duration_seconds != null
              ? `${clip.duration_seconds.toFixed(1)}s`
              : "—"}{" "}
            {clip.zone && `· ${clip.zone}`}
          </p>
        </div>
        <span
          className={`px-2 py-0.5 text-[11px] font-medium rounded-full ${
            clip.label
              ? "bg-success/10 text-success"
              : "bg-border/50 text-text-secondary"
          }`}
        >
          {clip.label ?? "Unlabeled"}
        </span>
      </div>

      {clip.extraction_reason && (
        <p className="text-[11px] text-text-secondary truncate">
          {clip.extraction_reason}
        </p>
      )}

      <button
        onClick={onLabel}
        className="text-sm font-medium text-accent hover:text-accent/80 transition-colors"
      >
        Label →
      </button>
    </div>
  );
}

/* ================================================================
   Tab 2: Label Clips
   ================================================================ */
function LabelClipsTab({
  preselectedId,
  onClearPreselected,
}: {
  preselectedId: number | null;
  onClearPreselected: () => void;
}) {
  const queryClient = useQueryClient();

  const clipsQuery = useQuery({
    queryKey: ["training-clips", "all", "all"],
    queryFn: () => getClips("all", "all"),
  });

  const allClips = clipsQuery.data?.clips ?? [];
  // Show unlabeled first, then labeled (for re-labeling)
  const clips = [...allClips].sort((a, b) => {
    if (a.label && !b.label) return 1;
    if (!a.label && b.label) return -1;
    return 0;
  });

  // Find starting index
  const startIdx = preselectedId != null
    ? Math.max(0, clips.findIndex((c) => c.id === preselectedId))
    : 0;

  const [currentIdx, setCurrentIdx] = useState(startIdx);

  // Clear preselection after mounting
  useEffect(() => {
    if (preselectedId != null) {
      const idx = clips.findIndex((c) => c.id === preselectedId);
      if (idx >= 0) setCurrentIdx(idx);
      onClearPreselected();
    }
  }, [clips, preselectedId, onClearPreselected]);

  const labelMutation = useMutation({
    mutationFn: ({ clipId, behavior }: { clipId: number; behavior: string }) =>
      labelClip(clipId, behavior),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training-clips"] });
      queryClient.invalidateQueries({ queryKey: ["training-readiness"] });
      setCurrentIdx((i) => Math.min(i + 1, clips.length));
    },
  });

  // Keyboard shortcuts
  const handleLabel = useCallback(
    (behavior: string) => {
      const clip = clips[currentIdx];
      if (!clip) return;
      if (behavior === "Skip") {
        setCurrentIdx((i) => Math.min(i + 1, clips.length));
        return;
      }
      labelMutation.mutate({ clipId: clip.id, behavior });
    },
    [clips, currentIdx, labelMutation],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const behavior = BEHAVIOR_KEYS[e.key];
      if (behavior) {
        e.preventDefault();
        handleLabel(behavior);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleLabel]);

  if (clipsQuery.isLoading) return <LoadingState />;
  if (clipsQuery.isError) return <SectionError message="Failed to load clips." onRetry={() => clipsQuery.refetch()} />;

  const reviewedCount = currentIdx;
  const totalCount = clips.length;
  const unlabeledCount = clips.filter((c) => !c.label).length;
  const currentClip = clips[currentIdx];
  const allDone = currentIdx >= totalCount;

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Progress */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-text-primary">
            {reviewedCount} of {totalCount} reviewed
            {unlabeledCount > 0 && (
              <span className="text-text-secondary font-normal">
                {" "}({unlabeledCount} unlabeled)
              </span>
            )}
          </span>
          <span className="text-[12px] text-text-secondary">
            {totalCount > 0
              ? `${Math.round((reviewedCount / totalCount) * 100)}%`
              : "—"}
          </span>
        </div>
        <div className="h-2 bg-bg rounded-full overflow-hidden">
          <div
            className="h-full bg-accent transition-all"
            style={{
              width: `${totalCount > 0 ? (reviewedCount / totalCount) * 100 : 0}%`,
            }}
          />
        </div>
      </div>

      {allDone || !currentClip ? (
        <div className="text-center py-12">
          <div className="w-14 h-14 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
            <Check size={28} className="text-success" />
          </div>
          <p className="text-sm font-medium text-text-primary">
            {totalCount === 0 ? "No unlabeled clips available." : "All clips labeled!"}
          </p>
        </div>
      ) : (
        <>
          {/* Video placeholder */}
          <div className="bg-black rounded-xl aspect-video flex items-center justify-center relative">
            <div className="text-center">
              <Play size={48} className="text-white/30 mx-auto mb-2" />
              <p className="text-white/40 text-sm">
                {currentClip.pigeon_id ?? "Clip"} ·{" "}
                {currentClip.duration_seconds?.toFixed(1) ?? "?"}s
                {currentClip.zone && ` · ${currentClip.zone}`}
              </p>
              {currentClip.clip_path && (
                <p className="text-white/25 text-[11px] mt-1 truncate max-w-md mx-auto px-4">
                  {currentClip.clip_path}
                </p>
              )}
              <p className="text-white/30 text-[11px] mt-1">
                Frames {currentClip.start_frame} – {currentClip.end_frame}
              </p>
            </div>
          </div>

          {/* Context metadata */}
          {(currentClip.extraction_reason || currentClip.velocity_context || currentClip.pairwise_context) && (
            <div className="flex flex-wrap gap-2">
              {currentClip.extraction_reason && (
                <span className="px-2.5 py-1 text-[11px] bg-surface border border-border rounded-lg text-text-secondary">
                  {currentClip.extraction_reason}
                </span>
              )}
              {currentClip.velocity_context && (
                <span className="px-2.5 py-1 text-[11px] bg-surface border border-border rounded-lg text-text-secondary">
                  {currentClip.velocity_context}
                </span>
              )}
              {currentClip.pairwise_context && (
                <span className="px-2.5 py-1 text-[11px] bg-surface border border-border rounded-lg text-text-secondary">
                  {currentClip.pairwise_context}
                </span>
              )}
            </div>
          )}

          {/* Existing label indicator */}
          {currentClip.label && (
            <div className="flex items-center justify-between bg-success/5 border border-success/20 rounded-xl px-4 py-3">
              <div className="flex items-center gap-2">
                <Check size={14} className="text-success" />
                <span className="text-sm text-text-primary">
                  Previously labeled: <span className="font-medium">{currentClip.label}</span>
                </span>
              </div>
              <span className="text-[11px] text-text-secondary">
                Select a class below to re-label
              </span>
            </div>
          )}

          {/* Behavior buttons */}
          <div>
            <p className="text-sm font-medium text-text-primary mb-3">
              {currentClip.label ? "Re-label this clip:" : "What behavior is this?"}
            </p>
            <div className="grid grid-cols-4 gap-2">
              {BEHAVIOR_CLASSES.map((b, i) => (
                <button
                  key={b}
                  onClick={() => handleLabel(b)}
                  disabled={labelMutation.isPending}
                  className="px-3 py-3 bg-surface border border-border rounded-xl text-sm font-medium text-text-primary hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
                >
                  <span className="text-[11px] text-text-secondary/60 block mb-0.5">
                    {i + 1}
                  </span>
                  {b}
                </button>
              ))}
              <button
                onClick={() => handleLabel("Skip")}
                disabled={labelMutation.isPending}
                className="px-3 py-3 bg-bg border border-border rounded-xl text-sm font-medium text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
              >
                <span className="text-[11px] text-text-secondary/60 block mb-0.5">
                  0
                </span>
                Skip
              </button>
            </div>
          </div>

          {/* Keyboard hint */}
          <p className="text-[11px] text-text-secondary/60 text-center">
            Keyboard: 1–7 to label, 0 to skip
          </p>
        </>
      )}
    </div>
  );
}

/* ================================================================
   Tab 3: Train Model
   ================================================================ */
function TrainModelTab() {
  const queryClient = useQueryClient();
  const [backbone, setBackbone] = useState("r3d_18");
  const [epochs, setEpochs] = useState(50);
  const [batchSize, setBatchSize] = useState(16);
  const [lr, setLr] = useState(0.001);
  const [freezeBackbone, setFreezeBackbone] = useState(false);
  const [selectedClasses, setSelectedClasses] = useState<Set<string>>(
    new Set(BEHAVIOR_CLASSES),
  );
  const [jobId, setJobId] = useState<string | null>(null);

  const readinessQuery = useQuery({
    queryKey: ["training-readiness"],
    queryFn: getReadiness,
  });

  const trainMutation = useMutation({
    mutationFn: (config: TrainConfig) => startTraining(config),
    onSuccess: (data) => {
      setJobId(data.job_id);
      queryClient.invalidateQueries({ queryKey: ["models"] });
    },
  });

  const statusQuery = useQuery({
    queryKey: ["training-status", jobId],
    queryFn: () => getTrainingStatus(jobId!),
    enabled: jobId != null,
    refetchInterval: 3000,
  });

  const readiness = readinessQuery.data;
  const readinessClasses = readiness?.classes ?? {};
  const allClasses = [
    ...BEHAVIOR_CLASSES,
    ...Object.keys(readinessClasses).filter(
      (k) => !(BEHAVIOR_CLASSES as readonly string[]).includes(k),
    ),
  ];

  function toggleClass(cls: string) {
    setSelectedClasses((prev) => {
      const next = new Set(prev);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return next;
    });
  }

  const configErrors = {
    epochs: epochs < 1 || epochs > 500 ? "Must be 1–500." : null,
    batchSize: batchSize < 1 || batchSize > 256 ? "Must be 1–256." : null,
    lr: lr < 0.00001 || lr > 1 ? "Must be 0.00001–1.0." : null,
  };
  const hasConfigError = Object.values(configErrors).some(Boolean);

  function launch() {
    if (hasConfigError) return;
    trainMutation.mutate({
      backbone,
      epochs,
      batch_size: batchSize,
      learning_rate: lr,
      freeze_backbone: freezeBackbone,
      behavior_classes: Array.from(selectedClasses),
    });
  }

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Readiness check */}
      <section className="bg-surface border border-border rounded-xl p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-3">
          Training Readiness
        </h2>
        {readinessQuery.isLoading ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-5 bg-border/30 rounded animate-pulse" />
            ))}
          </div>
        ) : readinessQuery.isError ? (
          <SectionError message="Failed to load readiness." onRetry={() => readinessQuery.refetch()} />
        ) : (
          <>
            {readiness && (
              <p className="text-[12px] text-text-secondary mb-3">
                {readiness.total_labeled_clips} clips labeled across{" "}
                {readiness.num_classes} classes.
                {readiness.all_ready ? (
                  <span className="text-success font-medium"> All classes ready!</span>
                ) : (
                  <span className="text-warning font-medium"> Some classes need more clips.</span>
                )}
              </p>
            )}
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[12px] text-text-secondary uppercase tracking-wider">
                  <th className="text-left pb-2 font-medium">Class</th>
                  <th className="text-right pb-2 font-medium">Clips</th>
                  <th className="text-right pb-2 font-medium">Min</th>
                  <th className="text-right pb-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {allClasses.map((cls) => {
                  const info = readinessClasses[cls];
                  const count = info?.count ?? 0;
                  const ready = info?.ready ?? false;
                  const needed = info?.needed ?? MIN_CLIPS_PER_CLASS;
                  return (
                    <tr key={cls}>
                      <td className="py-2 text-text-primary">{cls}</td>
                      <td className="py-2 text-right tabular-nums text-text-secondary">
                        {count}
                      </td>
                      <td className="py-2 text-right tabular-nums text-text-secondary/60">
                        {MIN_CLIPS_PER_CLASS}
                      </td>
                      <td className="py-2 text-right">
                        <span
                          className={`inline-flex items-center gap-1 text-[11px] font-medium ${
                            ready ? "text-success" : "text-error"
                          }`}
                        >
                          {ready ? (
                            <>
                              <Check size={12} /> Ready
                            </>
                          ) : (
                            <>Need {needed} more</>
                          )}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
      </section>

      {/* Config form */}
      <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
        <h2 className="text-sm font-semibold text-text-primary">
          Training Configuration
        </h2>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[12px] font-medium text-text-secondary mb-1">
              Backbone
            </label>
            <select
              value={backbone}
              onChange={(e) => setBackbone(e.target.value)}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            >
              <option value="r3d_18">r3d_18</option>
              <option value="slowfast">SlowFast</option>
              <option value="x3d_s">X3D-S</option>
            </select>
          </div>

          <div>
            <label className="block text-[12px] font-medium text-text-secondary mb-1">
              Epochs
            </label>
            <input
              type="number"
              min={1}
              max={500}
              value={epochs}
              onChange={(e) => setEpochs(Number(e.target.value) || 0)}
              className={`w-full px-3 py-2 bg-bg border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 transition-colors ${
                configErrors.epochs
                  ? "border-error focus:ring-error/30 focus:border-error"
                  : "border-border focus:ring-accent/30 focus:border-accent"
              }`}
            />
            {configErrors.epochs && (
              <p className="text-[12px] text-error mt-1">{configErrors.epochs}</p>
            )}
          </div>

          <div>
            <label className="block text-[12px] font-medium text-text-secondary mb-1">
              Batch Size
            </label>
            <input
              type="number"
              min={1}
              max={256}
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value) || 0)}
              className={`w-full px-3 py-2 bg-bg border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 transition-colors ${
                configErrors.batchSize
                  ? "border-error focus:ring-error/30 focus:border-error"
                  : "border-border focus:ring-accent/30 focus:border-accent"
              }`}
            />
            {configErrors.batchSize && (
              <p className="text-[12px] text-error mt-1">{configErrors.batchSize}</p>
            )}
          </div>

          <div>
            <label className="block text-[12px] font-medium text-text-secondary mb-1">
              Learning Rate
            </label>
            <input
              type="number"
              step={0.0001}
              min={0.00001}
              max={1}
              value={lr}
              onChange={(e) => setLr(Number(e.target.value) || 0)}
              className={`w-full px-3 py-2 bg-bg border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 transition-colors ${
                configErrors.lr
                  ? "border-error focus:ring-error/30 focus:border-error"
                  : "border-border focus:ring-accent/30 focus:border-accent"
              }`}
            />
            {configErrors.lr && (
              <p className="text-[12px] text-error mt-1">{configErrors.lr}</p>
            )}
          </div>
        </div>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={freezeBackbone}
            onChange={(e) => setFreezeBackbone(e.target.checked)}
            className="w-4 h-4 rounded border-border text-accent focus:ring-accent/30"
          />
          <span className="text-sm text-text-primary">Freeze backbone weights</span>
        </label>
      </section>

      {/* Behavior classes */}
      <section className="bg-surface border border-border rounded-xl p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-3">
          Behavior Classes to Train
        </h2>
        <div className="flex flex-wrap gap-2">
          {allClasses.map((cls) => (
            <label
              key={cls}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer text-sm transition-colors ${
                selectedClasses.has(cls)
                  ? "bg-accent/10 text-accent border border-accent/30"
                  : "bg-bg border border-border text-text-secondary"
              }`}
            >
              <input
                type="checkbox"
                checked={selectedClasses.has(cls)}
                onChange={() => toggleClass(cls)}
                className="sr-only"
              />
              {cls}
            </label>
          ))}
        </div>
      </section>

      {/* Launch */}
      <div className="space-y-3">
        <button
          onClick={launch}
          disabled={trainMutation.isPending || selectedClasses.size === 0 || hasConfigError}
          className="flex items-center gap-2 px-5 py-2.5 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {trainMutation.isPending ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Zap size={16} />
          )}
          Launch Training
        </button>

        {trainMutation.isError && (
          <p className="text-sm text-error">
            Failed to start training. Please try again.
          </p>
        )}

        {/* Job status */}
        {jobId && statusQuery.data && (
          <div className="bg-surface border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Loader2 size={14} className="animate-spin text-accent" />
              <span className="text-sm font-medium text-text-primary">
                Training {statusQuery.data.status}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1 h-2 bg-bg rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent transition-all"
                  style={{
                    width: `${statusQuery.data.total_epochs > 0 ? (statusQuery.data.epoch / statusQuery.data.total_epochs) * 100 : 0}%`,
                  }}
                />
              </div>
              <span className="text-[12px] text-text-secondary tabular-nums">
                Epoch {statusQuery.data.epoch}/{statusQuery.data.total_epochs}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ================================================================
   Tab 4: Model History
   ================================================================ */
function ModelHistoryTab() {
  const queryClient = useQueryClient();
  const [showReinfer, setShowReinfer] = useState(false);
  const [skipAlreadyInferred, setSkipAlreadyInferred] = useState(true);
  const [onlyApproved, setOnlyApproved] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [showComparison, setShowComparison] = useState(false);

  const modelsQuery = useQuery({
    queryKey: ["models"],
    queryFn: getModels,
  });

  const activateMutation = useMutation({
    mutationFn: (modelId: number) => activateModel(modelId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["models"] }),
  });

  const reinferMutation = useMutation({
    mutationFn: (opts: { skip_already_inferred: boolean; only_approved_videos: boolean }) =>
      reinferVideos(opts),
  });

  const models = modelsQuery.data ?? [];
  const activeModel = models.find((m) => m.is_active) ?? null;

  function toggleSelect(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        if (next.size >= 2) return prev;
        next.add(id);
      }
      return next;
    });
    setShowComparison(false);
  }

  const selectedIds = Array.from(selected);
  const canCompare = selectedIds.length === 2;
  const comparedA = models.find((m) => m.id === selectedIds[0]);
  const comparedB = models.find((m) => m.id === selectedIds[1]);

  if (modelsQuery.isLoading) return <LoadingState />;
  if (modelsQuery.isError) return <SectionError message="Failed to load models." onRetry={() => modelsQuery.refetch()} />;

  if (models.length === 0) {
    return (
      <EmptyState
        icon="🧠"
        title="No models trained yet"
        description="Label enough clips and train your first model."
      />
    );
  }

  return (
    <div className="space-y-5">
      {/* Table */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[12px] text-text-secondary uppercase tracking-wider bg-bg/50">
                <th className="w-10 px-3 py-3" />
                <th className="text-left px-4 py-3 font-medium">Version</th>
                <th className="text-left px-4 py-3 font-medium">Created</th>
                <th className="text-right px-4 py-3 font-medium">Train</th>
                <th className="text-right px-4 py-3 font-medium">Val</th>
                <th className="text-right px-4 py-3 font-medium">Test</th>
                <th className="text-center px-4 py-3 font-medium">Status</th>
                <th className="text-right px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {models.map((m) => (
                <ModelRow
                  key={m.id}
                  model={m}
                  onActivate={() => activateMutation.mutate(m.id)}
                  isActivating={activateMutation.isPending}
                  checked={selected.has(m.id)}
                  onToggle={() => toggleSelect(m.id)}
                  disableCheck={!selected.has(m.id) && selected.size >= 2}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Compare button */}
      {canCompare && !showComparison && (
        <button
          onClick={() => setShowComparison(true)}
          className="flex items-center gap-2 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors"
        >
          Compare Selected
        </button>
      )}

      {/* Comparison panel */}
      {showComparison && comparedA && comparedB && (
        <ModelComparison
          modelA={comparedA}
          modelB={comparedB}
          onClose={() => {
            setShowComparison(false);
            setSelected(new Set());
          }}
        />
      )}

      {/* Reinfer */}
      <div>
        {showReinfer ? (
          <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-text-primary">
                Re-Infer Videos
              </h3>
              <button
                onClick={() => setShowReinfer(false)}
                className="p-1 rounded-md hover:bg-bg text-text-secondary hover:text-text-primary transition-colors"
              >
                <X size={16} />
              </button>
            </div>

            {/* Active model info */}
            {activeModel && (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-text-secondary">Model:</span>
                <span className="font-medium text-text-primary">
                  {activeModel.version ?? activeModel.model_name}
                </span>
                <span className="px-2 py-0.5 bg-success/10 text-success text-[11px] font-medium rounded-full">
                  Active
                </span>
              </div>
            )}
            {!activeModel && (
              <div className="flex items-center gap-2 text-sm text-warning">
                <AlertTriangle size={14} />
                No active model set. Activate a model first.
              </div>
            )}

            {/* Options */}
            <div className="space-y-2.5">
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={skipAlreadyInferred}
                  onChange={(e) => setSkipAlreadyInferred(e.target.checked)}
                  className="w-4 h-4 rounded border-border text-accent focus:ring-accent/30"
                />
                <div>
                  <span className="text-sm text-text-primary">
                    Skip videos already inferred with this model
                  </span>
                  <p className="text-[11px] text-text-secondary">
                    Only process videos that haven't been analyzed by the active model
                  </p>
                </div>
              </label>
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={onlyApproved}
                  onChange={(e) => setOnlyApproved(e.target.checked)}
                  className="w-4 h-4 rounded border-border text-accent focus:ring-accent/30"
                />
                <div>
                  <span className="text-sm text-text-primary">
                    Only approved videos
                  </span>
                  <p className="text-[11px] text-text-secondary">
                    Restrict to videos that have passed QC review
                  </p>
                </div>
              </label>
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={() =>
                  reinferMutation.mutate({
                    skip_already_inferred: skipAlreadyInferred,
                    only_approved_videos: onlyApproved,
                  })
                }
                disabled={reinferMutation.isPending || !activeModel}
                className="flex items-center gap-1.5 px-4 py-2 bg-warning text-white text-sm font-medium rounded-lg hover:bg-warning/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {reinferMutation.isPending && (
                  <Loader2 size={14} className="animate-spin" />
                )}
                Start Re-Inference
              </button>
              <button
                onClick={() => setShowReinfer(false)}
                className="px-3 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
            </div>

            {/* Result */}
            {reinferMutation.isSuccess && reinferMutation.data && (
              <div className="flex items-center gap-2 bg-success/5 border border-success/20 rounded-lg px-4 py-3">
                <Check size={14} className="text-success shrink-0" />
                <span className="text-sm text-text-primary">
                  Re-inference started: {reinferMutation.data.videos_eligible} videos
                  eligible, {reinferMutation.data.videos_skipped} skipped.
                </span>
              </div>
            )}
            {reinferMutation.isError && (
              <p className="text-sm text-error">
                Failed to start re-inference. Please try again.
              </p>
            )}
          </div>
        ) : (
          <button
            onClick={() => {
              reinferMutation.reset();
              setShowReinfer(true);
            }}
            className="px-4 py-2 border border-border rounded-lg text-sm font-medium text-text-primary hover:bg-bg transition-colors"
          >
            Apply to All Videos
          </button>
        )}
      </div>
    </div>
  );
}

function ModelRow({
  model,
  onActivate,
  isActivating,
  checked,
  onToggle,
  disableCheck,
}: {
  model: ModelRegistryEntry;
  onActivate: () => void;
  isActivating: boolean;
  checked: boolean;
  onToggle: () => void;
  disableCheck: boolean;
}) {
  const fmt = (v: number | null) =>
    v != null ? `${(v * 100).toFixed(1)}%` : "—";

  return (
    <tr className={checked ? "bg-accent/5" : ""}>
      <td className="px-3 py-3 text-center">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          disabled={disableCheck}
          className="w-4 h-4 rounded border-border text-accent focus:ring-accent/30 disabled:opacity-30"
        />
      </td>
      <td className="px-4 py-3 text-text-primary font-medium">
        {model.version ?? model.model_name}
      </td>
      <td className="px-4 py-3 text-text-secondary">
        {model.created_at
          ? new Date(model.created_at).toLocaleDateString()
          : "—"}
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-text-primary">
        {fmt(model.train_accuracy)}
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-text-primary">
        {fmt(model.val_accuracy)}
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-text-primary">
        {fmt(model.test_accuracy)}
      </td>
      <td className="px-4 py-3 text-center">
        {model.is_active ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-success/10 text-success text-[11px] font-medium rounded-full">
            <Check size={10} strokeWidth={3} />
            Active
          </span>
        ) : (
          <span className="text-[11px] text-text-secondary">Inactive</span>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        {!model.is_active && (
          <button
            onClick={onActivate}
            disabled={isActivating}
            className="text-[12px] font-medium text-accent hover:text-accent/80 transition-colors disabled:opacity-50"
          >
            Set as Active
          </button>
        )}
      </td>
    </tr>
  );
}

/* ================================================================
   Model Comparison Panel
   ================================================================ */
function parseConfig(raw: string | null): Record<string, unknown> {
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function AccuracyCell({
  label,
  valA,
  valB,
}: {
  label: string;
  valA: number | null;
  valB: number | null;
}) {
  const fmt = (v: number | null) => (v != null ? `${(v * 100).toFixed(1)}%` : "—");
  const diff =
    valA != null && valB != null ? valB - valA : null;

  return (
    <div className="text-center space-y-1">
      <p className="text-[11px] text-text-secondary uppercase tracking-wider">{label}</p>
      <div className="flex items-center justify-center gap-3">
        <span className="text-sm tabular-nums text-text-primary">{fmt(valA)}</span>
        <span className="text-text-secondary/40">→</span>
        <span className="text-sm tabular-nums text-text-primary">{fmt(valB)}</span>
      </div>
      {diff != null && (
        <div className="flex items-center justify-center gap-0.5">
          {diff > 0.001 ? (
            <ArrowUpRight size={12} className="text-success" />
          ) : diff < -0.001 ? (
            <ArrowDownRight size={12} className="text-error" />
          ) : (
            <Minus size={12} className="text-text-secondary" />
          )}
          <span
            className={`text-[11px] font-medium tabular-nums ${
              diff > 0.001 ? "text-success" : diff < -0.001 ? "text-error" : "text-text-secondary"
            }`}
          >
            {diff > 0 ? "+" : ""}
            {(diff * 100).toFixed(1)}pp
          </span>
        </div>
      )}
    </div>
  );
}

function ModelComparison({
  modelA,
  modelB,
  onClose,
}: {
  modelA: ModelRegistryEntry;
  modelB: ModelRegistryEntry;
  onClose: () => void;
}) {
  const nameA = modelA.version ?? modelA.model_name;
  const nameB = modelB.version ?? modelB.model_name;
  const configA = parseConfig(modelA.training_config);
  const configB = parseConfig(modelB.training_config);

  // Collect all config keys
  const allKeys = Array.from(
    new Set([...Object.keys(configA), ...Object.keys(configB)]),
  ).sort();

  // Find differences
  const configDiffs = allKeys.map((key) => ({
    key,
    valA: configA[key],
    valB: configB[key],
    changed: JSON.stringify(configA[key]) !== JSON.stringify(configB[key]),
  }));

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-bg/30">
        <h3 className="text-sm font-semibold text-text-primary">
          Comparing: {nameA} vs {nameB}
        </h3>
        <button
          onClick={onClose}
          className="p-1 rounded-md hover:bg-bg text-text-secondary hover:text-text-primary transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      <div className="p-5 space-y-6">
        {/* Accuracy comparison */}
        <div>
          <p className="text-[12px] font-medium text-text-secondary uppercase tracking-wider mb-3">
            Accuracy Metrics
          </p>
          <div className="grid grid-cols-3 gap-4 bg-bg/50 rounded-xl p-4">
            <AccuracyCell label="Train" valA={modelA.train_accuracy} valB={modelB.train_accuracy} />
            <AccuracyCell label="Validation" valA={modelA.val_accuracy} valB={modelB.val_accuracy} />
            <AccuracyCell label="Test" valA={modelA.test_accuracy} valB={modelB.test_accuracy} />
          </div>
        </div>

        {/* Training clips comparison */}
        <div>
          <p className="text-[12px] font-medium text-text-secondary uppercase tracking-wider mb-3">
            Training Clips
          </p>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-text-primary tabular-nums">{modelA.training_clips ?? "—"}</span>
            <span className="text-text-secondary/40">→</span>
            <span className="text-text-primary tabular-nums">{modelB.training_clips ?? "—"}</span>
            {modelA.training_clips != null && modelB.training_clips != null && modelB.training_clips !== modelA.training_clips && (
              <span
                className={`text-[11px] font-medium ${
                  modelB.training_clips > modelA.training_clips ? "text-success" : "text-warning"
                }`}
              >
                ({modelB.training_clips > modelA.training_clips ? "+" : ""}
                {modelB.training_clips - modelA.training_clips})
              </span>
            )}
          </div>
        </div>

        {/* Config differences */}
        {configDiffs.length > 0 && (
          <div>
            <p className="text-[12px] font-medium text-text-secondary uppercase tracking-wider mb-3">
              Training Configuration
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] text-text-secondary uppercase tracking-wider">
                    <th className="text-left pb-2 font-medium">Parameter</th>
                    <th className="text-right pb-2 font-medium">{nameA}</th>
                    <th className="text-right pb-2 font-medium">{nameB}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {configDiffs.map(({ key, valA, valB, changed }) => (
                    <tr key={key} className={changed ? "bg-warning/5" : ""}>
                      <td className="py-2 text-text-primary">{key}</td>
                      <td className="py-2 text-right tabular-nums text-text-secondary">
                        {formatConfigValue(valA)}
                      </td>
                      <td
                        className={`py-2 text-right tabular-nums ${
                          changed ? "text-accent font-medium" : "text-text-secondary"
                        }`}
                      >
                        {formatConfigValue(valB)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {configDiffs.some((d) => d.changed) && (
              <p className="text-[11px] text-text-secondary mt-2">
                Highlighted rows indicate changes between models.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function formatConfigValue(v: unknown): string {
  if (v === undefined) return "—";
  if (v === null) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/* ================================================================
   Shared: Select filter
   ================================================================ */
function SelectFilter({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[12px] text-text-secondary">{label}:</span>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="appearance-none pl-3 pr-7 py-1.5 bg-surface border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown
          size={12}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-secondary pointer-events-none"
        />
      </div>
    </div>
  );
}
