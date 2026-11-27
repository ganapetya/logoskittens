import type { GameChrome } from "./registry";

/**
 * TabooGame's prompt slot: the card's ban, in Wren's words. Her question is in the log.
 * The beep on `buzzer` is played by the page (App), with no PCM from the hub.
 */
export function TabooGame({ chrome }: { chrome: GameChrome }) {
  if (chrome.finished || !chrome.instruction) return null;
  return (
    <p dir="auto" className="rounded border border-lk-red px-3 py-2 text-lk-red">
      {chrome.instruction}
    </p>
  );
}
