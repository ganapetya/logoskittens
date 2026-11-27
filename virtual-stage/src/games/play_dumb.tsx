import type { GameChrome } from "./registry";

/** PlayDumbGame's prompt slot. Her wrong statement is in the log. No passage: the user corrects from memory. */
export function PlayDumbGame({ chrome }: { chrome: GameChrome }) {
  if (chrome.finished) return null;
  return <p>She has it wrong. Correct her with the text's words.</p>;
}
