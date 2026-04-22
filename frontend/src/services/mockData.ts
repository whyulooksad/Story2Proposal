import type { RunDetail, RunItem } from "../types/run";
import type { StoryItem } from "../types/story";

export const mockRuns: RunItem[] = [
  {
    id: "adaptive_graph_writer_20260423_010812",
    storyId: "adaptive_graph_writer",
    model: "qwen-plus",
    status: "running",
    startedAt: "2026-04-23 01:08",
    updatedAt: "2026-04-23 01:15",
  },
  {
    id: "story2proposal_demo_20260422_221140",
    storyId: "story2proposal_demo",
    model: "qwen-plus",
    status: "completed",
    startedAt: "2026-04-22 22:11",
    updatedAt: "2026-04-22 22:19",
  },
];

export const mockStories: StoryItem[] = [
  {
    id: "adaptive_graph_writer",
    title: "Adaptive Graph Writer",
    topic: "结构化科研写作",
    updatedAt: "2026-04-23 00:40",
    summary: "一个围绕多 Agent 论文 scaffold 生成的研究故事样例。",
  },
  {
    id: "story2proposal_demo",
    title: "Story2Proposal Demo Story",
    topic: "多 Agent 科研写作",
    updatedAt: "2026-04-22 19:20",
    summary: "一个用来验证 blueprint、contract 和 review loop 的 demo story。",
  },
];

export const mockRunDetail: RunDetail = {
  ...mockRuns[0],
  currentNode: "review_controller",
  currentSectionId: "method",
  nextNode: "section_writer",
  sections: [
    { id: "intro", title: "引言", status: "approved", rewriteCount: 1 },
    { id: "method", title: "方法", status: "review", rewriteCount: 2 },
    { id: "experiment", title: "实验", status: "pending", rewriteCount: 0 },
    { id: "conclusion", title: "结论", status: "pending", rewriteCount: 0 },
  ],
  artifacts: [
    {
      id: "blueprint",
      label: "Blueprint",
      kind: "blueprint",
      content:
        "paper_title: Story2Proposal\nsections:\n  - intro\n  - method\n  - experiment\n  - conclusion",
    },
    {
      id: "contract",
      label: "Contract",
      kind: "contract",
      content:
        "{\n  \"current_section\": \"method\",\n  \"required_claims\": [\"c1\", \"c2\"],\n  \"required_visual_ids\": [\"fig_method\"]\n}",
    },
    {
      id: "drafts",
      label: "Drafts",
      kind: "drafts",
      content: "## Method\nWe frame manuscript generation as a constrained multi-agent writing process...",
    },
    {
      id: "reviews",
      label: "Reviews",
      kind: "reviews",
      content:
        "{\n  \"status\": \"revise\",\n  \"issues\": [\"Need clearer alignment between claim c2 and evidence e4\"]\n}",
    },
    {
      id: "manuscript",
      label: "Manuscript",
      kind: "manuscript",
      content: "# Story2Proposal\n\nA scaffold for structured scientific paper writing...",
    },
    {
      id: "logs",
      label: "Logs",
      kind: "logs",
      content:
        "[01:08] orchestrator started\n[01:09] architect completed\n[01:15] review_controller requested rewrite",
    },
  ],
  summary: [
    "当前章节正在 review 阶段。",
    "Method 章节已经被重写了两次。",
    "系统正在等待回到 section_writer。",
  ],
};
