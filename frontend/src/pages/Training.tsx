import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Play,
  Check,
  Loader2,
  AlertTriangle,
  ChevronDown,
  Zap,
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
    queryKey: ["training-clips", "all", "unlabeled"],
    queryFn: () => getClips("all", "unlabeled"),
  });

  const clips = clipsQuery.data?.clips ?? [];

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

  const labeledCount = currentIdx;
  const totalCount = clips.length;
  const currentClip = clips[currentIdx];
  const allDone = currentIdx >= totalCount;

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Progress */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-text-primary">
            {labeledCount} of {totalCount} labeled
          </span>
          <span className="text-[12px] text-text-secondary">
            {totalCount > 0
              ? `${Math.round((labeledCount / totalCount) * 100)}%`
              : "—"}
          </span>
        </div>
        <div className="h-2 bg-bg rounded-full overflow-hidden">
          <div
            className="h-full bg-accent transition-all"
            style={{
              width: `${totalCount > 0 ? (labeledCount / totalCount) * 100 : 0}%`,
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
          <div className="bg-black rounded-xl aspect-video flex items-center justify-center">
            <div className="text-center">
              <Play size={48} className="text-white/30 mx-auto mb-2" />
              <p className="text-white/40 text-sm">
                {currentClip.pigeon_id ?? "Clip"} ·{" "}
                {currentClip.duration_seconds?.toFixed(1) ?? "?"}s
                {currentClip.zone && ` · ${currentClip.zone}`}
              </p>
            </div>
          </div>

          {/* Behavior buttons */}
          <div>
            <p className="text-sm font-medium text-text-primary mb-3">
              What behavior is this?
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
    onSuccess: (data) => setJobId(data.job_id),
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

  function launch() {
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
              onChange={(e) => setEpochs(Number(e.target.value) || 50)}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            />
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
              onChange={(e) => setBatchSize(Number(e.target.value) || 16)}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            />
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
              onChange={(e) => setLr(Number(e.target.value) || 0.001)}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
            />
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
          disabled={trainMutation.isPending || selectedClasses.size === 0}
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
  const [confirmReinfer, setConfirmReinfer] = useState(false);

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
    mutationFn: () => reinferVideos({}),
    onSuccess: () => setConfirmReinfer(false),
  });

  const models = modelsQuery.data ?? [];

  if (modelsQuery.isLoading) return <LoadingState />;

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
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Reinfer */}
      <div>
        {confirmReinfer ? (
          <div className="bg-warning/5 border border-warning/30 rounded-xl p-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} className="text-warning shrink-0" />
              <span className="text-sm text-text-primary">
                This will re-run inference on all videos with the active model. Continue?
              </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => setConfirmReinfer(false)}
                className="px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => reinferMutation.mutate()}
                disabled={reinferMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-warning text-white text-sm font-medium rounded-lg hover:bg-warning/90 transition-colors disabled:opacity-50"
              >
                {reinferMutation.isPending && (
                  <Loader2 size={14} className="animate-spin" />
                )}
                Yes, Re-Infer All
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setConfirmReinfer(true)}
            className="px-4 py-2 border border-border rounded-lg text-sm font-medium text-text-primary hover:bg-bg transition-colors"
          >
            Apply to All Videos
          </button>
        )}

        {reinferMutation.isSuccess && reinferMutation.data && (
          <p className="text-sm text-success mt-2">
            Re-inference started: {reinferMutation.data.videos_eligible} videos
            eligible, {reinferMutation.data.videos_skipped} skipped.
          </p>
        )}
        {reinferMutation.isError && (
          <p className="text-sm text-error mt-2">
            Failed to start re-inference.
          </p>
        )}
      </div>
    </div>
  );
}

function ModelRow({
  model,
  onActivate,
  isActivating,
}: {
  model: ModelRegistryEntry;
  onActivate: () => void;
  isActivating: boolean;
}) {
  const fmt = (v: number | null) =>
    v != null ? `${(v * 100).toFixed(1)}%` : "—";

  return (
    <tr>
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
