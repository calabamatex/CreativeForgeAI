import { create } from "zustand";
import type { User } from "../api/types";

/**
 * Auth state (P5-T3): the access/refresh tokens live in httpOnly cookies the
 * browser cannot read, so the store tracks only the authenticated USER and an
 * `isAuthenticated` flag — never the raw token. On a fresh page load nothing is
 * authenticated until `/auth/me` succeeds (the cookie still rides along), at
 * which point `setUser` flips `isAuthenticated`.
 */
interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  /** Record the authenticated user (e.g. from the login response or /auth/me). */
  setUser: (user: User) => void;
  /** Clear client-side user state. Server-side revocation is done in useAuth. */
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,

  setUser: (user) => set({ user, isAuthenticated: true }),

  clear: () => set({ user: null, isAuthenticated: false }),
}));
