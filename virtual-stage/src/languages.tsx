/**
 * Source and target languages (games.md, H14). Connected, the sets come from LogosCat through the hub;
 * logged out, they are every language this hub speaks. Both hold only supported languages. Each origin
 * remembers its own choice (setup.ts). The source is spoken and heard. Targets are only written on the card.
 */

import { MAX_TARGETS } from "./setup";

export type SourceOption = { id: string; live: boolean; reason: string };
export type LanguageSets = {
  origin: "logoscat" | "local";
  sources: SourceOption[];
  targets: { id: string }[];
  /** LogosCat languages this hub cannot speak yet. They are named, not offered. */
  skipped?: string[];
  /** The first choice for an origin with nothing remembered yet. */
  default_source?: string;
  default_targets?: string[];
  notice?: string;
};
export type Gloss = { id: string; phrase: string; status: string; gloss: Record<string, string> };

export const LOCAL_SETS: LanguageSets = {
  origin: "local",
  sources: [
    { id: "en", live: true, reason: "" },
    { id: "nb", live: true, reason: "" },
    { id: "uk", live: true, reason: "" },
    { id: "de", live: true, reason: "" },
    { id: "he", live: true, reason: "" },
  ],
  targets: [{ id: "en" }, { id: "nb" }, { id: "uk" }, { id: "de" }, { id: "he" }],
};

const OWN_NAMES: Record<string, string> = { en: "English", nb: "Norsk", uk: "Українська", de: "Deutsch", he: "עברית" };

/** Languages written right to left. The page mirrors its layout while one of them is the source. */
const RTL = new Set(["he", "iw", "ar", "fa", "ur", "yi"]);

export function isRtl(code: string): boolean {
  return RTL.has((code || "").split("-")[0].toLowerCase());
}

/** The language's own name for itself: English, Norsk, עברית, Deutsch. Falls back to the code. */
export function languageName(code: string, known?: { id: string; display_name: string }[]): string {
  const listed = known?.find((item) => item.id === code)?.display_name;
  if (listed) return listed;
  if (OWN_NAMES[code]) return OWN_NAMES[code];
  try {
    const name = new Intl.DisplayNames([code], { type: "language" }).of(code);
    if (name && name !== code) return name.charAt(0).toLocaleUpperCase(code) + name.slice(1);
  } catch {
    /* an unknown code shows as itself */
  }
  return code;
}

/** The closed line of the section: `Norsk → English, עברית`. */
export function languagesLine(source: string, targets: string[], known?: { id: string; display_name: string }[]) {
  if (!source) return "No source chosen";
  const from = languageName(source, known);
  if (targets.length === 0) return from;
  return `${from} → ${targets.map((code) => languageName(code, known)).join(", ")}`;
}

/** The first visit takes the first live source and the first target that is not the source. */
export function firstChoice(sets: LanguageSets, source: string): { source: string; targets: string[] } {
  const live = sets.sources.filter((item) => item.live);
  const chosen = source && live.some((item) => item.id === source) ? source : (live[0]?.id ?? "");
  const target = sets.targets.find((item) => item.id !== chosen);
  return { source: chosen, targets: target ? [target.id] : [] };
}

/** The panel's short tag for where the lists come from. */
export function originTag(sets: LanguageSets, account: string): string {
  return sets.origin === "logoscat" ? (account ? `From LogosCat · ${account}` : "From LogosCat") : "Your choice";
}

export function LanguagesBlock({
  sets,
  account,
  source,
  targets,
  known,
  onSource,
  onTargets,
}: {
  sets: LanguageSets;
  account: string;
  source: string;
  targets: string[];
  known?: { id: string; display_name: string }[];
  onSource: (code: string) => void;
  onTargets: (codes: string[]) => void;
}) {
  function toggle(code: string) {
    if (targets.includes(code)) {
      onTargets(targets.filter((item) => item !== code));
    } else if (targets.length < MAX_TARGETS) {
      onTargets([...targets, code]);
    }
  }
  const fromLogosCat = sets.origin === "logoscat";
  const skipped = (sets.skipped ?? []).map((code) => languageName(code, known));
  return (
    <div>
      <p
        className={`mb-3 rounded-xl px-3 py-2 text-sm ${fromLogosCat ? "bg-lk-primary text-white" : "bg-lk-tint text-lk-ink"}`}
      >
        <span className="block">{originTag(sets, account)}</span>
        <span className="block text-xs opacity-80">
          {fromLogosCat
            ? "Your LogosCat language settings. Disconnect to use your own choice here."
            : "Every language this hub speaks. Connect LogosCat to use its settings."}
        </span>
      </p>
      <fieldset className="mb-3">
        <legend className="mb-1 text-xs text-lk-label">Source</legend>
        <ul className="flex flex-col gap-1">
          {sets.sources.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                disabled={!item.live}
                aria-pressed={item.id === source}
                onClick={() => onSource(item.id)}
                className={`w-full rounded-xl px-3 py-2 text-start disabled:opacity-60 ${item.id === source ? "bg-lk-primary text-white" : "bg-white"}`}
              >
                <span className="block">{languageName(item.id, known)}</span>
                {item.live ? null : <span className="block text-xs opacity-80">{item.reason}</span>}
              </button>
            </li>
          ))}
        </ul>
      </fieldset>
      <fieldset className="mb-2">
        <legend className="mb-1 flex w-full justify-between text-xs text-lk-label">
          <span>Targets</span>
          <span>
            {targets.length} of {MAX_TARGETS}
          </span>
        </legend>
        <ul className="flex flex-col gap-1">
          {sets.targets.map((item) => {
            const own = item.id === source;
            const checked = !own && targets.includes(item.id);
            const full = !checked && targets.length >= MAX_TARGETS;
            return (
              <li key={item.id}>
                <label
                  className={`flex items-center gap-2 rounded-xl bg-white px-3 py-2 ${own || full ? "opacity-60" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={own || full}
                    onChange={() => toggle(item.id)}
                  />
                  <span dir="auto">{languageName(item.id, known)}</span>
                  {own ? <span className="ms-auto text-xs">Source</span> : null}
                </label>
              </li>
            );
          })}
        </ul>
      </fieldset>
      {skipped.length > 0 ? (
        <p className="text-xs text-lk-muted">Not supported here yet: {skipped.join(", ")}</p>
      ) : null}
      {sets.notice ? <p className="text-xs text-lk-red">{sets.notice}</p> : null}
    </div>
  );
}

/** Glosses of closed targets. During a round the newest one, on Round over every one. */
export function GlossRow({
  glosses,
  targets,
  all,
  known,
}: {
  glosses: Gloss[];
  targets: string[];
  all: boolean;
  known?: { id: string; display_name: string }[];
}) {
  const shown = all ? glosses : glosses.slice(-1);
  if (shown.length === 0 || targets.length === 0) return null;
  return (
    <div aria-label="Glosses" className="mt-3 flex flex-col gap-2">
      {shown.map((row) => (
        <div key={row.id} className="rounded-xl bg-white px-3 py-2">
          <p className="text-lk-ink">{row.phrase}</p>
          <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            {targets
              .filter((code) => row.gloss[code])
              .map((code) => (
                <div key={code} className="contents">
                  <dt className="text-xs text-lk-label">{languageName(code, known)}</dt>
                  <dd dir="auto" lang={code}>
                    {row.gloss[code]}
                  </dd>
                </div>
              ))}
          </dl>
        </div>
      ))}
    </div>
  );
}
