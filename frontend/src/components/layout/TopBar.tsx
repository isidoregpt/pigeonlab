import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell } from "lucide-react";
import { apiFetch } from "../../api/client";

interface TopBarProps {
  title: string;
}

export default function TopBar({ title }: TopBarProps) {
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
    </header>
  );
}
