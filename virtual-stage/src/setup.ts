/**
 * The talk settings the user picks before Start. Editing them sends nothing to the hub.
 * Start applies them as one new session. The last draft is kept in this browser and prefilled.
 */

export type TeacherMode = "relaxed" | "pedantic";

export type Setup = {
  /** The source: the language of the text and the talk. "" until chosen. */
  languageId: string;
  /** Target languages, written on the card as glosses. Never the source. At most MAX_TARGETS. */
  targets: string[];
  /** Botnet mode when true, web mode when false. */
  hostMode: boolean;
  qa: boolean;
  /** "" until a buddy is chosen. */
  personalityId: string;
  /** "" until a raw material is chosen. */
  materialId: string;
  /** null until chosen. "" is Free speech. */
  gameId: string | null;
  /** The chosen game's declared options, by name. Sent as game_options. */
  gameOptions: Record<string, string>;
  teacherMode: TeacherMode;
};

export const MAX_TARGETS = 4;

export const EMPTY_SETUP: Setup = {
  languageId: "",
  targets: [],
  hostMode: false,
  qa: false,
  personalityId: "",
  materialId: "",
  gameId: null,
  gameOptions: {},
  teacherMode: "relaxed",
};

const SETUP_KEY = "logoskittens.setup";
const SOURCE_KEY = "logoskittens.source";
const TARGETS_KEY = "logoskittens.targets";

/** Targets in order, without the source, without repeats, at most MAX_TARGETS. */
export function cleanTargets(targets: string[], source: string): string[] {
  const kept: string[] = [];
  for (const code of targets) {
    if (typeof code !== "string" || !code || code === source || kept.includes(code)) continue;
    kept.push(code);
  }
  return kept.slice(0, MAX_TARGETS);
}

/** Whether this browser has ever stored a target choice. The first visit takes the first entry of the set. */
export function targetsChosen(): boolean {
  try {
    return localStorage.getItem(TARGETS_KEY) !== null;
  } catch {
    return false;
  }
}

function storedTargets(fallback: unknown): string[] {
  try {
    const raw = localStorage.getItem(TARGETS_KEY);
    const value = raw === null ? fallback : JSON.parse(raw);
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function stringMap(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const kept: Record<string, string> = {};
  for (const [key, item] of Object.entries(value)) if (typeof item === "string") kept[key] = item;
  return kept;
}

export function readSetup(): Setup {
  try {
    const raw = localStorage.getItem(SETUP_KEY);
    if (!raw) return { ...EMPTY_SETUP, targets: storedTargets([]) };
    const value = JSON.parse(raw) as Partial<Setup>;
    const languageId = typeof value.languageId === "string" ? value.languageId : "";
    return {
      languageId,
      targets: cleanTargets(storedTargets(value.targets), languageId),
      hostMode: value.hostMode === true,
      qa: value.qa === true,
      personalityId: typeof value.personalityId === "string" ? value.personalityId : "",
      materialId: typeof value.materialId === "string" ? value.materialId : "",
      gameId: typeof value.gameId === "string" ? value.gameId : null,
      gameOptions: stringMap(value.gameOptions),
      teacherMode: value.teacherMode === "pedantic" ? "pedantic" : "relaxed",
    };
  } catch {
    return EMPTY_SETUP;
  }
}

export function writeSetup(setup: Setup) {
  try {
    localStorage.setItem(SETUP_KEY, JSON.stringify(setup));
    localStorage.setItem(SOURCE_KEY, setup.languageId);
    localStorage.setItem(TARGETS_KEY, JSON.stringify(setup.targets));
  } catch {
    /* the next refresh starts from an empty panel */
  }
}

/** Language, buddy, raw material, and game must be chosen. Mode, QA, and teacher mode always have a value. */
export function setupComplete(setup: Setup): boolean {
  return Boolean(setup.languageId && setup.personalityId && setup.materialId && setup.gameId !== null);
}

export function sameSetup(left: Setup, right: Setup): boolean {
  return (
    left.languageId === right.languageId &&
    left.targets.join(",") === right.targets.join(",") &&
    left.hostMode === right.hostMode &&
    left.qa === right.qa &&
    left.personalityId === right.personalityId &&
    left.materialId === right.materialId &&
    left.gameId === right.gameId &&
    JSON.stringify(left.gameOptions) === JSON.stringify(right.gameOptions) &&
    (left.gameId !== "" || left.teacherMode === right.teacherMode)
  );
}

/** Drop choices the newly loaded language does not offer, so Start cannot send a stale id. */
export function pruneSetup(
  setup: Setup,
  language: string,
  offered: { personalities: string[]; materials: string[]; games: string[] },
): Setup {
  if (setup.languageId !== language) return setup;
  const next = { ...setup };
  if (next.personalityId && !offered.personalities.includes(next.personalityId)) next.personalityId = "";
  if (next.materialId && !offered.materials.includes(next.materialId)) next.materialId = "";
  if (next.gameId && !offered.games.includes(next.gameId)) next.gameId = null;
  return sameSetup(next, setup) && next.teacherMode === setup.teacherMode ? setup : next;
}
