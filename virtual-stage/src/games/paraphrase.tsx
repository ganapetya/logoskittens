import type { GameChrome } from "./registry";

/** ParaphraseChallengerGame's prompt slot: what to do with her plain line. The hint shows after a miss. */
export function ParaphraseGame({ chrome }: { chrome: GameChrome }) {
  if (chrome.finished || !chrome.instruction) return null;
  return <p dir="auto">{chrome.instruction}</p>;
}
