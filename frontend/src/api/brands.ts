import { api } from "./client";
import type { BrandGuidelines, Envelope, PaginatedEnvelope } from "./types";

export const brandApi = {
  list: () => api.get<PaginatedEnvelope<BrandGuidelines>>("/brands"),

  get: (id: string) => api.get<Envelope<BrandGuidelines>>(`/brands/${id}`),

  create: (data: { name: string }) =>
    api.post<Envelope<BrandGuidelines>>("/brands", data),

  update: (id: string, data: Partial<BrandGuidelines>) =>
    api.patch<Envelope<BrandGuidelines>>(`/brands/${id}`, data),

  delete: (id: string) => api.delete<void>(`/brands/${id}`),
};
