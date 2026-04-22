const STORY_KEY = "s2p.frontend.stories";
const RUN_KEY = "s2p.frontend.runs";
const RUN_DETAIL_KEY = "s2p.frontend.runDetails";

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function readStorage<T>(key: string, fallback: T): T {
  if (!canUseStorage()) {
    return fallback;
  }

  const raw = window.localStorage.getItem(key);
  if (!raw) {
    return fallback;
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeStorage<T>(key: string, value: T) {
  if (!canUseStorage()) {
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(value));
}

export const storageKeys = {
  stories: STORY_KEY,
  runs: RUN_KEY,
  runDetails: RUN_DETAIL_KEY,
};
