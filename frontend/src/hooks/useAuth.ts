import { useAuthStore } from "../store/authStore";
import { authApi } from "../api/auth";
import { useNavigate } from "react-router-dom";

export function useAuth() {
  const { user, isAuthenticated, setUser, clear } = useAuthStore();
  const navigate = useNavigate();

  const login = async (email: string, password: string) => {
    // The login response sets the httpOnly auth cookies; we then load the user
    // profile (cookie rides along) to populate client-side user state.
    await authApi.login({ email, password });
    const meRes = await authApi.me();
    setUser(meRes.data);
    navigate("/");
  };

  const register = async (email: string, password: string, displayName: string) => {
    await authApi.register({ email, password, display_name: displayName });
    await login(email, password);
  };

  const logout = async () => {
    // Hit the server so the access-token jti is denylisted (revoked) and the
    // cookies are cleared, THEN drop client-side state. Server revocation is the
    // security-critical step — without it the cookie would stay valid until
    // natural expiry.
    await authApi.logout().catch(() => {});
    clear();
    navigate("/login");
  };

  return { user, isAuthenticated, login, register, logout };
}
