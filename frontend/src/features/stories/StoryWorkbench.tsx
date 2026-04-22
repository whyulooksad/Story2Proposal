import { useMemo, useState } from "react";

import type { StoryDraft } from "../../types/story";

type StoryWorkbenchProps = {
  stories: StoryDraft[];
  onSave: (draft: StoryDraft) => Promise<void>;
  onRun: (draft: StoryDraft) => Promise<void>;
};

function createEmptyDraft(): StoryDraft {
  return {
    id: "new_story",
    title: "",
    topic: "",
    updatedAt: "",
    summary: "",
    problem: "",
    motivation: "",
    method: "",
    contributions: "",
    experiments: "",
    findings: "",
    limitations: "",
  };
}

export function StoryWorkbench({ stories, onSave, onRun }: StoryWorkbenchProps) {
  const [selectedId, setSelectedId] = useState<string>(stories[0]?.id ?? "new_story");
  const [draft, setDraft] = useState<StoryDraft>(stories[0] ?? createEmptyDraft());

  const selectedStory = useMemo(
    () => stories.find((item) => item.id === selectedId) ?? null,
    [selectedId, stories],
  );

  function syncDraft(nextId: string) {
    setSelectedId(nextId);
    const next = stories.find((item) => item.id === nextId);
    setDraft(next ?? createEmptyDraft());
  }

  function handleFieldChange<K extends keyof StoryDraft>(key: K, value: StoryDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function handleImportFile(file: File | null) {
    if (!file) {
      return;
    }
    const text = await file.text();
    const parsed = JSON.parse(text) as Partial<StoryDraft>;
    setDraft({
      ...createEmptyDraft(),
      ...parsed,
      id: parsed.id ?? parsed.title?.toLowerCase().replace(/\s+/g, "_") ?? "imported_story",
      title: parsed.title ?? "Imported Story",
      topic: parsed.topic ?? "",
      summary: parsed.summary ?? "",
      updatedAt: "",
      problem: parsed.problem ?? "",
      motivation: parsed.motivation ?? "",
      method: parsed.method ?? "",
      contributions: parsed.contributions ?? "",
      experiments: parsed.experiments ?? "",
      findings: parsed.findings ?? "",
      limitations: parsed.limitations ?? "",
    });
    setSelectedId("imported_story");
  }

  return (
    <div className="story-shell">
      <aside className="story-shell-side">
        <section className="panel">
          <div className="panel-header">
            <h2>Story 列表</h2>
          </div>
          <div className="story-list-stack">
            {stories.map((story) => (
              <button
                key={story.id}
                type="button"
                className={story.id === selectedId ? "story-list-item active" : "story-list-item"}
                onClick={() => syncDraft(story.id)}
              >
                <span className="story-list-title">{story.title}</span>
                <span className="story-list-meta">{story.updatedAt || "未保存"}</span>
              </button>
            ))}
            <button
              type="button"
              className={selectedId === "new_story" ? "story-list-item active" : "story-list-item"}
              onClick={() => syncDraft("new_story")}
            >
              <span className="story-list-title">新建 Story</span>
              <span className="story-list-meta">从空白开始</span>
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
              <strong>{draft.id || "-"}</strong>
            </div>
            <div className="story-glance-row">
              <span>标题</span>
              <strong>{draft.title || "-"}</strong>
            </div>
            <div className="story-glance-row">
              <span>主题</span>
              <strong>{draft.topic || "-"}</strong>
            </div>
            <div className="story-glance-row">
              <span>最近更新</span>
              <strong>{selectedStory?.updatedAt || "未保存"}</strong>
            </div>
          </div>
        </section>
      </aside>

      <section className="panel story-editor-panel">
        <div className="story-editor-top">
          <div>
            <div className="eyebrow">Editor</div>
            <h2>Story 编辑</h2>
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
            <button className="ghost-button" type="button" onClick={() => void onSave(draft)}>
              保存 Story
            </button>
            <button className="primary-button" type="button" onClick={() => void onRun(draft)}>
              创建 Run
            </button>
          </div>
        </div>

        <div className="form-grid story-form-grid">
          <label className="field">
            <span>Story ID</span>
            <input value={draft.id} onChange={(e) => handleFieldChange("id", e.target.value)} />
          </label>
          <label className="field">
            <span>标题</span>
            <input value={draft.title} onChange={(e) => handleFieldChange("title", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>主题</span>
            <input value={draft.topic} onChange={(e) => handleFieldChange("topic", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>摘要</span>
            <textarea value={draft.summary} onChange={(e) => handleFieldChange("summary", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>问题定义</span>
            <textarea value={draft.problem} onChange={(e) => handleFieldChange("problem", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>动机</span>
            <textarea value={draft.motivation} onChange={(e) => handleFieldChange("motivation", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>方法</span>
            <textarea value={draft.method} onChange={(e) => handleFieldChange("method", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>贡献</span>
            <textarea value={draft.contributions} onChange={(e) => handleFieldChange("contributions", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>实验</span>
            <textarea value={draft.experiments} onChange={(e) => handleFieldChange("experiments", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>结论与发现</span>
            <textarea value={draft.findings} onChange={(e) => handleFieldChange("findings", e.target.value)} />
          </label>
          <label className="field field-wide">
            <span>局限性</span>
            <textarea value={draft.limitations} onChange={(e) => handleFieldChange("limitations", e.target.value)} />
          </label>
        </div>
      </section>

      <aside className="story-shell-preview">
        <section className="panel story-preview-panel">
          <div className="panel-header">
            <h2>结构预览</h2>
            <div className="panel-kicker">{selectedStory?.updatedAt ? `最近更新：${selectedStory.updatedAt}` : "未保存"}</div>
          </div>
          <pre className="artifact-content compact-tall">{JSON.stringify(draft, null, 2)}</pre>
        </section>
      </aside>
    </div>
  );
}
