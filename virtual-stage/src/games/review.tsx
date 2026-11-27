import type { GameChrome } from "./registry";

/** ReviewGame's prompt slot: the meaning of an earlier chunk, and the text it came from. */
export function ReviewGame({ chrome }: { chrome: GameChrome }) {
  if (chrome.finished || !chrome.instruction) return null;
  return (
    <div>
      {chrome.origin ? <p className="text-xs text-lk-label">From: {chrome.origin}</p> : null}
      <p dir="auto" className="mt-1 text-lg text-lk-ink">
        {chrome.instruction}
      </p>
    </div>
  );
}
