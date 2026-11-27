import type { GameChrome } from "./registry";

/** FillInGame's prompt slot. Her unfinished line is in the log. The completion is never printed. */
export function FillInGame({ chrome }: { chrome: GameChrome }) {
  if (chrome.finished) return null;
  return <p>Finish her sentence.</p>;
}
