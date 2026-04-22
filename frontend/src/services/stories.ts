import type { StoryDraft } from "../types/story";
import { mockStories } from "./mockData";
import { readStorage, storageKeys, writeStorage } from "./storage";

const mockStoryDrafts: StoryDraft[] = mockStories.map((story, index) => ({
  ...story,
  problem:
    index === 0
      ? "How to turn a structured research story into a controllable manuscript scaffold."
      : "How to coordinate multiple writing agents under explicit section constraints.",
  motivation:
    "Free-form paper generation is easy to drift. We want a more traceable writing pipeline.",
  method:
    "Use a multi-agent workflow to produce blueprint, contract, drafts, reviews and rendered manuscript.",
  contributions:
    "A structured writing workflow, a section-level review loop, and a renderable manuscript state.",
  experiments:
    "Demonstrate the workflow on representative scientific writing stories.",
  findings:
    "The scaffold improves traceability and section-level control.",
  limitations:
    "The current system still relies on prompt quality and mock frontend data.",
}));

function mergeStories() {
  const localStories = readStorage<StoryDraft[]>(storageKeys.stories, []);
  const merged = [...localStories];

  for (const story of mockStoryDrafts) {
    if (!merged.some((item) => item.id === story.id)) {
      merged.push(story);
    }
  }

  return merged.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export async function listStories(): Promise<StoryDraft[]> {
  return Promise.resolve(mergeStories());
}

export async function saveStory(draft: StoryDraft): Promise<StoryDraft> {
  const current = mergeStories().filter((item) => item.id !== draft.id);
  const next = [{ ...draft, updatedAt: new Date().toISOString().slice(0, 16).replace("T", " ") }, ...current];
  writeStorage(storageKeys.stories, next);
  return Promise.resolve(next[0]);
}
