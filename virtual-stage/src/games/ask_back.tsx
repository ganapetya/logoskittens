import type { GameChrome } from "./registry";

/** AskBackGame's prompt slot: the passage. Her line is an answer; ask the question it answers. */
export function AskBackGame({ chrome }: { chrome: GameChrome }) {
  if (chrome.finished) return null;
  return (
    <div>
      <p>Ask the question her answer fits.</p>
      {chrome.source ? (
        <div className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap text-lk-ink">{chrome.source}</div>
      ) : null}
    </div>
  );
}
