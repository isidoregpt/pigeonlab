import { useCallback, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import KeyboardShortcutsModal from "../ui/KeyboardShortcutsModal";

const pageTitles: Record<string, string> = {
  "/": "Home",
  "/videos": "Videos",
  "/pigeons": "Pigeons",
  "/insights": "Insights",
  "/review": "Review",
  "/training": "Training",
  "/settings": "Settings",
};

function getPageTitle(pathname: string): string {
  if (pageTitles[pathname]) return pageTitles[pathname];
  if (pathname.startsWith("/videos/")) return "Video Detail";
  if (pathname.startsWith("/pigeons/")) return "Pigeon Profile";
  return "PigeonLab";
}

export default function Layout() {
  const location = useLocation();
  const title = getPageTitle(location.pathname);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  const openShortcuts = useCallback(() => setShortcutsOpen(true), []);
  const closeShortcuts = useCallback(() => setShortcutsOpen(false), []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "?" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        setShortcutsOpen((prev) => !prev);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:bg-accent focus:text-white focus:rounded-lg focus:text-sm focus:font-medium"
      >
        Skip to content
      </a>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar title={title} onShowShortcuts={openShortcuts} />
        <main id="main-content" className="flex-1 overflow-auto bg-bg p-6">
          <div key={location.pathname} className="page-enter">
            <Outlet />
          </div>
        </main>
      </div>
      <KeyboardShortcutsModal open={shortcutsOpen} onClose={closeShortcuts} />
    </div>
  );
}
