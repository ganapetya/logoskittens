import type { GameChrome } from "./registry";

/** WordOrderGame's prompt slot: the sentence's words, shuffled, as chips. Say them in order. */
export function WordOrderGame({ chrome }: { chrome: GameChrome }) {
  if (chrome.finished) return null;
  const words = (chrome.instruction ?? "")
    .split(" / ")
    .map((word) => word.trim())
    .filter(Boolean);
  if (words.length === 0) return null;
  return (
    <div>
      <p>Say the sentence with these words in order.</p>
      <ul className="mt-2 flex flex-wrap gap-2" aria-label="Shuffled words">
        {words.map((word, index) => (
          <li
            key={`${index}-${word}`}
            dir="auto"
            className="rounded border border-lk-line bg-white px-2 py-1 text-lk-ink"
          >
            {word}
          </li>
        ))}
      </ul>
    </div>
  );
}
