import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { campaignApi } from "../api/campaigns";

export function useCampaigns(params?: { status?: string }) {
  return useQuery({
    queryKey: ["campaigns", params],
    queryFn: () => campaignApi.list(params),
  });
}

export function useCampaign(id: string) {
  return useQuery({
    queryKey: ["campaign", id],
    queryFn: () => campaignApi.get(id),
    enabled: !!id,
  });
}

export function useCreateCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: campaignApi.create,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["campaigns"] }),
  });
}

export function useDeleteCampaign() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => campaignApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["campaigns"] }),
  });
}
