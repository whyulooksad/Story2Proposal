# Story2Proposal Agent

## 一、项目简介
**Story2Proposal Agent** 是我围绕科研写作这件事做的一个多 Agent 应用。

它想解决的问题很直接：把一份已经有一定结构的研究内容，逐步整理成论文草稿。这里的输入不是随便一段描述，而是一份结构化的 `ResearchStory`，里面通常已经有研究问题、方法、实验、结论、局限性这些材料，只是还没有真正组织成一篇论文。

这个项目关注的不是“一次性把论文吐出来”，而是把论文生成过程拆开来做。不同 Agent 分别负责结构规划、章节写作、评审、收敛和最终渲染，让整个过程更稳定，也更容易修改。

另外，这个应用建立在我之前写的多 Agent 编排框架 **AgentGraph** 之上。底层 runtime 在仓库的 `src/` 目录下，如果想看这部分设计，请直接看 [src/README.md](src/README.md)。

## 二、系统架构
```text
输入：ResearchStory
    |
    v
节点1：orchestrator
    |
    |-- 接收整份研究 story
    |-- 初始化本次写作运行状态
    |-- 启动整条论文生成流程
    v
节点2：architect
    |
    |-- 读取研究问题、方法、实验、结论等材料
    |-- 规划整篇论文的标题、章节结构和写作顺序
    |-- 生成 blueprint
    |-- 初始化 contract
    v
节点3：章节写作循环
    |
    |-- section_writer
    |   |-- 读取当前 section contract
    |   |-- 生成当前章节 draft
    |
    |-- 并行进入三个 evaluator
    |   |
    |   |-- reasoning_evaluator
    |   |   |-- 检查论证和 claim / evidence 对齐
    |   |
    |   |-- structure_evaluator
    |   |   |-- 检查章节结构、段落组织和衔接
    |   |
    |   |-- visual_evaluator
    |   |   |-- 检查图表和 visual 使用情况
    |   |
    |   v
    |  review_controller
    |   |-- 聚合三路 review
    |   |-- 应用 contract patch
    |   |-- 判断下一步流向
    |
    |-- 分支1：当前 section 需要重写
    |   |
    |   └-- 回到 section_writer
    |
    |-- 分支2：当前 section 通过，且还有下一节
    |   |
    |   └-- 进入下一轮 section_writer
    |
    |-- 分支3：所有 section 都完成
    |   |
    |   └-- 进入 refiner
    v
节点4：refiner
    |
    |-- 做全局收敛和整体润色
    |-- 补充摘要、章节备注等全局内容
    v
节点5：renderer
    |
    |-- 基于 blueprint / contract / drafts / reviews
    |-- 渲染最终 manuscript
    |-- 输出 markdown / LaTeX
    v
最终输出：论文草稿及其中间产物
```

## 三、代码结构
```text
Story2Proposal/
├── api/                      # FastAPI 接口层
│   ├── server.py             # API 入口与路由定义
│   ├── repository.py         # story / run 的文件读写与聚合逻辑
│   └── models.py             # run 相关请求与响应模型
├── frontend/                 # 前端运行工作台
├── runner.py                 # 应用层主运行入口，负责串起一次完整 run
├── config.py                 # 路径、.env 与默认模型配置
├── llm_io.py                 # 模型文本与结构化对象之间的解析 / 转换
├── README.md                 # 本文档
├── AGENTS.md                 # Story2Proposal Agent 的共享约束说明
├── .env                      # 环境变量配置
├── pyproject.toml            # 项目依赖与包配置
├── data/                     # 输入故事与运行产物
│   ├── stories/              # 输入 ResearchStory
│   └── outputs/              # 每次运行生成的输出目录
├── prompts/                  # 各个 Agent 使用的 prompt
│   ├── architect.md
│   ├── section_writer.md
│   ├── reasoning_evaluator.md
│   ├── structure_evaluator.md
│   ├── visual_evaluator.md
│   ├── review_controller.md
│   ├── refiner.md
│   └── renderer.md
├── schemas/                  # 应用层结构化对象定义
│   ├── story.py              # ResearchStory 定义
│   ├── blueprint.py          # blueprint 定义
│   ├── contract.py           # manuscript contract 定义
│   ├── draft.py              # draft / rendered manuscript 定义
│   └── review.py             # review / contract patch 定义
├── domain/                   # 应用层核心业务逻辑
│   ├── state.py              # 共享 context 的初始化、投影与落盘
│   ├── contracts.py          # contract 初始化与 patch 应用
│   ├── review.py             # review 聚合、检查与流程推进
│   └── rendering.py          # 最终 markdown / LaTeX 渲染
├── graph/                    # Agent 图定义与节点装配
│   ├── build.py              # 主流程图定义
│   └── agents.py             # 各个 Agent 的构造、prompt 与 hook 挂载
├── servers/                  # 应用层 workflow server
│   └── workflow.py           # hook 入口：负责把 Agent 输出写回共享状态
├── scripts/                  # 脚本入口
│   └── run_demo.py           # demo 运行脚本
└── src/                      # 底层 AgentGraph runtime
    ├── agent.py
    ├── edge.py
    ├── hook.py
    ├── nodes.py
    ├── mcp_manager.py
    ├── mcp_server.py
    ├── memory.py
    ├── skill.py
    ├── types.py
    ├── utils.py
    ├── _settings.py
    ├── README.md
    └── src_test/
```

## 四、

## 五、环境依赖
### 5.1 Python 依赖

- Python `>= 3.12`
- 建议使用 `uv` 管理后端依赖

安装方式：

```powershell
uv sync
```

当前项目在 `pyproject.toml` 里声明的核心依赖包括：
- `openai`
- `mcp`
- `pydantic`
- `pydantic-settings`
- `httpx`
- `Jinja2`
- `jsonschema`
- `common-expression-language`
- `Pygments`
- `fastapi`
- `uvicorn`
- `python-dotenv`

### 5.2 前端依赖

前端位于 `frontend/`，使用 `React + Vite + TypeScript`。

安装方式：

```powershell
cd frontend
npm install
```

### 5.3 环境变量（.env）

| 变量名 | 说明 |
| --- | --- |
| `OPENAI_API_KEY` | 模型服务的 API Key |
| `OPENAI_BASE_URL` | OpenAI 兼容接口地址 |
| `STORY2PROPOSAL_MODEL` | Story2Proposal 默认使用的后端模型 |

示例：

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
STORY2PROPOSAL_MODEL=qwen-plus
```

## 六、使用指南

先开后端：

```powershell
cd E:\Work\Story2Proposal
uv run python -m api.server
```

再开前端：

```powershell
cd E:\Work\Story2Proposal\frontend
npm run dev -- --host 0.0.0.0
```

然后在浏览器里走这条链路：

1. 打开 `Story` 页
2. 新建或编辑一个 `ResearchStory`
3. 点 `保存 Story`
4. 点 `创建 Run`
5. 跳到对应的 `Run Detail` 页
6. 观察这些状态是否正常更新

- 顶部状态会不会从 `running` 往后更新
- `currentNode / currentSectionId / nextNode` 会不会变化
- `section` 状态会不会变化
- artifact tabs 里哪些项会出现 `已更新`
- 点开某个已更新的 artifact 后，标记会不会消失
- run 完成后，轮询状态会不会变成“已停止轮询”

## 七、License

本项目基于 [MIT License](https://github.com/whyulooksad/ReportAgent/blob/main/LICENSE) 开源。
