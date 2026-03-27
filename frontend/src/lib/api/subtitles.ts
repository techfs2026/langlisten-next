import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { SubtitleListResponse, SubtitleUpdate } from "@/types";

export const subtitleKeys = {
    byMaterial: (materialId: number) =>
        ["subtitles", materialId] as const,
};

export function useSubtitles(materialId: number) {
    return useQuery({
        queryKey: subtitleKeys.byMaterial(materialId),
        queryFn: async () => {
            const res = await apiClient.get<SubtitleListResponse>(
                `/api/admin/materials/${materialId}/subtitles`
            );
            return res.data;
        },
        enabled: !!materialId,
    });
}

export function useSaveSubtitles(materialId: number) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (subtitles: SubtitleUpdate[]) => {
            const res = await apiClient.put<SubtitleListResponse>(
                `/api/admin/materials/${materialId}/subtitles`,
                { subtitles }
            );
            return res.data;
        },
        onSuccess: (data) => {
            // update cache directly without refetch
            qc.setQueryData(subtitleKeys.byMaterial(materialId), data);
        },
    });
}