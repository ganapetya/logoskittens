import type { GameChrome } from "./registry";

/** EchoChamberGame's prompt slot: the instruction and the line to say. */
export function EchoChamberGame({ chrome }: { chrome: GameChrome }) {
  if (chrome.finished) return null;
  return (
    <div>
      {chrome.instruction ? <p>{chrome.instruction}</p> : null}
      {chrome.phrase ? <p className="mt-2 text-lg text-lk-ink">{chrome.phrase}</p> : null}
    </div>
  );
}
