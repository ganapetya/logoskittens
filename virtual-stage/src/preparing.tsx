import { useEffect, useState } from "react";

const ROUND = [
  "kittens are unrolling the text like a ball of yarn",
  "herding kittens into neat little piles of words",
  "a kitten is sharpening its claws on the grammar",
  "kittens are chasing the best phrases around the room",
  "counting whiskers and verbs",
  "a sleepy kitten is reading the passage twice",
  "kittens are hiding the answers under the sofa",
  "warming up the purr engine",
  "untangling the sentences one paw at a time",
  "the kittens voted: one more stretch, then we play",
];

const IMPORT = [
  "kittens are fetching your session from LogosCat",
  "a kitten is carrying the text home in its mouth",
  "kittens are shaking the dust off the sentences",
];

/** The hub sends no progress, so the bar is a guess. It fills fast, then slows near the end, until the wait ends. */
const SLOWDOWN_MS = 9000;
const CAP = 94;

/**
 * The bar and the rotating line shown while a round is prepared or a session is imported. `kind` picks the lines.
 */
export function Preparing({ kind }: { kind: "round" | "import" }) {
  const lines = kind === "import" ? IMPORT : ROUND;
  const [started] = useState(() => Date.now());
  const [now, setNow] = useState(started);
  const [offset] = useState(() => Math.floor(Math.random() * lines.length));

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 200);
    return () => window.clearInterval(timer);
  }, []);

  const elapsed = now - started;
  const filled = CAP * (1 - Math.exp(-elapsed / SLOWDOWN_MS));
  const line = lines[(offset + Math.floor(elapsed / 2800)) % lines.length];
  return (
    <div>
      <div
        role="progressbar"
        aria-label={kind === "import" ? "Importing the session" : "Preparing the round"}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(filled)}
        className="h-2 overflow-hidden rounded-full bg-lk-line"
      >
        <div
          className="h-full bg-lk-primary transition-[width] duration-200 ease-linear"
          style={{ width: `${filled}%` }}
        />
      </div>
      <p className="mt-2 text-lk-ink">
        …{line}…
      </p>
    </div>
  );
}
