import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type InsertDemandData } from "@shared/routes"; // Note: Importing types from schema normally, but relying on route logic here

// GET /api/demand
export function useDemandData() {
  return useQuery({
    queryKey: [api.demand.list.path],
    queryFn: async () => {
      const res = await fetch(api.demand.list.path);
      if (!res.ok) throw new Error("Failed to fetch demand data");
      return api.demand.list.responses[200].parse(await res.json());
    },
  });
}

// POST /api/demand/upload
export function useUploadDemand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: any[]) => { // Using any[] here as simplified input, but in reality would match schema
       // We need to validate strictly before sending if possible, but for bulk upload we often trust the parser
      const res = await fetch(api.demand.upload.path, {
        method: api.demand.upload.method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        if (res.status === 400) throw new Error("Invalid data format");
        throw new Error("Failed to upload demand data");
      }
      
      return api.demand.upload.responses[201].parse(await res.json());
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [api.demand.list.path] });
    },
  });
}
