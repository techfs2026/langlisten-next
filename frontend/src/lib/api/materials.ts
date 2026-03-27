import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
    Material,
    PaginatedMaterials,
    TranscribeTask,
} from "@/types";

// ── query keys ────────────────────────────────────────────────────────────────
export const materialKeys = {
    all: ["materials"] as const,
    list: (page: number, pageSize: number) =>
        ["materials", "list", page, pageSize] as const,
    detail: (id: number) => ["materials", id] as const,
};

// ── hooks ─────────────────────────────────────────────────────────────────────
export function useMaterials(page = 1, pageSize = 20) {
    return useQuery({
        queryKey: materialKeys.list(page, pageSize),
        queryFn: async () => {
            const res = await apiClient.get<PaginatedMaterials>(
                "/api/admin/materials",
                { params: { page, page_size: pageSize } }
            );
            return res.data;
        },
    });
}

export function useMaterial(id: number) {
    return useQuery({
        queryKey: materialKeys.detail(id),
        queryFn: async () => {
            const res = await apiClient.get<Material>(`/api/admin/materials/${id}`);
            return res.data;
        },
        enabled: !!id,
    });
}

export function useUploadMaterial() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({
            file,
            title,
        }: {
            file: File;
            title: string;
        }) => {
            const fd = new FormData();
            fd.append("file", file);
            fd.append("title", title);
            const res = await apiClient.post<Material>("/api/admin/materials", fd);
            return res.data;
        },
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: materialKeys.all });
        },
    });
}

export function useDeleteMaterial() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            await apiClient.delete(`/api/admin/materials/${id}`);
        },
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: materialKeys.all });
        },
    });
}

export function useTriggerTranscribe() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({
            materialId,
            language = "en",
        }: {
            materialId: number;
            language?: string;
        }) => {
            const res = await apiClient.post<TranscribeTask>(
                `/api/admin/materials/${materialId}/transcribe`,
                null,
                { params: { language } }
            );
            return res.data;
        },
        onSuccess: (_, { materialId }) => {
            qc.invalidateQueries({ queryKey: materialKeys.detail(materialId) });
        },
    });
}