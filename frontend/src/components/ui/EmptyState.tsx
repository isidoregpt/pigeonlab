interface EmptyStateProps {
  message: string;
}

export default function EmptyState({ message }: EmptyStateProps) {
  return (
    <div className="flex items-center justify-center p-12">
      <span className="text-text-secondary text-sm">{message}</span>
    </div>
  );
}
