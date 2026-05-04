import { api } from "./client";
import type { Campaign, Envelope, PaginatedEnvelope } from "./types";

export const campaignApi = {
  list: (params?: { status?: string; cursor?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.cursor) query.set("cursor", params.cursor);
    if (params?.limit) query.set("limit", String(params.limit));
    const qs = query.toString();
    return api.get<PaginatedEnvelope<Campaign>>(`/campaigns${qs ? `?${qs}` : ""}`);
  },

  get: (id: string) => api.get<Envelope<Campaign>>(`/campaigns/${id}`),

  create: (data: { brief: Record<string, unknown>; brand_guidelines_id?: string; image_backend?: string }) =>
    api.post<Envelope<Campaign>>("/campaigns", data),

  update: (id: string, data: Record<string, unknown>) =>
    api.patch<Envelope<Campaign>>(`/campaigns/${id}`, data),

  delete: (id: string) => api.delete<void>(`/campaigns/${id}`),

  reprocess: (id: string) => api.post<Envelope<Campaign>>(`/campaigns/${id}/reprocess`),
};
