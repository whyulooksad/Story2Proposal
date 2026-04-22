import { Link } from "react-router-dom";

export function HomePage() {
  return (
    <div className="overview-page">
      <section className="home-hero">
        <div className="home-hero-copy">
          <div className="eyebrow">Story2Proposal</div>
          <h1>科研写作工作台</h1>
          <p>配置 Story，启动 Run，查看产物。</p>
        </div>
        <div className="home-hero-actions">
          <Link to="/stories" className="primary-button">
            新建 Story
          </Link>
          <Link to="/runs" className="ghost-button">
            查看 Runs
          </Link>
        </div>
      </section>

      <section className="home-grid">
        <article className="home-card">
          <div className="home-card-head">
            <span className="eyebrow">Stories</span>
            <Link to="/stories" className="inline-link">
              进入
            </Link>
          </div>
          <div className="home-list">
            <div className="home-list-row">
              <div>
                <div className="home-list-title">adaptive_graph_writer</div>
                <div className="home-list-subtle">结构化科研写作</div>
              </div>
              <div className="home-list-time">04-23</div>
            </div>
            <div className="home-list-row">
              <div>
                <div className="home-list-title">story2proposal_demo</div>
                <div className="home-list-subtle">多 Agent 科研写作</div>
              </div>
              <div className="home-list-time">04-22</div>
            </div>
          </div>
        </article>

        <article className="home-card">
          <div className="home-card-head">
            <span className="eyebrow">Runs</span>
            <Link to="/runs" className="inline-link">
              进入
            </Link>
          </div>
          <div className="home-list">
            <div className="home-list-row">
              <div>
                <div className="home-list-title">adaptive_graph_writer_20260423</div>
                <div className="home-list-subtle">qwen-plus · 运行中</div>
              </div>
              <div className="home-list-time">01:15</div>
            </div>
            <div className="home-list-row">
              <div>
                <div className="home-list-title">story2proposal_demo_20260422</div>
                <div className="home-list-subtle">qwen-plus · 已完成</div>
              </div>
              <div className="home-list-time">22:19</div>
            </div>
          </div>
        </article>

        <article className="home-card home-card-quiet">
          <div className="home-card-head">
            <span className="eyebrow">Status</span>
          </div>
          <div className="status-stack">
            <div className="status-line">
              <span>默认模型</span>
              <strong>qwen-plus</strong>
            </div>
            <div className="status-line">
              <span>当前模式</span>
              <strong>local mock</strong>
            </div>
            <div className="status-line">
              <span>主要入口</span>
              <strong>Story / Runs</strong>
            </div>
          </div>
        </article>
      </section>
    </div>
  );
}
