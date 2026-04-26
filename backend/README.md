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

这一层单独抽出来写是因为我不想让后面的流程建立在一堆松散的字典上。这个项目表面上看是在跑多 Agent，实际上更底层一点看，是在推动一组对象一步一步演化。也就是说，系统里真正稳定的东西不是 prompt，也不是某条消息，而是这些 schema。只要对象边界不乱，后面的 graph、review、render 就不会乱；对象边界一旦松掉，后面所有模块都会开始互相渗透。

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

### AgentGraph装配

### MCP服务

### 对外接口



