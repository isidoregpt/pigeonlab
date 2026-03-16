import { useState, useMemo } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { ChevronDown, Download, Loader2, AlertTriangle } from "lucide-react";
import {
  getInsightsHeatmap,
  getInsightsBehaviors,
  getInsightsPairwise,
  getInsightsDroppings,
  compareSessionsInsight,
  createExport,
} from "../api/insights";
import { getPigeons } from "../api/pigeons";
import { getSessions } from "../api/videos";
import { usePageTitle } from "../hooks/usePageTitle";
import HeatmapCanvas from "../components/ui/HeatmapCanvas";

type Period = "day" | "week" | "month" | "all";
const PERIOD_LABELS: Record<Period, string> = {
  day: "Today",
  week: "This Week",
  month: "This Month",
  all: "All Time",
};

const BEHAVIOR_COLORS = [
  "#0D9488",
  "#F59E0B",
  "#DC2626",
  "#6366F1",
  "#8B5CF6",
  "#EC4899",
  "#78716C",
  "#14B8A6",
];

/* ================================================================ */
function SectionSkeleton({ h = 200 }: { h?: number }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
      <div className="h-4 w-1/4 bg-border/50 rounded animate-pulse" />
      <div
        className="bg-border/20 rounded animate-pulse"
        style={{ height: h }}
      />
    </div>
  );
}

function SectionEmpty({ message }: { message: string }) {
  return (
    <p className="text-sm text-text-secondary py-6 text-center">{message}</p>
  );
}

/* ================================================================
   Social Map SVG
   ================================================================ */
function SocialMap({
  pairs,
}: {
  pairs: {
    pigeon_a: string;
    pigeon_b: string;
    total_duration_seconds: number;
  }[];
}) {
  // Collect unique pigeons
  const pigeonSet = new Set<string>();
  for (const p of pairs) {
    pigeonSet.add(p.pigeon_a);
    pigeonSet.add(p.pigeon_b);
  }
  const pigeonList = Array.from(pigeonSet);
  const n = pigeonList.length;

  if (n === 0) return <SectionEmpty message="No social data available." />;

  const cx = 200;
  const cy = 160;
  const radius = Math.min(120, 40 + n * 15);

  const positions = pigeonList.map((_, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
  });

  const posMap = new Map(pigeonList.map((id, i) => [id, positions[i]]));
  const maxDur = Math.max(...pairs.map((p) => p.total_duration_seconds), 1);

  return (
    <svg viewBox="0 0 400 320" className="w-full max-w-md mx-auto">
      {/* Edges */}
      {pairs.map((p, i) => {
        const a = posMap.get(p.pigeon_a)!;
        const b = posMap.get(p.pigeon_b)!;
        const w = 1 + (p.total_duration_seconds / maxDur) * 6;
        return (
          <line
            key={i}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="#0D9488"
            strokeWidth={w}
            strokeOpacity={0.35}
            strokeLinecap="round"
          />
        );
      })}
      {/* Nodes */}
      {pigeonList.map((id, i) => (
        <g key={id}>
          <circle
            cx={positions[i].x}
            cy={positions[i].y}
            r={22}
            fill="white"
            stroke="#0D9488"
            strokeWidth={2}
          />
          <text
            x={positions[i].x}
            y={positions[i].y + 1}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={10}
            fontWeight={600}
            fill="#1C1917"
          >
            {id.length > 8 ? id.slice(0, 7) + "…" : id}
          </text>
        </g>
      ))}
    </svg>
  );
}

/* ================================================================
   Main Insights Page
   ================================================================ */
export default function Insights() {
  usePageTitle("Insights");
  const [period, setPeriod] = useState<Period>("week");
  const [pigeonFilter, setPigeonFilter] = useState("all");
  const [periodOpen, setPeriodOpen] = useState(false);
  const [behaviorPigeonFilter, setBehaviorPigeonFilter] = useState("all");
  const [sessionA, setSessionA] = useState("");
  const [sessionB, setSessionB] = useState("");

  // Fetch registered pigeons for filter buttons
  const pigeonsQuery = useQuery({
    queryKey: ["pigeons"],
    queryFn: getPigeons,
  });
  const pigeonIds = (pigeonsQuery.data ?? []).map((p) => p.pigeon_id);

  // Section queries
  const heatmapQuery = useQuery({
    queryKey: ["insights-heatmap", pigeonFilter, period],
    queryFn: () => getInsightsHeatmap(pigeonFilter, period),
  });

  const behaviorsQuery = useQuery({
    queryKey: ["insights-behaviors", period],
    queryFn: () => getInsightsBehaviors(period),
  });

  const pairwiseQuery = useQuery({
    queryKey: ["insights-pairwise", period],
    queryFn: () => getInsightsPairwise(period),
  });

  const droppingsQuery = useQuery({
    queryKey: ["insights-droppings", period],
    queryFn: () => getInsightsDroppings(period),
  });

  const sessionsQuery = useQuery({
    queryKey: ["sessions"],
    queryFn: getSessions,
  });

  const compareQuery = useQuery({
    queryKey: ["insights-compare", sessionA, sessionB],
    queryFn: () => compareSessionsInsight(sessionA, sessionB),
    enabled: sessionA.length > 0 && sessionB.length > 0 && sessionA !== sessionB,
  });

  // Export
  const exportMutation = useMutation({
    mutationFn: () =>
      createExport({ format: "csv", include: ["features", "behaviors", "droppings"] }),
    onSuccess: (data) => {
      if (data.download_url) {
        window.open(data.download_url, "_blank");
      }
    },
  });

  // Build behavior chart data
  const behaviorChartData = useMemo(() => {
    const pigeons = behaviorsQuery.data?.pigeons;
    if (!pigeons) return { data: [], behaviorKeys: [] as string[] };

    const filtered =
      behaviorPigeonFilter === "all"
        ? Object.entries(pigeons)
        : Object.entries(pigeons).filter(([id]) => id === behaviorPigeonFilter);

    const behaviorSet = new Set<string>();
    for (const [, behaviors] of filtered) {
      for (const bk of Object.keys(behaviors)) behaviorSet.add(bk);
    }
    const behaviorKeys = Array.from(behaviorSet);

    const data = filtered.map(([pigeonId, behaviors]) => {
      const row: Record<string, string | number> = { pigeon: pigeonId };
      for (const bk of behaviorKeys) {
        row[bk] = behaviors[bk]?.duration_seconds ?? 0;
      }
      return row;
    });

    return { data, behaviorKeys };
  }, [behaviorsQuery.data, behaviorPigeonFilter]);

  return (
    <div className="space-y-8 max-w-5xl">
      {/* Header + Filters */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-bold text-text-primary">📊 Insights</h1>
        <div className="flex items-center gap-3">
          {/* Period selector */}
          <div className="relative">
            <button
              onClick={() => setPeriodOpen((o) => !o)}
              className="flex items-center gap-1.5 px-3 py-2 bg-surface border border-border rounded-lg text-sm font-medium text-text-primary hover:bg-bg transition-colors"
            >
              {PERIOD_LABELS[period]}
              <ChevronDown size={14} />
            </button>
            {periodOpen && (
              <div className="absolute right-0 mt-1 bg-surface border border-border rounded-lg shadow-lg z-20 py-1 min-w-[140px]">
                {(Object.entries(PERIOD_LABELS) as [Period, string][]).map(
                  ([key, label]) => (
                    <button
                      key={key}
                      onClick={() => {
                        setPeriod(key);
                        setPeriodOpen(false);
                      }}
                      className={`block w-full text-left px-4 py-2 text-sm transition-colors ${
                        key === period
                          ? "text-accent font-medium bg-accent/5"
                          : "text-text-primary hover:bg-bg"
                      }`}
                    >
                      {label}
                    </button>
                  ),
                )}
              </div>
            )}
          </div>

          {/* Camera placeholder */}
          <button className="flex items-center gap-1.5 px-3 py-2 bg-surface border border-border rounded-lg text-sm text-text-secondary cursor-default">
            All Cameras
            <ChevronDown size={14} />
          </button>
        </div>
      </div>

      {/* ===== 1. Zone Heatmap ===== */}
      <section className="bg-surface border border-border rounded-xl p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-4">
          Zone Heatmap
        </h2>

        {/* Pigeon filter buttons */}
        <div className="flex flex-wrap gap-2 mb-4">
          <FilterButton
            active={pigeonFilter === "all"}
            onClick={() => setPigeonFilter("all")}
          >
            All
          </FilterButton>
          {pigeonIds.map((id) => (
            <FilterButton
              key={id}
              active={pigeonFilter === id}
              onClick={() => setPigeonFilter(id)}
            >
              {id}
            </FilterButton>
          ))}
        </div>

        {heatmapQuery.isLoading ? (
          <div className="h-48 bg-border/20 rounded animate-pulse" />
        ) : heatmapQuery.isError ? (
          <SectionEmpty message="Failed to load heatmap data." />
        ) : heatmapQuery.data?.grid?.length ? (
          <HeatmapCanvas grid={heatmapQuery.data.grid} />
        ) : (
          <SectionEmpty message="No heatmap data for this period." />
        )}
      </section>

      {/* ===== 2. Behavior Summary ===== */}
      {behaviorsQuery.isLoading ? (
        <SectionSkeleton h={250} />
      ) : (
        <section className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4">
            Behavior Summary
          </h2>

          {/* Pigeon filter buttons */}
          <div className="flex flex-wrap gap-2 mb-4">
            <FilterButton
              active={behaviorPigeonFilter === "all"}
              onClick={() => setBehaviorPigeonFilter("all")}
            >
              All
            </FilterButton>
            {pigeonIds.map((id) => (
              <FilterButton
                key={id}
                active={behaviorPigeonFilter === id}
                onClick={() => setBehaviorPigeonFilter(id)}
              >
                {id}
              </FilterButton>
            ))}
          </div>

          {behaviorChartData.data.length === 0 ? (
            <SectionEmpty message="No behavior data for this period." />
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={behaviorChartData.data}
                  margin={{ left: 0, right: 8, top: 4, bottom: 4 }}
                >
                  <XAxis
                    dataKey="pigeon"
                    tick={{ fontSize: 12, fill: "#78716C" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#78716C" }}
                    axisLine={false}
                    tickLine={false}
                    width={50}
                    label={{
                      value: "seconds",
                      angle: -90,
                      position: "insideLeft",
                      style: { fontSize: 11, fill: "#78716C" },
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: "1px solid #E7E5E4",
                    }}
                    formatter={(value: number, name: string) => [
                      `${Math.round(value)}s`,
                      name.replace(/_/g, " "),
                    ]}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 11 }}
                    formatter={(v: string) => v.replace(/_/g, " ")}
                  />
                  {behaviorChartData.behaviorKeys.map((bk, i) => (
                    <Bar
                      key={bk}
                      dataKey={bk}
                      fill={BEHAVIOR_COLORS[i % BEHAVIOR_COLORS.length]}
                      radius={[3, 3, 0, 0]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      )}

      {/* ===== 3. Social Map ===== */}
      {pairwiseQuery.isLoading ? (
        <SectionSkeleton h={200} />
      ) : (
        <section className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4">
            Social Map
          </h2>
          {pairwiseQuery.isError ? (
            <SectionEmpty message="Failed to load social data." />
          ) : (pairwiseQuery.data?.pairs ?? []).length === 0 ? (
            <SectionEmpty message="No pairwise data for this period." />
          ) : (
            <SocialMap pairs={pairwiseQuery.data!.pairs} />
          )}
        </section>
      )}

      {/* ===== 4. Droppings Map ===== */}
      {droppingsQuery.isLoading ? (
        <SectionSkeleton h={200} />
      ) : (
        <section className="bg-surface border border-border rounded-xl p-5">
          <h2 className="text-sm font-semibold text-text-primary mb-4">
            Droppings Map
          </h2>

          {/* Warning banner */}
          <div className="flex items-center gap-2 px-4 py-2.5 bg-warning/10 border border-warning/30 rounded-lg mb-4">
            <AlertTriangle size={14} className="text-warning shrink-0" />
            <span className="text-[12px] text-text-primary">
              Not yet benchmarked — treat as preliminary
            </span>
          </div>

          {droppingsQuery.isError ? (
            <SectionEmpty message="Failed to load droppings data." />
          ) : droppingsQuery.data?.grid?.length ? (
            <HeatmapCanvas
              grid={droppingsQuery.data.grid}
              accent={[220, 38, 38]}
            />
          ) : (
            <SectionEmpty message="No droppings data for this period." />
          )}
        </section>
      )}

      {/* ===== 5. Compare Sessions ===== */}
      <section className="bg-surface border border-border rounded-xl p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-4">
          Compare Sessions
        </h2>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <select
            value={sessionA}
            onChange={(e) => setSessionA(e.target.value)}
            className="px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
          >
            <option value="">Session A</option>
            {(sessionsQuery.data ?? []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <span className="text-sm text-text-secondary">vs</span>
          <select
            value={sessionB}
            onChange={(e) => setSessionB(e.target.value)}
            className="px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
          >
            <option value="">Session B</option>
            {(sessionsQuery.data ?? []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {!sessionA || !sessionB || sessionA === sessionB ? (
          <SectionEmpty message="Select two sessions to compare." />
        ) : compareQuery.isLoading ? (
          <div className="h-32 bg-border/20 rounded animate-pulse" />
        ) : compareQuery.isError ? (
          <SectionEmpty message="Failed to load comparison data." />
        ) : compareQuery.data ? (
          <div className="space-y-5">
            {/* Zone Occupancy Changes */}
            <div>
              <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
                Zone Occupancy Changes
              </h3>
              {Object.keys(compareQuery.data.zone_occupancy_diff).length === 0 ? (
                <SectionEmpty message="No zone occupancy changes." />
              ) : (
                <div className="space-y-1">
                  {Object.entries(compareQuery.data.zone_occupancy_diff).map(
                    ([pigeon, zones]) => (
                      <div key={pigeon} className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                        <span className="font-medium text-text-primary w-24 shrink-0">
                          {pigeon}
                        </span>
                        {Object.entries(zones).map(([zone, diff]) => (
                          <span key={zone} className="text-text-secondary">
                            {zone}{" "}
                            <span
                              className={
                                diff > 0
                                  ? "text-success"
                                  : diff < 0
                                    ? "text-error"
                                    : "text-text-secondary"
                              }
                            >
                              {diff > 0 ? "↑" : diff < 0 ? "↓" : "–"}
                              {Math.abs(diff).toFixed(1)}%
                            </span>
                          </span>
                        ))}
                      </div>
                    ),
                  )}
                </div>
              )}
            </div>

            {/* Behavior Changes */}
            <div>
              <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
                Behavior Changes
              </h3>
              {Object.keys(compareQuery.data.behavior_diff).length === 0 ? (
                <SectionEmpty message="No behavior changes." />
              ) : (
                <div className="space-y-1">
                  {Object.entries(compareQuery.data.behavior_diff).map(
                    ([pigeon, behaviors]) => (
                      <div key={pigeon} className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                        <span className="font-medium text-text-primary w-24 shrink-0">
                          {pigeon}
                        </span>
                        {Object.entries(behaviors).map(([behavior, diff]) => (
                          <span key={behavior} className="text-text-secondary">
                            {behavior.replace(/_/g, " ")}{" "}
                            <span
                              className={
                                diff.duration_diff > 0
                                  ? "text-success"
                                  : diff.duration_diff < 0
                                    ? "text-error"
                                    : "text-text-secondary"
                              }
                            >
                              {diff.duration_diff > 0 ? "↑" : diff.duration_diff < 0 ? "↓" : "–"}
                              {Math.abs(diff.duration_diff)}s
                            </span>
                            {" "}
                            <span className="text-text-secondary/60">
                              ({diff.count_diff > 0 ? "+" : ""}
                              {diff.count_diff} events)
                            </span>
                          </span>
                        ))}
                      </div>
                    ),
                  )}
                </div>
              )}
            </div>

            {/* Identity Changes */}
            <div>
              <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
                Identity Changes
              </h3>
              <div className="flex flex-wrap gap-4 text-sm">
                <div>
                  <span className="text-text-secondary">Only in A: </span>
                  {compareQuery.data.identity_changes.only_in_a.length === 0 ? (
                    <span className="text-text-secondary/60">none</span>
                  ) : (
                    <span className="text-text-primary font-medium">
                      {compareQuery.data.identity_changes.only_in_a.join(", ")}
                    </span>
                  )}
                </div>
                <div>
                  <span className="text-text-secondary">Only in B: </span>
                  {compareQuery.data.identity_changes.only_in_b.length === 0 ? (
                    <span className="text-text-secondary/60">none</span>
                  ) : (
                    <span className="text-text-primary font-medium">
                      {compareQuery.data.identity_changes.only_in_b.join(", ")}
                    </span>
                  )}
                </div>
                <div>
                  <span className="text-text-secondary">In both: </span>
                  {compareQuery.data.identity_changes.in_both.length === 0 ? (
                    <span className="text-text-secondary/60">none</span>
                  ) : (
                    <span className="text-text-primary font-medium">
                      {compareQuery.data.identity_changes.in_both.join(", ")}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </section>

      {/* ===== 6. Export Buttons ===== */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => alert("PDF export coming soon")}
          className="flex items-center gap-1.5 px-4 py-2 border border-border rounded-lg text-sm font-medium text-text-primary hover:bg-bg transition-colors"
        >
          <Download size={14} />
          Export as PDF
        </button>
        <button
          onClick={() => exportMutation.mutate()}
          disabled={exportMutation.isPending}
          className="flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors disabled:opacity-50"
        >
          {exportMutation.isPending ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Download size={14} />
          )}
          Export Data as CSV
        </button>
        {exportMutation.isError && (
          <span className="text-sm text-error">Export failed. Please try again.</span>
        )}
        {exportMutation.isSuccess && (
          <span className="text-sm text-success">Export started!</span>
        )}
      </div>
    </div>
  );
}

/* ================================================================ */
function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-[12px] font-medium rounded-lg transition-colors ${
        active
          ? "bg-accent text-white"
          : "bg-bg border border-border text-text-secondary hover:text-text-primary hover:border-accent/30"
      }`}
    >
      {children}
    </button>
  );
}
