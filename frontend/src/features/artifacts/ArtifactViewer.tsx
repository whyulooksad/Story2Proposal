import { useEffect, useMemo, useRef, useState } from "react";

import { useUiStore } from "../../stores/uiStore";
import type { RunArtifact, RunDetail } from "../../types/run";
import { ArtifactInspector } from "./ArtifactInspector";
import { BenchmarkArtifactView } from "./BenchmarkArtifactView";
import { ContractArtifactView } from "./ContractArtifactView";
import { EvaluationArtifactView } from "./EvaluationArtifactView";
import { buildArtifactMap, buildArtifactFacts } from "./artifactUtils";

function DefaultArtifactView({ artifact }: { artifact: RunArtifact }) {
  const facts = buildArtifactFacts(artifact);
  return <pre className="artifact-content artifact-content-main">{facts.preview}</pre>;
}

export function ArtifactViewer({ run }: { run: RunDetail }) {
  const activeArtifact = useUiStore((state) => state.activeArtifact);
  const setActiveArtifact = useUiStore((state) => state.setActiveArtifact);
  const previousContentsRef = useRef<Record<string, string>>({});
  const [changedKinds, setChangedKinds] = useState<string[]>([]);

  const artifact = useMemo(
    () => run.artifacts.find((item) => item.kind === activeArtifact) ?? run.artifacts[0],
    [activeArtifact, run.artifacts],
  );

  useEffect(() => {
    const previous = previousContentsRef.current;
    const next = buildArtifactMap(run.artifacts);
    const hasPreviousSnapshot = Object.keys(previous).length > 0;

    if (!hasPreviousSnapshot) {
      previousContentsRef.current = next;
      return;
    }

    const changed = run.artifacts
      .filter((item) => previous[item.kind] !== undefined && previous[item.kind] !== item.content)
      .map((item) => item.kind);

    if (changed.length) {
      setChangedKinds((current) => Array.from(new Set([...current, ...changed])));
    }

    previousContentsRef.current = next;
  }, [run.artifacts]);

  function handleSelect(kind: RunArtifact["kind"]) {
    setActiveArtifact(kind);
    setChangedKinds((current) => current.filter((item) => item !== kind));
  }

  return (
    <section className="panel artifact-panel">
      <div className="panel-header">
        <div>
          <h2>产物查看</h2>
          <div className="panel-kicker">{artifact.label}</div>
        </div>
        {run.status === "running" ? <div className="artifact-sync-note">运行中，仅高亮发生变化的产物</div> : null}
      </div>

      <div className="artifact-tabs">
        {run.artifacts.map((item) => {
          const changed = changedKinds.includes(item.kind);
          return (
            <button
              key={item.id}
              type="button"
              className={item.kind === activeArtifact ? "artifact-tab active" : changed ? "artifact-tab changed" : "artifact-tab"}
              onClick={() => handleSelect(item.kind)}
            >
              <span>{item.label}</span>
              {changed ? <span className="artifact-tab-badge">已更新</span> : null}
            </button>
          );
        })}
      </div>

      {changedKinds.includes(artifact.kind) ? <div className="artifact-change-banner">当前产物有新的内容写入。</div> : null}

      <div className="artifact-shell">
        <ArtifactInspector artifact={artifact} />

        {artifact.kind === "evaluation" ? (
          <EvaluationArtifactView content={artifact.content} />
        ) : artifact.kind === "benchmark" ? (
          <BenchmarkArtifactView content={artifact.content} />
        ) : artifact.kind === "contract" ? (
          <ContractArtifactView content={artifact.content} />
        ) : (
          <DefaultArtifactView artifact={artifact} />
        )}
      </div>
    </section>
  );
}
