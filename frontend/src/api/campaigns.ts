import { api } from "./client";
import type {
  Campaign,
  CampaignCreate,
  Envelope,
  PaginatedEnvelope,
} from "./types";

export const campaignApi = {
  list: (params?: {
    status?: string;
    backend?: string;
    page?: number;
    per_page?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.backend) query.set("backend", params.backend);
    if (params?.page) query.set("page", String(params.page));
    if (params?.per_page) query.set("per_page", String(params.per_page));
    const qs = query.toString();
    return api.get<PaginatedEnvelope<Campaign>>(`/campaigns${qs ? `?${qs}` : ""}`);
  },

  get: (id: string) => api.get<Envelope<Campaign>>(`/campaigns/${id}`),

  create: (data: CampaignCreate) =>
    api.post<Envelope<Campaign>>("/campaigns", data),

  update: (id: string, data: Record<string, unknown>) =>
    api.patch<Envelope<Campaign>>(`/campaigns/${id}`, data),

  delete: (id: string) => api.delete<void>(`/campaigns/${id}`),

  reprocess: (id: string) => api.post<Envelope<Campaign>>(`/campaigns/${id}/reprocess`),
};
