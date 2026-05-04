import { useQuery } from "@tanstack/react-query";
import { fetchAggregateMetrics, fetchCampaignMetrics } from "../api/metrics";
import type { DateRangeParams } from "../api/types";

export function useCampaignMetrics(campaignId: string | null) {
  return useQuery({
    queryKey: ["campaignMetrics", campaignId],
    queryFn: () => fetchCampaignMetrics(campaignId!),
    enabled: !!campaignId,
  });
}

export function useAggregateMetrics(params?: DateRangeParams) {
  return useQuery({
    queryKey: ["aggregateMetrics", params],
    queryFn: () => fetchAggregateMetrics(params),
  });
}
