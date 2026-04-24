import type { SectionState } from "../../types/run";

const sectionStatusLabels: Record<SectionState["status"], string> = {
  pending: "待处理",
  writing: "写作中",
  review: "评审中",
  approved: "已通过",
  revise: "待重写",
  manual_review: "人工复核",
};

export function SectionStatusList({ sections }: { sections: SectionState[] }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>章节状态</h2>
      </div>
      <div className="section-list">
        {sections.length ? (
          sections.map((section) => (
            <div className="section-row" key={section.id}>
              <div>
                <div className="section-title">{section.title}</div>
                <div className="section-subtle">{section.id}</div>
              </div>
              <div className="section-right">
                <span className={`section-state state-${section.status}`}>
                  {sectionStatusLabels[section.status] ?? section.status}
                </span>
                <span className="section-rewrite">重写 {section.rewriteCount} 次</span>
              </div>
            </div>
          ))
        ) : (
          <div className="section-row">
            <div className="section-subtle">当前还没有章节状态。</div>
          </div>
        )}
      </div>
    </section>
  );
}
