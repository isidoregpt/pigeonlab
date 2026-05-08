import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Play, Camera, Film, Users } from "lucide-react";
import type { Video } from "../../types";
import StatusBadge from "./StatusBadge";
import { getVideoStatus } from "../../api/videos";

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
  const isProcessing = video.processing_status === "processing";

  const { data: statusData } = useQuery({
    queryKey: ["video-status", video.video_id],
    queryFn: () => getVideoStatus(video.video_id),
    enabled: isProcessing,
    refetchInterval: 3_000,
  });

  const progress = statusData?.progress ?? 0;
  const processingError = statusData?.error ?? video.processing_error;

  return (
    <div className="bg-surface border border-border rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-text-primary truncate">
            {video.video_name}
          </h3>
          <p className="text-[12px] text-text-secondary mt-0.5">
            {video.session_id || "No session"}
          </p>
        </div>
        <StatusBadge status={getDisplayStatus(video)} entityType="video" />
      </div>

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

      <div className="flex items-center gap-2">
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
        {video.processing_status === "failed" && processingError && (
          <span className="px-3 py-1.5 text-[12px] text-error truncate" title={processingError}>
            {processingError}
          </span>
        )}
      </div>

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
