import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { StoryWorkbench } from "../features/stories/StoryWorkbench";
import { createRunFromStory } from "../services/runs";
import { listStories, saveStory } from "../services/stories";
import type { StoryDraft } from "../types/story";

export function StoriesPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { data = [] } = useQuery({
    queryKey: ["stories"],
    queryFn: listStories,
  });

  const saveMutation = useMutation({
    mutationFn: (draft: StoryDraft) => saveStory(draft),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["stories"] });
    },
  });

  const createRunMutation = useMutation({
    mutationFn: (draft: StoryDraft) => createRunFromStory(draft),
    onSuccess: async (run) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["stories"] }),
        queryClient.invalidateQueries({ queryKey: ["runs"] }),
      ]);
      navigate(`/runs/${run.id}`);
    },
  });

  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <div className="eyebrow">Story</div>
          <h1>ResearchStory 配置</h1>
        </div>
      </div>
      <StoryWorkbench
        stories={data}
        onSave={async (draft) => {
          await saveMutation.mutateAsync(draft);
        }}
        onRun={async (draft) => {
          const saved = await saveMutation.mutateAsync(draft);
          await createRunMutation.mutateAsync(saved);
        }}
      />
    </div>
  );
}
