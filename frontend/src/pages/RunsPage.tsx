import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { RunTable } from "../features/runs/RunTable";
import { deleteRun, listRuns, stopRun } from "../services/runs";

export function RunsPage() {
  const queryClient = useQueryClient();
  const [confirmDeleteRunId, setConfirmDeleteRunId] = useState<string | null>(null);

  const { data = [] } = useQuery({
    queryKey: ["runs"],
    queryFn: listRuns,
    refetchInterval: (query) => {
      const runs = query.state.data ?? [];
      return runs.some((run) => run.status === "running" || run.status === "stopping") ? 2500 : false;
    },
    refetchIntervalInBackground: true,
  });

  const stopMutation = useMutation({
    mutationFn: stopRun,
    onSuccess: (run) => {
      queryClient.setQueryData(["runs"], (previous: typeof data | undefined) =>
        previous?.map((item) => (item.id === run.id ? { ...item, status: run.status, updatedAt: run.updatedAt } : item)) ?? previous,
      );
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
      void queryClient.invalidateQueries({ queryKey: ["run", run.id] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteRun,
    onSuccess: () => {
      setConfirmDeleteRunId(null);
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  const busyRunId =
    (stopMutation.isPending ? stopMutation.variables : null) ??
    (deleteMutation.isPending ? deleteMutation.variables : null);

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Run Index</div>
          <h1>运行列表</h1>
        </div>
      </div>

      {stopMutation.error ? <div className="inline-error">停止失败：{stopMutation.error.message}</div> : null}
      {deleteMutation.error ? <div className="inline-error">删除失败：{deleteMutation.error.message}</div> : null}

      <RunTable
        runs={data}
        busyRunId={busyRunId}
        onStop={(runId) => stopMutation.mutate(runId)}
        onDelete={(runId) => setConfirmDeleteRunId(runId)}
      />

      <ConfirmDialog
        open={confirmDeleteRunId !== null}
        title="删除 Run"
        body={confirmDeleteRunId ? `确定删除这个 Run 吗？\n\n${confirmDeleteRunId}` : ""}
        confirmLabel="确认删除"
        onCancel={() => setConfirmDeleteRunId(null)}
        onConfirm={() => {
          if (confirmDeleteRunId) {
            deleteMutation.mutate(confirmDeleteRunId);
          }
        }}
      />
    </div>
  );
}
