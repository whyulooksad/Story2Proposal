import type { StoryItem } from "../../types/story";

export function StoryList({ stories }: { stories: StoryItem[] }) {
  return (
    <div className="story-grid">
      {stories.map((story) => (
        <article className="story-card" key={story.id}>
          <div className="story-meta">{story.updatedAt}</div>
          <h3>{story.title}</h3>
          <p>{story.summary}</p>
          <div className="story-topic">{story.topic}</div>
          <button className="ghost-button" type="button">
            使用这个 Story
          </button>
        </article>
      ))}
    </div>
  );
}
