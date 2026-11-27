import { cerm } from "./element_solution.js";

const message = cerm.execution.v1.ElementSolution.create({
  solutionId: "sol-1",
  actorId: "actor_tutor_01",
  emotion: cerm.execution.v1.EmotionType.EMOTION_ENCOURAGEMENT,
  speech: {
    text: "Hei!",
    languageCode: "nb",
    voiceModelId: "no_NO-talesyntese-medium",
    precomputedAudioPcm: new Uint8Array([1, 2, 3, 4]),
  },
  physicalGestures: [
    {
      primitiveName: "nod",
      targetVector: { x: 0.1, y: 0.2, z: 0.3 },
      durationMs: 800,
    },
  ],
  screenVisuals: {
    animationId: "nod",
    focusTargetId: "user",
    highlightElements: ["correction"],
  },
});

const bytes = cerm.execution.v1.ElementSolution.encode(message).finish();
const restored = cerm.execution.v1.ElementSolution.decode(bytes);
if (restored.speech?.text !== "Hei!") {
  throw new Error("element solution round-trip failed");
}
if (restored.physicalGestures[0]?.primitiveName !== "nod") {
  throw new Error("gesture was not preserved");
}
if (!restored.screenVisuals?.highlightElements?.includes("correction")) {
  throw new Error("screen cue was not preserved");
}
