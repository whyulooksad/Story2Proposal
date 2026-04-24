import { dimensionLabels, type EvaluationPayload } from "./artifactTypes";
import { tryParseJson } from "./artifactUtils";

export function EvaluationArtifactView({ content }: { content: string }) {
  const parsed = tryParseJson(content) as EvaluationPayload | null;
  if (!parsed || !parsed.dimensions) {
    return <pre className="artifact-content artifact-content-main">{content}</pre>;
  }

  return (
    <div className="evaluation-report">
      <section className="evaluation-hero">
        <div className="evaluation-score">
          <span>总分</span>
          <strong>{parsed.overall_score ?? "-"}</strong>
        </div>
        <div className="evaluation-lists">
          <div className="evaluation-list">
            <div className="evaluation-list-title">评测协议</div>
            <div>{parsed.protocol_version ?? "未标注"}</div>
          </div>
          <div className="evaluation-list">
            <div className="evaluation-list-title">优势</div>
            {parsed.strengths?.length ? parsed.strengths.map((item) => <div key={item}>{item}</div>) : <div>暂无</div>}
          </div>
          <div className="evaluation-list">
            <div className="evaluation-list-title">风险</div>
            {parsed.risks?.length ? parsed.risks.map((item) => <div key={item}>{item}</div>) : <div>暂无</div>}
          </div>
        </div>
      </section>

      <section className="evaluation-grid">
        {parsed.dimensions.map((dimension) => (
          <article className="evaluation-card" key={dimension.name}>
            <div className="evaluation-card-top">
              <div className="evaluation-card-title">{dimensionLabels[dimension.name] ?? dimension.name}</div>
              <div className={dimension.passed ? "evaluation-badge passed" : "evaluation-badge risk"}>
                {dimension.score}
              </div>
            </div>

            <div className="evaluation-evidence">
              {dimension.evidence?.length ? (
                dimension.evidence.map((item) => <div key={item}>{item}</div>)
              ) : (
                <div>暂无摘要证据</div>
              )}
            </div>

            <div className="evaluation-criteria">
              {(dimension.criteria ?? []).map((criterion) => (
                <div className="evaluation-criterion" key={criterion.criterion_id}>
                  <div className="evaluation-criterion-top">
                    <span>{criterion.label}</span>
                    <span className={criterion.passed ? "evaluation-criterion-pass" : "evaluation-criterion-fail"}>
                      {criterion.passed ? "通过" : "未通过"}
                    </span>
                  </div>
                  {criterion.evidence?.length ? (
                    <div className="evaluation-criterion-evidence">
                      {criterion.evidence.map((item) => (
                        <div key={item}>{item}</div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>

      <section className="evaluation-actions">
        <div className="evaluation-list-title">建议动作</div>
        {parsed.recommended_actions?.length ? (
          parsed.recommended_actions.map((item) => <div key={item}>{item}</div>)
        ) : (
          <div>暂无</div>
        )}
      </section>
    </div>
  );
}
