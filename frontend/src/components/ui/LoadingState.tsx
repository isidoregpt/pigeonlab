export default function LoadingState() {
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
