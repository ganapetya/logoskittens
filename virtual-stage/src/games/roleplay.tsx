import type { GameChrome } from "./registry";

/** RoleplayGame's prompt slot: the scene. The quest list, its statuses, and Finish are on the card. */
export function RoleplayGame({ chrome }: { chrome: GameChrome }) {
  if (!chrome.instruction) return null;
  return (
    <div>
      <p dir="auto" className="text-lg text-lk-ink">
        {chrome.instruction}
      </p>
      {chrome.finished ? null : <p className="mt-1">Use the phrases below while you talk with her.</p>}
    </div>
  );
}
