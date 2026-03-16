import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { usePageTitle } from "../hooks/usePageTitle";
import { getPigeons } from "../api/pigeons";
import PigeonCard from "../components/ui/PigeonCard";
import LoadingState from "../components/ui/LoadingState";
import EmptyState from "../components/ui/EmptyState";
import RegisterPigeonModal from "../components/ui/RegisterPigeonModal";

export default function Pigeons() {
  usePageTitle("Pigeons");
  const [modalOpen, setModalOpen] = useState(false);

  const { data: pigeons, isLoading, isError, refetch } = useQuery({
    queryKey: ["pigeons"],
    queryFn: getPigeons,
  });

  if (isLoading) return <LoadingState />;

  if (isError) {
    return (
      <div className="text-center py-16 text-text-secondary text-sm">
        Something went wrong loading pigeons. Please try refreshing the page.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-text-primary">🐦 Your Pigeons</h1>
        <button
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-1.5 px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent/90 transition-colors"
        >
          <Plus size={16} strokeWidth={2} />
          Register New
        </button>
      </div>

      {/* Grid */}
      {(pigeons ?? []).length === 0 ? (
        <EmptyState
          icon="🕊️"
          title="No pigeons registered yet"
          description="Add your first pigeon to get started."
          actionLabel="+ Register New"
          onAction={() => setModalOpen(true)}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {(pigeons ?? []).map((p) => (
            <PigeonCard
              key={p.pigeon_id}
              pigeon={p}
              topZone={p.top_zone}
              sessionCount={p.session_count}
            />
          ))}
        </div>
      )}

      {/* Modal */}
      {modalOpen && (
        <RegisterPigeonModal
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
