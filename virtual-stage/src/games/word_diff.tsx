/** Word-level diff between what was heard and the line a game expected. */

export type DiffWord = { text: string; ok: boolean };

/** Same fold as the hub: NFKC, casefold, drop punctuation and symbols. */
function fold(word: string): string {
  return word
    .normalize("NFKC")
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]/gu, "");
}

function words(text: string): string[] {
  return text.split(/\s+/).filter((word) => fold(word) !== "");
}

/** Marks each word of both lines as kept (in the longest common subsequence) or not. */
export function diffWords(heard: string, expected: string): { heard: DiffWord[]; expected: DiffWord[] } {
  const left = words(heard);
  const right = words(expected);
  const a = left.map(fold);
  const b = right.map(fold);
  const table = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const keptLeft = new Array<boolean>(a.length).fill(false);
  const keptRight = new Array<boolean>(b.length).fill(false);
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      keptLeft[i] = true;
      keptRight[j] = true;
      i += 1;
      j += 1;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      i += 1;
    } else {
      j += 1;
    }
  }
  return {
    heard: left.map((text, index) => ({ text, ok: keptLeft[index] })),
    expected: right.map((text, index) => ({ text, ok: keptRight[index] })),
  };
}

function Words({ items, mark }: { items: DiffWord[]; mark: string }) {
  return (
    <>
      {items.map((item, index) => (
        <span key={index}>
          {index > 0 ? " " : ""}
          {item.ok ? item.text : <span className={mark}>{item.text}</span>}
        </span>
      ))}
    </>
  );
}

export function WordDiff({ heard, expected }: { heard: string; expected: string }) {
  const diff = diffWords(heard, expected);
  return (
    <div className="text-xs text-lk-muted">
      <p className="text-lk-red">
        Wrong. The line was: <Words items={diff.expected} mark="font-semibold underline decoration-2" />
      </p>
      <p>
        Heard: <Words items={diff.heard} mark="text-lk-red line-through" />
      </p>
    </div>
  );
}
