import { create } from "zustand";
import type { Subtitle } from "@/types";

interface WaveState {
    subtitles: Subtitle[];
    activeIdx: number;
    looping: boolean;

    // actions
    setSubtitles: (subtitles: Subtitle[]) => void;
    setActiveIdx: (idx: number) => void;
    setLooping: (v: boolean) => void;
    updateSubtitleTime: (
        idx: number,
        field: "start_time" | "end_time",
        value: number
    ) => void;
    updateSubtitleText: (idx: number, text: string) => void;
    setVerified: (idx: number, verified: boolean) => void;
    reset: () => void;
}

export const useWaveStore = create<WaveState>((set) => ({
    subtitles: [],
    activeIdx: -1,
    looping: false,

    setSubtitles: (subtitles) => set({ subtitles, activeIdx: -1 }),

    setActiveIdx: (activeIdx) => set({ activeIdx }),

    setLooping: (looping) => set({ looping }),

    updateSubtitleTime: (idx, field, value) =>
        set((state) => {
            const subtitles = [...state.subtitles];
            subtitles[idx] = { ...subtitles[idx], [field]: value };
            return { subtitles };
        }),

    updateSubtitleText: (idx, text) =>
        set((state) => {
            const subtitles = [...state.subtitles];
            subtitles[idx] = { ...subtitles[idx], text };
            return { subtitles };
        }),

    setVerified: (idx, is_verified) =>
        set((state) => {
            const subtitles = [...state.subtitles];
            subtitles[idx] = { ...subtitles[idx], is_verified };
            return { subtitles };
        }),

    reset: () => set({ subtitles: [], activeIdx: -1, looping: false }),
}));