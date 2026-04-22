import type { RunDetail } from "../../types/run";

export function EventLogPanel({ run }: { run: RunDetail }) {
  const logArtifact = run.artifacts.find((item) => item.kind === "logs");

  return (
    <section className="panel log-panel">
      <div className="panel-header">
        <h2>事件日志</h2>
      </div>
      <pre className="artifact-content compact">{logArtifact?.content ?? "暂时还没有事件。"}</pre>
    </section>
  );
}
