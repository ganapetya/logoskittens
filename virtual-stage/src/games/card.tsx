import { useEffect, useRef } from "react";

import { GlossRow } from "../languages";
import type { GameChrome, GameListing, GameView } from "./registry";

/**
 * The one card above the log for every game (Stage U). A game view supplies only the prompt slot.
 * Top to bottom: progress, tally, prompt slot, glosses, feedback, hint, quest, score, Round over actions.
 */
export function GameCard({
  chrome,
  view: View,
  targets,
  known,
  next,
  onNewRound,
  onNext,
  onFreeTalk,
  onFinish,
  readText,
  onReadText,
}: {
  chrome: GameChrome;
  view?: GameView;
  targets: string[];
  known?: { id: string; display_name: string }[];
  /** The listed game the manifest suggests next, when it can start. */
  next?: GameListing | null;
  onNewRound: () => void;
  onNext: (gameId: string) => void;
  onFreeTalk: () => void;
  /** H5. Close the round now and show its score. */
  onFinish?: () => void;
  /** The game's manifest `read_text`. `play`: the Read the text button shows the whole round. */
  readText?: "play" | "between";
  /** Opens the Read the text window on the round's material. */
  onReadText?: () => void;
}) {
  const total = chrome.total ?? 0;
  const closed = Math.min(total, closedCount(chrome));
  const feedback = chrome.feedback === "match" || chrome.feedback === "miss" ? chrome.feedback : "";
  const actions = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (chrome.finished) actions.current?.querySelector("button")?.focus();
  }, [chrome.finished]);
  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <div
          role="progressbar"
          aria-label="Targets closed"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={closed}
          className="h-2 flex-1 overflow-hidden rounded-full bg-lk-line"
        >
          <div className="h-full bg-lk-primary" style={{ width: total ? `${(closed / total) * 100}%` : "0%" }} />
        </div>
        <p className="shrink-0 text-lk-ink">
          {chrome.matches ?? 0} match · {chrome.misses ?? 0} miss
        </p>
      </div>
      {chrome.finished ? (
        <div className="mb-3">
          <p className="text-lg text-lk-ink">Round over</p>
          <p className="mt-1">
            {chrome.matches ?? 0} of {total} right.
          </p>
        </div>
      ) : null}
      {View ? <View chrome={chrome} /> : <Fallback chrome={chrome} />}
      {onReadText && readText === "play" && !chrome.finished && !chrome.source ? (
        <button
          type="button"
          onClick={onReadText}
          className="mt-2 rounded-full border border-lk-label px-3 py-1 text-sm text-lk-label"
        >
          Read the text
        </button>
      ) : null}
      <GlossRow glosses={chrome.glosses ?? []} targets={targets} all={Boolean(chrome.finished)} known={known} />
      <div aria-live="polite" className="mt-3 flex flex-col gap-2">
        {chrome.buzzer ? <p className="text-lk-red">Buzz. That word is off limits.</p> : null}
        {feedback && !chrome.finished ? (
          <p>
            <span className="inline-block rounded-full bg-lk-primary px-3 py-1 text-xs uppercase tracking-wide text-white">
              {feedback}
            </span>
            {feedback === "miss" && chrome.feedback_text ? <span className="ms-2">{chrome.feedback_text}</span> : null}
          </p>
        ) : null}
        {chrome.hint && !chrome.finished ? <p className="text-lk-ink">Hint: {chrome.hint}</p> : null}
      </div>
      {chrome.quest && chrome.quest.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-1">
          {chrome.quest.map((item) => (
            <li key={item.id} className="flex justify-between gap-2">
              <span>{item.text}</span>
              <span className="text-xs uppercase">{item.status}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {chrome.score ? <Score score={chrome.score} /> : null}
      {chrome.finish && !chrome.finished && onFinish ? (
        <div className="mt-4">
          <button
            type="button"
            onClick={onFinish}
            className="rounded-full border border-lk-primary px-4 py-2 text-lk-ink"
          >
            Finish
          </button>
        </div>
      ) : null}
      {chrome.finished ? (
        <div ref={actions} className="mt-4 flex flex-wrap gap-2">
          <button type="button" onClick={onNewRound} className="rounded-full bg-lk-primary px-4 py-2 text-white">
            New round
          </button>
          {onReadText ? (
            <button
              type="button"
              onClick={onReadText}
              className="rounded-full border border-lk-primary px-4 py-2 text-lk-ink"
            >
              Read the text
            </button>
          ) : null}
          {next && next.available !== false ? (
            <button
              type="button"
              onClick={() => onNext(next.id)}
              className="rounded-full border border-lk-primary px-4 py-2 text-lk-ink"
            >
              Next: {next.title}
            </button>
          ) : null}
          <button
            type="button"
            onClick={onFreeTalk}
            className="rounded-full border border-lk-primary px-4 py-2 text-lk-ink"
          >
            Back to free talk
          </button>
        </div>
      ) : null}
    </div>
  );
}

function closedCount(chrome: GameChrome): number {
  if (typeof chrome.closed === "number") return chrome.closed;
  return chrome.finished ? (chrome.total ?? 0) : (chrome.matches ?? 0);
}

function Fallback({ chrome }: { chrome: GameChrome }) {
  return (
    <div>
      {chrome.instruction ? <p>{chrome.instruction}</p> : null}
      {chrome.phrase ? <p className="mt-2 text-lg text-lk-ink">{chrome.phrase}</p> : null}
    </div>
  );
}

function Score({ score }: { score: NonNullable<GameChrome["score"]> }) {
  if (score.kind === "hits") {
    return (
      <p className="mt-3 text-lk-ink">
        Score: {score.hit} of {score.total}
      </p>
    );
  }
  return (
    <div className="mt-3 text-lk-ink">
      <p>
        Fluency {score.fluency} · Density {score.density}
      </p>
      {score.summary ? <p className="mt-1">{score.summary}</p> : null}
    </div>
  );
}
