import { api } from "./client";
import type { Asset, Envelope, PaginatedEnvelope } from "./types";

export const assetApi = {
  listByCampaign: (campaignId: string, params?: { locale?: string; aspect_ratio?: string }) => {
    const query = new URLSearchParams();
    if (params?.locale) query.set("locale", params.locale);
    if (params?.aspect_ratio) query.set("aspect_ratio", params.aspect_ratio);
    const qs = query.toString();
    return api.get<PaginatedEnvelope<Asset>>(`/campaigns/${campaignId}/assets${qs ? `?${qs}` : ""}`);
  },

  get: (id: string) => api.get<Envelope<Asset>>(`/assets/${id}`),

  downloadUrl: (id: string) => `/api/v1/assets/${id}/download`,
};
