import { create } from "zustand";

type ArtifactTab = "blueprint" | "contract" | "drafts" | "reviews" | "manuscript" | "evaluation" | "benchmark" | "logs";

interface UiState {
  activeArtifact: ArtifactTab;
  setActiveArtifact: (tab: ArtifactTab) => void;
}

export const useUiStore = create<UiState>((set) => ({
  activeArtifact: "blueprint",
  setActiveArtifact: (tab) => set({ activeArtifact: tab }),
}));
