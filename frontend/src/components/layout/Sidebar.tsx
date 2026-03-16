import { NavLink } from "react-router-dom";
import {
  Home,
  Video,
  Bird,
  BarChart3,
  FlaskConical,
  Settings,
} from "lucide-react";

const mainLinks = [
  { to: "/", label: "Home", icon: Home },
  { to: "/videos", label: "Videos", icon: Video },
  { to: "/pigeons", label: "Pigeons", icon: Bird },
  { to: "/insights", label: "Insights", icon: BarChart3 },
];

const secondaryLinks = [
  { to: "/training", label: "Training", icon: FlaskConical },
];

function NavItem({
  to,
  label,
  icon: Icon,
  end,
  subtle,
}: {
  to: string;
  label: string;
  icon: typeof Home;
  end?: boolean;
  subtle?: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        [
          "flex items-center gap-3 px-4 py-2.5 text-[13px] tracking-wide transition-colors relative",
          isActive
            ? "text-accent font-semibold before:absolute before:left-0 before:top-1 before:bottom-1 before:w-[3px] before:rounded-r before:bg-accent"
            : subtle
              ? "text-text-secondary/60 hover:text-text-secondary hover:bg-accent/[0.03]"
              : "text-text-secondary hover:text-text-primary hover:bg-accent/[0.04]",
        ].join(" ")
      }
    >
      <Icon size={18} strokeWidth={1.8} />
      {label}
    </NavLink>
  );
}

export default function Sidebar() {
  return (
    <aside className="w-[220px] h-screen bg-bg border-r border-border flex flex-col shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-16 shrink-0">
        <span className="text-xl leading-none">🕊️</span>
        <span className="text-[15px] font-bold tracking-tight text-accent">
          PigeonLab
        </span>
      </div>

      {/* Main nav */}
      <nav className="flex flex-col gap-0.5 mt-2 px-2">
        {mainLinks.map((link) => (
          <NavItem key={link.to} {...link} end={link.to === "/"} />
        ))}
      </nav>

      {/* Divider */}
      <div className="mx-5 my-3 border-t border-border" />

      {/* Secondary nav */}
      <nav className="flex flex-col gap-0.5 px-2">
        {secondaryLinks.map((link) => (
          <NavItem key={link.to} {...link} subtle />
        ))}
      </nav>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Settings */}
      <div className="px-2 pb-4">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            [
              "flex items-center gap-3 px-4 py-2.5 text-[13px] tracking-wide transition-colors rounded-lg",
              isActive
                ? "text-accent font-semibold"
                : "text-text-secondary/50 hover:text-text-secondary hover:bg-accent/[0.03]",
            ].join(" ")
          }
        >
          <Settings size={18} strokeWidth={1.8} />
          Settings
        </NavLink>
      </div>
    </aside>
  );
}
