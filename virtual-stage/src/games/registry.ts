import type { ComponentType } from "react";

import { AskBackGame } from "./ask_back";
import { CueCardGame } from "./cue_card";
import { EchoChamberGame } from "./echo_chamber";
import { FillInGame } from "./fill_blank";
import { InterviewerGame } from "./interviewer";
import { OverhearGame } from "./overhear";
import { ParaphraseGame } from "./paraphrase";
import { PlayDumbGame } from "./play_dumb";
import { ReactGame } from "./react";
import { ReviewGame } from "./review";
import { RoleplayGame } from "./roleplay";
import { TabooGame } from "./taboo";
import { WordOrderGame } from "./word_order";

export type GameOptionListing = {
  name: string;
  values: string[];
  default: string;
  /** value -> label in the source language */
  labels: Record<string, string>;
};

export type GameListing = {
  id: string;
  phase: number;
  title: string;
  summary?: string;
  tags?: string[];
  available?: boolean;
  reason?: string;
  next?: string;
  /** When the card offers Read the text: `play` the whole round, `between` once it is over. */
  read_text?: "play" | "between";
  last?: { hit: number; total: number } | null;
  options?: GameOptionListing[];
};

export type GameQuestItem = { id: string; text: string; status: string };

export type GameScore =
  | { kind: "rubric"; fluency: number; density: number; summary?: string }
  | { kind: "hits"; hit: number; total: number }
  | null;

export type GameChrome = {
  game_id?: string;
  finished?: boolean;
  instruction?: string;
  phrase?: string;
  hint?: string;
  feedback?: string;
  feedback_text?: string;
  quest?: GameQuestItem[];
  score?: GameScore;
  steer?: string;
  withheld?: boolean;
  buzzer?: boolean;
  source?: string;
  matches?: number;
  misses?: number;
  total?: number;
  /** Targets hit or missed out, for the progress bar. */
  closed?: number;
  /** H12. The page shows the open target's buddy lines as `…`. */
  mask_lines?: boolean;
  masked_lines?: string[];
  /** H12. The game the Round over card offers next. */
  next?: string;
  miss_note?: { sentence_id?: string; explanation?: string; expected?: string } | null;
  /** Closed targets with a gloss in the session's targets (H14). Open targets never appear. */
  glosses?: { id: string; phrase: string; status: string; gloss: Record<string, string> }[];
  /** H9. ReviewGame: the title of the open chunk's source. */
  origin?: string;
  /** H5. The game can be finished early from the card. */
  finish?: boolean;
};

/** A game view is the prompt slot of GameCard: the phrase, the passage, the shuffled words. */
export type GameView = ComponentType<{ chrome: GameChrome }>;

export const gameViews: Record<string, GameView> = {
  echo_chamber: EchoChamberGame,
  interviewer: InterviewerGame,
  fill_blank: FillInGame,
  /** ListenGame shares Echo's slot. The line is not sent (reveal_phrase off), so only the instruction shows. */
  listen: EchoChamberGame,
  word_order: WordOrderGame,
  cue_card: CueCardGame,
  taboo: TabooGame,
  paraphrase: ParaphraseGame,
  play_dumb: PlayDumbGame,
  ask_back: AskBackGame,
  react: ReactGame,
  overhear: OverhearGame,
  review: ReviewGame,
  roleplay: RoleplayGame,
};
