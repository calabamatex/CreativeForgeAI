import { NavLink } from "react-router-dom";
import { LayoutDashboard, Megaphone, BarChart3, Activity, Settings, BookOpen } from "lucide-react";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/campaigns", icon: Megaphone, label: "Campaigns" },
  { to: "/brands", icon: BookOpen, label: "Brand Guidelines" },
  { to: "/jobs", icon: Activity, label: "Jobs" },
  { to: "/metrics", icon: BarChart3, label: "Metrics" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  return (
    <aside className="w-64 bg-gray-900 text-white min-h-screen p-4 flex flex-col" aria-label="Main navigation">
      <div className="text-xl font-bold mb-8 px-2">GenAI Platform</div>
      <nav className="flex flex-col gap-1 flex-1" aria-label="Primary">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                isActive ? "bg-blue-600 text-white" : "text-gray-300 hover:bg-gray-800"
              }`
            }
          >
            <Icon size={20} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
