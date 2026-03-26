import { useEffect, useRef } from "react";
import { X } from "lucide-react";

interface KeyboardShortcutsModalProps {
  open: boolean;
  onClose: () => void;
}

interface ShortcutRow {
  keys: string[];
  description: string;
}

interface ShortcutSection {
  title: string;
  shortcuts: ShortcutRow[];
}

const sections: ShortcutSection[] = [
  {
    title: "Video Detail",
    shortcuts: [
      { keys: ["←"], description: "Previous frame" },
      { keys: ["→"], description: "Next frame" },
      { keys: ["Shift", "←"], description: "Back 10 frames" },
      { keys: ["Shift", "→"], description: "Forward 10 frames" },
    ],
  },
  {
    title: "Training Labels",
    shortcuts: [
      { keys: ["1", "–", "7"], description: "Select behavior label" },
      { keys: ["0"], description: "Skip clip" },
    ],
  },
  {
    title: "General",
    shortcuts: [
      { keys: ["Esc"], description: "Close modal / cancel" },
      { keys: ["?"], description: "Show this help" },
    ],
  },
];

function Kbd({ children }: { children: string }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[24px] h-6 px-1.5 text-[11px] font-mono font-medium text-text-primary bg-bg border border-border rounded-md shadow-sm">
      {children}
    </kbd>
  );
}

export default function KeyboardShortcutsModal({
  open,
  onClose,
}: KeyboardShortcutsModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      <div className="bg-surface rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 pt-5 pb-3">
          <h2 className="text-base font-semibold text-text-primary">
            Keyboard Shortcuts
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <div className="px-6 pb-5 space-y-4">
          {sections.map((section) => (
            <div key={section.title}>
              <h3 className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider mb-2">
                {section.title}
              </h3>
              <div className="space-y-1.5">
                {section.shortcuts.map((shortcut) => (
                  <div
                    key={shortcut.description}
                    className="flex items-center justify-between py-1"
                  >
                    <span className="text-sm text-text-secondary">
                      {shortcut.description}
                    </span>
                    <div className="flex items-center gap-1">
                      {shortcut.keys.map((key, i) => (
                        <Kbd key={i}>{key}</Kbd>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
