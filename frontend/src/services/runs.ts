import type { RunDetail, RunItem } from "../types/run";
import type { StoryDraft } from "../types/story";
import { mockRunDetail, mockRuns } from "./mockData";
import { readStorage, storageKeys, writeStorage } from "./storage";

function mergeRuns() {
  const localRuns = readStorage<RunItem[]>(storageKeys.runs, []);
  const merged = [...localRuns];

  for (const run of mockRuns) {
    if (!merged.some((item) => item.id === run.id)) {
      merged.push(run);
    }
  }

  return merged.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

function readRunDetails() {
  return readStorage<Record<string, RunDetail>>(storageKeys.runDetails, {});
}

export async function listRuns(): Promise<RunItem[]> {
  return Promise.resolve(mergeRuns());
}

export async function getRunDetail(runId: string): Promise<RunDetail> {
  const details = readRunDetails();
  return Promise.resolve(details[runId] ?? { ...mockRunDetail, id: runId });
}

export async function createRunFromStory(story: StoryDraft): Promise<RunDetail> {
  const timestamp = new Date();
  const stamp = timestamp.toISOString().replace(/[-:T]/g, "").slice(0, 14);
  const runId = `${story.id}_${stamp}`;
  const formattedTime = timestamp.toISOString().slice(0, 16).replace("T", " ");

  const runItem: RunItem = {
    id: runId,
    storyId: story.id,
    model: "qwen-plus",
    status: "running",
    startedAt: formattedTime,
    updatedAt: formattedTime,
  };

  const runDetail: RunDetail = {
    ...runItem,
    currentNode: "architect",
    currentSectionId: "introduction",
    nextNode: "section_writer",
    sections: [
      { id: "introduction", title: "引言", status: "writing", rewriteCount: 0 },
      { id: "method", title: "方法", status: "pending", rewriteCount: 0 },
      { id: "experiments", title: "实验", status: "pending", rewriteCount: 0 },
      { id: "conclusion", title: "结论", status: "pending", rewriteCount: 0 },
    ],
    artifacts: [
      {
        id: "blueprint",
        label: "Blueprint",
        kind: "blueprint",
        content: `paper_title: ${story.title}\nsection_plan:\n  - introduction\n  - method\n  - experiments\n  - conclusion`,
      },
      {
        id: "contract",
        label: "Contract",
        kind: "contract",
        content: JSON.stringify(
          {
            story_id: story.id,
            current_section: "introduction",
            topic: story.topic,
            required_claims: ["c1", "c2"],
          },
          null,
          2,
        ),
      },
      {
        id: "drafts",
        label: "Drafts",
        kind: "drafts",
        content: `## Introduction\n${story.problem}\n\n${story.motivation}`,
      },
      {
        id: "reviews",
        label: "Reviews",
        kind: "reviews",
        content: JSON.stringify(
          {
            status: "pending",
            issues: [],
            note: "Review not started yet.",
          },
          null,
          2,
        ),
      },
      {
        id: "manuscript",
        label: "Manuscript",
        kind: "manuscript",
        content: `# ${story.title}\n\nTopic: ${story.topic}\n\nProblem: ${story.problem}`,
      },
      {
        id: "logs",
        label: "Logs",
        kind: "logs",
        content: `[${formattedTime}] run created from story ${story.id}\n[${formattedTime}] orchestrator scheduled architect`,
      },
    ],
    summary: [
      `已基于 story ${story.id} 创建一个新的 run。`,
      "当前状态是 running，起始节点为 architect。",
      "这仍然是前端本地 run，后续再接真实后端接口。",
    ],
  };

  const nextRuns = [runItem, ...mergeRuns().filter((item) => item.id !== runId)];
  writeStorage(storageKeys.runs, nextRuns);

  const nextDetails = {
    ...readRunDetails(),
    [runId]: runDetail,
  };
  writeStorage(storageKeys.runDetails, nextDetails);

  return Promise.resolve(runDetail);
}
