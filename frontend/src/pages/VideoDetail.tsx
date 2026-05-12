import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { usePageTitle } from "../hooks/usePageTitle";
import {
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
  Camera,
  Film,
  Gauge,
  Users,
  AlertTriangle,
  Check,
  Loader2,
  Eye,
  EyeOff,
  BrainCircuit,
} from "lucide-react";
import {
  getVideo,
  getFrameUrl,
  getVideoFeatures,
  getVideoAIObservations,
  getVideoTrackEdits,
  updateVideoReview,
} from "../api/videos";
import { getQCFlags, reviewQCFlag } from "../api/review";
import StatusBadge from "../components/ui/StatusBadge";
import LoadingState from "../components/ui/LoadingState";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import { useToast } from "../components/ui/Toast";

export default function VideoDetail() {
  usePageTitle("Video Detail");
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const videoId = Number(id);

  const toast = useToast();
  const [frameNum, setFrameNum] = useState(0);
  const [frameLoading, setFrameLoading] = useState(true);
  const [frameError, setFrameError] = useState<string | null>(null);
  const [showOverlays, setShowOverlays] = useState(true);
  const [showRejectDialog, setShowRejectDialog] = useState(false);

  // --- Queries ---

  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => getVideo(videoId),
    enabled: !Number.isNaN(videoId),
  });

  const totalFrames = videoQuery.data?.total_frames ?? 0;

  // Jump to ?frame=N on mount once totalFrames is known
  useEffect(() => {
    const frameParam = searchParams.get("frame");
    if (frameParam !== null && totalFrames > 0) {
      const parsed = Number(frameParam);
      if (!Number.isNaN(parsed)) {
        setFrameNum(Math.max(0, Math.min(parsed, totalFrames - 1)));
      }
    }
  }, [totalFrames, searchParams]);

  const featuresQuery = useQuery({
    queryKey: ["video-features", videoId, frameNum],
    queryFn: () => getVideoFeatures(videoId, frameNum),
    enabled: !Number.isNaN(videoId) && totalFrames > 0,
  });

  const aiQuery = useQuery({
    queryKey: ["video-ai-observations", videoId, frameNum],
    queryFn: () => getVideoAIObservations(videoId, frameNum),
    enabled: !Number.isNaN(videoId) && totalFrames > 0,
  });

  const qcQuery = useQuery({
    queryKey: ["video-qc", videoId],
    queryFn: () => getQCFlags("pending", videoId),
    enabled: !Number.isNaN(videoId),
  });

  const editsQuery = useQuery({
    queryKey: ["video-edits", videoId],
    queryFn: () => getVideoTrackEdits(videoId),
    enabled: !Number.isNaN(videoId),
  });

  // QC flags for current frame
  const frameFlags = (qcQuery.data ?? []).filter(
    (f) => f.frame_idx === frameNum,
  );

  // --- Mutations ---

  const approveMutation = useMutation({
    mutationFn: () =>
      updateVideoReview(videoId, {
        review_status: "approved",
        reviewer: "lab_user",
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["video", videoId] }),
  });

  const rejectMutation = useMutation({
    mutationFn: () =>
      updateVideoReview(videoId, {
        review_status: "rejected",
        reviewer: "lab_user",
      }),
    onSuccess: () => {
      toast.success("Video rejected");
      navigate("/videos");
    },
    onError: () => {
      toast.error("Failed to reject video");
    },
    onSettled: () => setShowRejectDialog(false),
  });

  const dismissFlagMutation = useMutation({
    mutationFn: (flagId: number) =>
      reviewQCFlag({
        flag_id: flagId,
        action: "resolve",
        resolved_action: "ignored",
        reviewer: "lab_user",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["video-qc", videoId] });
      queryClient.invalidateQueries({ queryKey: ["attention-count"] });
      queryClient.invalidateQueries({ queryKey: ["attention-items"] });
    },
  });

  // --- Frame navigation ---

  const goToFrame = useCallback(
    (n: number) => {
      const clamped = Math.max(0, Math.min(totalFrames - 1, n));
      if (clamped !== frameNum) {
        setFrameLoading(true);
        setFrameError(null);
        setFrameNum(clamped);
      }
    },
    [frameNum, totalFrames],
  );

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        goToFrame(frameNum - (e.shiftKey ? 10 : 1));
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        goToFrame(frameNum + (e.shiftKey ? 10 : 1));
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [frameNum, goToFrame]);

  // Preload adjacent frames for instant navigation
  useEffect(() => {
    const preload = (n: number) => {
      if (n >= 0 && n < totalFrames) {
        const img = new Image();
        img.src = getFrameUrl(videoId, n, showOverlays);
      }
    };
    preload(frameNum - 1);
    preload(frameNum + 1);
  }, [videoId, frameNum, totalFrames, showOverlays]);

  // --- Render ---

  if (videoQuery.isLoading) return <LoadingState variant="detail" />;

  if (videoQuery.isError || !videoQuery.data) {
    return (
      <div className="text-center py-16">
        <p className="text-text-secondary text-sm">
          {videoQuery.isError
            ? "Could not load this video. It may have been removed or the ID is invalid."
            : "Video not found."}
        </p>
        <button
          onClick={() => navigate("/videos")}
          className="mt-4 text-sm text-accent hover:text-accent/80 font-medium transition-colors"
        >
          ← Back to Videos
        </button>
      </div>
    );
  }

  const video = videoQuery.data;
  const features = featuresQuery.data ?? [];
  const aiObservations = aiQuery.data ?? [];

  return (
    <div className="space-y-4">
      {/* Back link */}
      <button
        onClick={() => navigate("/videos")}
        className="flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary transition-colors"
      >
        <ArrowLeft size={14} />
        Back to Videos
      </button>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* ========== Left: Player ========== */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Frame viewer */}
          <div className="bg-surface border border-border rounded-xl overflow-hidden">
            <div className="flex items-center justify-end px-3 py-2 border-b border-border">
              <button
                onClick={() => {
                  setFrameLoading(true);
                  setFrameError(null);
                  setShowOverlays((v) => !v);
                }}
                className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary transition-colors"
              >
                {showOverlays ? <Eye size={14} /> : <EyeOff size={14} />}
                {showOverlays ? "Hide Overlays" : "Show Overlays"}
              </button>
            </div>
            <div className="relative bg-black aspect-video flex items-center justify-center">
              {frameLoading && (
                <div className="absolute inset-0 flex items-center justify-center z-10">
                  <Loader2 size={28} className="animate-spin text-white/60" />
                </div>
              )}
              {totalFrames > 0 ? (
                <img
                  key={`${frameNum}-${showOverlays}`}
                  src={getFrameUrl(videoId, frameNum, showOverlays)}
                  alt={`Frame ${frameNum}`}
                  className={`max-w-full max-h-full object-contain transition-opacity ${frameLoading || frameError ? "opacity-30" : "opacity-100"}`}
                  onLoad={() => setFrameLoading(false)}
                  onError={() => {
                    setFrameLoading(false);
                    setFrameError("Frame image unavailable. Reprocess this video so PigeonLab can rebuild its frame cache.");
                  }}
                />
              ) : (
                <span className="text-white/40 text-sm">No frames available</span>
              )}
              {frameError && (
                <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
                  <div className="max-w-sm rounded-lg border border-white/10 bg-black/70 px-4 py-3 text-white">
                    <AlertTriangle size={20} className="mx-auto mb-2 text-warning" />
                    <p className="text-sm font-medium">Frame could not be loaded</p>
                    <p className="mt-1 text-xs text-white/70">{frameError}</p>
                  </div>
                </div>
              )}
            </div>

            {/* Controls */}
            {totalFrames > 0 && (
              <div className="px-4 py-3 space-y-2">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => goToFrame(frameNum - 1)}
                    disabled={frameNum <= 0}
                    className="p-1.5 rounded-lg hover:bg-bg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    aria-label="Previous frame"
                  >
                    <ChevronLeft size={18} />
                  </button>

                  <span className="text-sm text-text-primary tabular-nums whitespace-nowrap">
                    Frame{" "}
                    <input
                      type="number"
                      min={1}
                      max={totalFrames}
                      value={frameNum + 1}
                      onChange={(e) => {
                        const v = parseInt(e.target.value, 10);
                        if (!Number.isNaN(v)) goToFrame(v - 1);
                      }}
                      className="w-16 px-1.5 py-0.5 bg-bg border border-border rounded text-sm text-center tabular-nums focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
                      aria-label="Frame number"
                    />{" "}
                    of {totalFrames}
                    {video.fps != null && video.fps > 0 && (
                      <span className="text-text-secondary ml-2">
                        ({formatTimestamp(frameNum / video.fps)})
                      </span>
                    )}
                  </span>

                  <button
                    onClick={() => goToFrame(frameNum + 1)}
                    disabled={frameNum >= totalFrames - 1}
                    className="p-1.5 rounded-lg hover:bg-bg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    aria-label="Next frame"
                  >
                    <ChevronRight size={18} />
                  </button>

                  <input
                    type="range"
                    min={0}
                    max={Math.max(0, totalFrames - 1)}
                    value={frameNum}
                    onChange={(e) => goToFrame(Number(e.target.value))}
                    className="flex-1 h-1.5 accent-accent cursor-pointer"
                    aria-label="Frame scrubber"
                  />
                </div>
                <p className="text-[11px] text-text-secondary/60">
                  ← → to navigate frames, Shift+← → to jump 10 frames
                </p>
                <p className="text-sm font-medium text-text-primary tabular-nums mt-1">
                  {video.fps != null && video.fps > 0
                    ? formatTimestamp(frameNum / video.fps)
                    : "FPS unknown"}
                </p>
              </div>
            )}
          </div>

          {/* QC flags for current frame */}
          {frameFlags.length > 0 && (
            <div className="space-y-2">
              {frameFlags.map((flag) => (
                <div
                  key={flag.id}
                  className="flex items-center justify-between gap-3 px-4 py-3 bg-warning/10 border border-warning/30 rounded-xl"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <AlertTriangle size={16} className="text-warning shrink-0" />
                    <span className="text-sm text-text-primary truncate">
                      {flag.reason || flag.rule_name}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => dismissFlagMutation.mutate(flag.id)}
                      className="px-3 py-1.5 text-[12px] font-medium border border-border rounded-lg hover:bg-bg transition-colors"
                    >
                      Looks Fine
                    </button>
                    <button
                      onClick={() =>
                        navigate(`/review?video_id=${videoId}&type=qc`)
                      }
                      className="px-3 py-1.5 text-[12px] font-medium text-white bg-warning rounded-lg hover:bg-warning/90 transition-colors"
                    >
                      Fix This
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* AI observations for current frame */}
          {aiObservations.length > 0 && (
            <section className="bg-surface border border-border rounded-xl p-4 space-y-3">
              <div className="flex items-center gap-2">
                <BrainCircuit size={16} className="text-accent" />
                <h2 className="text-sm font-semibold text-text-primary">
                  Gemma observations
                </h2>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {aiObservations.slice(0, 6).map((item) => (
                  <div key={item.id} className="bg-bg/50 border border-border rounded-lg px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-text-primary truncate">
                        {item.label ?? item.observation_type}
                      </p>
                      {item.confidence != null && (
                        <span className="text-[11px] text-text-secondary tabular-nums">
                          {Math.round(item.confidence * 100)}%
                        </span>
                      )}
                    </div>
                    <p className="text-[12px] text-text-secondary truncate">
                      {item.pigeon_id ? `${item.pigeon_id} · ` : ""}
                      {item.zone ?? item.observation_type}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Pigeons in this frame */}
          <section>
            <h2 className="text-sm font-semibold text-text-primary mb-3">
              Pigeons in this frame
            </h2>
            {features.length === 0 ? (
              <p className="text-sm text-text-secondary">
                {video.processing_status !== "completed" && video.processing_status !== "completed_no_detections"
                  ? "This video hasn't been processed yet."
                  : "No pigeons detected in this frame."}
              </p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {features.map((f) => {
                  const isMoving = f.velocity_mm_s != null && f.velocity_mm_s > 5;
                  const conf = f.confidence ?? 1;
                  return (
                    <div
                      key={f.id}
                      onClick={() => navigate(`/pigeons/${f.pigeon_id}`)}
                      className="relative bg-surface border-2 border-border rounded-xl px-4 py-3 flex items-center gap-3 cursor-pointer hover:border-accent hover:bg-accent/[0.03] hover:shadow-md transition-all overflow-hidden"
                    >
                      {/* Confidence bar */}
                      <div
                        className="absolute bottom-0 left-0 h-0.5 bg-accent/40 transition-all"
                        style={{ width: `${conf * 100}%` }}
                      />
                      <span className="text-lg">🕊️</span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-text-primary truncate">
                            {f.pigeon_id}
                          </p>
                          {f.heading_deg != null && (
                            <span
                              className="text-text-secondary text-xs leading-none"
                              title={`Heading: ${Math.round(f.heading_deg)}°`}
                            >
                              <span
                                className="inline-block"
                                style={{ transform: `rotate(${f.heading_deg}deg)` }}
                              >
                                ↑
                              </span>
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-[12px] mt-0.5">
                          {f.current_zone && (
                            <span className="text-text-secondary">
                              Zone: {f.current_zone}
                            </span>
                          )}
                          <span className={isMoving ? "text-accent font-medium" : "text-text-secondary"}>
                            {isMoving ? "Moving" : "Stationary"}
                          </span>
                          {f.velocity_mm_s != null && (
                            <span className="text-text-secondary">
                              {f.velocity_mm_s.toFixed(1)} mm/s
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        {/* ========== Right: Metadata panel ========== */}
        <aside className="w-full lg:w-80 shrink-0 space-y-5">
          {/* Video info */}
          <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
            <h2 className="text-base font-semibold text-text-primary truncate">
              {video.video_name}
            </h2>

            <div className="space-y-2.5 text-sm">
              <MetaRow
                icon={<Camera size={14} className="text-text-secondary" />}
                label="Camera"
                value={video.camera_type ?? "—"}
              />
              <MetaRow
                icon={<Film size={14} className="text-text-secondary" />}
                label="Frames"
                value={totalFrames.toLocaleString()}
              />
              {video.fps != null && (
                <MetaRow
                  icon={<Gauge size={14} className="text-text-secondary" />}
                  label="FPS"
                  value={String(video.fps)}
                />
              )}
              <MetaRow
                icon={<Users size={14} className="text-text-secondary" />}
                label="Tracks"
                value={String(video.track_count ?? video.pigeon_count ?? 0)}
              />
              {(video.confirmed_pigeon_count ?? 0) > 0 && (
                <MetaRow
                  label="Confirmed Pigeons"
                  value={String(video.confirmed_pigeon_count)}
                />
              )}
              {video.session_id && (
                <MetaRow label="Session" value={video.session_id} />
              )}
              <MetaRow
                label="Processed"
                value={video.processed_at ? new Date(video.processed_at).toLocaleDateString() : "Not yet"}
              />
              <MetaRow
                label="Model"
                value={video.model_version ?? "—"}
              />
            </div>

            {/* Status badges */}
            <div className="flex items-center gap-2 flex-wrap">
              <StatusBadge status={video.processing_status} size="md" />
              <StatusBadge status={video.review_status} size="md" />
            </div>
          </div>

          {/* Actions */}
          <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
            <h3 className="text-sm font-semibold text-text-primary">Actions</h3>

            <button
              onClick={() =>
                navigate(`/review?video_id=${videoId}&type=identity`)
              }
              className="w-full px-4 py-2 text-sm font-medium border border-border rounded-lg hover:bg-bg transition-colors text-text-primary"
            >
              Confirm Identities
            </button>

            <button
              onClick={() =>
                navigate(`/review?video_id=${videoId}&type=qc`)
              }
              className="w-full px-4 py-2 text-sm font-medium border border-border rounded-lg hover:bg-bg transition-colors text-text-primary"
            >
              Review QC Flags
              {(qcQuery.data?.length ?? 0) > 0 && (
                <span className="ml-1.5 text-warning text-xs font-medium">
                  ({qcQuery.data!.length} pending)
                </span>
              )}
            </button>

            {video.review_status === "reviewed" && (
              <button
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending}
                className="w-full flex items-center justify-center gap-1.5 px-4 py-2 bg-success text-white text-sm font-medium rounded-lg hover:bg-success/90 transition-colors disabled:opacity-50"
              >
                {approveMutation.isPending ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Check size={14} />
                )}
                Approve Video
              </button>
            )}

            {approveMutation.isSuccess && (
              <p className="text-[12px] text-success text-center">
                Video approved successfully.
              </p>
            )}
            {approveMutation.isError && (
              <p className="text-[12px] text-error text-center">
                Failed to approve. Please try again.
              </p>
            )}

            {video.review_status !== "rejected" && (
              <button
                onClick={() => setShowRejectDialog(true)}
                className="w-full px-4 py-2 text-sm font-medium border border-error/30 text-error rounded-lg hover:bg-error/5 transition-colors"
              >
                Reject Video
              </button>
            )}

            <ConfirmDialog
              open={showRejectDialog}
              title="Reject this video?"
              message="It will be excluded from all analytics and exports. You can restore it later."
              confirmLabel="Reject"
              variant="danger"
              loading={rejectMutation.isPending}
              onConfirm={() => rejectMutation.mutate()}
              onCancel={() => setShowRejectDialog(false)}
            />
          </div>

          {/* Edit history */}
          <div className="bg-surface border border-border rounded-xl p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3">
              Edit History
            </h3>
            {editsQuery.isLoading ? (
              <div className="space-y-2">
                {[0, 1].map((i) => (
                  <div key={i} className="h-4 bg-border/40 rounded animate-pulse" />
                ))}
              </div>
            ) : (editsQuery.data ?? []).length === 0 ? (
              <p className="text-sm text-text-secondary">No edits yet.</p>
            ) : (
              <div className="space-y-2.5 max-h-48 overflow-y-auto">
                {(editsQuery.data ?? []).map((edit) => (
                  <div key={edit.edit_id} className="text-[12px]">
                    <p className="text-text-primary">
                      <span className="font-medium capitalize">
                        {edit.edit_type.replace(/_/g, " ")}
                      </span>
                      {edit.editor && (
                        <span className="text-text-secondary"> by {edit.editor}</span>
                      )}
                    </p>
                    {edit.details && (
                      <p className="text-text-secondary truncate">{edit.details}</p>
                    )}
                    {edit.created_at && (
                      <p className="text-text-secondary/60">
                        {new Date(edit.created_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1);
  return `${m}:${s.padStart(4, "0")}`;
}

function MetaRow({
  icon,
  label,
  value,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2">
      {icon}
      <span className="text-text-secondary">{label}:</span>
      <span className="text-text-primary font-medium">{value}</span>
    </div>
  );
}
