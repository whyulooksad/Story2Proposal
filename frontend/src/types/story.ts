export interface StoryItem {
  id: string;
  title: string;
  topic: string;
  updatedAt: string;
  summary: string;
}

export interface StoryDraft extends StoryItem {
  problem: string;
  motivation: string;
  method: string;
  contributions: string;
  experiments: string;
  findings: string;
  limitations: string;
}
