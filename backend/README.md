# Story2Proposal Backend

这个agent应用建立在我之前写的多 Agent 编排框架 **AgentGraph** 之上，源码就在仓库的`backend/src`目录下。如果想看runtime的底层设计，请直接看[src/README.md](/main/backend/src/README.md)。

## 一、系统架构

```
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
  |-- 规划整篇论文的标题、摘要、章节结构、视觉规划和写作顺序
  |-- 生成 blueprint
  |-- 基于 blueprint 初始化 contract
  v
  节点3：章节写作循环
  |
  |-- section_writer
  |   |-- 读取当前 section contract
  |   |-- 生成当前章节 draft
  |   |-- 在需要时生成或登记 visual artifact
  |
  |-- 并行进入三个 evaluator
  |   |
  |   |-- reasoning_evaluator
  |   |   |-- 检查论证结构与 claim / evidence 对齐情况
  |   |
  |   |-- data_fidelity_evaluator
  |   |   |-- 检查 claim、evidence、experiment 与 story source 是否一致
  |   |
  |   |-- visual_evaluator
  |   |   |-- 检查图表引用、visual artifact 完整性与说明是否合理
  |   |
  |   v
  |  review_controller
  |   |-- 聚合三路 review
  |   |-- 应用 contract patch
  |   |-- 结合校验结果判断下一步流向
  |
  |-- 分支1：当前 section 需要修订
  |   |
  |   └-- 回到 section_writer
  |
  |-- 分支2：当前 section 通过，且还有下一节
  |   |
  |   └-- 进入下一轮 section_writer
  |
  |-- 分支3：当前 section 达到最大重写次数
  |   |
  |   └-- 标记为 manual_review 并继续推进后续章节
  |
  |-- 分支4：所有 section 全部完成
  |   |
  |   └-- 进入 refiner
  v
  节点4：refiner
  |
  |-- 对整篇草稿做全局收敛
  |-- 执行摘要覆盖、章节级重写、术语统一和全局 patch
  |-- 生成 RefinerOutput
  v
  节点5：renderer
  |
  |-- 基于 contract / drafts / refiner output
  |-- 渲染最终 manuscript
  |-- 输出 Markdown / LaTeX
  v
  节点6：evaluation
  |
  |-- 对最终 manuscript 执行整篇评测
  |-- 生成 evaluation report
  |-- 生成 benchmark report
  v
  最终输出：论文草稿及其中间产物
```

## 二、代码结构

```
backend/
  ├── runner.py                 # 后端主运行入口：串起一次 Story -> Proposal 的完整执行
  ├── config.py                 # 后端路径、.env、默认模型与 MCP 配置读取
  ├── llm_io.py                 # LLM 输出与结构化对象之间的解析/转换工具
  ├── README.md                 # 本文档
  ├── data/                     # 后端运行数据
  │   ├── stories/              # 输入的 ResearchStory 样例与持久化 story
  │   └── outputs/              # 每次运行生成的 drafts / reviews / rendered / logs
  │
  ├── prompts/                  # 各业务 Agent 的提示词模板
  │   ├── orchestrator.md
  │   ├── architect.md
  │   ├── section_writer.md
  │   ├── reasoning_evaluator.md
  │   ├── data_fidelity_evaluator.md
  │   ├── visual_evaluator.md
  │   ├── review_controller.md
  │   ├── refiner.md
  │   └── renderer.md
  │
  ├── schemas/                  # 结构化数据定义层
  │   ├── story.py              # ResearchStory 及输入故事相关定义
  │   ├── blueprint.py          # 论文 blueprint 定义
  │   ├── contract.py           # 写作 contract 定义
  │   ├── draft.py              # section draft / visual artifact / rendered draft 定义
  │   ├── review.py             # review / issue / patch 等评审结构定义
  │   └─── eval.py               # 评估结果结构定义
  │           
  ├── domain/                   # 核心业务逻辑层
  │   ├── state.py              # 共享上下文初始化、运行态落盘、产物持久化
  │   ├── contracts.py          # blueprint -> contract 初始化与 contract patch 应用
  │   ├── review.py             # review 聚合、修订记录与流程推进辅助
  │   ├── validation.py         # contract / render / review 的一致性校验
  │   ├── rendering.py          # 最终 manuscript 的 markdown 渲染
  │   ├── evaluation.py         # 渲染结果与整篇稿件的质量评估
  │   └── visual_artifacts.py   # 图表/SVG 等视觉产物物化与完整性检查
  │  
  ├── graph/                    # 多 Agent 流程图装配层
  │   ├── build.py              # 主流程图定义与 Story2Proposal graph 构建入口
  │   └── agents.py             # 各业务 Agent 的构造、prompt、hook 与 workflow server 配置
  │  
  ├── api/                      # FastAPI 接口层
  │   ├── server.py             # HTTP API 入口与 /api 路由定义
  │   ├── repository.py         # story / run 的文件持久化与运行生命周期管理
  │   ├── models.py             # API 请求/响应模型
  │   ├── run_job.py            # 单次 run 的子进程执行入口
  │   └── test/                 # 调试接口
  │       ├── section_writer_probe.py
  │       ├── section_writer_probe.json
  │       └── drawio_probe.json
  │   
  ├── servers/                  # MCP / workflow 服务层
  │   ├── workflow.py           # workflow MCP server：把 Agent 输出写回共享状态
  │   └── drawio_mcp/           # draw.io MCP 服务实现
  │       ├── src/              # TypeScript 源码
  │       ├── dist/             # 编译后的 Node 运行产物
  │       ├── tmp/              # 临时生成的 drawio/svg 文件
  │       ├── package.json
  │       └── README.md
  │   
  ├── scripts/                  # 命令行脚本入口
  │   ├── run_demo.py           # 读取 story 样例并执行一次完整 demo
  │   └── run_eval.py           # 对生成稿件/产物执行评估
  │   
  └── src/                      # 底层 AgentGraph runtime
      ├── agent.py              # Agent 主执行逻辑
      ├── edge.py               # 图边定义
      ├── nodes.py              # Node / Tool 抽象
      ├── hook.py               # Hook 定义
      ├── mcp_manager.py        # MCP client 管理与工具调用封装
      ├── mcp_server.py         # MCP server 构建辅助
      ├── memory.py             # Memory Provider 抽象
      ├── skill.py              # Skill 加载与注册
      ├── types.py              # runtime 类型定义
      ├── utils.py              # 通用工具函数
      ├── _settings.py          # runtime 配置读取
      ├── src_test/             # runtime 级示例/实验脚本
      └── README.md             # AgentGraph runtime 说明
   
```

## 三、代码详解

### 运行入口与基础工具

这一组代码对应 `runner.py`、`config.py` 和 `llm_io.py`。我把它们放在最前面讲，是因为它们决定了整个后端怎么跑。

`runner.py` 负责真正发起一次完整运行，`config.py` 负责把 prompt、路径、模型和 MCP 配置统一接进来，`llm_io.py` 负责把模型吐出来的文本重新拉回结构化对象。后面的 `domain/`、`graph/`、`servers/` 都是建立在这三层已经把基础打稳的前提上。

先看 `runner.py`。这里真正的入口是 `run_story_to_proposal()`。这个函数一上来做的不是调模型，而是先给本次运行分配一个独立输出目录：它用当前时间生成 `run_id`，然后在 `output_dir` 下预先建好 `drafts`、`reviews`、`rendered` 和 `logs` 四个子目录。这样做的原因很直接，我这个系统不是“生成完一段文本就结束”，而是一个会持续产生中间产物的流程，章节草稿、评审结果、最终稿、运行快照都要落盘，所以一开始就得把这次运行的文件空间准备好。目录就绪之后，它调用 `build_initial_context()` 把输入的 `ResearchStory` 包装成整条工作流共享的 `context`，然后调用 `build_story2proposal_graph()` 把整张 AgentGraph 拼出来，最后才真正执行 `await graph(...)`。也就是说，`run_story_to_proposal()` 干的是“把环境搭好，再把图跑起来”，而不是把论文生成逻辑硬写在入口里。

图执行完之后，它会在 `finally` 里关闭 `graph._mcp_manager`，保证这次运行过程中打开的 MCP 连接不会悬挂。接着它检查 `context["artifacts"]["rendered"]` 是否已经生成；如果已经有最终 manuscript，就进一步调用 `evaluate_and_store_manuscript(context)`，把整篇稿件再走一轮评测和 benchmark。最后再调用 `persist_run_outputs(context)`，把输入 story、最终 summary 和必要的运行元数据写回输出目录。所以 `runner.py` 不是一个薄薄的启动壳，它实际上把一次运行的生命周期收口了：前面建运行空间，中间驱动图执行，后面做资源回收、评估和摘要落盘。旁边的 `run_story_to_proposal_sync()` 则只是一个同步包装器，专门给脚本和子进程入口用。`api/run_job.py` 最终调用的就是它，因此 API 层并不会自己碰业务流程，只是把请求转交给这里。

再看 `config.py`。这一层我故意写得很集中，因为我不想让“路径从哪来、默认模型是什么、prompt 去哪读、MCP 配置在哪”这种问题散落到各个模块里。文件开头先统一定义 `REPO_ROOT`、`PACKAGE_ROOT`、`PROMPTS_DIR`、`STORIES_DIR`、`OUTPUTS_DIR` 这些路径常量，后面的脚本、API、runner 都直接复用。然后通过 `load_dotenv(REPO_ROOT / ".env")` 在配置层一次性加载环境变量，并给出 `DEFAULT_MODEL`。这样后面的代码只需要消费结果，不需要每个入口自己再去读 `.env`。这里最常用的两个函数是 `load_mcp_server()` 和 `load_prompt()`。`load_mcp_server(name)` 会打开仓库根目录的 `.mcp.json`，取出某个 MCP server 的启动配置；`graph/agents.py` 里挂载 `s2p_workflow` 和 `drawio` 时，走的就是这条线。`load_prompt(name)` 则负责从 `prompts/` 目录读取 prompt 模板文本，业务 Agent 在构造时不会自己碰文件系统，而是统一从这里拿 prompt。也就是说，`config.py` 虽然代码不长，但它把“系统运行依赖的静态资源”收成了一个稳定入口。

`llm_io.py` 解决的是另一件基础问题：模型输出怎么重新变成系统能消费的对象。这个项目里，architect、section_writer、evaluator、refiner 都不是随便输出一段自然语言就算完成任务，而是要输出 JSON，再分别落成 `ManuscriptBlueprint`、`SectionDraft`、`EvaluationFeedback`、`RefinerOutput` 这些 schema。所以这里最关键的函数是 `extract_json_object()` 和 `parse_model()`。`extract_json_object(text)` 会先找 ```json ... ``` 代码块，如果没有，再去正文里找最像 JSON 对象的 `{...}` 片段，然后逐个尝试 `json.loads()`。这里我是我当时阅读`mem0`源码的时候印象很深的一点，所以这里我也就这样做了，我不能假设模型每次都只输出一份干净 JSON，它经常会在外面包解释文字，或者把 JSON 放进代码块里，所以这个函数就是专门把真正有用的那一层抠出来。`parse_model(text, model_type)` 则在此基础上再走一步：先提取 JSON，再调用 `model_type.model_validate(payload)` 做 schema 校验。真正把“模型文本输出”变成“系统内部合法对象”的，就是这一步。比如 `servers/workflow.py` 里捕获 architect 输出时，不是直接信任那段文本，而是先通过 `parse_model(..., ManuscriptBlueprint)` 验证成功，后面才允许它进入 `initialize_contract()`。

`llm_io.py` 里还有一个很轻的小函数 `json_dumps()`，在运行里出现得非常频繁。它负责把 Pydantic 对象或者普通 Python 值稳定地格式化成 JSON 字符串，供 prompt 层直接使用。`domain/state.py` 里刷新 prompt 视图时，会把 `story`、`blueprint`、`contract`、`current_draft` 这些对象都转成字符串版本塞回 `context`，后面的 Agent prompt 直接消费这些 JSON 视图。也就是说，`llm_io.py` 做的是双向转换：一边把模型输出从文本拉回对象，一边把对象重新整理成稳定文本喂给下一个 Agent。

把这三份代码放在一起看，它们之间的衔接关系其实很清楚。`runner.py` 往下接的是 `domain.build_initial_context()` 和 `graph.build_story2proposal_graph()`，负责把一次运行真正启动起来；`config.py` 往下接的是 `graph/agents.py`，负责给 Agent 提供 prompt 和 MCP 配置；`llm_io.py` 往下接的是 `servers/workflow.py`，负责把各个 Agent 的文本输出解析成 blueprint、draft、review 这些结构化产物。后面章节里会看到，很多复杂逻辑都发生在 `domain/` 和 workflow hook 里，但如果没有这一层先把运行入口、配置入口和结构化输入输出边界处理干净，后面的工作流其实是站不住的。

### 核心数据对象

这一组代码对应 `schemas/`。这一层单独抽出来写是因为我不想让后面的流程建立在一堆松散的字典上。这个项目表面上看是在跑多 Agent，实际上更底层一点看，是在推动一组对象一步一步演化。也就是说，系统里真正稳定的东西不是 prompt，也不是某条消息，而是这些 schema。只要对象边界不乱，后面的 graph、review、render 就不会乱；对象边界一旦松掉，后面所有模块都会开始互相渗透。

最开始的对象是 `ResearchStory`。我把它设计成“研究材料包”，而不是一段自由文本。这里面有 `topic`、`problem_statement`、`motivation`、`core_idea`、`method_summary`、`contributions`、`experiments`、`findings`、`limitations`、`references`、`assets`。我这么拆可能看起来是为了显得结构化，但其实是因为后面每个环节关心的信息粒度根本不一样。architect 在看的是“这些材料能组织出什么论文结构”，section writer 在看的是“这一节到底该从 story 的哪些字段里取东西”，data fidelity evaluator 在看的是“这段 claim 有没有真的回到原始实验和发现上”。如果一开始输入只是大段叙述，后面所有环节都只能靠猜。

`ResearchStory` 下面又拆了几个更小的对象，这些小对象其实都很实用。`ExperimentSpec` 把实验固定成 `setup`、`dataset`、`metrics`、`result_summary` 这几个槽位，所以后面无论是规划 experiments section，还是检查结果部分有没有把实验讲清，代码里都能按字段直接拿。`ReferenceSpec` 也是同样的思路，先把参考文献规整成作者、年份、venue 这些字段，后面 contract 初始化时再把它们变成 citation slot。`ArtifactSeed` 则是给已有图表线索留入口。还有一个很小但很关键的函数是 `ResearchStory.from_path()`，它不让外部代码自己解析 JSON，而是统一走 `model_validate_json()`。这一步其实是在卡输入边界：进系统的 story 先得是一个合法对象，后面我才放心让所有流程围着它跑。

再往后是 `ManuscriptBlueprint`。我把它定位成 architect 给出来的“论文施工图”，它还不是正式 contract，但已经不是随便写写的大纲了。这里最核心的是 `SectionPlan` 和 `VisualPlan`。`SectionPlan` 里除了章节标题和目标，我还要求它明确写出 `must_cover`、`evidence_refs`、`visual_refs`、`citation_refs`、`input_dependencies`、`source_story_fields`。这背后的想法很简单：如果 architect 只给我一个标题列表，那后面 contract 初始化就没法真正落地；但如果 architect 已经说清楚“这一节要覆盖哪些 claim，用哪些证据，主要吃 story 的哪些字段，还依赖哪些前文”，那后面就可以把这份 blueprint 压成执行约束。`VisualPlan` 也是这样，我不想让图表停留在“这里可能放张图”的程度，所以它要带 `artifact_id`、`label`、`caption_brief`、`semantic_role` 和目标章节。这样后面 `visual registry` 才有东西可接。

真正进入执行期之后，中心对象就变成了 `ManuscriptContract`。这一层我当时写得比较重，因为它本来就是整个系统的中轴。后面的 section writer 不是直接看 blueprint，review controller 也不是直接看 draft 原文，renderer 更不是重新从 story 开始理解整篇论文，它们最后看的都是 contract。这里面我把执行期需要持续维护的东西都收进来了：整篇稿件的风格约束、术语表、章节级 obligations、图表注册表、引用注册表、claim-evidence 链接、validation rules、revision log、global status。换句话说，到了这一层，“论文要怎么写”已经不再只是一个计划，而是变成了一套运行中的约束系统。

`ManuscriptContract` 里面我最看重的是 `SectionContract`。因为写到 section writer 那一步时，真正驱动它的就是这一节的 section contract。这里我没有只放一个 `purpose` 和几个 `required ids` 就结束，而是继续往下拆。`claim_requirements` 里每一条 `ClaimRequirement` 不只记录 claim 文本，还绑定它需要的 `evidence_ids`、`citation_ids` 和 `source_story_fields`。这样后面校验的时候，就不只是问“这个 claim 写没写”，而是可以继续问“它有没有证据 trace”“有没有 story trace”“有没有 citation grounding”。`SectionVisualObligation` 和 `SectionCitationObligation` 也是这个思路，我不想只留下一个 `artifact id` 或 `citation id`，而是把 `required`、`purpose`、`grounded claims`、`explanation_required` 这些执行时真的会用到的约束提前写进去。

contract 里还有几类对象，是为了把整篇稿件的可追踪性保留下来。`VisualArtifact` 负责登记图表，从它的 label、semantic role，一直到 source path、rendered path、materialization status、render status，后面都会不断回写。`CitationSlot` 负责登记引用，它不是 story 里那条原始参考文献的简单拷贝，而是执行期真正会被 section 使用、会被 render 校验、会被 grounding 检查的 citation 对象。`ClaimEvidenceLink` 则是我专门拉出来的一层，因为我希望系统始终能回答一个问题：某个 claim 到底是被哪些 evidence 和 citation 支撑的。再往后 `ValidationRule`、`RevisionRecord`、`ContractStatus` 这几类对象，实际上是在告诉后面的模块：这个 contract 不是静态文件，而是会随着 review、rewrite、render 不断演化的。

写作产物对应的是 `SectionDraft`。这一层我当时下了一个比较硬的限制，就是不允许 section writer 只回一段正文。我要求它除了 `content` 之外，还要显式给出 `covered_claim_ids`、`referenced_visual_ids`、`referenced_citation_ids`、`story_traces`、`evidence_traces`、`visual_artifacts`、`terminology_used` 和 `unresolved_items`。原因很直接：只要 draft 退化成纯文本，后面的 review 和 validation 就会重新掉回模糊判断；但只要 draft 把这些结构带回来，后面的代码就能顺着这些字段继续走。比如 `StoryTrace` 让我知道这一段内容回到的是哪个 story 字段，`EvidenceTrace` 让我知道某个 evidence 实际支撑了哪些 claim，`VisualArtifactMaterialization` 让我知道这一轮到底生成了什么视觉产物，文件路径和对象映射又是什么。后面 `save_section_draft()` 能一口气更新 claim coverage、citation grounding、visual registry，说到底就是因为 `SectionDraft` 已经把这些信息带回来了。

再往后，`draft.py` 里还有一组对象是给全局收敛和最终渲染准备的。`RefinerOutput` 的作用，我定位成“refiner 不是重写整篇论文，而是交一个收敛包”。所以它不是直接塞一篇新稿子回来，而是带着 `abstract_override`、`rewrite_goals`、`section_rewrites`、`terminology_updates` 和少量 `contract_patches`。这样我后面在 `store_refiner_output()` 里就可以只吸收必要修改，而不会把整个流程重新打散。最后 renderer 对应的是 `FinalizedSection`、`RenderValidationReport` 和 `RenderedManuscript`。这里我同样把边界卡住了：renderer 负责的是把已经收敛下来的 section 组装成最终稿，并做确定性校验，它不是再调模型重新写一遍全文。所以 `RenderedManuscript` 里除了 `markdown` 和 `latex`，我还保留了 `finalized_sections` 和 `validation`，这样 render 结果本身也是可追踪的。

评审对象这一层，我最在意的是 `EvaluationFeedback`。因为在这个系统里，review 不是随手给点评价，它必须变成下一步流程能消费的输入。所以 evaluator 不能只说“这节有问题”，而是要交出 `status`、`issues`、`suggested_actions` 和 `contract_patches`。这里的 `ContractPatch` 很关键，我当时专门把 patch type 列得比较细，就是不想让 review 停留在口头建议上。比如补 citation、补 visual、调整 placement、收紧 validation rule，这些都应该变成明确 patch，后面才能真正打进 contract。`AggregatedFeedback` 则是 review controller 用的对象，它把三路 evaluator 再加上确定性检查结果收成一份最终裁决。到了这一步，review 就不再是“谁提了什么意见”，而是“系统下一步到底要 advance、rewrite 还是 repair”。

最后一层是评测对象，也就是 `eval.py`。这一层不参与中间写作循环，它是整轮运行结束之后，系统用来审视自己结果的。`ManuscriptEvaluationReport` 把整篇稿件拆成不同维度去打分，`EvaluationDimension` 和 `EvaluationCriterion` 继续把每个维度的证据展开，避免最后只剩一个黑箱分数。`BenchmarkSuiteReport` 以及它下面那几个 comparison 对象，则是为了让我能把最终稿和 baseline 放在同一个结构里比较。也就是说，到这一步，对象已经不再服务于“生成”，而是转去服务于“评估”。

总的来说：`schemas/` 规定这个系统到底允许哪些东西流动。`ResearchStory` 规定了输入长什么样，`ManuscriptBlueprint` 规定了 architect 的输出长什么样，`ManuscriptContract` 规定了执行期的核心约束长什么样，`SectionDraft` 规定了 writer 必须交回什么，`EvaluationFeedback` 规定了 evaluator 的反馈必须长什么样，`RenderedManuscript` 规定了最终结果如何被封装，`ManuscriptEvaluationReport` 规定了系统怎样评价自己。后面的 `domain/` 和 `graph/` 之所以能成立，不是因为 prompt 写得多漂亮，而是因为这一层先把对象边界钉死了。

### 业务规则与状态管理

`domain/` 这一层在回答一个更实际的问题：这些对象到底怎么被推进，怎么被修改，怎么被校验，怎么一步一步收敛成最后的 manuscript。这一层我自己看得很重，因为真正把 Story2Proposal 从“几个 Agent 串起来”变成“一个能跑完闭环的系统”的，不是 prompt，而是这里的业务规则。后面的 graph 负责把节点接起来，但节点跑完之后状态往哪写、怎么判断这一轮该不该重写、contract 怎么越跑越具体、render 为什么不重新调模型，这些核心问题都在这里解决。

我先从 `state.py` 讲，因为这份文件里放的是整条运行最核心的共享状态操作。这里最开始的函数是 `build_initial_context()`。这个函数做的事情很简单——负责把所有模块默认依赖的运行骨架一次性搭起来。它先把 `ResearchStory` 转成 JSON 形式塞进 `context["story"]`，然后把 `blueprint`、`contract`、`drafts`、`reviews`、`artifacts`、`runtime` 这些槽位全部预留出来。`runtime` 里我又提前放了 `current_section_id`、`pending_sections`、`completed_sections`、`rewrite_count`、`max_rewrite_per_section`、`section_writer_mode`、`section_writer_plan` 这些运行时字段，这是因为我不想让后面的节点各自往 context 里随手加状态。最后它会立刻调一次 `refresh_prompt_views()`，把这一版初始 context 预渲染出一批 prompt 可直接消费的 JSON 视图。也就是说，`build_initial_context()` 不是在“存故事”，它是在给整轮运行搭一个有明确插槽的工作台。

`refresh_prompt_views()` 这一个函数用得非常频繁。它做的事情可以概括成一句话：把业务状态重新整理成 prompt 友好的视图。它先从 context 里取出当前 story、blueprint、contract、current section、current draft、current reviews，再调用 `json_dumps()` 生成 `story_json`、`contract_json`、`current_section_contract_json`、`current_draft_json` 这些字符串版本。接着它还会根据运行态拼出 `section_writer_mode_instruction` 和 `writing_language_instruction`，比如当前是 compose 模式还是 repair 模式，当前论文要写英文还是中文。它甚至还会额外构造一个 `current_section_obligation_summary_json`，把当前 section contract 中最关键的 obligations 再压成更短的一份摘要。这样后面的 prompt 模板就不用每次自己去从一大坨 contract 里挑重点了。这个函数的重要性在于：它让 prompt 层永远消费的是“状态的投影视图”，而不是直接把所有业务判断塞进 prompt 里。

接着是 `set_blueprint_and_contract()`。这个函数是 architect 阶段和后面写作循环真正接上的地方。architect 在 `servers/workflow.py` 那边产出 `ManuscriptBlueprint` 之后，不是直接把 blueprint 扔给 section writer，而是先在这里把 blueprint 和初始化后的 `ManuscriptContract` 一起写进 context。写进去之后，它立刻做几件事：把 `writing_order` 拿出来初始化 `pending_sections`；把第一个 section 设成 `current_section_id`；给每个 section 建一份 `rewrite_count` 计数器；把 section writer 模式重置成 `compose`；同时把 contract 里的 `global_status.current_section_id`、`pending_sections`、`completed_sections` 也同步起来。最后它还会把这一版最初始的 contract 深拷贝一份保存到 `artifacts["contract_init"]`，方便后面追踪 contract 是怎么演化的。也就是说，这个函数做的不是“保存 architect 输出”，而是正式把系统从 blueprint 阶段切到 contract 驱动的执行期。

`state.py` 里真正最关键的函数，我觉得是 `save_section_draft()`。这一块你在 guide 里举的例子本来就很对，因为它确实是典型的“不能只说保存草稿”的函数。它一上来先根据 `runtime["current_draft_version"]` 自增出新的 version，再把当前 `SectionDraft` 转成 JSON payload，连同这个 version 一起写进 `context["drafts"][section_id]`。然后它会立刻去更新 contract 里同一节的状态：把 `latest_draft_version` 写进去，把 `status` 改成 `drafted`，把 `draft_path` 指到 `drafts/{section_id}_v{version}.md`。接着它还会顺着 `draft.covered_claim_ids` 回写 claim coverage，把对应 `ClaimRequirement.coverage_status` 标成 `covered`。

这还只是前半段。再往后它会处理 visual 这一支：先检查 `draft.referenced_visual_ids`，把当前 section 记进相关 artifact 的 `resolved_references`，并把 render status 从 `planned` 推到 `registered`。然后它会调用 `materialize_visual_artifacts()` 去真正处理 `draft.visual_artifacts` 里带回来的视觉产物。这里处理完之后，不只是 draft 本身会被替换成规范化后的 artifact payload，contract 里的对应 `VisualArtifact` 也会被继续回写：`materialization_status` 变成 `materialized`，`generator`、`source_path`、`rendered_path`、`thumbnail_path`、`object_map` 都会补全。最后它还会处理 citation：凡是当前 draft 显式引用到的 citation，都先标成 `used`，然后再顺着 `evidence_traces` 把这条 citation 具体 grounded 到哪些 claim 上。到这一步，一份 section draft 才算真正落进了系统。函数最后还要再把 contract 的 global status 切到 `drafted`，重置 writer 模式和计划，刷新 prompt 视图，并调用 `persist_run_state()` 立刻落盘。所以 `save_section_draft()` 的本质不是“存一份文稿”，而是把这一轮 section writer 产出的正文、claim 覆盖、图表状态、citation grounding 和运行态一起推进一格。

`append_review()` 则是 reviewer 支线进入状态树的入口。它会先取当前 `current_section_id` 和当前 draft version，把 `EvaluationFeedback` 转成 JSON，再额外打上 `draft_version`。这里我专门做了一步替换逻辑：同一个 section、同一个 evaluator 类型，只保留当前 draft 的最新一份 review。这样后面 review controller 聚合时，不会把旧草稿的反馈也算进去。写完 reviews 之后，它同样会刷新 prompt 视图并立刻落盘。也就是说，review 在我的实现里不是随手附加一条日志，而是始终和某个具体 draft version 绑定的。

`store_refiner_output()` 和 `store_render_output()` 可以放在一起看，它们都属于“全局阶段把产物重新写回中心状态”。`store_refiner_output()` 先把 `RefinerOutput` 整体存进 `artifacts["refiner_output"]`，如果里面带了 `abstract_override`，就额外单独挂出来。接着它会顺着 `terminology_updates` 去改 contract 里 glossary 的 `preferred_form`；如果 refiner 还给了 `contract_patches`，就直接走 `apply_contract_patches()` 再把 contract 收紧一轮；如果它还做了 section rewrite 或全局 rewrite goal，就往 `revision_log` 里补一条 refiner 级别的修订记录。最后它把 global status 改成 `refined`，再刷新和落盘。`store_render_output()` 则是把最终 `RenderedManuscript` 放进 `artifacts["rendered"]`，把 `runtime["final_status"]` 设成 `rendered`，然后调用 `finalize_contract_after_render()` 根据最终稿和 render validation 结果，把 contract 里的 visual status、citation status 和 warnings 再同步一遍。这里我特意没有让 renderer 只生成一个最终字符串就结束，而是要求它最后还要把 contract 的执行状态彻底闭环回写。

最后 `state.py` 里还有一组和持久化相关的函数。`persist_run_state()` 负责把当前运行快照写进输出目录，它不只是写 `run_state.json`，还会顺手把 `blueprint.json`、`contract_final.json`、所有 drafts、reviews、final manuscript、evaluation 和 benchmark 一起落盘。`persist_run_outputs()` 则更偏最终收尾，它会把 `input_story.json` 和最终 `run_summary.json` 写出去。`build_run_summary()` 是给 runner 和 API 都能直接消费的一份精简摘要。还有一个 `evaluate_and_store_manuscript()`，它在最终稿已经生成之后，再调 `evaluate_manuscript_bundle()` 跑完整篇评测，并把 evaluation 和 benchmark 一起回写到 context 和磁盘里。也就是说，`state.py` 这一层管的不只是内存状态，还管“什么时候把哪一层状态固化成文件”。

如果说 `state.py` 是在维护运行中的共享现场，那 `contracts.py` 做的就是两件更底层的事：一是把 blueprint 压成正式 contract，二是让 review 真正有能力改动 contract。先看 `initialize_contract()`。这个函数是 architect 阶段之后最关键的一步。它先遍历 blueprint 里的每个 `SectionPlan`，给 `must_cover` 里的每一条 claim 编出稳定的 `claim_id`，同时构造对应的 `ClaimRequirement` 和 `ClaimEvidenceLink`。接着它把 section 级别的 evidence、visual、citation 要求全部拷进去，再顺手构造 `SectionVisualObligation` 和 `SectionCitationObligation`。然后它再去建整篇级别的 visual registry 和 citation registry：前者从 `VisualPlan` 变成 `VisualArtifact`，后者从 `ReferenceSpec` 变成 `CitationSlot`。最后它会一次性塞进一批默认 `ValidationRule`，比如 section coverage、claim-evidence alignment、citation grounding、visual resolution、label uniqueness 这些我认为运行里必须始终存在的规则。换句话说，`initialize_contract()` 干的事不是机械转换 schema，而是把 architect 的高层规划翻译成一套后面 writer、reviewer、renderer 都能共同执行的约束系统。

这里面还有几步我自己觉得很值。比如 `_build_citation_keys()` 会先根据作者、年份和标题生成稳定 citation key，再在冲突时加序号去重；这样后面的 bibliography 和 citation resolution 就有一致的 key 可用。`_section_story_fields()` 则会在 blueprint 没显式给出 `source_story_fields` 时，根据 section 语义给默认映射，比如 `introduction` 默认看 `problem_statement` 和 `motivation`，`method` 默认看 `core_idea` 和 `method_summary`。这些默认值其实都不是装饰，它们决定了后面 data fidelity 和 traceability 校验有没有基线可以依靠。

`apply_contract_patches()` 是另一半。review 之所以能真正影响后续写作，不是因为 reviewer 提了意见，而是因为这里会把 `ContractPatch` 一条一条落下去。这个函数一进来先把 contract 版本号加一，然后按 patch type 分支处理。比如 `append_glossary` 会往 glossary 里补术语；`add_required_citation` 会同时改 section 的 `required_citation_ids` 和 `citation_obligations`；`add_required_visual` 会同时改 `required_visual_ids` 和 `visual_obligations`；`mark_claim_verified` 不只改 `claim_evidence_links`，还会把 section 里对应 requirement 的 `coverage_status` 标成 `verified`；`tighten_validation_rule` 会直接提高某条规则的 severity，或者往它的 params 里叠加信息；`ground_citation_to_claim` 则会把 citation 明确接到某个 claim 上。也就是说，contract patch 在这里不是日志，而是真修改。这也是为什么前面我会强调 `EvaluationFeedback` 必须结构化，因为只有这样它才能一路传到这里，变成真实的状态演化。

`review.py` 这一层负责的是“当前这一轮 review 到底怎么判，下一步往哪走”。最前面的 `aggregate_current_feedback()` 会把当前 section contract、当前 draft、当前 reviews 抓出来，再把输出目录也带进去，最后统一交给 `validation.aggregate_feedback()`。这样 review controller 不是只看 evaluator 的主观反馈，还会把确定性检查结果也并进来。接着 `_derive_contract_evolution_patches()` 会根据这一轮里反复出现的问题，反过来收紧 contract 规则。比如 citation hygiene 老出问题，它就会去加重 `citation_grounding`；visual 引用老出问题，就会去加重 `visual_reference_resolution`；如果已经重写过一次仍然在出问题，它还会额外打一个 revision note，明确记下“这类确定性检查已经反复触发过了”。这一块其实是我比较想要的一个行为：不是每轮 review 都从零开始，而是让 contract 逐渐学会对常出问题的地方更严格。

`apply_review_cycle()` 是这份文件里真正拍板的函数。它先拿到聚合后的 feedback，再读取当前 section、当前 rewrite count，然后默认把本轮动作设成 `advance`。如果 aggregate status 是 `revise` 或 `fail`，它就先判断有没有超过 `max_rewrite_per_section`。没超的话，就把这一节的 rewrite count 加一，并决定下一步是普通 `rewrite_section`，还是更局部一点的 `repair_visual`。这里的区分来自 `_should_use_visual_repair()` 和 `_build_section_writer_plan()`：如果问题只集中在 visual，而且别的 evaluator 没意见，那我不想把整节重写一遍，而是切 writer 到 `repair` 模式，只修图和图的解释。超出最大重写次数的话，它就不会无休止卡在这一节，而是把该节加入 `needs_manual_review`，然后继续推进后续章节。

拍完这一轮的动作之后，`apply_review_cycle()` 还会做几件收尾动作。它先把 aggregate 里带回来的 patch 和 contract evolution patch 一起交给 `apply_contract_patches()`，让 contract 真正演化。然后如果本轮决定 `advance`，它就把当前 section 从 `pending_sections` 挪到 `completed_sections`，把 `current_section_id` 切到下一节，清空当前 draft version，并把 writer 模式重置回 `compose`。如果本轮不 advance，它就把 `section_writer_mode` 和 `section_writer_plan` 写进 runtime，让下一轮 section writer 知道自己是在重写全文，还是只做 visual repair。最后它还会同步 contract 的 `global_status`，把 `last_aggregate_feedback` 和 `next_action` 存进 artifacts，并往 `revision_log` 里追加一条 review cycle 记录。也就是说，这个函数做的不是“判断过没过”，而是把 reviewer 的判决真正翻译成下一步运行态。

确定性校验逻辑都在 `validation.py`。这里我做的不是大模型式评审，而是一组很硬的检查器。最基础的是 `tokens_in_text()`，它会把正文里的 `[FIG:id]` 和 `[CIT:id]` token 抠出来，后面很多检查都靠它。`validate_section_coverage()` 很直接，就是拿 `covered_claim_ids` 去对比 contract 的 `required_claim_ids`，少一个就报一个。`validate_visual_references()` 会同时看两件事：正文和 `referenced_visual_ids` 里到底有没有引用到所有 required visual；以及这些 visual 是否真的在 `draft.visual_artifacts` 里带回了物化 payload。如果带了输出目录，它还会再调用 `validate_visual_artifact_integrity()` 去检查文件是否真的存在。`validate_citation_slots()` 则不只检查 citation 有没有被引用，还会继续检查 evidence trace 里有没有真正把 citation 挂上去，并在需要的时候直接生成 `ground_citation_to_claim` patch。`validate_data_fidelity()` 会沿着 `ClaimRequirement` 去查：claim 如果已经被声明覆盖了，那对应 evidence trace 和 story trace 是否也存在；缺 evidence 的时候，它甚至会顺手补 `add_required_evidence` patch。`validate_traceability()` 则更像是最后一道兜底，确保 section 声称自己来源于哪些 story 字段，最后真的留下了 trace。

这些检查最后都在 `aggregate_feedback()` 里汇总。这个函数先把三路 evaluator 的 `issues` 和 `contract_patches` 吃进来，再把前面那些确定性检查结果全跑一遍，然后把所有 issues 合在一起。只要 deterministic checks 报了问题，就算 evaluator 都给 `pass`，这里也会把整体 status 拉成 `revise`。最后它返回的不只是 `status`、`issues` 和 `patches`，还会把各类确定性检查按类别分开放进 `deterministic_checks`。后面的 review controller 正是根据这份聚合结果，决定下一步怎么推进。

render 阶段的业务规则放在 `rendering.py`。这一层我故意让它保持“尽量不再发明内容”。`build_finalized_sections()` 会遍历 contract 里的 sections，按 section_id 去找对应 draft。如果缺草稿，就记 warning；如果有 `abstract_override`，就优先用 refiner 覆盖的摘要；如果 refiner 对这一节给了 `SectionRewrite`，就用 rewrite 后的内容替换原 draft；然后再调 `_apply_terminology_updates()` 做一次术语统一。最后得到的是一组 `FinalizedSection`，也就是 renderer 真正拿来拼全文的“最终 section 真相源”。这一步很重要，因为它表明 renderer 不是从 story 再理解一遍论文，而是严格站在前面已经收敛好的结果之上。

`render_markdown_manuscript()` 则是最后的组装函数。它先通过 `build_finalized_sections()` 拿到所有 final section，再调用 `build_bibliography_block()` 从 contract 里的 citation slots 渲染出参考文献列表，然后拼出 markdown 和 latex 两个版本。拼完之后，它不会直接返回，而是会立刻把 `finalized_sections` 交给 `validate_render_output()` 再做一轮确定性校验。这样最终的 `RenderedManuscript` 里除了两份文本，还有 `validation` 和 `warnings`。也正因为 render 阶段是这样做的，后面的 `store_render_output()` 才有可能继续把 visual status、citation status 和 warnings 回写到 contract，而不是把系统在最终一步断开。

整篇评测逻辑放在 `evaluation.py`。这里的主函数是 `_evaluate_protocol()`，它基本上把最终稿再重新读一遍，但目的不是生成内容，而是按维度打分。它先把稿件拆成 section map，再从 contract、drafts、citations、visuals、revision log 里取各种证据，然后分别构造 `structural_integrity`、`writing_clarity`、`methodological_rigor`、`experimental_substance`、`citation_hygiene`、`reproducibility`、`formatting_stability`、`visual_communication` 这几个维度。每个维度不是直接给个分，而是通过 `_criterion()` 和 `_dimension()` 把子标准、证据和得分一起建起来。比如 methodological rigor 会去看 verified claims、dataset mentions、metric mentions；citation hygiene 会去看 duplicate citation key、unresolved citation、grounding gap；visual communication 会去看 visual 是否真的 rendered、有没有 explanation、有没有出现在目标 section。最后 `evaluate_primary_report()` 会基于最终稿产出主评测报告，而 `evaluate_manuscript_bundle()` 则会再构造一个 baseline，把“最终稿”和“直接把 section drafts 拼起来的版本”一起送去比，产出 benchmark suite。

最后一块是 `visual_artifacts.py`。这份文件做的事情看起来比较技术，但它其实是整条链里“图到底是不是真的落地了”的关键。`materialize_visual_artifact()` 会先把 artifact 里带回来的 `source_path`、`rendered_path`、`thumbnail_path` 全都解析到输出目录里，而且 `_resolve_within_output_dir()` 会明确禁止路径逃出 `output_dir`。这个约束我加得很死，因为视觉产物最后都是系统运行过程里的副产物，我不想让任意路径写到输出目录外面。然后它会根据 `generator` 选对应 renderer。现在最主要的是 `drawio`：`_render_drawio_artifact()` 会读 drawio 源文件，把 SVG markup 正规化，再把最终 `.svg` 写到 `rendered/visuals/` 下。对于非 drawio 的产物，就走 `_passthrough_artifact()`，只要文件存在，就把路径规范化回写。`validate_visual_artifact_integrity()` 则是它的反面：给我一组 artifact payload，我会逐个检查文件路径是否合法、目标文件是否存在，最后把异常都整理成确定性 issue。前面 `save_section_draft()` 物化 visual，后面 `validate_visual_references()` 检查 artifact integrity，靠的就是这一层。

把 `domain/` 这一层整体看下来，它其实就是在解决一个问题：前面那些对象不是定义完就放着，而是要在运行里不断被推进、被收紧、被校验、被落盘。`state.py` 负责让共享状态真的活起来，`contracts.py` 负责把 blueprint 压成执行约束并让 review 能改 contract，`review.py` 负责决定这一轮是前进还是回写，`validation.py` 负责给系统一组不依赖模型判断的硬检查，`rendering.py` 负责把已经收敛的 section 组装成最终稿，`evaluation.py` 负责在结束后再回头审视结果，`visual_artifacts.py` 负责让图表从 payload 变成真实文件。前面的 graph 只是把 Agent 连起来，但真正让流程闭环的，是这里。

### AgentGraph装配

前面 `domain/` 那一层解决的是“状态怎么推进”，到了 `graph/` 这一层，我要解决的问题就变成了“这些推进动作到底由谁来触发，顺序怎么排，哪些节点该并行，哪些节点该等前面跑完再进”。我这里没有把整个流程写成一个巨大控制器函数，而是把它装成一张明确的 AgentGraph。这样做对我来说有两个好处：第一，流程结构会被显式写出来，而不是散在各种 if/else 里；第二，每个业务节点只需要关心自己的输入输出，不用自己知道整条论文生成链到底怎么调度。

这一层的入口很短，就在 `graph/build.py` 里的 `build_story2proposal_graph()`。函数本身不长，但它其实把整条主流程一次性定死了。它先调 `build_agents(model)` 拿到所有静态业务 Agent，然后返回一个新的根 `Agent`，名字叫 `orchestrator`。这个根 Agent 自己也有 prompt，而且我专门给它挂上了 `mcpServers={"s2p_workflow": workflow_server_config()}`。这里的意思不是 orchestrator 自己要去做复杂业务，而是整张图从一开始就要能看到 workflow hook server，因为后面 architect、writer、review、render 这些业务节点最终都要靠这个 MCP server 把输出写回共享 context。

真正决定流程形状的是 `edges`。我这里写的每一条边其实都对应一条很明确的业务判断。`Edge(source="orchestrator", target="architect")` 表示根节点启动之后先交给 architect；`Edge(source="architect", target="section_writer")` 表示 blueprint 和 contract 建好之后，流程正式进入章节写作。再往后，`section_writer` 后面同时连了 `reasoning_evaluator`、`data_fidelity_evaluator` 和 `visual_evaluator` 三个 evaluator。这里我用三条并列边，而不是串行跑，是因为这三个 evaluator 看的是同一版 draft 的三个不同侧面，它们彼此之间没有依赖关系，让它们并行才符合这个阶段的语义。

接下来最关键的一条边，是从三路 evaluator 汇到 `review_controller` 这一条：`Edge(source=("reasoning_evaluator", "data_fidelity_evaluator", "visual_evaluator"), target="review_controller")`。这里我故意用了 tuple source，而不是三条独立边。原因很简单，我不想让 review controller 在只收到其中一路 feedback 的时候就提前开始判。只有等三路 evaluator 都跑完，这一轮 section review 才算材料齐全，review controller 才有资格决定下一步是继续前进、重写全文，还是只做 visual repair。

再往后还有一条我自己很喜欢的边：`Edge(source="review_controller", target="runtime.next_node")`。这里的 target 不是某个写死的节点名，而是一个运行时表达式。它的意思是：review_controller 自己不直接 handoff 给某个固定下游，而是先通过 `apply_review_cycle()` 把当前 runtime 改好，再由 `runtime.next_node` 决定下一跳到底是谁。这样一来，graph 层就不用把“通过则进下一节 section_writer，全部完成则进 refiner，失败则重写当前节”这些复杂分支全写死在边上，而是把真正的流向判断下放给 `domain/review.py`。最后还有一条简单边 `Edge(source="refiner", target="renderer")`，表示所有 section 完成并进入 refiner 之后，下一步固定就是 renderer。也就是说，`build.py` 做的事不是堆一组节点名，而是在把论文生成流程最核心的控制结构直接编码成一张图。

不过只看 `build.py` 还不够，因为那份文件只决定“谁连谁”，并没有决定“每个节点自己长什么样”。这一部分放在 `graph/agents.py`。我在这里专门写了一个 `_make_agent()`，其实就是想把应用层 Agent 的公共约定收一收。它接收 `name`、`model`、`prompt_name`，再加可选的 `on_start`、`on_end` 和 `mcp_servers`。函数内部先根据有没有 hook 名称构造 `Hook` 列表，再统一用 `load_prompt(prompt_name)` 读取 prompt 模板，最后生成一个 `backend.src.Agent`。这样我后面在定义业务节点的时候，就不会每个 Agent 都重新写一遍“读 prompt、造 hook、绑 mcpServers”这套样板。

`agents.py` 里还有几个专门处理 MCP 配置的小函数。`workflow_server_config()` 会强制从 `.mcp.json` 里取出 `s2p_workflow` 的配置，如果没有就直接报错；这说明对 Story2Proposal 来说，workflow MCP 不是可有可无的插件，而是主流程的一部分。`drawio_server_config()` 则是可选读取 `drawio` 配置，因为不是每次运行都一定要画图，如果没有 drawio server，我不希望整套流程直接起不来。也就是说，在装配层我对这两类 MCP server 的态度是不同的：workflow 是核心依赖，drawio 是增强能力。

真正的节点定义都在 `build_agents()` 里。这里返回的是一组已经配好 prompt、hook 和可见 MCP server 的静态 Agent。先看 `architect`。它的 prompt 来自 `architect.md`，而且我给它绑的是 `on_end="mcp__s2p_workflow__capture_architect_output"`。这个 hook 的意义非常直接：architect 可以自由生成 blueprint 的 JSON，但它一结束，workflow server 就会立刻把最新 assistant message 解析成 `ManuscriptBlueprint`，再在同一个 hook 里调用 `initialize_contract()` 和 `set_blueprint_and_contract()`，把系统正式切换到 contract 驱动的执行期。所以 architect 节点不是“自己负责创建 contract”，而是“自己负责产出 blueprint，然后在 on_end 阶段由 workflow server 把 blueprint 落进状态树”。

`section_writer` 的装配也很关键。它同样是 `on_end` hook，但绑定的是 `capture_section_writer_output`，也就是说 writer 一旦输出 JSON，workflow server 就会立刻把它解析成 `SectionDraft`，再走 `save_section_draft()` 那整条状态回写逻辑。除此之外，我只给 `section_writer` 这个节点额外挂了 `drawio` MCP server。这个决策其实反映了我对业务边界的划分：如果要在写章节时创建或编辑图表，那是 writer 的职责，所以 drawio 工具只需要在 writer 这一侧可见；reasoning evaluator 或 review controller 不需要直接操作 drawio，它们只需要检查 draft 和 visual artifact 的结果。

三个 evaluator 的装配则很统一：`reasoning_evaluator`、`data_fidelity_evaluator`、`visual_evaluator` 都是各自加载各自的 prompt，然后在 `on_end` 时分别调用 `capture_reasoning_feedback`、`capture_data_fidelity_feedback` 和 `capture_visual_feedback`。也就是说，evaluator 节点在图里虽然是三个不同角色，但在装配逻辑上我给它们的约定是一致的：它们都不自己碰共享状态，只负责产出 `EvaluationFeedback`，然后由 workflow hook 在结束时把反馈写进当前 section 的 review bucket。这样一来，review 数据进状态树的入口也被统一住了。

`review_controller` 和前面几个节点不一样。它没有 `on_end`，而是用 `on_start="mcp__s2p_workflow__apply_review_cycle"`。这里是一个很刻意的设计。因为 review_controller 的核心职责不是再生成一份结构化对象写回状态，而是先根据已有的 draft、reviews 和确定性检查结果，把当前 section 的裁决和 runtime 下一步该去哪先算出来。也就是说，它一启动，workflow server 就先调用 `apply_review_cycle()`，把 `runtime.next_node`、`section_writer_mode`、`section_writer_plan`、`completed_sections`、`pending_sections`、`revision_log` 这些状态先改好。这样 review_controller 自己在 prompt 里看到的就已经是“这一轮判完之后的最新状态”，而后面的边 `target="runtime.next_node"` 也才能真正解析出下一跳。

`refiner` 和 `renderer` 则分别代表全局阶段的两个不同职责。`refiner` 用的是 `on_end="capture_refiner_output"`，也就是说它先生成 `RefinerOutput`，然后 workflow server 再把 abstract override、section rewrites、terminology update 和 contract patch 吸回中心状态。`renderer` 则更特殊，它用的是 `on_start="render_and_finalize"`。这意味着 renderer 一启动，workflow server 就不会再让模型自由写一遍全文，而是直接调用 `render_markdown_manuscript(context)` 和 `store_render_output(context, rendered)`，把已经收敛好的 drafts、refiner output 和 contract 组装成最终稿，再把 render validation 结果同步回 contract。这里其实正好体现了我前面在 `domain/` 里一直强调的那个原则：render 阶段是确定性收口，不是重新打开内容生成。

如果把 `agents.py` 和 `servers/workflow.py` 放在一起看，装配逻辑会更清楚。`agents.py` 决定的是每个节点在什么时候触发哪个 hook，`workflow.py` 决定的是这个 hook 触发时到底要把消息解析成什么对象、再把对象怎样写回状态。比如 architect 的 on_end 为什么会进 `initialize_contract()`，不是因为 graph 里写了一条直达边，而是因为 `capture_architect_output()` 内部先 `parse_model(..., ManuscriptBlueprint)`，再调 `initialize_contract()` 和 `set_blueprint_and_contract()`。section writer 的 JSON 为什么会变成 `context["drafts"]`，也不是 writer 自己手动写进去，而是因为 `capture_section_writer_output()` 解析出 `SectionDraft` 后，调用了 `save_section_draft()`。review 为什么会继续影响 contract，也是同样的原因：evaluator 的 JSON 先被转成 `EvaluationFeedback`，review_controller 启动时再走 `apply_review_cycle()` 和 `apply_contract_patches()`。所以装配这一层真正做成的事情是：把“模型生成消息”和“业务状态演化”之间，用 hook 和 workflow MCP 稳稳地焊死了。

最后还得回头说一句 `backend.src.Agent`，因为应用层的 graph 装配其实是站在这个 runtime 之上的。底层 `Agent` 自己既能作为一个节点执行，也能作为一张子图的根；它有 `nodes`、`edges`、`hooks` 和 `mcpServers` 这些能力。`build.py` 和 `agents.py` 真正利用的，就是这几样基础能力：把业务节点当成 `nodes` 放进去，把控制流写成 `edges`，把状态同步动作写成 `hooks`，把 workflow / drawio 能力挂成 `mcpServers`。换句话说，应用层 graph 装配并没有自己重新发明一套调度系统，它只是把 Story2Proposal 这个任务专属的业务结构，编码到 AgentGraph runtime 已经提供好的抽象上。

所以如果我自己总结这一层，我会说：`build.py` 决定的是整条工作流的骨架，`agents.py` 决定的是每个业务节点的个性和边界。前者回答“下一步该谁跑”，后者回答“这个节点跑的时候能看到什么 prompt、能触发什么 hook、能调用什么 MCP server”。前面 `domain/` 那一层负责把对象往前推进，而 `graph/` 这一层负责把这些推进动作安排到正确的节点和正确的时机上。

### MCP服务

这一层我其实是把两类完全不同的能力拆开了。一个是 `servers/workflow.py`，它负责把业务 Agent 的输出重新接回系统状态；另一个是 `servers/drawio_mcp/`，它负责把图真正创建出来、修改掉、存成 `.drawio.svg` 文件。它们都叫 MCP 服务，但在我的设计里，地位完全不一样。`workflow.py` 更像是“状态桥”，负责把 AgentGraph 和 `domain/` 连起来；`drawio_mcp` 更像是“外部能力插件”，负责给 section writer 提供画图和改图的手。

我先说 `servers/workflow.py`。这份文件虽然放在 `servers/` 下面，但它本质上不是在做一个通用 MCP 服务，而是在做 Story2Proposal 自己的 workflow adapter。前面在 graph 装配那一节已经提到过，应用层 Agent 大量依赖 hook，比如 architect 的 `on_end`、section writer 的 `on_end`、review_controller 的 `on_start`、renderer 的 `on_start`。这些 hook 触发之后，总得有个地方真正去读当前 Agent 的输出，把它解析成 schema，再调用 `domain/` 里的函数把状态推进下去。`workflow.py` 就是干这个的。

这份文件的入口很直接：`server = FastMCP("s2p_workflow")`。也就是说，它把自己暴露成一个 MCP server，供应用层 Agent 在运行时通过 `mcp__s2p_workflow__...` 的方式调用。真正反复出现的基础动作其实就两个。第一个是 `_latest_agent_message()`，它会倒着扫描消息列表，找到某个指定 Agent 最新的一条 assistant message。第二个是 `_parse_agent_output()`，它在拿到那条文本消息之后，会立刻调用 `parse_model()` 按指定 schema 去做解析和校验。也就是说，这里并不信任“Agent 好像说了一段 JSON”，而是每次都要明确问：你这次输出，能不能真的被解释成 `ManuscriptBlueprint`、`SectionDraft`、`EvaluationFeedback` 或 `RefinerOutput`。

`capture_architect_output()` 是这一层里最关键的 tool 之一。它先把 architect 的最新输出解析成 `ManuscriptBlueprint`，再从 `context["story"]` 恢复出 `ResearchStory`。如果 story metadata 里带了 `active_sections`，它还会先走 `trim_blueprint_to_sections()`，把 blueprint 裁成一个更小的章节子集。做完这些以后，它不会自己去操作字典，而是直接调用 `initialize_contract()` 和 `set_blueprint_and_contract()`。这一步其实就是前面多次提到的那个接缝：architect 只是负责把论文施工图交出来，真正把施工图变成执行期 contract，并把运行态切到第一节，是 workflow server 在 hook 里完成的。

`capture_section_writer_output()` 也很关键。它做的事情看起来很简单，就是把 writer 的最新输出解析成 `SectionDraft`，然后调用 `save_section_draft(context, draft)`。但这里的重要性不在代码长度，而在边界意义。section writer 本身不应该知道 `context["drafts"]` 的内部布局，也不应该自己去改 contract、改 visual status、改 citation grounding。它只负责按 prompt 协议产出一份合法 `SectionDraft`。至于这份 draft 怎样落进中心状态，怎样触发 claim coverage 更新，怎样顺手把 visual artifact 物化，都是 workflow server 这一层接过去之后再做的。也就是说，workflow.py 在这里真正做的是“把 Agent 输出和业务状态改动解耦”。

三个 evaluator 对应的是另一组 capture 函数：`capture_reasoning_feedback()`、`capture_data_fidelity_feedback()`、`capture_visual_feedback()`。这几个函数最后都会落到 `_capture_feedback()` 和 `_store_feedback()`。逻辑也是同一个套路：先按 `EvaluationFeedback` schema 解析当前消息，再调用 `append_review()` 写进当前 section 的 review bucket。这里我自己比较在意的一点是，workflow server 会明确修正 `feedback.evaluator_type`，保证 reasoning、data_fidelity、visual 三路反馈不会在状态里混淆。换句话说，evaluator 节点负责“提出结构化反馈”，而 workflow server 负责“把这份反馈挂到正确的 section、正确的 evaluator 类型下面”。

`apply_review_cycle()` 这一支就更能体现 workflow server 的位置了。它和前面几个 capture tool 不一样，不是拿某个 Agent 的文本输出去 parse，而是直接对当前 `context` 做一次业务推进。review_controller 一启动，这个 tool 就会先调用 `domain.review.apply_review_cycle()`，把当前 section 是前进、重写还是 repair visual 先判出来，再顺手 `refresh_prompt_views()` 和 `persist_run_state()`。也就是说，review_controller 这个节点之所以能用 `runtime.next_node` 做动态分发，不是因为 graph 层自己有判断逻辑，而是因为 workflow server 在它开始前已经先把下一步状态算出来了。

`capture_refiner_output()` 和 `render_and_finalize()` 对应的是全局阶段。前者把 refiner 的最新消息解析成 `RefinerOutput`，再走 `store_refiner_output()`；后者则干脆不再 parse 文本，而是直接调用 `render_markdown_manuscript(context)` 和 `store_render_output(context, rendered)`。这一步我当时就是故意写成确定性 render 的，因为到了 renderer 这里，前面的 drafts、refiner output、contract 都已经齐了，我不想再让模型自由发挥一次。workflow server 在这里扮演的角色其实很清楚：它不是“业务逻辑本体”，但它是所有业务动作真正落地的统一入口。

如果把 `workflow.py` 抽象一下，它其实在重复做同一件事：从 AgentGraph 那边接住 hook 调用，拿到 `messages` 和 `context`，把消息解析成明确对象，然后把对象送到 `domain/` 里对应的状态函数。也正因为有了这层，前面的 graph 装配才能保持干净。Agent 只需要声明“我结束时调用哪个 hook”，不需要自己知道输出怎么落盘；`domain/` 只需要提供“拿一个 blueprint / draft / feedback 之后怎么改状态”的纯业务函数，不需要自己知道消息列表长什么样。MCP 在这里起到的，其实是一个非常实用的胶水作用。

另一边的 `servers/drawio_mcp/` 就完全是另一类服务了。它不碰 contract，不碰 review，也不碰共享 context。它只负责一件事：通过 MCP tool 去创建和修改 `.drawio.svg` 图文件。我把这部分单独留成一个本地 fork，而不是直接用上游 `npx drawio-mcp`，主要是因为我不想把运行时稳定性绑在外部 npm registry 上，也不想让 Node 兼容性问题在每次启动时才暴露。你可以把它理解成：workflow server 处理的是“系统状态”，drawio MCP 处理的是“图形文件”。

这个 drawio MCP 的入口在 `src/index.ts`。代码很短，就是 new 了一个 `McpServer`，然后把 `NewDiagramTool`、`AddNodeTool`、`LinkNodesTool`、`GetDiagramInfoTool`、`EditNodeTool`、`RemoveNodesTool` 这些工具全注册进去。也就是说，这个服务本身不做复杂调度，它只是把一组图形操作封成 MCP tool 暴露出来。真正负责 MCP 协议交互的是 `src/mcp/McpServer.ts`。这个类在 `run()` 里会做两件很标准的事：一是给 `ListToolsRequestSchema` 注册 handler，把所有 tool 的 schema 暴露出去；二是给 `CallToolRequestSchema` 注册 handler，收到调用之后按工具名找到对应 tool，再把参数传给它的 `execute()`。如果找不到工具，就抛 `MethodNotFound`；如果执行异常，就统一包成 MCP error。也就是说，这一层做的是最薄的 MCP 封装：协议归它管，图形逻辑归具体 tool 管。

真正和 draw.io 文件打交道的，是 `Graph.ts` 和 `GraphFileManager.ts`。`Graph` 这一层负责内存里的图模型操作。比如 `addNode()` 会根据 kind 决定节点样式和默认尺寸，再把节点插到当前 mxGraph 里；`editNode()` 会改标题、kind、几何信息，必要时还会处理圆角矩形的 corner radius；`linkNodes()` 会给边生成稳定 id，并根据是不是无向边来调整箭头；`applyLayout()` 则把层次布局、圆形布局、organic 布局这些 mxGraph layout 算法收进一个统一入口。也就是说，`Graph.ts` 管的是“内存里的图怎么改”。

`GraphFileManager.ts` 管的则是“图怎么从文件里读出来，又怎么写回文件”。`loadGraphFromSvg()` 会先把路径 resolve 成绝对路径，再读 `.drawio.svg` 内容，然后通过 `extractXMLFromSVG()` 把嵌在 SVG `content` 属性里的 mxGraph XML 解码出来，最后交给 `Graph.fromXML()` 恢复成内存图。反过来，`saveGraphToSvg()` 会先确保目标目录存在，再把 `graph.toXML()` 的结果做 URI encode、deflateRaw、base64 编码，重新塞回 draw.io 兼容的 `<mxfile><diagram>...</diagram></mxfile>` 结构里，最后写成标准 `.drawio.svg`。我之所以这样做，是因为我希望系统最后留下来的不只是一个浏览器能显示的 SVG，而是一个还能继续被 draw.io 工具链编辑的 SVG。

具体每个 tool 的逻辑其实都比较直白，但它们的分工很清楚。`new_diagram` 创建一张空图；`add_nodes` 接一批节点参数，逐个调用 `graph.addNode()`，必要时还可以顺手跑 layout；`link_nodes` 则按边列表去建连接；`edit_nodes` 修改已有节点或边；`remove_nodes` 删除指定 id；`get_diagram_info` 则把当前图重新导出成 XML 供外部检查。这里我比较在意的一点是，这些工具都是无状态的：每次都显式传 `file_path`，真正的 source of truth 永远是磁盘上的 `.drawio.svg` 文件，而不是 MCP server 内存里偷偷维持一份状态。这样调试和回放都简单很多。

把这两类 MCP 服务放在一起看，就能看出我当时的边界划分。`s2p_workflow` 解决的是“Agent 输出怎么进入系统状态树”，所以它直接依赖 `schemas/`、`llm_io.py` 和 `domain/`；`drawio` 解决的是“图文件怎么生成和编辑”，所以它只关心图模型、文件格式和 MCP tool 封装，不应该碰 Story2Proposal 的 contract、review 或 run lifecycle。这种分拆对我来说不是为了好看，而是为了避免两个方向互相污染。如果以后我想换掉图形生成实现，不应该动 workflow server；如果我想改 contract 演化逻辑，也不应该碰 drawio MCP。MCP 这一层真正提供给整个系统的价值，就是把这两类能力都变成了清晰、可替换、可装配的外部接口。

### 对外接口

这一层我确实做得比较薄。前面真正复杂的逻辑都已经放在 `runner.py`、`domain/`、`graph/` 和 `servers/` 里了，所以到了 `api/`，我主要做的是把这些能力包成 HTTP 接口，而不是再写一套新的业务流程。

入口在 `api/server.py`。这里就是很标准的 FastAPI 门面：挂一个 `/api` 前缀的 router，把 story 和 run 相关接口暴露出来。`/stories` 负责 story 的增删查，`/runs` 负责 run 的创建、停止、删除、详情查询和文件读取。路由本身都很薄，基本只是调 `StoryRepository` 和 `RunRepository`，然后把异常翻译成合适的 HTTP 状态码。

真正稍微重要一点的是 `repository.py`。我把它拆成了两个仓库。`StoryRepository` 很简单，就是 story 文件的读写包装。`RunRepository` 则负责 run 生命周期：创建 run 时先建输出目录，再把 story 落盘，然后起一个独立子进程去跑 `backend.api.run_job`；查询 run 时，再从内存中的活动进程和输出目录里的状态文件一起推断当前状态，并把 blueprint、contract、drafts、reviews、manuscript、logs 这些产物重新整理成前端能直接消费的结构。这里我坚持走子进程，而不是在 HTTP 请求里直接跑完整流程，主要是因为一次 Story2Proposal 运行本来就是长任务，拆出来更容易做停止、恢复和日志追踪。

`api/run_job.py` 就是这个子进程入口。它只做一件事：读入 `ResearchStory`，调用 `run_story_to_proposal_sync()`，如果失败就把错误写进 `logs/error.json`。`models.py` 则只是把 API 对外返回的数据形状固定下来，比如 run 列表项、run 详情、章节状态、overview、latestReview 这些。整体上看，API 这一层不是系统的大脑，它只是把前面已经存在的文件驱动运行系统，整理成前端更容易调用的一组接口。



