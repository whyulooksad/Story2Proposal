import { useQuery } from "@tanstack/react-query";

import { RunTable } from "../features/runs/RunTable";
import { listRuns } from "../services/runs";

export function RunsPage() {
  const { data = [] } = useQuery({
    queryKey: ["runs"],
    queryFn: listRuns,
  });

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Run Index</div>
          <h1>运行列表</h1>
        </div>
      </div>
      <RunTable runs={data} />
    </div>
  );
}
