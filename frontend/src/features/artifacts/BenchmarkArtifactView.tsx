import type { BenchmarkPayload } from "./artifactTypes";
import { tryParseJson } from "./artifactUtils";

export function BenchmarkArtifactView({ content }: { content: string }) {
  const parsed = tryParseJson(content) as BenchmarkPayload | null;
  if (!parsed || !parsed.candidates) {
    return <pre className="artifact-content artifact-content-main">{content}</pre>;
  }

  return (
    <div className="evaluation-report">
      <section className="evaluation-hero">
        <div className="evaluation-score">
          <span>Winner</span>
          <strong>{parsed.winner_candidate_id ?? "-"}</strong>
        </div>
        <div className="evaluation-lists">
          <div className="evaluation-list">
            <div className="evaluation-list-title">Benchmark</div>
            <div>{parsed.benchmark_name ?? "未标注"}</div>
            <div>{parsed.protocol_version ?? "未标注"}</div>
          </div>
          <div className="evaluation-list">
            <div className="evaluation-list-title">摘要</div>
            {parsed.summary?.length ? parsed.summary.map((item) => <div key={item}>{item}</div>) : <div>暂无</div>}
          </div>
        </div>
      </section>

      <section className="evaluation-grid">
        {parsed.candidates.map((candidate) => (
          <article className="evaluation-card" key={candidate.candidate_id}>
            <div className="evaluation-card-top">
              <div>
                <div className="evaluation-card-title">{candidate.label}</div>
                <div className="contract-list-subtle">{candidate.candidate_id}</div>
              </div>
              <div className={candidate.candidate_id === parsed.winner_candidate_id ? "evaluation-badge passed" : "evaluation-badge risk"}>
                {candidate.report.overall_score}
              </div>
            </div>
            <div className="evaluation-evidence">
              <div>source={candidate.source}</div>
              {candidate.candidate_id === parsed.primary_candidate_id ? <div>primary candidate</div> : null}
            </div>
          </article>
        ))}
      </section>

      <section className="evaluation-actions">
        <div className="evaluation-list-title">对比结果</div>
        {parsed.comparisons?.length ? (
          parsed.comparisons.map((comparison) => (
            <div className="evaluation-criterion" key={`${comparison.candidate_id}-${comparison.baseline_id}`}>
              <div className="evaluation-criterion-top">
                <span>
                  {comparison.candidate_id} vs {comparison.baseline_id}
                </span>
                <span className={comparison.overall_delta >= 0 ? "evaluation-criterion-pass" : "evaluation-criterion-fail"}>
                  {comparison.overall_delta >= 0 ? `+${comparison.overall_delta}` : comparison.overall_delta}
                </span>
              </div>
              {comparison.summary?.length ? (
                <div className="evaluation-criterion-evidence">
                  {comparison.summary.map((item) => (
                    <div key={item}>{item}</div>
                  ))}
                </div>
              ) : null}
            </div>
          ))
        ) : (
          <div>暂无</div>
        )}
      </section>
    </div>
  );
}
