import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Camera, Film, Loader2, Play, RotateCcw, Trash2, Users } from "lucide-react";
import type { Video } from "../../types";
import StatusBadge from "./StatusBadge";
import { deleteVideo, getVideoStatus, retryFailedChunkGroup, retryVideo } from "../../api/videos";
import { useToast } from "./Toast";

interface VideoCardProps {
  video: Video;
}

function getDisplayStatus(video: Video) {
  if (video.processing_status === "failed") return "failed";
  if (video.processing_status !== "completed") return video.processing_status;
  return video.review_status;
}

export default function VideoCard({ video }: VideoCardProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const isProcessing = video.processing_status === "processing";

  const { data: statusData } = useQuery({
    queryKey: ["video-status", video.video_id],
    queryFn: () => getVideoStatus(video.video_id),
    enabled: isProcessing,
    refetchInterval: 3_000,
  });

  const progress = statusData?.progress ?? 0;
  const processingError = statusData?.error ?? video.processing_error;
  const isBusy = isProcessing || video.processing_status === "queued";
  const groupStatusLabel = statusData?.chunk_group_status_label ?? video.chunk_group_status_label;
  const isChunked = Boolean(video.chunk_group_id && (video.chunk_count ?? 1) > 1);

  const refreshVideos = () => {
    queryClient.invalidateQueries({ queryKey: ["videos"] });
    queryClient.invalidateQueries({ queryKey: ["video-status", video.video_id] });
    queryClient.invalidateQueries({ queryKey: ["stats-today"] });
  };

  const retryMutation = useMutation({
    mutationFn: () => retryVideo(video.video_id),
    onSuccess: () => {
      toast.success("Video queued for processing");
      refreshVideos();
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Could not retry video");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteVideo(video.video_id),
    onSuccess: () => {
      toast.success("Video deleted");
      refreshVideos();
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Could not delete video");
    },
  });

  const retryGroupMutation = useMutation({
    mutationFn: () => retryFailedChunkGroup(video.chunk_group_id ?? ""),
    onSuccess: (result) => {
      toast.success(`Queued ${result.chunks_queued} failed chunk${result.chunks_queued === 1 ? "" : "s"}`);
      refreshVideos();
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Could not retry failed chunks");
    },
  });

  const handleDelete = () => {
    const confirmed = window.confirm(
      `Delete ${video.video_name}? This removes its frames, detections, reviews, and analytics.`,
    );
    if (confirmed) deleteMutation.mutate();
  };

  return (
    <div className="bg-surface border border-border rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-text-primary truncate">
            {video.logical_video_name || video.video_name}
          </h3>
          <p className="text-[12px] text-text-secondary mt-0.5">
            {isChunked
              ? `Chunk ${video.chunk_index ?? "?"} of ${video.chunk_count ?? "?"}`
              : video.session_id || "No session"}
          </p>
        </div>
        <StatusBadge status={getDisplayStatus(video)} entityType="video" />
      </div>

      {isChunked && groupStatusLabel && (
        <div className="mb-3 rounded-lg border border-border bg-bg/60 px-3 py-2 text-[12px] text-text-secondary">
          <span className="font-medium text-text-primary">{groupStatusLabel}</span>
          <span className="ml-2">{video.video_name}</span>
        </div>
      )}

      <div className="flex items-center gap-4 text-[12px] text-text-secondary mb-4">
        {video.camera_type && (
          <span className="flex items-center gap-1">
            <Camera size={13} strokeWidth={1.6} />
            {video.camera_type}
          </span>
        )}
        <span className="flex items-center gap-1">
          <Film size={13} strokeWidth={1.6} />
          {video.total_frames?.toLocaleString() ?? 0} frames
        </span>
        {(video as Video & { pigeon_count?: number }).pigeon_count != null && (
          <span className="flex items-center gap-1">
            <Users size={13} strokeWidth={1.6} />
            {(video as Video & { pigeon_count?: number }).pigeon_count}
          </span>
        )}
      </div>

      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => navigate(`/videos/${video.video_id}`)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white text-[12px] font-medium rounded-lg hover:bg-accent/90 transition-colors"
          >
            <Play size={13} fill="currentColor" />
            Watch
          </button>
          {video.processing_status === "completed" && video.review_status === "raw" && (
            <button
              onClick={() => navigate(`/review?type=identity&video_id=${video.video_id}`)}
              className="px-3 py-1.5 border border-border text-[12px] font-medium text-text-secondary rounded-lg hover:bg-bg transition-colors"
            >
              Review
            </button>
          )}
          {video.processing_status === "queued" && (
            <span className="px-3 py-1.5 text-[12px] text-text-secondary/60">
              Waiting in queue...
            </span>
          )}
          {isProcessing && (
            <span className="px-3 py-1.5 text-[12px] text-text-secondary/60">
              Processing... {Math.round(progress)}%
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {video.processing_status === "failed" && (
            <button
              onClick={() => retryMutation.mutate()}
              disabled={retryMutation.isPending || deleteMutation.isPending}
              className="p-1.5 rounded-lg border border-border text-text-secondary hover:text-accent hover:bg-bg transition-colors disabled:opacity-40"
              title="Retry processing"
              aria-label={`Retry ${video.video_name}`}
            >
              {retryMutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RotateCcw size={14} />
              )}
            </button>
          )}
          {isChunked && (video.chunk_group_failed ?? 0) > 0 && (video.chunk_index ?? 1) === 1 && (
            <button
              onClick={() => retryGroupMutation.mutate()}
              disabled={retryGroupMutation.isPending || deleteMutation.isPending || isBusy}
              className="p-1.5 rounded-lg border border-border text-text-secondary hover:text-accent hover:bg-bg transition-colors disabled:opacity-40"
              title="Retry failed chunks"
              aria-label={`Retry failed chunks for ${video.logical_video_name || video.video_name}`}
            >
              {retryGroupMutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <RotateCcw size={14} />
              )}
            </button>
          )}
          <button
            onClick={handleDelete}
            disabled={deleteMutation.isPending || retryMutation.isPending || isBusy}
            className="p-1.5 rounded-lg border border-border text-text-secondary hover:text-error hover:bg-error/5 transition-colors disabled:opacity-40"
            title={isBusy ? "Stop processing before deleting" : "Delete video"}
            aria-label={`Delete ${video.video_name}`}
          >
            {deleteMutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Trash2 size={14} />
            )}
          </button>
        </div>
      </div>

      {video.processing_status === "failed" && processingError && (
        <details className="mt-3 rounded-lg border border-error/20 bg-error/5 px-3 py-2">
          <summary className="flex cursor-pointer items-center gap-1.5 text-[12px] font-medium text-error">
            <AlertCircle size={13} />
            Show error details
          </summary>
          <p className="mt-2 whitespace-pre-wrap break-words text-[12px] leading-relaxed text-error/90">
            {processingError}
          </p>
        </details>
      )}

      {/* Progress bar at bottom of card */}
      {isProcessing && (
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-accent/10">
          <div
            className="h-full bg-accent transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}
