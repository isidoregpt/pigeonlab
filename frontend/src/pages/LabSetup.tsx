import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BrainCircuit, CheckCircle2, Copy, Loader2, Save } from "lucide-react";
import { usePageTitle } from "../hooks/usePageTitle";
import {
  getZones,
  getSystemInfo,
  getFullHealthDiagnostics,
  getSam3Info,
  getGemmaInfo,
  updateGemmaSettings,
  resetDatabase,
  seedDatabase,
  type GemmaSettingsPayload,
} from "../api/settings";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import { useToast } from "../components/ui/Toast";

export default function LabSetup() {
  usePageTitle("Settings");
  const queryClient = useQueryClient();
  const toast = useToast();
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showSeedConfirm, setShowSeedConfirm] = useState(false);
  const [gemmaDraft, setGemmaDraft] = useState<GemmaSettingsPayload | null>(null);

  const zonesQuery = useQuery({
    queryKey: ["settings-zones"],
    queryFn: getZones,
  });

  const infoQuery = useQuery({
    queryKey: ["settings-info"],
    queryFn: getSystemInfo,
  });

  const sam3Query = useQuery({
    queryKey: ["settings-sam3"],
    queryFn: getSam3Info,
  });

  const diagnosticsQuery = useQuery({
    queryKey: ["health-full"],
    queryFn: getFullHealthDiagnostics,
    enabled: false,
  });

  const gemmaQuery = useQuery({
    queryKey: ["settings-gemma"],
    queryFn: getGemmaInfo,
  });

  useEffect(() => {
    if (!gemmaQuery.data) return;
    setGemmaDraft({
      mode: gemmaQuery.data.mode,
      model: gemmaQuery.data.model,
      base_url: gemmaQuery.data.base_url,
      sample_interval_seconds: gemmaQuery.data.sample_interval_seconds,
      max_frames_per_video: gemmaQuery.data.max_frames_per_video,
      confidence_threshold: gemmaQuery.data.confidence_threshold,
    });
  }, [gemmaQuery.data]);

  const resetMutation = useMutation({
    mutationFn: resetDatabase,
    onSuccess: () => {
      toast.success("Database has been reset.");
      setShowResetConfirm(false);
      queryClient.invalidateQueries();
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Database reset failed.");
    },
  });

  const seedMutation = useMutation({
    mutationFn: seedDatabase,
    onSuccess: () => {
      toast.success("Sample data loaded successfully.");
      setShowSeedConfirm(false);
      queryClient.invalidateQueries();
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to load sample data.");
    },
  });

  const gemmaMutation = useMutation({
    mutationFn: updateGemmaSettings,
    onSuccess: () => {
      toast.success("Gemma reviewer settings saved.");
      queryClient.invalidateQueries({ queryKey: ["settings-gemma"] });
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed to save Gemma settings.");
    },
  });

  const zones = zonesQuery.data?.zones ?? [];
  const info = infoQuery.data;

  const copyDiagnostics = async () => {
    const result = await diagnosticsQuery.refetch();
    if (!result.data) {
      toast.error("Could not collect diagnostics.");
      return;
    }
    const text = JSON.stringify(result.data, null, 2);
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Diagnostics copied to clipboard.");
    } catch {
      window.prompt("Copy diagnostics", text);
    }
  };

  return (
    <div className="space-y-8 max-w-3xl">
      <h1 className="text-xl font-bold text-text-primary">Settings</h1>

      {/* Arena Zones */}
      <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text-primary">
            Arena Zones
          </h2>
          <button
            disabled
            title="Zone editing coming soon"
            className="px-3 py-1.5 text-[12px] font-medium border border-border rounded-lg text-text-secondary opacity-50 cursor-not-allowed"
          >
            Edit Zones
          </button>
        </div>

        {zonesQuery.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-text-secondary">
            <Loader2 size={14} className="animate-spin" />
            Loading zones...
          </div>
        ) : zones.length > 0 ? (
          <>
            <div className="flex flex-wrap gap-2">
              {zones.map((zone) => (
                <span
                  key={zone}
                  className="px-3 py-1.5 bg-accent/5 border border-accent/20 text-accent text-sm font-medium rounded-lg"
                >
                  {zone}
                </span>
              ))}
            </div>
            <p className="text-[11px] text-text-secondary">
              These zones were detected from your processed video data.
            </p>
          </>
        ) : (
          <p className="text-sm text-text-secondary">
            No zones detected yet. Process some videos to discover arena zones.
          </p>
        )}
      </section>

      {/* Camera Config */}
      <section className="bg-surface border border-border rounded-xl p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-2">
          Camera Configuration
        </h2>
        <p className="text-sm text-text-secondary">
          Set up camera positions, calibration, and resolution settings.
          Camera configuration will be available in a future update.
        </p>
      </section>

      {/* Behavior Rules */}
      <section className="bg-surface border border-border rounded-xl p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-2">
          Behavior Rules
        </h2>
        <p className="text-sm text-text-secondary">
          Configure behavior detection thresholds and custom rules.
          Behavior rule configuration will be available in a future update.
        </p>
      </section>

      {/* System Info */}
      <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-text-primary">
            System Info
          </h2>
          <button
            onClick={() => copyDiagnostics()}
            disabled={diagnosticsQuery.isFetching}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-border text-[12px] font-medium text-text-secondary rounded-lg hover:bg-bg transition-colors disabled:opacity-40"
          >
            {diagnosticsQuery.isFetching ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Copy size={13} />
            )}
            Copy diagnostics
          </button>
        </div>

        {infoQuery.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-text-secondary">
            <Loader2 size={14} className="animate-spin" />
            Loading system info...
          </div>
        ) : info ? (
          <>
            {/* Database */}
            <div>
              <h3 className="text-[12px] font-medium text-text-secondary uppercase tracking-wider mb-2">
                Database
              </h3>
              <p className="text-sm text-text-primary font-mono bg-bg/50 border border-border rounded-lg px-3 py-2 break-all">
                {info.database_path}
              </p>
              <p className="text-[11px] text-text-secondary mt-1">
                Size: {info.database_size_mb} MB
              </p>
            </div>

            {/* Dataset counts */}
            <div>
              <h3 className="text-[12px] font-medium text-text-secondary uppercase tracking-wider mb-2">
                Dataset
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <InfoCard label="Videos" value={info.total_videos} />
                <InfoCard label="Pigeons" value={info.total_pigeons} />
                <InfoCard label="Features" value={info.total_features} />
                <InfoCard label="Behaviors" value={info.total_behaviors} />
                <InfoCard label="Clips" value={info.total_clips} />
                <InfoCard label="Models" value={info.model_count} />
              </div>
            </div>
          </>
        ) : (
          <div className="text-center py-4 space-y-2">
            <p className="text-sm text-text-secondary">Could not load system information.</p>
            <button
              onClick={() => infoQuery.refetch()}
              className="text-sm font-medium text-accent hover:text-accent/80 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}
      </section>

      {/* SAM3 Status */}
      <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-text-primary">
            SAM3 Processing
          </h2>
          {sam3Query.data && (
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                sam3Query.data.ready
                  ? "bg-success/10 text-success"
                  : "bg-error/10 text-error"
              }`}
            >
              {sam3Query.data.ready ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
              {sam3Query.data.ready ? "Ready" : "Needs setup"}
            </span>
          )}
        </div>

        {sam3Query.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-text-secondary">
            <Loader2 size={14} className="animate-spin" />
            Checking SAM3...
          </div>
        ) : sam3Query.data ? (
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <InfoCard label="Version" value={sam3Query.data.version} />
              <InfoCard label="Backend" value={sam3Query.data.backend ?? "not available"} />
              <InfoCard label="Python" value={sam3Query.data.python_version} />
              <InfoCard label="PyTorch" value={sam3Query.data.torch_version ?? "not installed"} />
              <InfoCard label="CUDA" value={sam3Query.data.cuda_available ? (sam3Query.data.cuda_version ?? "available") : "not detected"} />
              <InfoCard label="GPU" value={sam3Query.data.gpu_name ?? "not detected"} />
              <InfoCard label="Dtype" value={sam3Query.data.recommended_dtype ?? "auto"} />
            </div>

            <div>
              <h3 className="text-[12px] font-medium text-text-secondary uppercase tracking-wider mb-2">
                Model Files
              </h3>
              <p className="text-sm text-text-primary font-mono bg-bg/50 border border-border rounded-lg px-3 py-2 break-all">
                {sam3Query.data.checkpoint_path ?? sam3Query.data.model_dir}
              </p>
            </div>

            {(sam3Query.data.errors.length > 0 || sam3Query.data.warnings.length > 0) && (
              <div className="space-y-2">
                {sam3Query.data.errors.map((message) => (
                  <p key={message} className="text-sm text-error">
                    {message}
                  </p>
                ))}
                {sam3Query.data.warnings.map((message) => (
                  <p key={message} className="text-sm text-warning">
                    {message}
                  </p>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-4 space-y-2">
            <p className="text-sm text-text-secondary">Could not check SAM3 status.</p>
            <button
              onClick={() => sam3Query.refetch()}
              className="text-sm font-medium text-accent hover:text-accent/80 transition-colors"
            >
              Try Again
            </button>
          </div>
        )}
      </section>

      {/* Gemma Reviewer */}
      <section className="bg-surface border border-border rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <BrainCircuit size={18} className="text-accent" />
            <h2 className="text-sm font-semibold text-text-primary">
              Gemma Reviewer
            </h2>
          </div>
          {gemmaQuery.data && (
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                gemmaQuery.data.mode === "off"
                  ? "bg-border/60 text-text-secondary"
                  : gemmaQuery.data.ready
                    ? "bg-success/10 text-success"
                    : "bg-error/10 text-error"
              }`}
            >
              {gemmaQuery.data.mode === "off" ? (
                <BrainCircuit size={13} />
              ) : gemmaQuery.data.ready ? (
                <CheckCircle2 size={13} />
              ) : (
                <AlertTriangle size={13} />
              )}
              {gemmaQuery.data.mode === "off"
                ? "Off"
                : gemmaQuery.data.ready
                  ? "Ready"
                  : "Needs setup"}
            </span>
          )}
        </div>

        {gemmaQuery.isLoading || !gemmaDraft ? (
          <div className="flex items-center gap-2 text-sm text-text-secondary">
            <Loader2 size={14} className="animate-spin" />
            Checking Gemma...
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label className="block">
                <span className="block text-sm font-medium text-text-primary mb-1.5">
                  Review mode
                </span>
                <select
                  value={gemmaDraft.mode}
                  onChange={(e) =>
                    setGemmaDraft((prev) =>
                      prev ? { ...prev, mode: e.target.value as GemmaSettingsPayload["mode"] } : prev,
                    )
                  }
                  className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
                >
                  <option value="off">Off - human review</option>
                  <option value="assist">Assist - queue suggestions</option>
                  <option value="auto">Auto - approve confident labels</option>
                </select>
              </label>

              <SettingsTextField
                label="Ollama model"
                value={gemmaDraft.model}
                onChange={(value) =>
                  setGemmaDraft((prev) => (prev ? { ...prev, model: value } : prev))
                }
                placeholder="gemma4:e4b"
              />

              <SettingsTextField
                label="Ollama URL"
                value={gemmaDraft.base_url}
                onChange={(value) =>
                  setGemmaDraft((prev) => (prev ? { ...prev, base_url: value } : prev))
                }
                placeholder="http://localhost:11434"
              />

              <div className="grid grid-cols-3 gap-3">
                <SettingsNumberField
                  label="Seconds"
                  value={gemmaDraft.sample_interval_seconds}
                  min={1}
                  max={300}
                  onChange={(value) =>
                    setGemmaDraft((prev) =>
                      prev ? { ...prev, sample_interval_seconds: value } : prev,
                    )
                  }
                />
                <SettingsNumberField
                  label="Frames"
                  value={gemmaDraft.max_frames_per_video}
                  min={1}
                  max={200}
                  onChange={(value) =>
                    setGemmaDraft((prev) =>
                      prev ? { ...prev, max_frames_per_video: value } : prev,
                    )
                  }
                />
                <SettingsNumberField
                  label="Confidence"
                  value={gemmaDraft.confidence_threshold}
                  min={0}
                  max={1}
                  step={0.05}
                  onChange={(value) =>
                    setGemmaDraft((prev) =>
                      prev ? { ...prev, confidence_threshold: value } : prev,
                    )
                  }
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <InfoCard label="Ollama" value={gemmaQuery.data?.reachable ? "reachable" : "not reachable"} />
              <InfoCard label="Model" value={gemmaQuery.data?.model_available ? "installed" : "missing"} />
              <InfoCard label="Installed Models" value={gemmaQuery.data?.installed_models.length ?? 0} />
            </div>

            {(gemmaQuery.data?.errors.length || gemmaQuery.data?.warnings.length) ? (
              <div className="space-y-2">
                {gemmaQuery.data.errors.map((message) => (
                  <p key={message} className="text-sm text-error">
                    {message}
                  </p>
                ))}
                {gemmaQuery.data.warnings.map((message) => (
                  <p key={message} className="text-sm text-warning">
                    {message}
                  </p>
                ))}
              </div>
            ) : null}

            <button
              onClick={() => gemmaMutation.mutate(gemmaDraft)}
              disabled={gemmaMutation.isPending}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {gemmaMutation.isPending ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save size={14} />
                  Save Gemma Settings
                </>
              )}
            </button>
          </div>
        )}
      </section>

      {/* Danger Zone */}
      <section className="border-2 border-error/30 rounded-xl p-5 space-y-3">
        <h2 className="text-sm font-semibold text-error">Danger Zone</h2>
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-text-primary">Reset Database</p>
            <p className="text-[12px] text-text-secondary">
              Delete all data and start fresh. This cannot be undone.
            </p>
          </div>
          <button
            onClick={() => setShowResetConfirm(true)}
            className="px-4 py-2 text-sm font-medium text-error border border-error/30 rounded-lg hover:bg-error/5 transition-colors whitespace-nowrap"
          >
            Reset Database
          </button>
        </div>
        <div className="border-t border-error/15" />
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-text-primary">Load Sample Data</p>
            <p className="text-[12px] text-text-secondary">
              Add demo pigeons, videos, and other sample data for testing.
            </p>
          </div>
          <button
            onClick={() => setShowSeedConfirm(true)}
            className="px-4 py-2 text-sm font-medium text-warning border border-warning/30 rounded-lg hover:bg-warning/5 transition-colors whitespace-nowrap"
          >
            Load Sample Data
          </button>
        </div>
      </section>

      <ConfirmDialog
        open={showResetConfirm}
        title="Reset Database"
        message="This will delete all data including videos, pigeons, and training models. This cannot be undone. Are you sure?"
        confirmLabel="Reset Everything"
        variant="danger"
        onConfirm={() => resetMutation.mutate()}
        onCancel={() => setShowResetConfirm(false)}
        loading={resetMutation.isPending}
      />

      <ConfirmDialog
        open={showSeedConfirm}
        title="Load Sample Data"
        message="This will add sample pigeons, videos, and other demo data. Existing data will not be removed."
        confirmLabel="Load Data"
        variant="warning"
        onConfirm={() => seedMutation.mutate()}
        onCancel={() => setShowSeedConfirm(false)}
        loading={seedMutation.isPending}
      />
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-bg/50 border border-border rounded-lg px-3 py-2.5">
      <p className="text-lg font-semibold text-text-primary tabular-nums">
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
      <p className="text-[11px] text-text-secondary">{label}</p>
    </div>
  );
}

function SettingsTextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-text-primary mb-1.5">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary placeholder:text-text-secondary/40 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
      />
    </label>
  );
}

function SettingsNumberField({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-text-primary mb-1.5">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
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
