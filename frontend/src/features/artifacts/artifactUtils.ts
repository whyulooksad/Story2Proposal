import type { RunArtifact } from "../../types/run";

export function buildArtifactMap(artifacts: RunArtifact[]): Record<string, string> {
  return Object.fromEntries(artifacts.map((artifact) => [artifact.kind, artifact.content]));
}

export function tryParseJson(content: string): unknown | null {
  try {
    return JSON.parse(content);
  } catch {
    return null;
  }
}

export function buildArtifactFacts(artifact: RunArtifact) {
  const content = artifact.content ?? "";
  const parsed = tryParseJson(content);
  const lineCount = content ? content.split(/\r?\n/).length : 0;
  const charCount = content.length;
  const hasJson = parsed !== null;

  let topLevelKeys = 0;
  let preview = content.trim();

  if (hasJson && parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
    topLevelKeys = Object.keys(parsed as Record<string, unknown>).length;
    preview = JSON.stringify(parsed, null, 2);
  } else if (hasJson && Array.isArray(parsed)) {
    topLevelKeys = parsed.length;
    preview = JSON.stringify(parsed, null, 2);
  }

  return {
    lineCount,
    charCount,
    hasJson,
    topLevelKeys,
    preview,
  };
}

export const artifactDescriptions: Record<RunArtifact["kind"], string> = {
  blueprint: "高层论文规划，定义章节顺序、依赖关系和 visual plan。",
  contract: "执行期约束，包含 claim、citation、visual 和 validation rule。",
  drafts: "各章节草稿与局部重写结果。",
  reviews: "各 evaluator 输出与 review controller 聚合结果。",
  manuscript: "最终渲染后的 manuscript。",
  evaluation: "整篇稿件的 rubric 评测结果。",
  benchmark: "单次 run 的 benchmark suite 与 baseline 对比。",
  logs: "运行状态、摘要与事件记录。",
};
