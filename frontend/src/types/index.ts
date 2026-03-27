// ── Material ──────────────────────────────────────────────────────────────────
export type MaterialStatus = "pending" | "transcribing" | "transcribed" | "verified";

export interface Material {
    id: number;
    title: string;
    filename: string;
    duration: number | null;
    status: MaterialStatus;
    created_at: string;
    audio_url: string;
}

export interface PaginatedMaterials {
    items: Material[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

// ── Subtitle ──────────────────────────────────────────────────────────────────
export interface Subtitle {
    id: number;
    material_id: number;
    seq: number;
    start_time: number;
    end_time: number;
    text: string;
    is_verified: boolean;
}

export interface SubtitleListResponse {
    material_id: number;
    subtitles: Subtitle[];
    total: number;
    verified_count: number;
}

export interface SubtitleUpdate {
    id: number;
    seq: number;
    start_time: number;
    end_time: number;
    text: string;
    is_verified: boolean;
}

// ── Task / SSE ────────────────────────────────────────────────────────────────
export interface TranscribeTask {
    task_id: string;
    material_id: number;
}

export interface TaskProgress {
    current: number;
    total: number;
    message: string;
    status: "pending" | "running" | "done" | "error";
}

// ── Practice ──────────────────────────────────────────────────────────────────
export interface PracticeSession {
    id: number;
    session_id: string;
    material_id: number;
    started_at: string;
    finished_at: string | null;
}

export interface DiffToken {
    word: string;
    status: "correct" | "wrong" | "missing";
}