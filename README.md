# Story2Proposal Agent

Story2Proposal Agent 是一个面向**结构化科研论文 scaffold 生成**的多 Agent 应用。

它接收一份结构化研究故事 `ResearchStory`，再把这份故事逐步加工成：

- 论文蓝图 `blueprint`
- 可执行写作约束 `contract`
- 每一节的 `draft`
- 每一轮 `review`
- 最终 `markdown / LaTeX` 稿件

所以它不是一条简单的“论文写作 prompt”，而是一套建立在图驱动多 Agent runtime 之上的论文生成系统。

## 基础依赖：AgentGraph

这个应用建立在我之前写的多 Agent 编排框架 **AgentGraph** 之上。

在这个仓库里：

- `src/` 是底层 AgentGraph runtime
- 根目录其余部分是 Story2Proposal Agent 的应用层

如果你想看底层 runtime 的设计、能力边界和 API，请直接看：

- [src/README.md](/src/README.md)

本文档只介绍 Story2Proposal Agent 的应用层。

## 这个 Agent 解决什么问题

大模型可以直接生成论文草稿，但自由生成很容易出现这些问题：

- 章节之间漂移，前后约束不一致
- claim 和 evidence 对不齐
- 图表、引用、章节依赖关系容易丢
- 多 Agent 协作时状态分散，难以收束

Story2Proposal Agent 的思路是：

1. 先把研究故事整理成论文蓝图
2. 再把蓝图收敛成可执行的 manuscript contract
3. 按章节逐节写作
4. 用多维 evaluator 做评审
5. 通过 review loop 推进或重写章节
6. 最后统一渲染成最终稿

它追求的不是“直接出一篇像样的长文”，而是“生成过程可追踪、可校验、可重写”。

## 当前主流程

当前应用层的主流程是：

1. `orchestrator` 启动
2. `architect` 生成 `blueprint`
3. `section_writer` 生成当前章节 `draft`
4. 三个 evaluator 并行评审
5. `review_controller` 聚合反馈并决定下一跳
6. 所有章节完成后进入 `refiner`
7. 最后由 `renderer` 生成最终稿

从图结构上看，大致是：

```text
orchestrator
  -> architect
  -> section_writer
  -> reasoning_evaluator
  -> structure_evaluator
  -> visual_evaluator
  -> review_controller
  -> runtime.next_node
     -> section_writer
     -> refiner
  -> renderer
```

这张图定义在：

- [graph/build.py](/E:/Work/Story2Proposal/graph/build.py:1)

## 项目结构

应用层的关键目录和文件如下：

- `prompts/`
  各个 Agent 的提示词
- `schemas/`
  输入、蓝图、contract、draft、review、rendered manuscript 的数据模型
- `domain/`
  业务核心：状态推进、contract 构建、review 聚合、render
- `graph/`
  Agent 图定义
- `servers/`
  应用层 Hook / MCP 适配层
- `scripts/`
  命令行 demo 入口
- `data/stories/`
  输入研究故事
- `data/outputs/`
  运行产物
- `config.py`
  路径与 prompt 读取入口
- `llm_io.py`
  模型文本与结构化对象的轻量转换
- `runner.py`
  应用层正式运行入口

可以把它理解成 5 层：

1. `schemas/`
   定义对象长什么样
2. `domain/`
   定义状态怎么变
3. `graph/`
   定义流程怎么走
4. `servers/`
   把 Hook / MCP 接进来
5. `runner.py` + `scripts/`
   提供运行入口

## 怎么运行

默认 demo 运行方式：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_demo
```

默认读取：

```text
data/stories/sample_story.json
```

也可以指定自己的输入 story：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_demo --story data/stories/your_story.json
```

也可以切换模型：

```powershell
.\.venv\Scripts\python.exe -m scripts.run_demo --model qwen-plus
```

如果你直接用其他解释器运行，例如：

```powershell
D:\Anaconda3\envs\agent_frame\python.exe E:\Work\Story2Proposal\scripts\run_demo.py
```

要注意该解释器自身的网络代理配置是否可用；这类错误通常不是应用代码错误，而是环境变量里的代理把模型请求打坏了。

## 输入是什么

输入是一份 `ResearchStory` JSON 文件，默认示例在：

- [data/stories/sample_story.json](/E:/Work/Story2Proposal/data/stories/sample_story.json:1)

这份输入通常包含：

- 研究主题
- 问题定义
- 动机
- 核心方法
- 贡献
- 实验
- 参考文献
- 可用图表种子
- 元信息

如果你想看更完整的输入说明，包括：

- 最小可用输入长什么样
- 推荐输入长什么样
- 每个字段应该怎么理解

请看：

- [story_io.md](/E:/Work/Story2Proposal/story_io.md:1)

## 输出是什么

每次运行都会在：

- [data/outputs/](/E:/Work/Story2Proposal/data/outputs)

下面生成一个新的 run 目录，通常名字像：

- `adaptive_graph_writer_20260421_110748`

其中通常会包含：

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

如果你想知道这些输出文件分别是什么、应该先看哪一个、调不同阶段时该看哪些产物，请看：

- [story_io.md](/E:/Work/Story2Proposal/story_io.md:1)

## 代码分层约定

Story2Proposal Agent 当前的边界是：

- `graph/`
  只负责声明流程骨架，不负责业务状态推进
- `servers/`
  只负责 Hook / MCP 适配，不承载业务本体
- `domain/`
  是应用层业务核心，负责状态推进与产物生成
- `schemas/`
  只定义数据结构
- `runner.py`
  只负责启动、收尾和返回结果
- `scripts/run_demo.py`
  只是 CLI 外壳

这套边界是刻意保持的。它的目的就是避免把业务逻辑重新塞回 graph、hook 或脚本层，保持应用层优雅、克制、结构统一。
