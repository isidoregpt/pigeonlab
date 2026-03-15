import type { Video } from "../../types";
import StatusBadge from "./StatusBadge";

interface VideoCardProps {
  video: Video;
}

export default function VideoCard({ video }: VideoCardProps) {
  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-text-primary">{video.video_name}</h3>
        <StatusBadge status={video.processing_status} />
      </div>
      <p className="text-sm text-text-secondary mt-1">{video.total_frames} frames</p>
    </div>
  );
}
