import { useMemo } from "react";

import { useUiStore } from "../../stores/uiStore";
import type { RunDetail } from "../../types/run";

export function ArtifactViewer({ run }: { run: RunDetail }) {
  const activeArtifact = useUiStore((state) => state.activeArtifact);
  const setActiveArtifact = useUiStore((state) => state.setActiveArtifact);

  const artifact = useMemo(
    () => run.artifacts.find((item) => item.kind === activeArtifact) ?? run.artifacts[0],
    [activeArtifact, run.artifacts],
  );

  return (
    <section className="panel artifact-panel">
      <div className="panel-header">
        <h2>产物查看</h2>
        <div className="panel-kicker">{artifact.label}</div>
      </div>
      <div className="artifact-tabs">
        {run.artifacts.map((item) => (
          <button
            key={item.id}
            type="button"
            className={item.kind === activeArtifact ? "artifact-tab active" : "artifact-tab"}
            onClick={() => setActiveArtifact(item.kind)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <pre className="artifact-content artifact-content-main">{artifact.content}</pre>
    </section>
  );
}
