import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { ArtifactViewer } from "../features/artifacts/ArtifactViewer";
import { EventLogPanel } from "../features/logs/EventLogPanel";
import { RunStatusBadge } from "../features/runs/RunStatusBadge";
import { SectionStatusList } from "../features/workflow/SectionStatusList";
import { WorkflowPanel } from "../features/workflow/WorkflowPanel";
import { getRunDetail } from "../services/runs";

const reviewCheckLabels: Record<string, string> = {
  section_coverage: "章节覆盖",
  visual_references: "图表引用",
  citation_hygiene: "引用卫生",
  data_fidelity: "数据忠实性",
  traceability: "可追踪性",
};

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRunDetail(runId),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const run = query.state.data;
      if (!runId || !run) {
        return false;
      }
      return run.status === "running" ? 2500 : false;
    },
    refetchIntervalInBackground: true,
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
    data.status === "running" ? (isFetching ? "同步中" : "自动轮询中") : "已停止轮询";

  return (
    <div className="page-stack">
      <section className="run-hero">
        <div className="run-hero-copy">
          <div className="eyebrow">Run</div>
          <h1>{data.id}</h1>
          <p>{data.storyId}</p>
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
                <span>渲染警告</span>
                <strong>{data.overview.renderWarningCount}</strong>
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
    </div>
  );
}
