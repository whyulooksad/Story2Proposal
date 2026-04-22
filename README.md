# Story2Proposal Agent

# 一、项目简介

**Story2Proposal Agent** 是我在科研写作这个方向上做的一个多 Agent 应用。

它想解决的事情其实很直接，就是把一份研究内容一步步整理成论文草稿。这里说的研究内容，不是随便一段描述，而是已经有一定结构的 story，比如你已经知道研究问题是什么、方法是什么、实验做了什么、最后想表达什么，只是还没有把这些东西真正组织成一篇论文。所以这个项目更关注“怎么把写论文这件事拆开来做”。我把论文生成过程拆成了几个相互配合的 Agent 角色，让它们分别去负责结构规划、章节写作、评审、收敛和最后的渲染。这样做的目的是希望整个过程更稳定一些，也更容易持续修改。

另外，这个 Agent 应用建立在我之前写的多 Agent 编排框架 **AgentGraph** 之上。这个框架就在当前仓库的 `src/` 目录下，如果你想看底层 runtime 的设计，请直接看 [src/README.md](src/README.md)。

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
    |   |   |-- 检查论证和 claim/evidence 对齐
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
├── runner.py                 # 应用层主运行入口，负责串起一次完整 run
├── config.py                 # 路径与基础配置
├── llm_io.py                 # 模型文本与结构化对象之间的解析/转换
├── README.md                 # 本文档
├── AGENTS.md                 # Story2Proposal Agent 的共享约束说明
├── .env                      # 环境变量配置
├── pyproject.toml            # 项目依赖与包配置
├── data/                     # 输入故事与运行产物
│   ├── stories/              # 输入 ResearchStory 样例
│   └── outputs/              # 每次运行生成的输出目录
├── prompts/                  # 各个 Agent 使用的 prompt
│   ├── orchestrator.md
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
│   ├── draft.py              # draft / refiner / rendered manuscript 定义
│   └── review.py             # review / contract patch 定义
├── domain/                   # 应用层核心业务逻辑
│   ├── state.py              # 共享 context 的初始化、读写与落盘
│   ├── contracts.py          # contract 初始化与 patch 应用
│   ├── review.py             # review 聚合、确定性检查与流程推进
│   └── rendering.py          # 最终 markdown / LaTeX 渲染
├── graph/                    # Agent 图定义与节点装配
│   ├── build.py              # 主流程图定义
│   └── agents.py             # 各个 Agent 的构造、prompt 与 hook 挂载
├── servers/                  # 应用层 workflow server
│   └── workflow.py           # hook 入口：负责把 Agent 输出写回共享状态
├── scripts/                  # 脚本入口
│   └── run_demo.py           # demo 运行脚本
└── src/                      # 底层 AgentGraph runtime
    ├── agent.py              # Agent 主体实现
    ├── edge.py               # 图边定义
    ├── hook.py               # Hook 定义
    ├── nodes.py              # 节点调度相关实现
    ├── mcp_manager.py        # MCP 管理
    ├── mcp_server.py         # MCP server 封装
    ├── memory.py             # 记忆管理
    ├── skill.py              # skill 相关能力
    ├── types.py              # runtime 类型定义
    ├── utils.py              # 通用工具函数
    ├── _settings.py          # runtime 配置
    ├── README.md             # AgentGraph runtime 说明
    └── src_test/             # runtime 测试目录
```

- data/ 是 Story2Proposal 的数据落点：stories/ 存放输入研究故事，outputs/ 存放每次运行生成的中间状态、最终稿和日志快照。
- schemas/ 是 Story2Proposal 的数据模型中心，它把研究故事、论文蓝图、执行 contract、章节草稿、评审反馈和最终稿件这些对象，组织成一条完整且可验证的写作数据链。
- domain/ 是 Story2Proposal 的业务核心，负责维护论文生成过程中的共享状态，并把 blueprint、contract、draft、review、final manuscript 这些对象组织成一条真正可推进的写作状态机。
- graph/ 是 Story2Proposal 的流程骨架，负责把 architect、writer、evaluator、review controller、refiner、renderer这些角色组织成一张可执行的论文生成图。

## 四、

## 五、环境依赖

### 5.1 python依赖

- Python `>= 3.12`
- 建议使用 `uv` 管理依赖
- 也可以使用你自己的虚拟环境安装 `pyproject.toml` 中定义的依赖

安装方式可以直接用：

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

### 5.2 环境变量（.env）

| 变量名            | 说明                         |
| ----------------- | ---------------------------- |
| `OPENAI_API_KEY`  | 模型服务的 API Key，用于调用 LLM |
| `OPENAI_BASE_URL` | OpenAI 兼容接口地址              |

### 5.3 模型使用

如果不手动指定模型，整套 Story2Proposal Agent 默认使用 `qwen-plus`。

如果要切换模型，可以在运行时通过 `--model` 指定，例如：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_demo --model qwen-plus
```

## 六、 License

本项目基于 [MIT License](https://github.com/whyulooksad/ReportAgent/blob/main/LICENSE) 开源。

