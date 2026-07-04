import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, buildUrl } from "@shared/routes";

// GET /api/decisions/pending
export function usePendingDecisions() {
  return useQuery({
    queryKey: [api.decisions.listPending.path],
    queryFn: async () => {
      const res = await fetch(api.decisions.listPending.path);
      if (!res.ok) throw new Error("Failed to fetch pending decisions");
      return api.decisions.listPending.responses[200].parse(await res.json());
    },
    refetchInterval: 2000, // Frequent polling for real-time feel
  });
}

// POST /api/decisions/:id/review
export function useReviewDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, status, overrideValue }: { id: number, status: "approved" | "rejected" | "overridden", overrideValue?: number }) => {
      const url = buildUrl(api.decisions.review.path, { id });
      const res = await fetch(url, {
        method: api.decisions.review.method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, overrideValue }),
      });
      
      if (!res.ok) {
        if (res.status === 404) throw new Error("Decision not found");
        throw new Error("Failed to review decision");
      }
      
      return api.decisions.review.responses[200].parse(await res.json());
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [api.decisions.listPending.path] });
      queryClient.invalidateQueries({ queryKey: [api.simulation.state.path] });
    },
  });
}
