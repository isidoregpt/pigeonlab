import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
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
} from "lucide-react";
import {
  getVideo,
  getFrameUrl,
  getVideoFeatures,
  getVideoTrackEdits,
  updateVideoReview,
} from "../api/videos";
import { getQCFlags, reviewQCFlag } from "../api/review";
import StatusBadge from "../components/ui/StatusBadge";
import LoadingState from "../components/ui/LoadingState";

export default function VideoDetail() {
  usePageTitle("Video Detail");
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const videoId = Number(id);

  const [frameNum, setFrameNum] = useState(0);
  const [frameLoading, setFrameLoading] = useState(true);

  // --- Queries ---

  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => getVideo(videoId),
    enabled: !Number.isNaN(videoId),
  });

  const totalFrames = videoQuery.data?.total_frames ?? 0;

  const featuresQuery = useQuery({
    queryKey: ["video-features", videoId, frameNum],
    queryFn: () => getVideoFeatures(videoId, frameNum),
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

  const dismissFlagMutation = useMutation({
    mutationFn: (flagId: number) =>
      reviewQCFlag({
        flag_id: flagId,
        action: "resolve",
        resolved_action: "dismissed",
        reviewer: "lab_user",
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["video-qc", videoId] }),
  });

  // --- Frame navigation ---

  const goToFrame = useCallback(
    (n: number) => {
      const clamped = Math.max(0, Math.min(totalFrames - 1, n));
      if (clamped !== frameNum) {
        setFrameLoading(true);
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
        goToFrame(frameNum - 1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        goToFrame(frameNum + 1);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [frameNum, goToFrame]);

  // --- Render ---

  if (videoQuery.isLoading) return <LoadingState />;

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
            <div className="relative bg-black aspect-video flex items-center justify-center">
              {frameLoading && (
                <div className="absolute inset-0 flex items-center justify-center z-10">
                  <Loader2 size={28} className="animate-spin text-white/60" />
                </div>
              )}
              {totalFrames > 0 ? (
                <img
                  src={getFrameUrl(videoId, frameNum, true)}
                  alt={`Frame ${frameNum}`}
                  className={`max-w-full max-h-full object-contain transition-opacity ${frameLoading ? "opacity-30" : "opacity-100"}`}
                  onLoad={() => setFrameLoading(false)}
                  onError={() => setFrameLoading(false)}
                />
              ) : (
                <span className="text-white/40 text-sm">No frames available</span>
              )}
            </div>

            {/* Controls */}
            {totalFrames > 0 && (
              <div className="px-4 py-3 flex items-center gap-3">
                <button
                  onClick={() => goToFrame(frameNum - 1)}
                  disabled={frameNum <= 0}
                  className="p-1.5 rounded-lg hover:bg-bg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                  aria-label="Previous frame"
                >
                  <ChevronLeft size={18} />
                </button>

                <span className="text-sm text-text-primary tabular-nums whitespace-nowrap">
                  Frame {frameNum + 1} of {totalFrames}
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

          {/* Pigeons in this frame */}
          <section>
            <h2 className="text-sm font-semibold text-text-primary mb-3">
              Pigeons in this frame
            </h2>
            {features.length === 0 ? (
              <p className="text-sm text-text-secondary">
                No pigeon data for this frame.
              </p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {features.map((f) => (
                  <div
                    key={f.id}
                    className="bg-surface border border-border rounded-xl px-4 py-3 flex items-center gap-3"
                  >
                    <span className="text-lg">🕊️</span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-text-primary truncate">
                        {f.pigeon_id}
                      </p>
                      <div className="flex items-center gap-3 text-[12px] text-text-secondary mt-0.5">
                        {f.current_zone && <span>Zone: {f.current_zone}</span>}
                        <span>
                          {f.velocity_mm_s != null && f.velocity_mm_s > 5
                            ? "Moving"
                            : "Stationary"}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
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
                label="Pigeons"
                value={String(video.pigeon_count)}
              />
              {video.session_id && (
                <MetaRow label="Session" value={video.session_id} />
              )}
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
