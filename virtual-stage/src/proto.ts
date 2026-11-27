import { cerm } from "./gen/element_solution.js";

const EMOTIONS = [
  "EMOTION_NEUTRAL",
  "EMOTION_CURIOSITY",
  "EMOTION_DISAPPOINTMENT",
  "EMOTION_AMUSEMENT",
  "EMOTION_ENCOURAGEMENT",
  "EMOTION_FRUSTRATION",
] as const;

export type SolutionView = {
  solutionId: string;
  actorId: string;
  emotion: string;
  text: string;
  animationId: string;
  highlights: string[];
  pcm: Uint8Array;
};

type ProtoMessage = {
  solutionId?: string;
  actorId?: string;
  emotion?: number;
  speech?: { text?: string; precomputedAudioPcm?: Uint8Array };
  screenVisuals?: { animationId?: string; highlightElements?: string[] };
};

export function decodeSolution(payload: Uint8Array): SolutionView {
  const message = cerm.execution.v1.ElementSolution.decode(payload) as ProtoMessage;
  const emotionIndex = message.emotion ?? 0;
  return {
    solutionId: message.solutionId ?? "",
    actorId: message.actorId ?? "",
    emotion: EMOTIONS[emotionIndex] ?? "EMOTION_NEUTRAL",
    text: message.speech?.text ?? "",
    animationId: message.screenVisuals?.animationId ?? "",
    highlights: message.screenVisuals?.highlightElements ?? [],
    pcm: message.speech?.precomputedAudioPcm ?? new Uint8Array(),
  };
}
