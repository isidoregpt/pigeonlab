import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search, Loader2 } from "lucide-react";
import { usePageTitle } from "../hooks/usePageTitle";
import { getVideos } from "../api/videos";
import type { Video } from "../types";
import VideoCard from "../components/ui/VideoCard";
import LoadingState from "../components/ui/LoadingState";
import EmptyState from "../components/ui/EmptyState";
import AddVideosModal from "../components/ui/AddVideosModal";

const PER_PAGE = 20;

function groupByDate(videos: Video[]): [string, Video[]][] {
  const groups = new Map<string, Video[]>();
  const now = new Date();
  const todayStr = now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayStr = yesterday.toDateString();

  for (const v of videos) {
    const d = v.processed_at ? new Date(v.processed_at) : null;
    let label: string;
    if (!d) {
      label = "Unprocessed";
    } else if (d.toDateString() === todayStr) {
      label = "Today";
    } else if (d.toDateString() === yesterdayStr) {
      label = "Yesterday";
    } else {
      label = d.toLocaleDateString("en-US", {
        weekday: "short",
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    }
    const arr = groups.get(label) ?? [];
    arr.push(v);
    groups.set(label, arr);
  }
  return Array.from(groups.entries());
}

export default function Videos() {
  usePageTitle("Videos");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["videos", page],
    queryFn: () => getVideos("date", page, PER_PAGE),
    refetchInterval: 10_000,
  });

  const videos = data?.videos ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PER_PAGE);

  const filtered = useMemo(() => {
    if (!search.trim()) return videos;
    const q = search.toLowerCase();
    return videos.filter(
      (v) =>
        v.video_name.toLowerCase().includes(q) ||
        (v.session_id?.toLowerCase().includes(q) ?? false),
    );
  }, [videos, search]);

  const groups = useMemo(() => groupByDate(filtered), [filtered]);

  if (isLoading) return <LoadingState />;

  if (isError) {
    return (
      <div className="text-center py-16 space-y-3">
        <p className="text-sm text-text-secondary">Something went wrong loading videos.</p>
        <button
          onClick={() => refetch()}
          className="text-sm font-medium text-accent hover:text-accent/80 transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">📹 Videos</h1>
        <button
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors"
        >
          <Plus size={16} strokeWidth={2} />
          Add Videos
        </button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary/60"
        />
        <input
          type="text"
          placeholder="Search videos..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 bg-surface border border-border rounded-lg text-sm text-text-primary placeholder:text-text-secondary/50 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition-colors"
        />
      </div>

      {/* Videos */}
      {filtered.length === 0 && total === 0 ? (
        <EmptyState
          icon="📹"
          title="No videos yet"
          description="No videos processed yet — add some videos to get started."
          actionLabel="+ Add Videos"
          onAction={() => setModalOpen(true)}
        />
      ) : filtered.length === 0 ? (
        <p className="text-sm text-text-secondary text-center py-8">
          No videos match &ldquo;{search}&rdquo;
        </p>
      ) : (
        <div className="space-y-8">
          {groups.map(([label, vids]) => (
            <section key={label}>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-3">
                {label}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {vids.map((v) => (
                  <div key={v.video_id} className="relative">
                    <VideoCard video={v} />
                    {v.processing_status === "processing" && (
                      <div className="absolute top-3 right-3">
                        <Loader2
                          size={16}
                          className="animate-spin text-accent"
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 text-sm border border-border rounded-lg hover:bg-bg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm text-text-secondary tabular-nums">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="px-3 py-1.5 text-sm border border-border rounded-lg hover:bg-bg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}

      {/* Modal */}
      {modalOpen && (
        <AddVideosModal
          onClose={() => setModalOpen(false)}
          onSuccess={() => {
            setModalOpen(false);
            refetch();
          }}
        />
      )}
    </div>
  );
}
