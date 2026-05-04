import { useAuthStore } from "../store/authStore";
import { authApi } from "../api/auth";
import { useNavigate } from "react-router-dom";

export function useAuth() {
  const { user, isAuthenticated, setAuth, logout: clearAuth } = useAuthStore();
  const navigate = useNavigate();

  const login = async (email: string, password: string) => {
    const res = await authApi.login({ email, password });
    const meRes = await authApi.me();
    setAuth(meRes.data, res.data.access_token);
    navigate("/");
  };

  const register = async (email: string, password: string, displayName: string) => {
    await authApi.register({ email, password, display_name: displayName });
    await login(email, password);
  };

  const logout = async () => {
    await authApi.logout().catch(() => {});
    clearAuth();
    navigate("/login");
  };

  return { user, isAuthenticated, login, register, logout };
}
