import { Link } from "react-router-dom";

import type { RunItem } from "../../types/run";
import { RunStatusBadge } from "./RunStatusBadge";

interface RunTableProps {
  busyRunId?: string | null;
  onDelete: (runId: string) => void;
  onStop: (runId: string) => void;
  runs: RunItem[];
}

export function RunTable({ runs, onStop, onDelete, busyRunId }: RunTableProps) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h2>运行列表</h2>
      </div>
      {runs.length ? (
        <table className="data-table">
          <thead>
            <tr>
              <th>Run</th>
              <th>Story</th>
              <th>模型</th>
              <th>状态</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => {
              const isBusy = busyRunId === run.id;
              const canStop = run.status === "running";
              const canDelete = run.status !== "running" && run.status !== "stopping";

              return (
                <tr key={run.id}>
                  <td>
                    <Link to={`/runs/${run.id}`} className="inline-link">
                      {run.id}
                    </Link>
                  </td>
                  <td>{run.storyId}</td>
                  <td>{run.model}</td>
                  <td>
                    <RunStatusBadge status={run.status} />
                  </td>
                  <td>{run.updatedAt}</td>
                  <td>
                    <div className="table-actions">
                      {canStop ? (
                        <button
                          type="button"
                          className="ghost-button table-action-button"
                          onClick={() => onStop(run.id)}
                          disabled={isBusy}
                        >
                          停止
                        </button>
                      ) : null}
                      {canDelete ? (
                        <button
                          type="button"
                          className="danger-button table-action-button"
                          onClick={() => onDelete(run.id)}
                          disabled={isBusy}
                        >
                          删除
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <div className="home-list-subtle">还没有运行记录。</div>
      )}
    </div>
  );
}
