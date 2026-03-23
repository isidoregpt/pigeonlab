import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { usePageTitle } from "../hooks/usePageTitle";
import { getZones, getSystemInfo } from "../api/settings";

export default function LabSetup() {
  usePageTitle("Settings");

  const zonesQuery = useQuery({
    queryKey: ["settings-zones"],
    queryFn: getZones,
  });

  const infoQuery = useQuery({
    queryKey: ["settings-info"],
    queryFn: getSystemInfo,
  });

  const zones = zonesQuery.data?.zones ?? [];
  const info = infoQuery.data;

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
        <h2 className="text-sm font-semibold text-text-primary">
          System Info
        </h2>

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
          <p className="text-sm text-text-secondary">
            Could not load system information.
          </p>
        )}
      </section>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-bg/50 border border-border rounded-lg px-3 py-2.5">
      <p className="text-lg font-semibold text-text-primary tabular-nums">
        {value.toLocaleString()}
      </p>
      <p className="text-[11px] text-text-secondary">{label}</p>
    </div>
  );
}
