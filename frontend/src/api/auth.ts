import { api } from "./client";
import type { Envelope, TokenResponse, User } from "./types";

export const authApi = {
  register: (data: { email: string; password: string; display_name: string }) =>
    api.post<Envelope<User>>("/auth/register", data),

  login: (data: { email: string; password: string }) =>
    api.post<Envelope<TokenResponse>>("/auth/login", data),

  refresh: () => api.post<Envelope<TokenResponse>>("/auth/refresh"),

  logout: () => api.post<void>("/auth/logout"),

  me: () => api.get<Envelope<User>>("/auth/me"),
};
