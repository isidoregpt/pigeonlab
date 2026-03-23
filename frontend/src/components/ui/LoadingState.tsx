export default function LoadingState({
  variant = "grid",
}: {
  variant?: "grid" | "detail" | "list" | "profile";
}) {
  if (variant === "detail") return <DetailSkeleton />;
  if (variant === "list") return <ListSkeleton />;
  if (variant === "profile") return <ProfileSkeleton />;
  return <GridSkeleton />;
}

/* ---------- Grid (default) ---------- */
function GridSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="bg-surface border border-border rounded-xl p-5 space-y-3"
        >
          <div className="flex items-start justify-between">
            <div className="space-y-2 flex-1">
              <div className="h-4 w-3/4 bg-border/60 rounded animate-pulse" />
              <div className="h-3 w-1/2 bg-border/40 rounded animate-pulse" />
            </div>
            <div className="h-5 w-16 bg-border/40 rounded-full animate-pulse" />
          </div>
          <div className="flex gap-3">
            <div className="h-3 w-20 bg-border/30 rounded animate-pulse" />
            <div className="h-3 w-20 bg-border/30 rounded animate-pulse" />
          </div>
          <div className="flex gap-2 pt-1">
            <div className="h-7 w-20 bg-border/40 rounded-lg animate-pulse" />
            <div className="h-7 w-16 bg-border/30 rounded-lg animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---------- Detail (video detail page) ---------- */
function DetailSkeleton() {
  return (
    <div className="flex gap-6">
      {/* Large video area */}
      <div className="flex-1 space-y-4">
        <div className="h-6 w-1/3 bg-border/50 rounded animate-pulse" />
        <div className="aspect-video bg-border/30 rounded-xl animate-pulse" />
        <div className="flex gap-3">
          <div className="h-8 w-24 bg-border/40 rounded-lg animate-pulse" />
          <div className="h-8 w-24 bg-border/30 rounded-lg animate-pulse" />
        </div>
      </div>
      {/* Sidebar */}
      <div className="w-72 shrink-0 space-y-4">
        <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
          <div className="h-4 w-1/2 bg-border/50 rounded animate-pulse" />
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="flex justify-between">
              <div className="h-3 w-20 bg-border/40 rounded animate-pulse" />
              <div className="h-3 w-16 bg-border/30 rounded animate-pulse" />
            </div>
          ))}
        </div>
        <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
          <div className="h-4 w-1/3 bg-border/50 rounded animate-pulse" />
          <div className="h-20 bg-border/30 rounded animate-pulse" />
        </div>
      </div>
    </div>
  );
}

/* ---------- List (table / list views) ---------- */
function ListSkeleton() {
  return (
    <div className="space-y-3">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className="flex items-center gap-4 bg-surface border border-border rounded-xl px-5 py-4"
        >
          <div className="h-4 w-4 bg-border/40 rounded animate-pulse" />
          <div className="h-4 w-1/4 bg-border/50 rounded animate-pulse" />
          <div className="h-3 w-1/5 bg-border/30 rounded animate-pulse" />
          <div className="flex-1" />
          <div className="h-3 w-16 bg-border/40 rounded animate-pulse" />
          <div className="h-6 w-20 bg-border/30 rounded-lg animate-pulse" />
        </div>
      ))}
    </div>
  );
}

/* ---------- Profile (pigeon profile page) ---------- */
function ProfileSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="flex items-center gap-4">
          <div className="h-14 w-14 bg-border/40 rounded-full animate-pulse" />
          <div className="space-y-2 flex-1">
            <div className="h-5 w-1/4 bg-border/50 rounded animate-pulse" />
            <div className="h-3 w-1/3 bg-border/30 rounded animate-pulse" />
          </div>
          <div className="h-8 w-20 bg-border/40 rounded-lg animate-pulse" />
        </div>
      </div>
      {/* Chart areas */}
      {[0, 1].map((i) => (
        <div
          key={i}
          className="bg-surface border border-border rounded-xl p-5 space-y-3"
        >
          <div className="h-4 w-1/4 bg-border/50 rounded animate-pulse" />
          <div className="h-48 bg-border/30 rounded-lg animate-pulse" />
        </div>
      ))}
    </div>
  );
}
