import type { RunStatus } from "../../types/run";

const LABELS: Record<RunStatus, string> = {
  pending: "等待中",
  running: "运行中",
  stopping: "停止中",
  completed: "已完成",
  failed: "失败",
  stopped: "已停止",
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return <span className={`status-badge status-${status}`}>{LABELS[status]}</span>;
}
