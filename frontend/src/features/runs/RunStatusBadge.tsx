import type { RunStatus } from "../../types/run";

const labelMap: Record<RunStatus, string> = {
  pending: "等待中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return <span className={`status-badge status-${status}`}>{labelMap[status]}</span>;
}
