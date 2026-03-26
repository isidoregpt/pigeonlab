import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, HelpCircle } from "lucide-react";
import { apiFetch } from "../../api/client";

interface TopBarProps {
  title: string;
  onShowShortcuts?: () => void;
}

export default function TopBar({ title, onShowShortcuts }: TopBarProps) {
  const navigate = useNavigate();
  const [attentionCount, setAttentionCount] = useState(0);

  useEffect(() => {
    apiFetch<{ total: number }>("/review/attention/count")
      .then((data) => setAttentionCount(data.total))
      .catch(() => setAttentionCount(0));

    const interval = setInterval(() => {
      apiFetch<{ total: number }>("/review/attention/count")
        .then((data) => setAttentionCount(data.total))
        .catch(() => {});
    }, 30_000);

    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-14 bg-surface border-b border-border flex items-center justify-between px-6 shrink-0">
      <h2 className="text-[15px] font-semibold text-text-primary tracking-tight">
        {title}
      </h2>

      <div className="flex items-center gap-1">
      <button
        onClick={onShowShortcuts}
        className="flex items-center justify-center w-8 h-8 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg transition-colors"
        title="Keyboard shortcuts (?)"
      >
        <HelpCircle size={18} strokeWidth={1.8} />
      </button>
      <button
        onClick={() => navigate("/review")}
        className="relative flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors hover:bg-bg"
      >
        <Bell size={18} className={attentionCount > 0 ? "text-warning" : "text-text-secondary"} strokeWidth={1.8} />
        {attentionCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-warning text-white text-[10px] font-bold px-1 animate-pulse">
            {attentionCount > 99 ? "99+" : attentionCount}
          </span>
        )}
      </button>
      </div>
    </header>
  );
}
