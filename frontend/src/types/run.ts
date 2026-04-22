export type RunStatus = "pending" | "running" | "completed" | "failed";

export interface RunItem {
  id: string;
  storyId: string;
  model: string;
  status: RunStatus;
  startedAt: string;
  updatedAt: string;
}

export interface SectionState {
  id: string;
  title: string;
  status: "pending" | "writing" | "review" | "approved" | "revise";
  rewriteCount: number;
}

export interface RunArtifact {
  id: string;
  label: string;
  kind: "blueprint" | "contract" | "drafts" | "reviews" | "manuscript" | "logs";
  content: string;
}

export interface RunDetail extends RunItem {
  currentNode: string;
  currentSectionId: string | null;
  nextNode: string | null;
  sections: SectionState[];
  artifacts: RunArtifact[];
  summary: string[];
}
