import { useEffect, useMemo, useState } from "react";

import type {
  ArtifactSeed,
  ExperimentSpec,
  ReferenceSpec,
  ResearchStory,
} from "../../types/story";

type StoryWorkbenchProps = {
  stories: ResearchStory[];
  onSave: (story: ResearchStory) => Promise<void>;
  onRun: (story: ResearchStory) => Promise<void>;
};

type StoryMetadata = {
  target_venue: string;
  writing_language: string;
  paper_type: string;
  domain: string;
  expected_sections: string[];
  keywords: string[];
  notes: string;
};

const DEFAULT_METADATA: StoryMetadata = {
  target_venue: "",
  writing_language: "en",
  paper_type: "",
  domain: "",
  expected_sections: [],
  keywords: [],
  notes: "",
};

function createEmptyExperiment(index = 1): ExperimentSpec {
  return {
    experiment_id: `exp_${index}`,
    name: "",
    setup: "",
    dataset: "",
    metrics: [],
    result_summary: "",
  };
}

function createEmptyAsset(index = 1): ArtifactSeed {
  return {
    artifact_id: `fig_${index}`,
    kind: "figure",
    title: "",
    description: "",
    target_sections: [],
  };
}

function createEmptyReference(index = 1): ReferenceSpec {
  return {
    reference_id: `ref_${index}`,
    title: "",
    authors: [],
    year: null,
    venue: null,
    notes: null,
  };
}

function createEmptyStory(): ResearchStory {
  return {
    story_id: "new_story",
    title_hint: "",
    topic: "",
    problem_statement: "",
    motivation: "",
    core_idea: "",
    method_summary: "",
    contributions: [],
    experiments: [createEmptyExperiment()],
    baselines: [],
    findings: [],
    limitations: [],
    references: [createEmptyReference()],
    assets: [createEmptyAsset()],
    metadata: { ...DEFAULT_METADATA },
  };
}

function toText(value: string[]): string {
  return value.join("\n");
}

function fromText(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeMetadata(metadata: ResearchStory["metadata"]): StoryMetadata {
  return {
    target_venue: typeof metadata.target_venue === "string" ? metadata.target_venue : "",
    writing_language: typeof metadata.writing_language === "string" ? metadata.writing_language : "en",
    paper_type: typeof metadata.paper_type === "string" ? metadata.paper_type : "",
    domain: typeof metadata.domain === "string" ? metadata.domain : "",
    expected_sections: Array.isArray(metadata.expected_sections)
      ? metadata.expected_sections.map(String).filter(Boolean)
      : [],
    keywords: Array.isArray(metadata.keywords) ? metadata.keywords.map(String).filter(Boolean) : [],
    notes: typeof metadata.notes === "string" ? metadata.notes : "",
  };
}

export function StoryWorkbench({ stories, onSave, onRun }: StoryWorkbenchProps) {
  const [selectedId, setSelectedId] = useState<string>(stories[0]?.story_id ?? "new_story");
  const [story, setStory] = useState<ResearchStory>(stories[0] ?? createEmptyStory());

  const selectedStory = useMemo(
    () => stories.find((item) => item.story_id === selectedId) ?? null,
    [selectedId, stories],
  );
  const metadata = useMemo(() => normalizeMetadata(story.metadata), [story.metadata]);

  useEffect(() => {
    if (!stories.length) {
      return;
    }
    if (selectedId === "new_story") {
      return;
    }
    if (!selectedStory) {
      setSelectedId(stories[0].story_id);
      setStory(stories[0]);
    }
  }, [selectedId, selectedStory, stories]);

  function syncStory(nextId: string) {
    setSelectedId(nextId);
    const next = stories.find((item) => item.story_id === nextId);
    setStory(next ?? createEmptyStory());
  }

  function patch<K extends keyof ResearchStory>(key: K, value: ResearchStory[K]) {
    setStory((current) => ({ ...current, [key]: value }));
  }

  function patchMetadata<K extends keyof StoryMetadata>(key: K, value: StoryMetadata[K]) {
    setStory((current) => ({
      ...current,
      metadata: {
        ...normalizeMetadata(current.metadata),
        [key]: value,
      },
    }));
  }

  function patchExperiment(index: number, next: ExperimentSpec) {
    setStory((current) => ({
      ...current,
      experiments: current.experiments.map((item, i) => (i === index ? next : item)),
    }));
  }

  function removeExperiment(index: number) {
    setStory((current) => ({
      ...current,
      experiments:
        current.experiments.length > 1
          ? current.experiments.filter((_, i) => i !== index)
          : [createEmptyExperiment()],
    }));
  }

  function patchReference(index: number, next: ReferenceSpec) {
    setStory((current) => ({
      ...current,
      references: current.references.map((item, i) => (i === index ? next : item)),
    }));
  }

  function removeReference(index: number) {
    setStory((current) => ({
      ...current,
      references:
        current.references.length > 1
          ? current.references.filter((_, i) => i !== index)
          : [createEmptyReference()],
    }));
  }

  function patchAsset(index: number, next: ArtifactSeed) {
    setStory((current) => ({
      ...current,
      assets: current.assets.map((item, i) => (i === index ? next : item)),
    }));
  }

  function removeAsset(index: number) {
    setStory((current) => ({
      ...current,
      assets: current.assets.length > 1 ? current.assets.filter((_, i) => i !== index) : [createEmptyAsset()],
    }));
  }

  async function handleImportFile(file: File | null) {
    if (!file) {
      return;
    }
    const text = await file.text();
    const parsed = JSON.parse(text) as ResearchStory;
    setStory({
      ...parsed,
      metadata: normalizeMetadata(parsed.metadata),
      references: parsed.references.length ? parsed.references : [createEmptyReference()],
      experiments: parsed.experiments.length ? parsed.experiments : [createEmptyExperiment()],
      assets: parsed.assets.length ? parsed.assets : [createEmptyAsset()],
    });
    setSelectedId(parsed.story_id);
  }

  return (
    <div className="story-shell">
      <aside className="story-shell-side">
        <section className="panel">
          <div className="panel-header">
            <h2>Story 列表</h2>
          </div>
          <div className="story-list-stack">
            {stories.map((item) => (
              <button
                key={item.story_id}
                type="button"
                className={item.story_id === selectedId ? "story-list-item active" : "story-list-item"}
                onClick={() => syncStory(item.story_id)}
              >
                <span className="story-list-title">{item.title_hint || item.story_id}</span>
                <span className="story-list-meta">{item.story_id}</span>
              </button>
            ))}
            <button
              type="button"
              className={selectedId === "new_story" ? "story-list-item active" : "story-list-item"}
              onClick={() => syncStory("new_story")}
            >
              <span className="story-list-title">新建 Story</span>
              <span className="story-list-meta">ResearchStory</span>
            </button>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header">
            <h2>当前概览</h2>
          </div>
          <div className="story-glance">
            <div className="story-glance-row">
              <span>Story ID</span>
              <strong>{story.story_id || "-"}</strong>
            </div>
            <div className="story-glance-row">
              <span>标题</span>
              <strong>{story.title_hint || "-"}</strong>
            </div>
            <div className="story-glance-row">
              <span>主题</span>
              <strong>{story.topic || "-"}</strong>
            </div>
            <div className="story-glance-row">
              <span>实验</span>
              <strong>{story.experiments.length}</strong>
            </div>
            <div className="story-glance-row">
              <span>参考文献</span>
              <strong>{story.references.length}</strong>
            </div>
            <div className="story-glance-row">
              <span>图表资产</span>
              <strong>{story.assets.length}</strong>
            </div>
          </div>
        </section>
      </aside>

      <section className="panel story-editor-panel">
        <div className="story-editor-top">
          <div>
            <div className="eyebrow">Editor</div>
            <h2>ResearchStory 编辑</h2>
          </div>
          <div className="story-editor-actions">
            <label className="ghost-button file-button">
              导入 JSON
              <input
                type="file"
                accept="application/json"
                hidden
                onChange={(event) => {
                  void handleImportFile(event.target.files?.[0] ?? null);
                }}
              />
            </label>
            <button className="ghost-button" type="button" onClick={() => void onSave(story)}>
              保存 Story
            </button>
            <button className="primary-button" type="button" onClick={() => void onRun(story)}>
              创建 Run
            </button>
          </div>
        </div>

        <div className="form-grid story-form-grid">
          <label className="field">
            <span>故事 ID</span>
            <input value={story.story_id} onChange={(e) => patch("story_id", e.target.value)} />
          </label>
          <label className="field">
            <span>标题提示</span>
            <input value={story.title_hint ?? ""} onChange={(e) => patch("title_hint", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>研究主题</span>
            <input value={story.topic} onChange={(e) => patch("topic", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>问题陈述</span>
            <textarea value={story.problem_statement} onChange={(e) => patch("problem_statement", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>研究动机</span>
            <textarea value={story.motivation} onChange={(e) => patch("motivation", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>核心思路</span>
            <textarea value={story.core_idea} onChange={(e) => patch("core_idea", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>方法概述</span>
            <textarea value={story.method_summary} onChange={(e) => patch("method_summary", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>主要贡献</span>
            <textarea
              value={toText(story.contributions)}
              onChange={(e) => patch("contributions", fromText(e.target.value))}
            />
          </label>
          <label className="field field-wide">
            <span>对比基线</span>
            <textarea value={toText(story.baselines)} onChange={(e) => patch("baselines", fromText(e.target.value))} />
          </label>
          <label className="field field-wide">
            <span>核心发现</span>
            <textarea value={toText(story.findings)} onChange={(e) => patch("findings", fromText(e.target.value))} />
          </label>
          <label className="field field-wide">
            <span>局限性</span>
            <textarea
              value={toText(story.limitations)}
              onChange={(e) => patch("limitations", fromText(e.target.value))}
            />
          </label>
        </div>

        <section className="nested-panel">
          <div className="panel-header">
            <h2>实验设计</h2>
            <button
              className="ghost-button"
              type="button"
              onClick={() => patch("experiments", [...story.experiments, createEmptyExperiment(story.experiments.length + 1)])}
            >
              新增实验
            </button>
          </div>
          <div className="nested-grid">
            {story.experiments.map((experiment, index) => (
              <div className="nested-card" key={`${experiment.experiment_id}-${index}`}>
                <div className="nested-card-head">
                  <strong>实验 {index + 1}</strong>
                  <button className="ghost-button compact-button" type="button" onClick={() => removeExperiment(index)}>
                    删除
                  </button>
                </div>
                <label className="field">
                  <span>实验 ID</span>
                  <input
                    value={experiment.experiment_id}
                    onChange={(e) => patchExperiment(index, { ...experiment, experiment_id: e.target.value })}
                  />
                </label>
                <label className="field">
                  <span>实验名称</span>
                  <input value={experiment.name} onChange={(e) => patchExperiment(index, { ...experiment, name: e.target.value })} />
                </label>
                <label className="field field-wide">
                  <span>实验设置</span>
                  <textarea value={experiment.setup} onChange={(e) => patchExperiment(index, { ...experiment, setup: e.target.value })} />
                </label>
                <label className="field">
                  <span>数据集</span>
                  <input
                    value={experiment.dataset}
                    onChange={(e) => patchExperiment(index, { ...experiment, dataset: e.target.value })}
                  />
                </label>
                <label className="field">
                  <span>评价指标</span>
                  <input
                    value={experiment.metrics.join(", ")}
                    onChange={(e) =>
                      patchExperiment(index, {
                        ...experiment,
                        metrics: e.target.value.split(",").map((item) => item.trim()).filter(Boolean),
                      })
                    }
                  />
                </label>
                <label className="field field-wide">
                  <span>结果摘要</span>
                  <textarea
                    value={experiment.result_summary}
                    onChange={(e) => patchExperiment(index, { ...experiment, result_summary: e.target.value })}
                  />
                </label>
              </div>
            ))}
          </div>
        </section>

        <section className="nested-panel">
          <div className="panel-header">
            <h2>参考文献</h2>
            <button
              className="ghost-button"
              type="button"
              onClick={() => patch("references", [...story.references, createEmptyReference(story.references.length + 1)])}
            >
              新增 reference
            </button>
          </div>
          <div className="nested-grid">
            {story.references.map((reference, index) => (
              <div className="nested-card" key={`${reference.reference_id}-${index}`}>
                <div className="nested-card-head">
                  <strong>Reference {index + 1}</strong>
                  <button className="ghost-button compact-button" type="button" onClick={() => removeReference(index)}>
                    删除
                  </button>
                </div>
                <label className="field">
                  <span>文献 ID</span>
                  <input
                    value={reference.reference_id}
                    onChange={(e) => patchReference(index, { ...reference, reference_id: e.target.value })}
                  />
                </label>
                <label className="field">
                  <span>年份</span>
                  <input
                    value={reference.year ?? ""}
                    onChange={(e) =>
                      patchReference(index, {
                        ...reference,
                        year: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                  />
                </label>
                <label className="field field-wide">
                  <span>标题</span>
                  <input
                    value={reference.title}
                    onChange={(e) => patchReference(index, { ...reference, title: e.target.value })}
                  />
                </label>
                <label className="field field-wide">
                  <span>作者</span>
                  <input
                    value={reference.authors.join(", ")}
                    onChange={(e) =>
                      patchReference(index, {
                        ...reference,
                        authors: e.target.value.split(",").map((item) => item.trim()).filter(Boolean),
                      })
                    }
                  />
                </label>
                <label className="field">
                  <span>期刊 / 会议</span>
                  <input
                    value={reference.venue ?? ""}
                    onChange={(e) =>
                      patchReference(index, {
                        ...reference,
                        venue: e.target.value || null,
                      })
                    }
                  />
                </label>
                <label className="field field-wide">
                  <span>备注</span>
                  <textarea
                    value={reference.notes ?? ""}
                    onChange={(e) =>
                      patchReference(index, {
                        ...reference,
                        notes: e.target.value || null,
                      })
                    }
                  />
                </label>
              </div>
            ))}
          </div>
        </section>

        <section className="nested-panel">
          <div className="panel-header">
            <h2>图表资产</h2>
            <button
              className="ghost-button"
              type="button"
              onClick={() => patch("assets", [...story.assets, createEmptyAsset(story.assets.length + 1)])}
            >
              新增 asset
            </button>
          </div>
          <div className="nested-grid">
            {story.assets.map((asset, index) => (
              <div className="nested-card" key={`${asset.artifact_id}-${index}`}>
                <div className="nested-card-head">
                  <strong>Asset {index + 1}</strong>
                  <button className="ghost-button compact-button" type="button" onClick={() => removeAsset(index)}>
                    删除
                  </button>
                </div>
                <label className="field">
                  <span>资产 ID</span>
                  <input
                    value={asset.artifact_id}
                    onChange={(e) => patchAsset(index, { ...asset, artifact_id: e.target.value })}
                  />
                </label>
                <label className="field">
                  <span>类型</span>
                  <input value={asset.kind} onChange={(e) => patchAsset(index, { ...asset, kind: e.target.value })} />
                </label>
                <label className="field field-wide">
                  <span>标题</span>
                  <input value={asset.title} onChange={(e) => patchAsset(index, { ...asset, title: e.target.value })} />
                </label>
                <label className="field field-wide">
                  <span>描述</span>
                  <textarea
                    value={asset.description}
                    onChange={(e) => patchAsset(index, { ...asset, description: e.target.value })}
                  />
                </label>
                <label className="field field-wide">
                  <span>目标章节</span>
                  <input
                    value={asset.target_sections.join(", ")}
                    onChange={(e) =>
                      patchAsset(index, {
                        ...asset,
                        target_sections: e.target.value.split(",").map((item) => item.trim()).filter(Boolean),
                      })
                    }
                  />
                </label>
              </div>
            ))}
          </div>
        </section>

        <section className="nested-panel">
          <div className="panel-header">
            <h2>元数据</h2>
          </div>
          <div className="form-grid metadata-grid">
            <label className="field">
              <span>目标期刊 / 会议</span>
              <input
                value={metadata.target_venue}
                onChange={(e) => patchMetadata("target_venue", e.target.value)}
              />
            </label>
            <label className="field">
              <span>写作语言</span>
              <select
                className="story-select"
                value={metadata.writing_language}
                onChange={(e) => patchMetadata("writing_language", e.target.value)}
              >
                <option value="en">English</option>
                <option value="zh">中文</option>
              </select>
            </label>
            <label className="field">
              <span>论文类型</span>
              <input value={metadata.paper_type} onChange={(e) => patchMetadata("paper_type", e.target.value)} />
            </label>
            <label className="field">
              <span>研究领域</span>
              <input value={metadata.domain} onChange={(e) => patchMetadata("domain", e.target.value)} />
            </label>
            <label className="field field-wide">
              <span>预期章节</span>
              <textarea
                value={toText(metadata.expected_sections)}
                onChange={(e) => patchMetadata("expected_sections", fromText(e.target.value))}
              />
            </label>
            <label className="field field-wide">
              <span>关键词</span>
              <textarea
                value={toText(metadata.keywords)}
                onChange={(e) => patchMetadata("keywords", fromText(e.target.value))}
              />
            </label>
            <label className="field field-wide">
              <span>附加说明</span>
              <textarea value={metadata.notes} onChange={(e) => patchMetadata("notes", e.target.value)} />
            </label>
          </div>
        </section>
      </section>

      <aside className="story-shell-preview">
        <section className="panel story-preview-panel">
          <div className="panel-header">
            <h2>结构预览</h2>
            <div className="panel-kicker">{selectedStory ? selectedStory.story_id : "new_story"}</div>
          </div>
          <pre className="artifact-content compact-tall">{JSON.stringify(story, null, 2)}</pre>
        </section>
      </aside>
    </div>
  );
}
