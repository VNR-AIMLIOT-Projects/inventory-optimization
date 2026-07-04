import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, buildUrl } from "@shared/routes";

// GET /api/simulation/state
export function useSimulationState() {
  return useQuery({
    queryKey: [api.simulation.state.path],
    queryFn: async () => {
      const res = await fetch(api.simulation.state.path);
      if (!res.ok) throw new Error("Failed to fetch simulation state");
      return api.simulation.state.responses[200].parse(await res.json());
    },
    // Poll every 2 seconds to keep dashboard alive without manual refresh
    refetchInterval: 2000, 
  });
}

// POST /api/simulation/reset
export function useResetSimulation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await fetch(api.simulation.reset.path, {
        method: api.simulation.reset.method,
      });
      if (!res.ok) throw new Error("Failed to reset simulation");
      return api.simulation.reset.responses[200].parse(await res.json());
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [api.simulation.state.path] });
      queryClient.invalidateQueries({ queryKey: [api.stats.get.path] });
    },
  });
}

// POST /api/simulation/step
export function useStepSimulation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (action?: number) => {
      const res = await fetch(api.simulation.nextStep.path, {
        method: api.simulation.nextStep.method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (!res.ok) throw new Error("Failed to advance simulation");
      return api.simulation.nextStep.responses[200].parse(await res.json());
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [api.simulation.state.path] });
      queryClient.invalidateQueries({ queryKey: [api.stats.get.path] });
    },
  });
}

// GET /api/stats
export function useStats() {
  return useQuery({
    queryKey: [api.stats.get.path],
    queryFn: async () => {
      const res = await fetch(api.stats.get.path);
      if (!res.ok) throw new Error("Failed to fetch stats");
      return api.stats.get.responses[200].parse(await res.json());
    },
    refetchInterval: 5000,
  });
}
