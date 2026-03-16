import { useNavigate } from "react-router-dom";
import { Play, Camera, Film, Users } from "lucide-react";
import type { Video } from "../../types";
import StatusBadge from "./StatusBadge";

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

  return (
    <div className="bg-surface border border-border rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
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
            onClick={() => navigate(`/review?video=${video.video_id}`)}
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
      </div>
    </div>
  );
}
