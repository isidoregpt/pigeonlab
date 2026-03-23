import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

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

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar title={title} />
        <main className="flex-1 overflow-auto bg-bg p-6">
          <div key={location.pathname} className="page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
