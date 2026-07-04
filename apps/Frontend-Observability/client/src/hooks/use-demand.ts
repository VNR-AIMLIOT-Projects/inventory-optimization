import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@shared/routes";

// GET /api/demand — returns list of demand uploads (metadata, not raw data)
export function useDemandUploads() {
  return useQuery({
    queryKey: [api.demand.list.path],
    queryFn: async () => {
      const res = await fetch(api.demand.list.path);
      if (!res.ok) throw new Error("Failed to fetch demand uploads");
      return api.demand.list.responses[200].parse(await res.json());
    },
  });
}

// POST /api/demand/upload — uploads file, stores path in DB
export function useUploadDemand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append('file', file);

      const res = await fetch(api.demand.upload.path, {
        method: api.demand.upload.method,
        body: form,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ message: "Upload failed" }));
        throw new Error(err.message || "Failed to upload demand data");
      }
      
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [api.demand.list.path] });
    },
  });
}
