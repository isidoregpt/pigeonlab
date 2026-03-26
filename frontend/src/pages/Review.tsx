import { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Check, AlertTriangle, Loader2, SkipForward } from "lucide-react";
import {
  getNextVideoForIdentityReview,
  getUnconfirmedIdentities,
  reviewIdentity,
  batchConfirmIdentities,
  getQCFlags,
  reviewQCFlag,
  batchResolveQCFlags,
  getDroppingsForReview,
  reviewDropping,
  getBehaviorsForReview,
  reviewBehavior,
} from "../api/review";
import { getFrameUrl } from "../api/videos";
import { getPigeons } from "../api/pigeons";
import { getAttentionCount } from "../api/stats";
import type { VideoAssignment, QCFlag } from "../types";
import StatusBadge from "../components/ui/StatusBadge";
import LoadingState from "../components/ui/LoadingState";
import SectionError from "../components/ui/SectionError";
import { formatDuration } from "../utils/formatTime";
import { useToast } from "../components/ui/Toast";
import { usePageTitle } from "../hooks/usePageTitle";

/* ================================================================
   QC Flag rule_name → plain-language translation
   ================================================================ */
const QC_TRANSLATIONS: Record<string, string> = {
  id_swap_detected: "Possible identity swap between two pigeons",
  low_confidence_id: "Pigeon identity has low confidence",
  track_gap: "Tracking gap detected — pigeon may have disappeared briefly",
  overlap_detected: "Two pigeon tracks are overlapping",
  velocity_spike: "Abnormally high velocity detected",
  mask_drift: "Segmentation mask may be drifting off the pigeon",
  frame_drop: "Frames may have been dropped during processing",
  low_segmentation_quality: "Segmentation quality is below threshold",
  duplicate_detection: "Possible duplicate detection of the same pigeon",
};

function translateFlag(flag: QCFlag): string {
  return QC_TRANSLATIONS[flag.rule_name] ?? flag.reason ?? flag.rule_name.replace(/_/g, " ");
}

/* ================================================================
   Main Review Page
   ================================================================ */
export default function Review() {
  usePageTitle("Review");
  const [params] = useSearchParams();
  const type = params.get("type");
  const videoId = params.get("video_id");

  if (type === "identity" && videoId) {
    return <IdentityReview videoId={Number(videoId)} />;
  }
  if (type === "qc") {
    return <QCReview videoId={videoId ? Number(videoId) : undefined} />;
  }
  if (type === "dropping") {
    return <DroppingReview />;
  }
  if (type === "behavior") {
    return <BehaviorReview />;
  }
  return <ReviewQueue />;
}

/* ================================================================
   1. Identity Review
   ================================================================ */
function IdentityReview({ videoId }: { videoId: number }) {
  const queryClient = useQueryClient();
  const [currentIdx, setCurrentIdx] = useState(0);
  const navigate = useNavigate();
  const toast = useToast();

  const assignmentsQuery = useQuery({
    queryKey: ["unconfirmed-identities", videoId],
    queryFn: () => getUnconfirmedIdentities(videoId),
  });

  const pigeonsQuery = useQuery({
    queryKey: ["pigeons"],
    queryFn: getPigeons,
  });

  const confirmMutation = useMutation({
    mutationFn: ({
      assignmentId,
      pigeonId,
    }: {
      assignmentId: number;
      pigeonId: string;
    }) =>
      reviewIdentity({
        assignment_id: assignmentId,
        action: "confirm",
        pigeon_id: pigeonId,
        reviewer: "lab_user",
      }),
    onSuccess: (_data, variables) => {
      toast.success(`Identity confirmed as ${variables.pigeonId}`);
      queryClient.invalidateQueries({ queryKey: ["unconfirmed-identities", videoId] });
      queryClient.invalidateQueries({ queryKey: ["attention-count"] });
      queryClient.invalidateQueries({ queryKey: ["attention-items"] });
      queryClient.invalidateQueries({ queryKey: ["stats-today"] });
      advance();
    },
    onError: () => {
      toast.error("Failed to confirm identity. Please try again.");
    },
  });

  const assignments = assignmentsQuery.data ?? [];
  const pigeons = pigeonsQuery.data ?? [];
  const current: VideoAssignment | undefined = assignments[currentIdx];
  const total = assignments.length;

  function advance() {
    if (currentIdx < total - 1) {
      setCurrentIdx((i) => i + 1);
    }
  }

  if (assignmentsQuery.isLoading || pigeonsQuery.isLoading) return <LoadingState variant="list" />;

  if (assignmentsQuery.isError) {
    return <SectionError message="Failed to load identity assignments." onRetry={() => assignmentsQuery.refetch()} />;
  }

  if (total === 0) {
    return (
      <div className="text-center py-16">
        <div className="w-14 h-14 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
          <Check size={28} className="text-success" />
        </div>
        <p className="text-sm font-medium text-text-primary">All identities confirmed!</p>
        <p className="text-sm text-text-secondary mt-1">
          No unconfirmed pigeon identities remain for this video.
        </p>
        <button
          onClick={() => navigate(`/videos/${videoId}`)}
          className="mt-4 text-sm text-accent hover:text-accent/80 font-medium transition-colors"
        >
          ← Back to Video
        </button>
      </div>
    );
  }

  const allDone = currentIdx >= total;

  if (allDone || !current) {
    return (
      <div className="text-center py-16">
        <div className="w-14 h-14 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
          <Check size={28} className="text-success" />
        </div>
        <p className="text-sm font-medium text-text-primary">
          You've reviewed all assignments!
        </p>
        <button
          onClick={() => navigate(`/videos/${videoId}`)}
          className="mt-4 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors"
        >
          Done with this Video
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-xl font-bold text-text-primary">Identity Review</h1>

      {/* Frame preview */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="bg-black aspect-video flex items-center justify-center">
          <img
            src={getFrameUrl(videoId, current.video_obj_id, true)}
            alt={`Pigeon assignment ${currentIdx + 1}`}
            className="max-w-full max-h-full object-contain"
          />
        </div>
      </div>

      {/* Counter */}
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-text-primary">
          Pigeon {currentIdx + 1} of {total}
        </p>
        <button
          onClick={advance}
          className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <SkipForward size={14} />
          Skip for Now
        </button>
      </div>

      {/* Pigeon selection */}
      <div>
        <p className="text-sm font-medium text-text-primary mb-3">
          This pigeon is:
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {pigeons.map((p) => (
            <button
              key={p.pigeon_id}
              onClick={() =>
                confirmMutation.mutate({
                  assignmentId: current.id,
                  pigeonId: p.pigeon_id,
                })
              }
              disabled={confirmMutation.isPending}
              className="bg-surface border border-border rounded-xl p-4 text-left hover:border-accent hover:shadow-md transition-all group disabled:opacity-50"
            >
              <div className="flex items-center gap-3">
                <span className="text-xl">🕊️</span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-text-primary group-hover:text-accent truncate">
                    {p.pigeon_id}
                  </p>
                  {p.physical_markers && (
                    <p className="text-[11px] text-text-secondary truncate mt-0.5">
                      {p.physical_markers}
                    </p>
                  )}
                </div>
              </div>
            </button>
          ))}
          {/* New pigeon placeholder */}
          <button
            onClick={() => toast.success("New Pigeon registration coming soon — this feature is in development")}
            className="border-2 border-dashed border-border rounded-xl p-4 text-center hover:border-accent/50 transition-colors"
          >
            <p className="text-sm font-medium text-text-secondary">
              + New Pigeon
            </p>
            <p className="text-[11px] text-text-secondary/60 mt-0.5">
              This is a new pigeon
            </p>
          </button>
        </div>
      </div>

      {/* Progress list */}
      <div className="bg-surface border border-border rounded-xl p-4">
        <h3 className="text-[12px] font-semibold text-text-secondary uppercase tracking-wider mb-2">
          Progress
        </h3>
        <div className="flex flex-wrap gap-2">
          {assignments.map((a, i) => (
            <span
              key={a.id}
              className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-medium ${
                i < currentIdx
                  ? "bg-success/10 text-success"
                  : i === currentIdx
                    ? "bg-accent text-white"
                    : "bg-bg text-text-secondary"
              }`}
            >
              {i < currentIdx ? (
                <Check size={12} strokeWidth={3} />
              ) : (
                i + 1
              )}
            </span>
          ))}
        </div>
      </div>

      {/* Done button */}
      <button
        onClick={() => navigate(`/videos/${videoId}`)}
        className="w-full px-4 py-2.5 border border-border text-sm font-medium rounded-lg hover:bg-bg transition-colors text-text-primary"
      >
        Done with this Video
      </button>
    </div>
  );
}

/* ================================================================
   2. QC Flag Review
   ================================================================ */
function QCReview({ videoId }: { videoId?: number }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();

  const flagsQuery = useQuery({
    queryKey: ["qc-flags", videoId],
    queryFn: () => getQCFlags("pending", videoId),
  });

  const resolveMutation = useMutation({
    mutationFn: (flagId: number) =>
      reviewQCFlag({
        flag_id: flagId,
        action: "resolve",
        resolved_action: "accepted",
        reviewer: "lab_user",
      }),
    onSuccess: () => {
      toast.success("QC flag resolved");
      queryClient.invalidateQueries({ queryKey: ["qc-flags", videoId] });
      queryClient.invalidateQueries({ queryKey: ["attention-count"] });
      queryClient.invalidateQueries({ queryKey: ["attention-items"] });
    },
    onError: () => {
      toast.error("Failed to resolve QC flag");
    },
  });

  const batchResolveMutation = useMutation({
    mutationFn: (flagIds: number[]) =>
      batchResolveQCFlags({
        flag_ids: flagIds,
        action: "resolve",
        resolved_action: "accepted",
        reviewer: "lab_user",
      }),
    onSuccess: () => {
      toast.success("All low-severity flags resolved");
      queryClient.invalidateQueries({ queryKey: ["qc-flags", videoId] });
      queryClient.invalidateQueries({ queryKey: ["attention-count"] });
      queryClient.invalidateQueries({ queryKey: ["attention-items"] });
    },
    onError: () => {
      toast.error("Failed to batch resolve flags");
    },
  });

  const flags = flagsQuery.data ?? [];
  const lowFlags = flags.filter(
    (f) => f.severity === "low" || f.severity === null,
  );

  if (flagsQuery.isLoading) return <LoadingState variant="list" />;

  if (flagsQuery.isError) {
    return <SectionError message="Failed to load QC flags." onRetry={() => flagsQuery.refetch()} />;
  }

  if (flags.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="w-14 h-14 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
          <Check size={28} className="text-success" />
        </div>
        <p className="text-sm font-medium text-text-primary">All QC flags resolved!</p>
        <p className="text-sm text-text-secondary mt-1">No pending quality issues.</p>
        {videoId && (
          <button
            onClick={() => navigate(`/videos/${videoId}`)}
            className="mt-4 text-sm text-accent hover:text-accent/80 font-medium transition-colors"
          >
            ← Back to Video
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">QC Flag Review</h1>
        {lowFlags.length > 1 && (
          <button
            onClick={() =>
              batchResolveMutation.mutate(lowFlags.map((f) => f.id))
            }
            disabled={batchResolveMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border border-border rounded-lg hover:bg-bg transition-colors disabled:opacity-50"
          >
            {batchResolveMutation.isPending && (
              <Loader2 size={14} className="animate-spin" />
            )}
            Accept All Low-Severity ({lowFlags.length})
          </button>
        )}
      </div>

      <div className="bg-surface border border-border rounded-xl divide-y divide-border">
        {flags.map((flag) => (
          <QCFlagRow
            key={flag.id}
            flag={flag}
            onAccept={() => resolveMutation.mutate(flag.id)}
            onFix={() =>
              navigate(
                `/videos/${flag.video_id}${flag.frame_idx != null ? `?frame=${flag.frame_idx}` : ""}`,
              )
            }
            isPending={resolveMutation.isPending}
          />
        ))}
      </div>
    </div>
  );
}

function QCFlagRow({
  flag,
  onAccept,
  onFix,
  isPending,
}: {
  flag: QCFlag;
  onAccept: () => void;
  onFix: () => void;
  isPending: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div className="flex items-start gap-3 min-w-0 flex-1">
        <AlertTriangle size={16} className="text-warning shrink-0 mt-0.5" />
        <div className="min-w-0">
          <p className="text-sm text-text-primary">
            {translateFlag(flag)}
          </p>
          <div className="flex items-center gap-3 mt-1">
            {flag.frame_idx != null && (
              <span className="text-[11px] text-text-secondary">
                Frame {flag.frame_idx}
              </span>
            )}
            {flag.severity && <StatusBadge status={flag.severity} />}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={onAccept}
          disabled={isPending}
          className="px-3 py-1.5 text-[12px] font-medium border border-border rounded-lg hover:bg-bg transition-colors disabled:opacity-50"
        >
          Looks Fine
        </button>
        <button
          onClick={onFix}
          className="px-3 py-1.5 text-[12px] font-medium text-white bg-warning rounded-lg hover:bg-warning/90 transition-colors"
        >
          Fix This
        </button>
      </div>
    </div>
  );
}

/* ================================================================
   3. Dropping Review
   ================================================================ */
function DroppingReview() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();

  const droppingsQuery = useQuery({
    queryKey: ["droppings-review"],
    queryFn: () => getDroppingsForReview("raw"),
  });

  const mutation = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "confirm" | "reject" }) =>
      reviewDropping({ dropping_id: id, action, reviewer: "lab_user" }),
    onSuccess: (_data, variables) => {
      toast.success(
        variables.action === "confirm" ? "Dropping confirmed" : "Dropping rejected",
      );
      queryClient.invalidateQueries({ queryKey: ["droppings-review"] });
      queryClient.invalidateQueries({ queryKey: ["attention-count"] });
      queryClient.invalidateQueries({ queryKey: ["insights-droppings"] });
    },
    onError: () => {
      toast.error("Failed to review dropping");
    },
  });

  const droppings = droppingsQuery.data ?? [];

  if (droppingsQuery.isLoading) return <LoadingState variant="list" />;

  if (droppingsQuery.isError) {
    return <SectionError message="Failed to load droppings." onRetry={() => droppingsQuery.refetch()} />;
  }

  if (droppings.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="w-14 h-14 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
          <Check size={28} className="text-success" />
        </div>
        <p className="text-sm font-medium text-text-primary">All droppings reviewed!</p>
        <p className="text-sm text-text-secondary mt-1">No pending dropping detections.</p>
        <button
          onClick={() => navigate("/review")}
          className="mt-4 text-sm text-accent hover:text-accent/80 font-medium transition-colors"
        >
          ← Back to Review Queue
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">Dropping Review</h1>
        <span className="text-sm text-text-secondary">
          {droppings.length} pending
        </span>
      </div>

      <div className="bg-surface border border-border rounded-xl divide-y divide-border">
        {droppings.map((d) => (
          <div
            key={d.id}
            className="flex items-center justify-between gap-4 px-5 py-4"
          >
            <div className="flex items-start gap-3 min-w-0 flex-1">
              <span className="text-base shrink-0 mt-0.5">🔍</span>
              <div className="min-w-0">
                <p className="text-sm text-text-primary">
                  Dropping in{" "}
                  <span className="font-medium">{d.zone ?? "unknown zone"}</span>
                </p>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-[11px] text-text-secondary">
                    Frame {d.frame_idx}
                  </span>
                  {d.confidence != null && (
                    <span className="text-[11px] text-text-secondary">
                      {Math.round(d.confidence * 100)}% confidence
                    </span>
                  )}
                  {d.detection_method && (
                    <span className="text-[11px] text-text-secondary">
                      {d.detection_method}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => mutation.mutate({ id: d.id, action: "confirm" })}
                disabled={mutation.isPending}
                className="flex items-center gap-1 px-3 py-1.5 text-[12px] font-medium text-white bg-success rounded-lg hover:bg-success/90 transition-colors disabled:opacity-50"
              >
                <Check size={12} />
                Confirm
              </button>
              <button
                onClick={() => mutation.mutate({ id: d.id, action: "reject" })}
                disabled={mutation.isPending}
                className="px-3 py-1.5 text-[12px] font-medium border border-border rounded-lg hover:bg-bg transition-colors disabled:opacity-50"
              >
                Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ================================================================
   4. Behavior Review
   ================================================================ */
function BehaviorReview() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();

  const behaviorsQuery = useQuery({
    queryKey: ["behaviors-review"],
    queryFn: () => getBehaviorsForReview("raw"),
  });

  const mutation = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "confirm" | "reject" }) =>
      reviewBehavior({ behavior_id: id, action, reviewer: "lab_user" }),
    onSuccess: (_data, variables) => {
      toast.success(
        variables.action === "confirm" ? "Behavior confirmed" : "Behavior rejected",
      );
      queryClient.invalidateQueries({ queryKey: ["behaviors-review"] });
      queryClient.invalidateQueries({ queryKey: ["attention-count"] });
    },
    onError: () => {
      toast.error("Failed to review behavior");
    },
  });

  const behaviors = behaviorsQuery.data ?? [];

  if (behaviorsQuery.isLoading) return <LoadingState variant="list" />;

  if (behaviorsQuery.isError) {
    return <SectionError message="Failed to load behaviors." onRetry={() => behaviorsQuery.refetch()} />;
  }

  if (behaviors.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="w-14 h-14 rounded-full bg-success/10 flex items-center justify-center mx-auto mb-4">
          <Check size={28} className="text-success" />
        </div>
        <p className="text-sm font-medium text-text-primary">All behaviors reviewed!</p>
        <p className="text-sm text-text-secondary mt-1">No pending behavior detections.</p>
        <button
          onClick={() => navigate("/review")}
          className="mt-4 text-sm text-accent hover:text-accent/80 font-medium transition-colors"
        >
          ← Back to Review Queue
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">Behavior Review</h1>
        <span className="text-sm text-text-secondary">
          {behaviors.length} pending
        </span>
      </div>

      <div className="bg-surface border border-border rounded-xl divide-y divide-border">
        {behaviors.map((b) => (
          <div
            key={b.id}
            className="flex items-center justify-between gap-4 px-5 py-4"
          >
            <div className="flex items-start gap-3 min-w-0 flex-1">
              <span className="text-base shrink-0 mt-0.5">🎬</span>
              <div className="min-w-0">
                <p className="text-sm text-text-primary">
                  <span className="font-medium">{b.pigeon_id}</span>
                  {" — "}
                  <span className="capitalize">{b.behavior.replace(/_/g, " ")}</span>
                </p>
                <div className="flex items-center gap-3 mt-1">
                  {b.duration_seconds != null && (
                    <span className="text-[11px] text-text-secondary">
                      {formatDuration(b.duration_seconds)}
                    </span>
                  )}
                  {b.confidence != null && (
                    <span className="text-[11px] text-text-secondary">
                      {Math.round(b.confidence * 100)}% confidence
                    </span>
                  )}
                  {b.zone && (
                    <span className="text-[11px] text-text-secondary">
                      {b.zone}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => mutation.mutate({ id: b.id, action: "confirm" })}
                disabled={mutation.isPending}
                className="flex items-center gap-1 px-3 py-1.5 text-[12px] font-medium text-white bg-success rounded-lg hover:bg-success/90 transition-colors disabled:opacity-50"
              >
                <Check size={12} />
                Confirm
              </button>
              <button
                onClick={() => mutation.mutate({ id: b.id, action: "reject" })}
                disabled={mutation.isPending}
                className="px-3 py-1.5 text-[12px] font-medium border border-border rounded-lg hover:bg-bg transition-colors disabled:opacity-50"
              >
                Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ================================================================
   5a. Batch Confirm Modal
   ================================================================ */
function BatchConfirmModal({
  onClose,
}: {
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();

  const nextVideoQuery = useQuery({
    queryKey: ["next-identity-video"],
    queryFn: getNextVideoForIdentityReview,
  });

  const videoId = nextVideoQuery.data?.video_id ?? null;

  const assignmentsQuery = useQuery({
    queryKey: ["unconfirmed-identities-batch", videoId],
    queryFn: () => getUnconfirmedIdentities(videoId!),
    enabled: videoId !== null,
  });

  const assignments = assignmentsQuery.data ?? [];
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [submitting, setSubmitting] = useState(false);

  const toggle = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const selectAbove85 = () => {
    const ids = assignments
      .filter((a) => (a.confidence ?? 0) >= 0.85)
      .map((a) => a.id);
    setSelected(new Set(ids));
  };

  const allAbove85Selected =
    assignments.filter((a) => (a.confidence ?? 0) >= 0.85).length > 0 &&
    assignments
      .filter((a) => (a.confidence ?? 0) >= 0.85)
      .every((a) => selected.has(a.id));

  const handleConfirm = async () => {
    const items = assignments
      .filter((a) => selected.has(a.id))
      .map((a) => ({ assignment_id: a.id, pigeon_id: a.pigeon_id }));
    if (items.length === 0) return;

    setSubmitting(true);
    try {
      const result = await batchConfirmIdentities(items);
      toast.success(`Confirmed ${result.confirmed} identit${result.confirmed === 1 ? "y" : "ies"}.`);
      queryClient.invalidateQueries({ queryKey: ["attention-count"] });
      queryClient.invalidateQueries({ queryKey: ["next-identity-video"] });
      queryClient.invalidateQueries({ queryKey: ["unconfirmed-identities-batch"] });
      onClose();
    } catch {
      toast.error("Batch confirmation failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const loading = nextVideoQuery.isLoading || assignmentsQuery.isLoading;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-surface border border-border rounded-xl shadow-lg w-full max-w-lg max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-bold text-text-primary">Batch Confirm Identities</h2>
          <button onClick={onClose} className="text-text-secondary hover:text-text-primary text-lg leading-none">&times;</button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-1">
          {loading ? (
            <LoadingState variant="list" />
          ) : assignments.length === 0 ? (
            <p className="text-sm text-text-secondary py-4 text-center">No unconfirmed identities found.</p>
          ) : (
            <>
              <label className="flex items-center gap-2 py-2 text-xs text-text-secondary cursor-pointer">
                <input
                  type="checkbox"
                  checked={allAbove85Selected}
                  onChange={() => (allAbove85Selected ? setSelected(new Set()) : selectAbove85())}
                  className="accent-accent"
                />
                Select all above 85% confidence
              </label>
              <div className="border-t border-border" />
              {assignments.map((a) => (
                <label
                  key={a.id}
                  className="flex items-center gap-3 py-2 cursor-pointer hover:bg-accent/[0.03] rounded-lg px-1"
                >
                  <input
                    type="checkbox"
                    checked={selected.has(a.id)}
                    onChange={() => toggle(a.id)}
                    className="accent-accent"
                  />
                  <span className="text-sm text-text-primary font-medium truncate">
                    {a.pigeon_id}
                  </span>
                  <span className="ml-auto text-xs text-text-secondary tabular-nums">
                    {a.confidence !== null ? `${(a.confidence * 100).toFixed(0)}%` : "—"}
                  </span>
                </label>
              ))}
            </>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-border">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={selected.size === 0 || submitting}
            className="px-4 py-1.5 text-sm font-medium text-white bg-accent rounded-lg hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? "Confirming…" : `Confirm Selected (${selected.size})`}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ================================================================
   5. General Review Queue
   ================================================================ */
function ReviewQueue() {
  const navigate = useNavigate();
  const [showBatchModal, setShowBatchModal] = useState(false);

  const countQuery = useQuery({
    queryKey: ["attention-count"],
    queryFn: getAttentionCount,
  });

  const nextVideoQuery = useQuery({
    queryKey: ["next-identity-video"],
    queryFn: getNextVideoForIdentityReview,
    enabled: (countQuery.data?.identity ?? 0) > 0,
  });

  if (countQuery.isLoading) return <LoadingState variant="list" />;

  if (countQuery.isError) {
    return <SectionError message="Failed to load review queue." onRetry={() => countQuery.refetch()} />;
  }

  const counts = countQuery.data;
  const total = counts?.total ?? 0;

  const sections = [
    {
      key: "identity",
      title: "Unconfirmed Identities",
      icon: "🕊️",
      count: counts?.identity ?? 0,
      description:
        "Pigeon identities that need manual confirmation",
      action: () => {
        const vid = nextVideoQuery.data?.video_id;
        if (vid) navigate(`/review?type=identity&video_id=${vid}`);
      },
    },
    {
      key: "qc",
      title: "QC Flags",
      icon: "⚠️",
      count: counts?.qc ?? 0,
      description:
        "Quality control issues flagged during processing",
      action: () => navigate("/review?type=qc"),
    },
    {
      key: "behaviors",
      title: "Behaviors to Review",
      icon: "🎬",
      count: counts?.behaviors ?? 0,
      description:
        "Behavior detections that need confirmation",
      action: () => navigate("/review?type=behavior"),
    },
    {
      key: "droppings",
      title: "Droppings to Review",
      icon: "🔍",
      count: counts?.droppings ?? 0,
      description:
        "Dropping detections that need confirmation",
      action: () => navigate("/review?type=dropping"),
    },
  ];

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-text-primary">Review Queue</h1>
        <p className="text-sm text-text-secondary mt-1">
          {total === 0
            ? "Nothing needs your attention right now."
            : `${total} item${total !== 1 ? "s" : ""} need${total === 1 ? "s" : ""} your attention.`}
        </p>
      </div>

      <div className="space-y-4">
        {sections.map((s) => (
          <div
            key={s.key}
            className="bg-surface border border-border rounded-xl p-5 flex items-center justify-between gap-4"
          >
            <div className="flex items-center gap-4 min-w-0">
              <span className="text-2xl">{s.icon}</span>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold text-text-primary">
                    {s.title}
                  </h3>
                  {s.count > 0 && (
                    <span className="px-2 py-0.5 bg-warning/10 text-warning text-[11px] font-medium rounded-full">
                      {s.count}
                    </span>
                  )}
                </div>
                <p className="text-[12px] text-text-secondary mt-0.5">
                  {s.description}
                </p>
              </div>
            </div>
            {s.count > 0 && (
              <div className="flex items-center gap-2 shrink-0">
                {s.key === "identity" && (
                  <button
                    onClick={() => setShowBatchModal(true)}
                    className="px-3 py-1.5 text-xs font-medium text-accent border border-accent/30 rounded-lg hover:bg-accent/5 transition-colors whitespace-nowrap"
                  >
                    Batch Confirm
                  </button>
                )}
                <button
                  onClick={s.action}
                  className="flex items-center gap-1 text-sm font-medium text-accent hover:text-accent/80 transition-colors whitespace-nowrap"
                >
                  Start Reviewing
                  <ChevronRight size={14} />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {showBatchModal && (
        <BatchConfirmModal onClose={() => setShowBatchModal(false)} />
      )}
    </div>
  );
}
