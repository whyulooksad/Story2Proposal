import { Link } from "react-router-dom";

import type { RunItem } from "../../types/run";
import { RunStatusBadge } from "./RunStatusBadge";

export function RunTable({ runs }: { runs: RunItem[] }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h2>运行列表</h2>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Run</th>
            <th>Story</th>
            <th>模型</th>
            <th>状态</th>
            <th>更新时间</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
