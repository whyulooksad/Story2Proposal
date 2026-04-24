import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { ArtifactViewer } from "../features/artifacts/ArtifactViewer";
import { EventLogPanel } from "../features/logs/EventLogPanel";
import { RunStatusBadge } from "../features/runs/RunStatusBadge";
import { SectionStatusList } from "../features/workflow/SectionStatusList";
import { WorkflowPanel } from "../features/workflow/WorkflowPanel";
import { deleteRun, getRunDetail, stopRun } from "../services/runs";

const reviewCheckLabels: Record<string, string> = {
  section_coverage: "章节覆盖",
  visual_references: "图表引用",
  citation_hygiene: "引用规范",
  data_fidelity: "数据忠实性",
  traceability: "可追踪性",
};

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRunDetail(runId),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const run = query.state.data;
      if (!runId || !run) {
        return false;
      }
      return run.status === "running" || run.status === "stopping" ? 2500 : false;
    },
    refetchIntervalInBackground: true,
  });

  const stopMutation = useMutation({
    mutationFn: stopRun,
    onSuccess: (run) => {
      queryClient.setQueryData(["run", run.id], run);
      void queryClient.invalidateQueries({ queryKey: ["runs"] });
      void queryClient.invalidateQueries({ queryKey: ["run", run.id] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteRun,
    onSuccess: async () => {
      setConfirmDeleteOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["runs"] });
      queryClient.removeQueries({ queryKey: ["run", runId] });
      navigate("/runs");
    },
  });

  if (isLoading) {
    return (
      <div className="page-stack">
        <section className="run-hero">
          <div className="run-hero-copy">
            <div className="eyebrow">Run</div>
            <h1>加载中</h1>
            <p>正在读取运行详情。</p>
          </div>
        </section>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="page-stack">
        <section className="run-hero">
          <div className="run-hero-copy">
            <div className="eyebrow">Run</div>
            <h1>未找到 Run</h1>
            <p>{runId}</p>
          </div>
        </section>
      </div>
    );
  }

  const refreshStatus =
    data.status === "running" || data.status === "stopping"
      ? isFetching
        ? "同步中"
        : "自动轮询中"
      : "已停止轮询";
  const canStop = data.status === "running";
  const canDelete = data.status !== "running" && data.status !== "stopping";

  return (
    <div className="page-stack">
      <section className="run-hero">
        <div className="run-hero-copy">
          <div className="eyebrow">Run</div>
          <h1>{data.id}</h1>
          <p>{data.storyId}</p>
        </div>
        <div className="run-hero-actions">
          {canStop ? (
            <button
              type="button"
              className="ghost-button"
              onClick={() => stopMutation.mutate(data.id)}
              disabled={stopMutation.isPending}
            >
              终止 Run
            </button>
          ) : null}
          {canDelete ? (
            <button
              type="button"
              className="danger-button"
              onClick={() => setConfirmDeleteOpen(true)}
              disabled={deleteMutation.isPending}
            >
              删除 Run
            </button>
          ) : null}
        </div>
        <div className="run-hero-meta">
          <div className="run-chip">
            <span>状态</span>
            <RunStatusBadge status={data.status} />
          </div>
          <div className="run-chip">
            <span>模型</span>
            <strong>{data.model}</strong>
          </div>
          <div className="run-chip">
            <span>当前章节</span>
            <strong>{data.currentSectionId ?? "-"}</strong>
          </div>
          <div className="run-chip">
            <span>下一节点</span>
            <strong>{data.nextNode ?? "-"}</strong>
          </div>
          <div className="run-chip">
            <span>刷新状态</span>
            <strong>{refreshStatus}</strong>
          </div>
          <div className="run-chip">
            <span>更新时间</span>
            <strong>{data.updatedAt}</strong>
          </div>
        </div>
      </section>

      {stopMutation.error ? <div className="inline-error">停止失败：{stopMutation.error.message}</div> : null}
      {deleteMutation.error ? <div className="inline-error">删除失败：{deleteMutation.error.message}</div> : null}

      {data.error ? (
        <section className="panel">
          <div className="panel-header">
            <h2>失败原因</h2>
          </div>
          <pre className="artifact-content compact">{data.error}</pre>
        </section>
      ) : null}

      <div className="run-shell">
        <aside className="run-shell-side">
          <section className="panel">
            <div className="panel-header">
              <h2>运行概览</h2>
            </div>
            <div className="summary-grid">
              <div className="summary-card">
                <span>最终状态</span>
                <strong>{data.overview.finalStatus}</strong>
              </div>
              <div className="summary-card">
                <span>Contract 状态</span>
                <strong>{data.overview.contractState}</strong>
              </div>
              <div className="summary-card">
                <span>已完成章节</span>
                <strong>{data.overview.completedSections}</strong>
              </div>
              <div className="summary-card">
                <span>待处理章节</span>
                <strong>{data.overview.pendingSections}</strong>
              </div>
              <div className="summary-card">
                <span>人工复核</span>
                <strong>{data.overview.manualReviewCount}</strong>
              </div>
              <div className="summary-card">
                <span>流程警告</span>
                <strong>{data.overview.workflowWarningCount}</strong>
              </div>
              <div className="summary-card summary-card-wide">
                <span>评测总分</span>
                <strong>{data.overview.evaluationOverallScore ?? "-"}</strong>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <h2>最近一次评审</h2>
            </div>
            <div className="summary-grid">
              <div className="summary-card">
                <span>评审结论</span>
                <strong>{data.latestReview.status ?? "-"}</strong>
              </div>
              <div className="summary-card">
                <span>下一动作</span>
                <strong>{data.latestReview.nextAction ?? "-"}</strong>
              </div>
              <div className="summary-card">
                <span>问题数量</span>
                <strong>{data.latestReview.issueCount}</strong>
              </div>
              <div className="summary-card">
                <span>Patch 数量</span>
                <strong>{data.latestReview.patchCount}</strong>
              </div>
            </div>
            <div className="review-checks">
              {Object.entries(data.latestReview.deterministicChecks).length ? (
                Object.entries(data.latestReview.deterministicChecks).map(([key, issues]) => (
                  <div className="review-check-item" key={key}>
                    <div className="review-check-label">{reviewCheckLabels[key] ?? key}</div>
                    <div className="review-check-value">{issues.length ? `${issues.length} 个问题` : "通过"}</div>
                  </div>
                ))
              ) : (
                <div className="section-subtle">当前还没有聚合评审结果。</div>
              )}
            </div>
          </section>

          <SectionStatusList sections={data.sections} />
          <EventLogPanel run={data} />
        </aside>

        <section className="run-shell-main">
          <WorkflowPanel run={data} />
          <ArtifactViewer run={data} />
        </section>
      </div>

      <ConfirmDialog
        open={confirmDeleteOpen}
        title="删除 Run"
        body={`确定删除这个 Run 吗？\n\n${data.id}`}
        confirmLabel="确认删除"
        onCancel={() => setConfirmDeleteOpen(false)}
        onConfirm={() => deleteMutation.mutate(data.id)}
      />
    </div>
  );
}
