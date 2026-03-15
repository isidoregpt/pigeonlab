import { NavLink } from "react-router-dom";
import {
  Home,
  Video,
  Bird,
  BarChart3,
  CheckCircle,
  GraduationCap,
} from "lucide-react";

const links = [
  { to: "/", label: "Home", icon: Home },
  { to: "/videos", label: "Videos", icon: Video },
  { to: "/pigeons", label: "Pigeons", icon: Bird },
  { to: "/insights", label: "Insights", icon: BarChart3 },
  { to: "/review", label: "Review", icon: CheckCircle },
  { to: "/training", label: "Training", icon: GraduationCap },
];

export default function Sidebar() {
  return (
    <aside className="w-56 h-screen bg-surface border-r border-border flex flex-col p-4 gap-1">
      <h1 className="text-lg font-bold text-accent mb-6 px-2">PigeonLab</h1>
      <nav className="flex flex-col gap-1">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-accent/10 text-accent font-medium"
                  : "text-text-secondary hover:bg-bg"
              }`
            }
          >
            <link.icon size={18} />
            {link.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
