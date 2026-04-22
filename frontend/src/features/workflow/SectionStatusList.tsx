import type { SectionState } from "../../types/run";

export function SectionStatusList({ sections }: { sections: SectionState[] }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>章节状态</h2>
      </div>
      <div className="section-list">
        {sections.map((section) => (
          <div className="section-row" key={section.id}>
            <div>
              <div className="section-title">{section.title}</div>
              <div className="section-subtle">{section.id}</div>
            </div>
            <div className="section-right">
              <span className={`section-state state-${section.status}`}>{section.status}</span>
              <span className="section-rewrite">重写 {section.rewriteCount} 次</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
