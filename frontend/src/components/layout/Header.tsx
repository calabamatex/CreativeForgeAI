import { useAuthStore } from "../../store/authStore";
import { LogOut, User } from "lucide-react";

export function Header() {
  const { user, logout } = useAuthStore();

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <h1 className="text-lg font-semibold text-gray-800">Adobe GenAI Creative Automation</h1>
      <div className="flex items-center gap-4">
        {user && (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <User size={16} aria-hidden="true" />
            <span>{user.display_name}</span>
            <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 text-xs">{user.role}</span>
          </div>
        )}
        <button
          onClick={logout}
          className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100"
          aria-label="Logout"
        >
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
}
