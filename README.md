# Story2Proposal

**Story2Proposal Agent** 是我围绕科研写作这件事做的一个多 Agent 应用。

它想解决的问题很直接：接收一份结构化的 `ResearchStory`（包含研究问题、方法、实验、结论等材料），通过多轮规划、写作、评审和收敛，逐步生成可追溯的论文草稿。

目前项目还在优化中。。。

## 工作流程

```text
ResearchStory
  → Orchestrator      初始化运行状态
  → Architect          规划标题、章节结构，生成 blueprint 和 contract
  → Section Loop       逐章写作 + 三路并行评审（reasoning / data fidelity / visual）
                       → 评审不通过则重写当前章节
                       → 通过则进入下一章
  → Refiner            全局收敛、摘要补充、术语统一
  → Renderer           渲染最终 Markdown / LaTeX 稿件
```

## 项目结构

```text
Story2Proposal/
├── backend/          # Python 后端（FastAPI + AgentGraph）
│   ├── api/          # 接口层
│   ├── domain/       # 业务逻辑
│   ├── graph/        # Agent 图定义
│   ├── schemas/      # 结构化对象
│   ├── prompts/      # Agent prompt 模板
│   ├── src/          # AgentGraph runtime
│   └── README.md     # 后端详细文档 ← 看这里
├── frontend/         # React + Vite + TypeScript 前端工作台
├── AGENTS.md         # Agent 共享约束与角色定义
├── pyproject.toml    # Python 依赖
└── LICENSE           # MIT
```

后端的完整架构、模块说明和设计细节请看 **[backend/README.md](backend/README.md)**。

## 快速开始

### 环境要求

- Python >= 3.12（推荐用 [uv](https://github.com/astral-sh/uv) 管理）
- Node.js >= 18

### 安装

```bash
# 后端
uv sync

# 前端
cd frontend && npm install
```

### 配置

在项目根目录创建 `.env`：

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
STORY2PROPOSAL_MODEL=qwen-plus
```

### 运行

```bash
# 启动后端
uv run python -m backend.api.server

# 启动前端（另一个终端）
cd frontend && npm run dev -- --host 0.0.0.0
```

打开浏览器 → Story 页 → 新建/编辑 ResearchStory → 保存 → 创建 Run → 在 Run Detail 页观察生成过程。

## License

[MIT](LICENSE)
