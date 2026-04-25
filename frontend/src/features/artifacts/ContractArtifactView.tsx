import type { ContractPayload } from "./artifactTypes";
import { tryParseJson } from "./artifactUtils";

function renderInlineList(items?: string[], emptyLabel = "暂无") {
  if (!items?.length) {
    return <span className="contract-empty-inline">{emptyLabel}</span>;
  }

  return (
    <div className="contract-inline-list">
      {items.map((item) => (
        <span key={item}>{item}</span>
      ))}
    </div>
  );
}

function buildRunFileUrl(runId: string, filePath: string) {
  return `/api/runs/${encodeURIComponent(runId)}/file?path=${encodeURIComponent(filePath)}`;
}

export function ContractArtifactView({ content, runId }: { content: string; runId: string }) {
  const parsed = tryParseJson(content) as ContractPayload | null;
  if (!parsed || !parsed.sections) {
    return <pre className="artifact-content artifact-content-main">{content}</pre>;
  }

  const sections = parsed.sections ?? [];
  const visuals = parsed.visuals ?? [];
  const citations = parsed.citations ?? [];
  const rules = parsed.validation_rules ?? [];
  const revisions = parsed.revision_log ?? [];
  const warnings = parsed.global_status?.warnings ?? [];
  const completedSections = parsed.global_status?.completed_sections?.length ?? 0;
  const pendingSections = parsed.global_status?.pending_sections?.length ?? 0;

  return (
    <div className="contract-report">
      <section className="contract-hero">
        <div className="contract-hero-main">
          <div className="contract-eyebrow">Manuscript Contract</div>
          <h3>{parsed.paper_title || "未命名论文"}</h3>
          <div className="contract-hero-meta">
            <span>版本 {parsed.version ?? "-"}</span>
            <span>状态 {parsed.global_status?.state ?? "-"}</span>
            <span>当前章节 {parsed.global_status?.current_section_id ?? "无"}</span>
            <span>输出语言 {parsed.style_guide?.output_language ?? "-"}</span>
            <span>语气 {parsed.style_guide?.tone ?? "-"}</span>
            <span>引用风格 {parsed.style_guide?.citation_style ?? "-"}</span>
            <span>目标 venue {parsed.target_venue ?? "未设置"}</span>
          </div>
        </div>

        <div className="contract-stat-grid">
          <article className="contract-stat-card">
            <span>章节</span>
            <strong>{sections.length}</strong>
          </article>
          <article className="contract-stat-card">
            <span>Visual</span>
            <strong>{visuals.length}</strong>
          </article>
          <article className="contract-stat-card">
            <span>Citation</span>
            <strong>{citations.length}</strong>
          </article>
          <article className="contract-stat-card">
            <span>规则</span>
            <strong>{rules.length}</strong>
          </article>
          <article className="contract-stat-card">
            <span>已完成章节</span>
            <strong>{completedSections}</strong>
          </article>
          <article className="contract-stat-card">
            <span>待完成章节</span>
            <strong>{pendingSections}</strong>
          </article>
        </div>
      </section>

      <section className="contract-grid">
        <article className="contract-card contract-card-wide">
          <div className="contract-card-head">
            <h4>章节约束</h4>
            <span>{sections.length} 个 section</span>
          </div>
          <div className="contract-section-grid">
            {sections.map((section) => (
              <article className="contract-section-card" key={section.section_id}>
                <div className="contract-section-top">
                  <div>
                    <div className="contract-section-title">{section.title}</div>
                    <div className="contract-section-id">{section.section_id}</div>
                  </div>
                  <span className="contract-chip">{section.status ?? "pending"}</span>
                </div>
                {section.purpose ? <p className="contract-section-purpose">{section.purpose}</p> : null}
                <div className="contract-mini-grid">
                  <div>
                    <span>Claims</span>
                    <strong>{section.required_claim_ids?.length ?? 0}</strong>
                  </div>
                  <div>
                    <span>Evidence</span>
                    <strong>{section.required_evidence_ids?.length ?? 0}</strong>
                  </div>
                  <div>
                    <span>Visuals</span>
                    <strong>{section.required_visual_ids?.length ?? 0}</strong>
                  </div>
                  <div>
                    <span>Citations</span>
                    <strong>{section.required_citation_ids?.length ?? 0}</strong>
                  </div>
                </div>
                {section.source_story_fields?.length ? renderInlineList(section.source_story_fields) : null}
                {section.depends_on_sections?.length ? (
                  <div className="contract-card-note">依赖：{section.depends_on_sections.join("、")}</div>
                ) : null}
              </article>
            ))}
          </div>
        </article>

        <article className="contract-card">
          <div className="contract-card-head">
            <h4>Visual Registry</h4>
            <span>{visuals.length} 项</span>
          </div>
          <div className="contract-list">
            {visuals.length ? (
              visuals.map((visual) => {
                const previewPath = visual.thumbnail_path || visual.rendered_path;
                const previewUrl = previewPath ? buildRunFileUrl(runId, previewPath) : null;
                const objectCount = visual.object_map?.length ?? 0;
                return (
                  <div className="contract-list-item contract-visual-item" key={visual.artifact_id}>
                    <div className="contract-list-title">{visual.label ?? visual.artifact_id}</div>
                    <div className="contract-list-subtle">
                      {visual.kind ?? "visual"} · {visual.semantic_role ?? "未说明角色"}
                    </div>
                    <div className="contract-list-subtle">
                      {visual.placement_constraint ?? "unspecified"} · {visual.render_status ?? "planned"}
                    </div>
                    <div className="contract-list-subtle">
                      materialization：{visual.materialization_status ?? "planned"} · {visual.generator ?? "未指定"}
                    </div>
                    {previewUrl ? (
                      <div className="contract-visual-preview">
                        <img src={previewUrl} alt={visual.label ?? visual.artifact_id} loading="lazy" />
                      </div>
                    ) : (
                      <div className="contract-empty">尚未生成可预览的图</div>
                    )}
                    {visual.rendered_path ? (
                      <a
                        className="contract-file-link"
                        href={buildRunFileUrl(runId, visual.rendered_path)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        打开渲染文件
                      </a>
                    ) : null}
                    {visual.source_path ? (
                      <div className="contract-list-subtle">源文件：{visual.source_path}</div>
                    ) : null}
                    <div className="contract-list-subtle">对象映射：{objectCount}</div>
                    {visual.target_sections?.length ? (
                      <div className="contract-list-subtle">目标章节：{visual.target_sections.join("、")}</div>
                    ) : null}
                  </div>
                );
              })
            ) : (
              <div className="contract-empty">暂无 visual 约束</div>
            )}
          </div>
        </article>

        <article className="contract-card">
          <div className="contract-card-head">
            <h4>Citation Registry</h4>
            <span>{citations.length} 项</span>
          </div>
          <div className="contract-list">
            {citations.length ? (
              citations.map((citation) => (
                <div className="contract-list-item" key={citation.citation_id}>
                  <div className="contract-list-title">{citation.citation_key ?? citation.citation_id}</div>
                  <div className="contract-list-subtle">{citation.title ?? "未命名引用"}</div>
                  <div className="contract-list-subtle">状态：{citation.status ?? "planned"}</div>
                  {citation.required_sections?.length ? (
                    <div className="contract-list-subtle">要求章节：{citation.required_sections.join("、")}</div>
                  ) : null}
                  {citation.grounded_claim_ids?.length ? (
                    <div className="contract-list-subtle">Grounded claims：{citation.grounded_claim_ids.join(", ")}</div>
                  ) : null}
                </div>
              ))
            ) : (
              <div className="contract-empty">暂无 citation 约束</div>
            )}
          </div>
        </article>

        <article className="contract-card">
          <div className="contract-card-head">
            <h4>Validation Rules</h4>
            <span>{rules.length} 条</span>
          </div>
          <div className="contract-list">
            {rules.length ? (
              rules.map((rule) => (
                <div className="contract-list-item" key={rule.rule_id}>
                  <div className="contract-list-title">{rule.rule_type ?? rule.rule_id}</div>
                  <div className="contract-list-subtle">{rule.description ?? "无描述"}</div>
                  <div className="contract-list-subtle">
                    {rule.scope ?? "document"} · {rule.severity ?? "medium"} · {rule.target_id ?? "global"}
                  </div>
                </div>
              ))
            ) : (
              <div className="contract-empty">暂无 validation rule</div>
            )}
          </div>
        </article>

        <article className="contract-card">
          <div className="contract-card-head">
            <h4>Revision Memory</h4>
            <span>{revisions.length} 条</span>
          </div>
          <div className="contract-list">
            {revisions.length ? (
              revisions.slice(-6).reverse().map((revision) => (
                <div className="contract-list-item" key={revision.revision_id}>
                  <div className="contract-list-title">{revision.summary ?? revision.revision_id}</div>
                  <div className="contract-list-subtle">
                    {revision.stage ?? "-"} · {revision.agent ?? "-"}
                  </div>
                  {revision.affected_sections?.length ? (
                    <div className="contract-list-subtle">章节：{revision.affected_sections.join("、")}</div>
                  ) : null}
                  {revision.patch_types?.length ? (
                    <div className="contract-list-subtle">Patch：{revision.patch_types.join(", ")}</div>
                  ) : null}
                </div>
              ))
            ) : (
              <div className="contract-empty">暂无 revision 记录</div>
            )}
          </div>
        </article>

        <article className="contract-card">
          <div className="contract-card-head">
            <h4>Warnings</h4>
            <span>{warnings.length} 条</span>
          </div>
          <div className="contract-list">
            {warnings.length ? (
              warnings.map((warning) => (
                <div className="contract-list-item" key={warning}>
                  <div className="contract-list-subtle">{warning}</div>
                </div>
              ))
            ) : (
              <div className="contract-empty">暂无 warning</div>
            )}
          </div>
        </article>
      </section>
    </div>
  );
}
