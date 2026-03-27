"use client";

import { useEffect, useRef, useState } from "react";
import { Progress, Alert } from "antd";
import { API_BASE } from "@/lib/api/client";
import type { TaskProgress } from "@/types";

interface Props {
    taskId: string;
    onDone: () => void;
}

export function TranscribeProgress({ taskId, onDone }: Props) {
    const [progress, setProgress] = useState<TaskProgress>({
        current: 0,
        total: 100,
        message: "等待任务开始...",
        status: "pending",
    });
    const esRef = useRef<EventSource | null>(null);

    useEffect(() => {
        const es = new EventSource(
            `${API_BASE}/api/admin/tasks/${taskId}/progress`
        );
        esRef.current = es;

        es.onmessage = (e) => {
            const data: TaskProgress = JSON.parse(e.data);
            setProgress(data);

            if (data.status === "done" || data.status === "error") {
                es.close();
                if (data.status === "done") {
                    // slight delay so user sees 100%
                    setTimeout(onDone, 800);
                }
            }
        };

        es.onerror = () => {
            es.close();
            setProgress((p) => ({
                ...p,
                status: "error",
                message: "连接中断，请刷新页面",
            }));
        };

        return () => es.close();
    }, [taskId, onDone]);

    const pct =
        progress.total > 0
            ? Math.round((progress.current / progress.total) * 100)
            : 0;

    const status =
        progress.status === "error"
            ? "exception"
            : progress.status === "done"
                ? "success"
                : "active";

    return (
        <div className="space-y-2">
            <Progress percent={pct} status={status} size="small" />
            <p className="text-xs text-gray-500">{progress.message}</p>
            {progress.status === "error" && (
                <Alert
                    type="error"
                    message={progress.message}
                    showIcon
                    className="text-xs"
                />
            )}
        </div>
    );
}