# Story2Proposal

基于 `src/` 下的图驱动 Agent runtime，实现Story2Proposal。

这个仓库现在分成两层：

- `src/`: 通用 Agent Graph runtime
- 根目录其余目录: Story2Proposal 应用层

应用层建立在 `src/` 提供的 `Agent`、`Edge`、Hook、MCP 集成和共享 `context` 机制之上。

## 项目结构

- `prompts/`: 各个 Agent 的提示词
- `schemas/`: 领域数据模型
- `domain/`: 业务状态推进、评审循环、渲染与落盘
- `graph/`: Agent 定义和图构建
- `servers/`: 应用层 MCP / Hook 入口
- `scripts/`: 运行脚本
- `data/stories/`: 输入 story
- `data/outputs/`: 运行输出
- `src/`: 底层通用 runtime

## 当前流程

当前实现的主流程是：

1. `orchestrator` 启动
2. `architect` 生成 blueprint
3. `section_writer` 生成当前章节草稿
4. 三个 evaluator 并行评审
5. `review_controller` 聚合反馈并决定下一步
6. 所有章节完成后进入 `refiner`
7. 最后由 `renderer` 生成最终稿

图定义在 [graph/build.py](/E:/Work/Story2Proposal/graph/build.py:1)，应用层 MCP 入口在 [servers/workflow.py](/E:/Work/Story2Proposal/servers/workflow.py:1)。

## 运行方式

先确保依赖已经安装到项目虚拟环境，然后运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_demo
```

默认会读取：

```text
data/stories/sample_story.json
```

也可以指定自己的 story 文件：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_demo --story data/stories/your_story.json
```

## 输出内容

每次运行会在 `data/outputs/` 下生成一个以 `story_id + 时间戳` 命名的目录，包含：

- `input_story.json`
- `blueprint.json`
- `contract_init.json`
- `contract_final.json`
- `drafts/`
- `reviews/`
- `rendered/final_manuscript.md`
- `rendered/final_manuscript.tex`
- `logs/run_state.json`
- `logs/run_summary.json`

## 代码分层约定

- `graph/` 只负责定义图，不负责业务状态修改
- `domain/` 只负责业务状态推进和产物生成
- `servers/` 只做 MCP / Hook 适配，不承载业务本体
- `runner.py` 只负责启动、关闭和返回结果

如果你要看底层 runtime 的设计和能力边界，去看 [src/README.md](/E:/Work/Story2Proposal/src/README.md:1)。
