import type { RunArtifact } from "../../types/run";
import { artifactDescriptions, buildArtifactFacts } from "./artifactUtils";

export function ArtifactInspector({ artifact }: { artifact: RunArtifact }) {
  const facts = buildArtifactFacts(artifact);

  return (
    <aside className="artifact-inspector">
      <div className="artifact-inspector-card">
        <div className="artifact-inspector-label">类型</div>
        <div className="artifact-inspector-value">{artifact.kind}</div>
      </div>
      <div className="artifact-inspector-card artifact-inspector-card-wide">
        <div className="artifact-inspector-label">说明</div>
        <div className="artifact-inspector-value artifact-inspector-copy">{artifactDescriptions[artifact.kind]}</div>
      </div>
      <div className="artifact-inspector-card">
        <div className="artifact-inspector-label">行数</div>
        <div className="artifact-inspector-value">{facts.lineCount}</div>
      </div>
      <div className="artifact-inspector-card">
        <div className="artifact-inspector-label">字符数</div>
        <div className="artifact-inspector-value">{facts.charCount}</div>
      </div>
      <div className="artifact-inspector-card">
        <div className="artifact-inspector-label">JSON</div>
        <div className="artifact-inspector-value">{facts.hasJson ? "是" : "否"}</div>
      </div>
      <div className="artifact-inspector-card">
        <div className="artifact-inspector-label">顶层项</div>
        <div className="artifact-inspector-value">{facts.topLevelKeys || "-"}</div>
      </div>
    </aside>
  );
}
