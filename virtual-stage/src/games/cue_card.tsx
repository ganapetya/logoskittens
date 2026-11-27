import type { GameChrome } from "./registry";

/** CueCardGame's prompt slot: the meaning, or its gloss in a target language. The chunk itself is never printed. */
export function CueCardGame({ chrome }: { chrome: GameChrome }) {
  if (chrome.finished || !chrome.instruction) return null;
  return (
    <div>
      <p>Say the text's words for this.</p>
      <p dir="auto" className="mt-2 text-lg text-lk-ink">
        {chrome.instruction}
      </p>
    </div>
  );
}
