"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { Button, Slider, Tooltip } from "antd";
import {
    PlayCircleOutlined, PauseCircleOutlined,
    RetweetOutlined, StepBackwardOutlined, StepForwardOutlined,
} from "@ant-design/icons";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.js";
import TimelinePlugin from "wavesurfer.js/dist/plugins/timeline.js";
import { useWaveStore } from "@/lib/stores/waveStore";
import { API_BASE } from "@/lib/api/client";

interface Props {
    audioUrl: string;
    onRegionSync?: (idx: number) => void;
}

// wider resize handle via injected style
const REGION_HANDLE_STYLE = `
  .wavesurfer-region .wavesurfer-handle {
    width: 10px !important;
    background: rgba(59,110,248,0.5) !important;
    border-radius: 3px !important;
    cursor: ew-resize !important;
  }
  .wavesurfer-region .wavesurfer-handle:hover {
    background: rgba(59,110,248,0.85) !important;
  }
`;

export function WaveformEditor({ audioUrl, onRegionSync }: Props) {
    const wsRef = useRef<WaveSurfer | null>(null);
    const regionsRef = useRef<RegionsPlugin | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [zoom, setZoom] = useState(100);

    const {
        subtitles, activeIdx, looping,
        setActiveIdx, setLooping, updateSubtitleTime,
    } = useWaveStore();

    const fmt = (s: number) => {
        const m = Math.floor(s / 60);
        const sec = (s % 60).toFixed(1);
        return `${m}:${sec.padStart(4, "0")}`;
    };

    // ── init ────────────────────────────────────────────────────────────────────
    useEffect(() => {
        if (!containerRef.current) return;

        // inject handle style once
        if (!document.getElementById("ws-handle-style")) {
            const s = document.createElement("style");
            s.id = "ws-handle-style";
            s.textContent = REGION_HANDLE_STYLE;
            document.head.appendChild(s);
        }

        const regions = RegionsPlugin.create();
        const timeline = TimelinePlugin.create({
            height: 20,
            timeInterval: 1,
            primaryLabelInterval: 5,
            style: { fontSize: "10px", color: "#94a3b8" },
        });

        const ws = WaveSurfer.create({
            container: containerRef.current,
            waveColor: "#bfdbfe",
            progressColor: "#3b6ef8",
            cursorColor: "#1d4ed8",
            cursorWidth: 2,
            height: "auto" as unknown as number,
            minPxPerSec: zoom,
            plugins: [regions, timeline],
            url: `${API_BASE}${audioUrl}`,
        });

        wsRef.current = ws;
        regionsRef.current = regions;

        ws.on("ready", () => {
            setDuration(ws.getDuration());
            renderRegions(regions);
        });

        ws.on("play", () => setIsPlaying(true));
        ws.on("pause", () => setIsPlaying(false));
        ws.on("finish", () => {
            setIsPlaying(false);
            const { looping, activeIdx, subtitles } = useWaveStore.getState();
            if (looping && activeIdx >= 0 && subtitles[activeIdx]) {
                ws.play(subtitles[activeIdx].start_time);
            }
        });

        ws.on("audioprocess", (t) => {
            setCurrentTime(t);

            // ── problem 3 fix: auto-activate subtitle matching current time ──
            const { subtitles, activeIdx } = useWaveStore.getState();
            const idx = subtitles.findIndex(
                (s) => t >= s.start_time && t <= s.end_time
            );
            if (idx >= 0 && idx !== activeIdx) {
                useWaveStore.getState().setActiveIdx(idx);
            }

            // loop check
            const { looping: l } = useWaveStore.getState();
            if (l && activeIdx >= 0 && subtitles[activeIdx]) {
                if (t >= subtitles[activeIdx].end_time) {
                    ws.seekTo(subtitles[activeIdx].start_time / ws.getDuration());
                }
            }
        });

        ws.on("interaction", (t) => {
            const { subtitles } = useWaveStore.getState();
            const idx = subtitles.findIndex(
                (s) => t >= s.start_time && t <= s.end_time
            );
            if (idx >= 0) {
                useWaveStore.getState().setActiveIdx(idx);
                ws.seekTo(t / ws.getDuration());
            }
        });

        return () => { ws.destroy(); wsRef.current = null; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [audioUrl]);

    // ── render regions ──────────────────────────────────────────────────────────
    const renderRegions = useCallback((regions: RegionsPlugin) => {
        regions.clearRegions();
        const { subtitles, activeIdx } = useWaveStore.getState();

        subtitles.forEach((sub, i) => {
            const r = regions.addRegion({
                id: `sub-${i}`,
                start: sub.start_time,
                end: sub.end_time,
                color: i === activeIdx
                    ? "rgba(59,110,248,0.20)"
                    : "rgba(59,110,248,0.06)",
                drag: false,
                resize: true,
            });

            // real-time drag sync
            r.on("update", () => {
                updateSubtitleTime(i, "start_time", parseFloat(r.start.toFixed(3)));
                updateSubtitleTime(i, "end_time", parseFloat(r.end.toFixed(3)));
                onRegionSync?.(i);
            });

            r.on("click", (e) => {
                e.stopPropagation();
                activateRow(i);
            });
        });
    }, [updateSubtitleTime, onRegionSync]); // eslint-disable-line

    // re-render when subtitles change
    useEffect(() => {
        if (!regionsRef.current || subtitles.length === 0) return;
        renderRegions(regionsRef.current);
    }, [subtitles, renderRegions]);

    // highlight active region
    useEffect(() => {
        regionsRef.current?.getRegions().forEach((r, i) => {
            r.setOptions({
                color: i === activeIdx
                    ? "rgba(59,110,248,0.20)"
                    : "rgba(59,110,248,0.06)",
            });
        });
    }, [activeIdx]);

    // zoom
    useEffect(() => {
        const ws = wsRef.current;
        if (!ws) return;

        const applyZoom = () => ws.zoom(zoom);

        if (ws.isReady) {
            // already loaded
            applyZoom();
        } else {
            // wait for ready event
            ws.once("ready", applyZoom);
        }

        // cleanup
        return () => {
            ws.un("ready", applyZoom); // in case component unmounts
        };
    }, [zoom]);

    const activateRow = useCallback((idx: number) => {
        const { subtitles } = useWaveStore.getState();
        useWaveStore.getState().setActiveIdx(idx);
        const sub = subtitles[idx];
        if (sub && wsRef.current) {
            wsRef.current.seekTo(sub.start_time / wsRef.current.getDuration());
            wsRef.current.play(sub.start_time, sub.end_time);
        }
    }, []);

    // ── expose syncRegion for SubtitleList ────────────────────────────────────
    const syncRegion = useCallback((idx: number) => {
        const sub = useWaveStore.getState().subtitles[idx];
        if (!sub || !regionsRef.current) return;
        const r = regionsRef.current.getRegions().find((r) => r.id === `sub-${idx}`);
        r?.setOptions({ start: sub.start_time, end: sub.end_time });
    }, []);

    // expose via custom event so SubtitleList can call it
    useEffect(() => {
        const handler = (e: CustomEvent) => syncRegion(e.detail);
        window.addEventListener("syncRegion" as any, handler);
        return () => window.removeEventListener("syncRegion" as any, handler);
    }, [syncRegion]);

    // ── keyboard ────────────────────────────────────────────────────────────────
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            const ws = wsRef.current;
            if (!ws) return;
            const inInput = ["INPUT", "TEXTAREA"].includes((e.target as HTMLElement).tagName);
            const { activeIdx, subtitles } = useWaveStore.getState();

            if (e.key === " " && !inInput) {
                e.preventDefault(); ws.playPause();
            }
            if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && !inInput) {
                e.preventDefault();
                const next = activeIdx + (e.key === "ArrowLeft" ? -1 : 1);
                if (next >= 0 && next < subtitles.length) activateRow(next);
            }
            if (e.key === "[" && !inInput && activeIdx >= 0) {
                e.preventDefault();
                const t = parseFloat(ws.getCurrentTime().toFixed(3));
                updateSubtitleTime(activeIdx, "start_time", t);
                syncRegion(activeIdx);
            }
            if (e.key === "]" && !inInput && activeIdx >= 0) {
                e.preventDefault();
                const t = parseFloat(ws.getCurrentTime().toFixed(3));
                updateSubtitleTime(activeIdx, "end_time", t);
                syncRegion(activeIdx);
            }
            if (e.key === "r" && !inInput) {
                setLooping(!useWaveStore.getState().looping);
            }
            if (e.key === "Tab" && !inInput && activeIdx >= 0) {
                e.preventDefault();
                useWaveStore.getState().setVerified(activeIdx, true);
                const next = activeIdx + 1;
                if (next < subtitles.length) activateRow(next);
            }
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [activateRow, syncRegion, updateSubtitleTime, setLooping]);

    return (
        <div
            className="flex-shrink-0 flex flex-col gap-3 px-6 py-4"
            style={{
                background: "var(--surface)",
                borderBottom: "1px solid var(--border)",
                boxShadow: "0 2px 8px rgba(30,42,69,.04)",
            }}
        >
            {/* controls row */}
            <div className="flex items-center gap-3">
                {/* playback */}
                <div className="flex items-center gap-1.5">
                    <Tooltip title="上一句 ←">
                        <Button
                            size="small" shape="circle" icon={<StepBackwardOutlined />}
                            onClick={() => {
                                const { activeIdx, subtitles } = useWaveStore.getState();
                                if (activeIdx > 0) activateRow(activeIdx - 1);
                            }}
                        />
                    </Tooltip>

                    <Button
                        type="primary" shape="circle"
                        className="!w-9 !h-9 flex items-center justify-center"
                        icon={isPlaying
                            ? <PauseCircleOutlined className="text-lg" />
                            : <PlayCircleOutlined className="text-lg" />
                        }
                        onClick={() => wsRef.current?.playPause()}
                    />

                    <Tooltip title="下一句 →">
                        <Button
                            size="small" shape="circle" icon={<StepForwardOutlined />}
                            onClick={() => {
                                const { activeIdx, subtitles } = useWaveStore.getState();
                                if (activeIdx < subtitles.length - 1) activateRow(activeIdx + 1);
                            }}
                        />
                    </Tooltip>
                </div>

                {/* time */}
                <span className="text-xs tabular-nums text-[var(--text-2)] w-28">
                    {fmt(currentTime)} / {fmt(duration)}
                </span>

                {/* loop */}
                <Tooltip title="循环当前句 R">
                    <Button
                        size="small"
                        icon={<RetweetOutlined />}
                        type={looping ? "primary" : "default"}
                        onClick={() => setLooping(!looping)}
                        className={looping ? "" : "!text-[var(--text-3)]"}
                    >
                        循环
                    </Button>
                </Tooltip>

                {/* zoom */}
                <div className="flex items-center gap-2 ml-auto">
                    <span className="text-xs text-[var(--text-3)]">缩放</span>
                    <Slider
                        min={50} max={1200} value={zoom} step={10}
                        style={{ width: 110 }}
                        onChange={setZoom}
                        tooltip={{ formatter: (v) => `${v}px/s` }}
                    />
                </div>

                {/* kbd hints */}
                <div className="hidden xl:flex items-center gap-2 text-[var(--text-3)]">
                    {[
                        ["Space", "播放"],
                        ["[ ]", "打点"],
                        ["Tab", "校验+下一句"],
                    ].map(([k, v]) => (
                        <span key={k} className="text-xs flex items-center gap-1">
                            <kbd className="bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded text-[10px] font-mono border border-gray-200">
                                {k}
                            </kbd>
                            {v}
                        </span>
                    ))}
                </div>
            </div>

            {/* waveform */}
            <div
                className="rounded-xl overflow-hidden border border-[var(--border)]"
                style={{ height: 130, background: "var(--surface2)" }}
                ref={containerRef}
            />
        </div>
    );
}