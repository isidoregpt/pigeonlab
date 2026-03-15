import type { Pigeon } from "../../types";

interface PigeonCardProps {
  pigeon: Pigeon;
}

export default function PigeonCard({ pigeon }: PigeonCardProps) {
  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <h3 className="font-medium text-text-primary">{pigeon.pigeon_id}</h3>
      <p className="text-sm text-text-secondary mt-1">{pigeon.physical_markers}</p>
    </div>
  );
}
