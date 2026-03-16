import { useNavigate } from "react-router-dom";
import { MapPin, Video } from "lucide-react";
import type { Pigeon } from "../../types";

interface PigeonCardProps {
  pigeon: Pigeon;
  topZone?: string | null;
  sessionCount?: number;
}

export default function PigeonCard({ pigeon, topZone, sessionCount }: PigeonCardProps) {
  const navigate = useNavigate();

  return (
    <div
      onClick={() => navigate(`/pigeons/${pigeon.pigeon_id}`)}
      className="bg-surface border border-border rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow cursor-pointer group"
    >
      <div className="flex items-start gap-4">
        {/* Pigeon avatar placeholder */}
        <div className="w-12 h-12 rounded-lg bg-bg border border-border flex items-center justify-center text-2xl shrink-0 group-hover:border-accent/30 transition-colors">
          🕊️
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-text-primary truncate group-hover:text-accent transition-colors">
            {pigeon.pigeon_id}
          </h3>
          {pigeon.physical_markers && (
            <p className="text-[12px] text-text-secondary mt-0.5 truncate">
              {pigeon.physical_markers}
            </p>
          )}

          <div className="flex items-center gap-4 mt-3 text-[12px] text-text-secondary">
            {sessionCount != null && (
              <span className="flex items-center gap-1">
                <Video size={13} strokeWidth={1.6} />
                {sessionCount} session{sessionCount !== 1 ? "s" : ""}
              </span>
            )}
            {topZone && (
              <span className="flex items-center gap-1">
                <MapPin size={13} strokeWidth={1.6} />
                {topZone}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
