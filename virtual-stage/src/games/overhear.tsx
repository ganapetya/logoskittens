import type { GameChrome } from "./registry";

/** OverhearGame's prompt slot. Savelij and she talk first; their lines are in the log. No passage. */
export function OverhearGame({ chrome }: { chrome: GameChrome }) {
  if (chrome.finished) return null;
  return <p>Listen to them talk, then answer her question.</p>;
}
