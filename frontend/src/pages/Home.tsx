import { useQuery } from "@tanstack/react-query";
import { useNavigate, Link } from "react-router-dom";
import { usePageTitle } from "../hooks/usePageTitle";
import { getStatsToday } from "../api/stats";
import { getAttentionItems } from "../api/stats";
import { getStatsSummary } from "../api/stats";
import { getActivity } from "../api/stats";
import LoadingState from "../components/ui/LoadingState";
import SectionError from "../components/ui/SectionError";
import { formatRelativeTime } from "../utils/formatTime";

const severityDots: Record<string, string> = {
  critical: "bg-error",
  high: "bg-error",
  medium: "bg-warning",
  low: "bg-gray-400",
};

export default function Home() {
  usePageTitle("Home");
  const navigate = useNavigate();

  const statsQuery = useQuery({ queryKey: ["stats-today"], queryFn: getStatsToday });
  const attentionQuery = useQuery({ queryKey: ["attention-items"], queryFn: () => getAttentionItems(5) });
  const summaryQuery = useQuery({ queryKey: ["stats-summary"], queryFn: () => getStatsSummary("week") });
  const activityQuery = useQuery({ queryKey: ["activity"], queryFn: () => getActivity(10) });

  const isLoading = statsQuery.isLoading || attentionQuery.isLoading;

  if (isLoading) return <LoadingState />;

  const stats = statsQuery.data;
  const attention = attentionQuery.data ?? [];
  const summary = summaryQuery.data;
  const activity = activityQuery.data ?? [];

  const isEmpty = !statsQuery.isError
    && (stats?.videos_processed ?? 0) === 0
    && (stats?.pigeons_tracked ?? 0) === 0
    && attention.length === 0
    && activity.length === 0;

  if (isEmpty) {
    return (
      <div className="max-w-2xl mx-auto py-12 space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold text-text-primary">
            Welcome to PigeonLab
          </h1>
          <p className="text-sm text-text-secondary leading-relaxed max-w-md mx-auto">
            Get started by adding your pigeon videos. PigeonLab will detect,
            track, and analyze your pigeons automatically.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            {
              step: 1,
              title: "Register your pigeons",
              description: "Register your pigeons so PigeonLab can identify them",
              to: "/pigeons",
            },
            {
              step: 2,
              title: "Add videos for processing",
              description: "Add videos for processing — PigeonLab will find and track your pigeons",
              to: "/videos",
            },
            {
              step: 3,
              title: "Review and analyze results",
              description: "Review results, view insights, and export data",
              to: "/insights",
            },
          ].map(({ step, title, description, to }) => (
            <Link
              key={step}
              to={to}
              className="bg-surface border border-border rounded-xl p-5 space-y-3 hover:border-accent/50 hover:shadow-sm transition-all group"
            >
              <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-accent/10 text-accent text-sm font-bold">
                {step}
              </span>
              <p className="text-sm font-medium text-text-primary group-hover:text-accent transition-colors">
                {title}
              </p>
              <p className="text-xs text-text-secondary leading-relaxed">
                {description}
              </p>
            </Link>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-8">
      {/* Greeting */}
      <h1 className="text-xl font-bold text-text-primary">
        Good morning, Lab 🏠
      </h1>

      {/* Stat cards */}
      {statsQuery.isError ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <StatCard value="—" label="videos processed today" />
          <StatCard value="—" label="pigeons tracked" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <StatCard
            value={stats?.videos_processed ?? 0}
            label="videos processed today"
          />
          <StatCard
            value={stats?.pigeons_tracked ?? 0}
            label="pigeons tracked"
          />
        </div>
      )}

      {/* Needs attention */}
      {attentionQuery.isError ? (
        <SectionError message="Could not load attention items." onRetry={() => attentionQuery.refetch()} />
      ) : attention.length > 0 ? (
        <section>
          <h2 className="text-sm font-semibold text-text-primary mb-3">
            ⚡ Needs Your Attention
          </h2>
          <div className="bg-surface border border-border rounded-xl divide-y divide-border">
            {attention.map((item, i) => (
              <div key={i} className="flex items-center justify-between px-5 py-3.5">
                <div className="flex items-center gap-3 min-w-0">
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${severityDots[item.severity] ?? "bg-gray-400"}`}
                  />
                  <span className="text-sm text-text-primary truncate">
                    {item.description}
                  </span>
                </div>
                <button
                  onClick={() => navigate(item.link)}
                  className="text-xs font-medium text-accent hover:text-accent/80 whitespace-nowrap ml-4 transition-colors"
                >
                  {item.type === "identity" ? "Review Now →" : "Check →"}
                </button>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {/* Quick Stats */}
      {summaryQuery.isError ? (
        <SectionError message="Could not load stats." onRetry={() => summaryQuery.refetch()} />
      ) : summary && Object.keys(summary.pigeons).length > 0 ? (
        <section>
          <h2 className="text-sm font-semibold text-text-primary mb-3">
            📊 Quick Stats This Week
          </h2>
          <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
            {Object.entries(summary.pigeons).map(([pigeonId, zones]) => {
              const topZone = Object.entries(zones).sort(([, a], [, b]) => b - a)[0];
              return (
                <div key={pigeonId}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm font-medium text-text-primary">
                      {pigeonId}
                    </span>
                    {topZone && (
                      <span className="text-[12px] text-text-secondary">
                        Top: {topZone[0]} ({topZone[1]}%)
                      </span>
                    )}
                  </div>
                  <div className="flex gap-0.5 h-2.5 rounded-full overflow-hidden bg-bg">
                    {Object.entries(zones)
                      .sort(([, a], [, b]) => b - a)
                      .map(([zone, pct], i) => (
                        <div
                          key={zone}
                          className={`h-full transition-all ${zoneColor(i)}`}
                          style={{ width: `${pct}%` }}
                          title={`${zone}: ${pct}%`}
                        />
                      ))}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {/* Recent Activity */}
      {activity.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-text-primary mb-3">
            🕐 Recent Activity
          </h2>
          <div className="bg-surface border border-border rounded-xl divide-y divide-border">
            {activity.map((item, i) => (
              <div key={i} className="flex items-center gap-3 px-5 py-3">
                <span className="text-sm">✅</span>
                <div className="min-w-0 flex-1">
                  <span className="text-sm text-text-primary truncate block">
                    {item.description}
                  </span>
                </div>
                {item.timestamp && (
                  <span className="text-[11px] text-text-secondary whitespace-nowrap shrink-0">
                    {formatRelativeTime(item.timestamp)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function StatCard({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 flex items-center gap-4 border-l-[3px] border-l-accent">
      <span className="text-3xl font-bold text-accent tabular-nums">
        {value}
      </span>
      <span className="text-sm text-text-secondary">{label}</span>
    </div>
  );
}

const ZONE_COLORS = [
  "bg-accent",
  "bg-accent/60",
  "bg-accent/30",
  "bg-warning/60",
  "bg-gray-300",
];

function zoneColor(index: number): string {
  return ZONE_COLORS[index] ?? "bg-gray-200";
}

