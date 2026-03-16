import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { ArrowLeft, Pencil, Check, X, Loader2 } from "lucide-react";
import {
  getPigeon,
  getPigeonBehaviors,
  getPigeonIdentityStatus,
  updatePigeon,
} from "../api/pigeons";
import { usePageTitle } from "../hooks/usePageTitle";

const ZONE_COLORS = [
  "#0D9488", // accent
  "#14B8A6",
  "#2DD4BF",
  "#5EEAD4",
  "#99F6E4",
  "#CCFBF1",
];

const BEHAVIOR_COLORS = [
  "#0D9488",
  "#F59E0B",
  "#DC2626",
  "#6366F1",
  "#8B5CF6",
  "#EC4899",
  "#78716C",
];

function SectionSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
      <div className="h-4 w-1/3 bg-border/50 rounded animate-pulse" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-6 bg-border/30 rounded animate-pulse" />
      ))}
    </div>
  );
}

export default function PigeonProfile() {
  usePageTitle("Pigeon Profile");
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const pigeonId = id ?? "";

  const [editing, setEditing] = useState(false);
  const [editMarkers, setEditMarkers] = useState("");
  const [editNotes, setEditNotes] = useState("");

  // Fetch all three in parallel
  const profileQuery = useQuery({
    queryKey: ["pigeon", pigeonId],
    queryFn: () => getPigeon(pigeonId),
    enabled: pigeonId.length > 0,
  });

  const behaviorsQuery = useQuery({
    queryKey: ["pigeon-behaviors", pigeonId],
    queryFn: () => getPigeonBehaviors(pigeonId, "week"),
    enabled: pigeonId.length > 0,
  });

  const identityQuery = useQuery({
    queryKey: ["pigeon-identity", pigeonId],
    queryFn: () => getPigeonIdentityStatus(pigeonId),
    enabled: pigeonId.length > 0,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      updatePigeon(pigeonId, {
        physical_markers: editMarkers.trim() || undefined,
        notes: editNotes.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pigeon", pigeonId] });
      setEditing(false);
    },
  });

  const pigeon = profileQuery.data;
  const behaviors = behaviorsQuery.data?.behaviors;
  const identity = identityQuery.data;

  // Zone data from behavior_summary on the profile
  const zoneData = pigeon?.behavior_summary
    ? Object.entries(pigeon.behavior_summary)
        .map(([zone, pct]) => ({ zone, pct: Number(pct) }))
        .sort((a, b) => b.pct - a.pct)
    : [];

  // Behavior data
  const behaviorData = behaviors
    ? Object.entries(behaviors)
        .map(([name, stats]) => ({
          name: name.replace(/_/g, " "),
          seconds: stats.duration_seconds,
          events: stats.event_count,
        }))
        .sort((a, b) => b.seconds - a.seconds)
    : [];

  function startEdit() {
    setEditMarkers(pigeon?.physical_markers ?? "");
    setEditNotes(pigeon?.notes ?? "");
    setEditing(true);
  }

  // Top-level error for profile
  if (profileQuery.isError) {
    return (
      <div className="text-center py-16">
        <p className="text-text-secondary text-sm">
          Could not load this pigeon. It may not exist.
        </p>
        <button
          onClick={() => navigate("/pigeons")}
          className="mt-4 text-sm text-accent hover:text-accent/80 font-medium transition-colors"
        >
          ← Back to Pigeons
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Back */}
      <button
        onClick={() => navigate("/pigeons")}
        className="flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary transition-colors"
      >
        <ArrowLeft size={14} />
        Back to Pigeons
      </button>

      {/* ===== Header ===== */}
      {profileQuery.isLoading ? (
        <SectionSkeleton rows={2} />
      ) : pigeon ? (
        <div className="bg-surface border border-border rounded-xl p-5">
          {editing ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span className="text-3xl">🕊️</span>
                <h1 className="text-xl font-bold text-text-primary">
                  {pigeon.pigeon_id}
                </h1>
              </div>
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">
                  Physical Markers
                </label>
                <input
                  type="text"
                  value={editMarkers}
                  onChange={(e) => setEditMarkers(e.target.value)}
                  className="w-full max-w-md px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">
                  Notes
                </label>
                <textarea
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  rows={2}
                  className="w-full max-w-md px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors resize-none"
                />
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => saveMutation.mutate()}
                  disabled={saveMutation.isPending}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50"
                >
                  {saveMutation.isPending ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Check size={14} />
                  )}
                  Save
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="flex items-center gap-1.5 px-3 py-1.5 border border-border text-sm rounded-lg hover:bg-bg transition-colors"
                >
                  <X size={14} />
                  Cancel
                </button>
              </div>
              {saveMutation.isError && (
                <p className="text-sm text-error">Failed to save. Please try again.</p>
              )}
            </div>
          ) : (
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-4">
                <span className="text-3xl">🕊️</span>
                <div>
                  <h1 className="text-xl font-bold text-text-primary">
                    {pigeon.pigeon_id}
                  </h1>
                  {pigeon.physical_markers && (
                    <p className="text-sm text-text-secondary mt-0.5">
                      {pigeon.physical_markers}
                    </p>
                  )}
                </div>
              </div>
              <button
                onClick={startEdit}
                className="flex items-center gap-1.5 px-3 py-1.5 border border-border text-sm font-medium rounded-lg hover:bg-bg transition-colors text-text-primary shrink-0"
              >
                <Pencil size={14} />
                Edit Profile
              </button>
            </div>
          )}
        </div>
      ) : null}

      {/* ===== Where [Name] Spends Time ===== */}
      {profileQuery.isLoading ? (
        <SectionSkeleton rows={4} />
      ) : zoneData.length > 0 ? (
        <div className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4">
            Where {pigeon?.pigeon_id} Spends Time
          </h2>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={zoneData}
                layout="vertical"
                margin={{ left: 0, right: 16, top: 0, bottom: 0 }}
              >
                <XAxis type="number" domain={[0, "auto"]} hide />
                <YAxis
                  type="category"
                  dataKey="zone"
                  width={80}
                  tick={{ fontSize: 12, fill: "#78716C" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  formatter={(value: number) => [`${value}%`, "Time"]}
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 8,
                    border: "1px solid #E7E5E4",
                  }}
                />
                <Bar dataKey="pct" radius={[0, 4, 4, 0]} barSize={18}>
                  {zoneData.map((_, i) => (
                    <Cell
                      key={i}
                      fill={ZONE_COLORS[i % ZONE_COLORS.length]}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Identity confidence inline */}
          {identity && (
            <div className="mt-4 pt-4 border-t border-border flex items-center justify-between">
              <span className="text-sm text-text-secondary">
                Confirmed in{" "}
                <span className="font-medium text-text-primary">
                  {identity.confirmed_sessions}
                </span>{" "}
                of{" "}
                <span className="font-medium text-text-primary">
                  {identity.total_sessions}
                </span>{" "}
                sessions
              </span>
              {identity.unconfirmed_sessions > 0 && (
                <Link
                  to={`/review?pigeon_id=${pigeonId}&type=identity`}
                  className="text-sm text-accent hover:text-accent/80 font-medium transition-colors"
                >
                  Review Unconfirmed →
                </Link>
              )}
            </div>
          )}
        </div>
      ) : !profileQuery.isLoading ? (
        <div className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-2">
            Where {pigeon?.pigeon_id} Spends Time
          </h2>
          <p className="text-sm text-text-secondary">
            No zone data available yet.
          </p>
        </div>
      ) : null}

      {/* ===== What [Name] Does ===== */}
      {behaviorsQuery.isLoading ? (
        <SectionSkeleton rows={4} />
      ) : behaviorData.length > 0 ? (
        <div className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4">
            What {pigeon?.pigeon_id} Does
          </h2>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={behaviorData}
                layout="vertical"
                margin={{ left: 0, right: 16, top: 0, bottom: 0 }}
              >
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={100}
                  tick={{ fontSize: 12, fill: "#78716C" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  formatter={(value: number) => [
                    `${Math.round(value)}s (${Math.round(value / 60)}m)`,
                    "Duration",
                  ]}
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 8,
                    border: "1px solid #E7E5E4",
                  }}
                />
                <Bar dataKey="seconds" radius={[0, 4, 4, 0]} barSize={18}>
                  {behaviorData.map((_, i) => (
                    <Cell
                      key={i}
                      fill={BEHAVIOR_COLORS[i % BEHAVIOR_COLORS.length]}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : !behaviorsQuery.isLoading ? (
        <div className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-2">
            What {pigeon?.pigeon_id} Does
          </h2>
          <p className="text-sm text-text-secondary">
            No behavior data available yet.
          </p>
        </div>
      ) : null}

      {/* ===== Identity Confidence ===== */}
      {identityQuery.isLoading ? (
        <SectionSkeleton rows={2} />
      ) : identity ? (
        <div className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-3">
            Identity Confidence
          </h2>
          <div className="flex items-center gap-6">
            <IdentityStat
              value={identity.confirmed_sessions}
              label="Confirmed"
              color="text-success"
            />
            <IdentityStat
              value={identity.unconfirmed_sessions}
              label="Unconfirmed"
              color="text-warning"
            />
            <IdentityStat
              value={identity.total_sessions}
              label="Total"
              color="text-text-primary"
            />
          </div>
          {identity.total_sessions > 0 && (
            <div className="mt-3">
              <div className="flex h-2 rounded-full overflow-hidden bg-bg">
                <div
                  className="bg-success transition-all"
                  style={{
                    width: `${(identity.confirmed_sessions / identity.total_sessions) * 100}%`,
                  }}
                />
                <div
                  className="bg-warning transition-all"
                  style={{
                    width: `${(identity.unconfirmed_sessions / identity.total_sessions) * 100}%`,
                  }}
                />
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function IdentityStat({
  value,
  label,
  color,
}: {
  value: number;
  label: string;
  color: string;
}) {
  return (
    <div className="text-center">
      <p className={`text-2xl font-bold tabular-nums ${color}`}>{value}</p>
      <p className="text-[12px] text-text-secondary">{label}</p>
    </div>
  );
}
