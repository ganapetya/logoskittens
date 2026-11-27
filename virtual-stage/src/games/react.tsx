import type { GameChrome } from "./registry";

/**
 * ReactGame's prompt slot: the situation, and the text the reactions come from. The text starts open so it can be
 * read before the first line, and folds away while playing. Her feeling shows on the avatar; the token is never drawn.
 */
export function ReactGame({ chrome }: { chrome: GameChrome }) {
  if (chrome.finished) return null;
  return (
    <div>
      {chrome.instruction ? (
        <p dir="auto" className="text-lg text-lk-ink">
          {chrome.instruction}
        </p>
      ) : null}
      <p className="mt-1">React with words from the text.</p>
      {chrome.source ? (
        <details open className="mt-2">
          <summary className="cursor-pointer text-sm text-lk-label">The text</summary>
          <div dir="auto" className="mt-1 max-h-48 overflow-y-auto whitespace-pre-wrap text-lk-ink">
            {chrome.source}
          </div>
        </details>
      ) : null}
    </div>
  );
}
