import type { GameChrome } from "./registry";

/** InterviewerGame's prompt slot: the passage the questions are about. */
export function InterviewerGame({ chrome }: { chrome: GameChrome }) {
  if (!chrome.source) return null;
  return <div className="max-h-48 overflow-y-auto whitespace-pre-wrap text-lk-ink">{chrome.source}</div>;
}
