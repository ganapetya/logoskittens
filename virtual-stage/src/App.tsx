import { FormEvent, PointerEvent as ReactPointerEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { ActorCard } from "./avatars";
import {
  clearAuth,
  displayName,
  ConnectPanel,
  readAuth,
  SessionsPanel,
  ENDED,
  type LogosCatAuth,
  type WorkspaceSession,
} from "./logoscat";
import { GameCard } from "./games/card";
import { gameViews, type GameChrome, type GameListing } from "./games/registry";
import { WordDiff } from "./games/word_diff";
import { firstChoice, languageName, LanguagesBlock, languagesLine, LOCAL_SETS, type LanguageSets } from "./languages";
import { playPcm } from "./pcm";
import { Preparing } from "./preparing";
import { decodeSolution, type SolutionView } from "./proto";
import { TextReader } from "./text_reader";
import { MaterialEditor, type SavedMaterial } from "./material_editor";
import { startRecording, type HoldRecording } from "./vad";
import {
  cleanTargets,
  pruneSetup,
  readSetup,
  sameSetup,
  setupComplete,
  targetsChosen,
  writeSetup,
  type Setup,
  type TeacherMode,
} from "./setup";

const HUB_WS = import.meta.env.VITE_HUB_WS ?? "ws://localhost:8090/ws";
const HUB_HTTP = import.meta.env.VITE_HUB_HTTP ?? "http://localhost:8090";
const DIAL_URL = dialUrl(HUB_WS);

/** H8. The one game in which Savelij speaks (deck lines only), so his card shows while it runs. */
const TEACHER_GAME = "overhear";

type PlayerRow = {
  body_id: string;
  display_name: string;
  role: string;
  steerer: string;
  speaking: string;
  stances: string[];
  ready: boolean;
  reason: string;
};

type Line = {
  id: string;
  speaker: string;
  text: string;
  altered?: boolean;
  steer?: string;
  noteId?: string;
  explanation?: string;
  verdict?: string;
  expected?: string;
};
type Material = { id: string; title: string; language: string; origin?: string; logoscat_user_id?: number };
type Personality = { id: string; name: string; summary: string };
type Catalog = {
  languages: { id: string; display_name: string }[];
  materials: Material[];
  personalities: Personality[];
  teacher_name?: string;
  teacher_summary?: string;
  games?: GameListing[];
};
type Sentence = {
  id?: string;
  speaker: string;
  text: string;
  altered?: boolean;
  steer?: string;
  note_id?: string;
  explanation?: string;
  verdict?: string;
  expected?: string;
};
type HeardPiece = { id?: string; text?: string };
type TeacherNote = { sentence_id?: string; note_id?: string; explanation?: string };
type BobStatus = "idle" | "thinking" | "failed";

function dialUrl(hubWs: string): string {
  const trimmed = hubWs.replace(/\/$/, "");
  if (trimmed.endsWith("/ws")) return `${trimmed.slice(0, -3)}/players`;
  return `${trimmed}/players`;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  const step = 0x8000;
  for (let index = 0; index < bytes.length; index += step) {
    binary += String.fromCharCode(...bytes.subarray(index, index + step));
  }
  return btoa(binary);
}

function playBeep() {
  const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctx) return;
  const ctx = new Ctx();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.frequency.value = 880;
  gain.gain.value = 0.05;
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.12);
  osc.onended = () => void ctx.close();
}

const PHASES: [number, string][] = [
  [1, "Phase 1 · Guided"],
  [2, "Phase 2 · Apply"],
  [3, "Phase 3 · Free"],
];

const NARROW = "(max-width: 767px)";

function narrowViewport(): boolean {
  try {
    return window.matchMedia(NARROW).matches;
  } catch {
    return false;
  }
}

/** One collapsible Talk panel section. Closed, it shows its current choice on one line. */
function PanelSection({
  id,
  title,
  summary,
  open,
  onToggle,
  children,
}: {
  id: string;
  title: string;
  summary: string;
  open: boolean;
  onToggle: (id: string) => void;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={`panel-${id}`} className="mb-3 rounded-2xl bg-white/80 px-3 py-2">
      <h2 id={`panel-${id}`}>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={`panel-${id}-body`}
          onClick={() => onToggle(id)}
          className="flex w-full items-baseline justify-between gap-2 py-1 text-left"
        >
          <span className="text-xs tracking-[0.16em] uppercase text-lk-label">{title}</span>
          <span aria-hidden="true" className="text-xs text-lk-label">
            {open ? "−" : "+"}
          </span>
        </button>
      </h2>
      {open ? null : <p className="truncate pb-1 text-sm text-lk-ink" dir="auto">{summary}</p>}
      <div id={`panel-${id}-body`} hidden={!open} className="pt-2">
        {children}
      </div>
    </section>
  );
}

export function App() {
  const [status, setStatus] = useState("Not started");
  const [draft, setDraft] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [emotion, setEmotion] = useState("EMOTION_NEUTRAL");
  const [animation, setAnimation] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [hostMode, setHostMode] = useState(false);
  const [refusal, setRefusal] = useState("");
  const [players, setPlayers] = useState<PlayerRow[]>([]);
  const [listDown, setListDown] = useState(false);
  const [catalog, setCatalog] = useState<Catalog>({ languages: [], materials: [], personalities: [] });
  // The draft in the panel. Nothing here reaches the hub until Start.
  const [setup, setSetup] = useState<Setup>(() => readSetup());
  // The settings of the running session. null until the first Start in this tab.
  const [live, setLive] = useState<Setup | null>(null);
  const [catalogTick, setCatalogTick] = useState(0);
  // The LogosCat sets, or the local defaults. Read before the first write, so a first visit is known.
  const [languageSets, setLanguageSets] = useState<LanguageSets>(LOCAL_SETS);
  const [firstVisit] = useState(() => !targetsChosen());
  // At a narrow viewport every section but the one being edited starts closed.
  const [openSections, setOpenSections] = useState<Record<string, boolean>>(() => {
    const open: Record<string, boolean> = {};
    if (narrowViewport()) open.languages = true;
    return open;
  });
  const lineInput = useRef<HTMLInputElement>(null);
  const turnInFlight = useRef(false);
  const sentOptions = useRef<Record<string, string>>({});
  const [panelTeacher, setPanelTeacher] = useState({ name: "", summary: "" });
  const [buddyName, setBuddyName] = useState("Buddy");
  const [buddySummary, setBuddySummary] = useState("");
  const buddyNameRef = useRef("Buddy");
  const [auth, setAuth] = useState<LogosCatAuth | null>(() => readAuth());
  const [connectOpen, setConnectOpen] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [theme, setTheme] = useState("");
  const [practiceWords, setPracticeWords] = useState<string[]>([]);
  const [qa, setQa] = useState(false);
  const [bobSteer, setBobSteer] = useState("");
  const [bobPose, setBobPose] = useState("");
  const [bobWhy, setBobWhy] = useState("");
  const [bobStatus, setBobStatus] = useState<BobStatus>("idle");
  const [teacherName, setTeacherName] = useState("");
  const [teacherSummary, setTeacherSummary] = useState("");
  const [teacherEmotion, setTeacherEmotion] = useState("EMOTION_NEUTRAL");
  const [teacherSpeaking, setTeacherSpeaking] = useState(false);
  const teacherNameRef = useRef("");
  const [robLine, setRobLine] = useState("");
  const [robWhy, setRobWhy] = useState("");
  const [robQuiet, setRobQuiet] = useState(false);
  const [robStatus, setRobStatus] = useState<BobStatus>("idle");
  const [games, setGames] = useState<GameListing[]>([]);
  const [gameId, setGameId] = useState("");
  const [gameTitle, setGameTitle] = useState("Free speech");
  const [gameChrome, setGameChrome] = useState<GameChrome | null>(null);
  const roundOver = Boolean(gameId && gameChrome?.finished);
  const [correction, setCorrection] = useState<{ noteId: string; explanation: string } | null>(null);
  /** The Read the text window: which material, in which language. */
  const [reading, setReading] = useState<{ languageId: string; materialId: string } | null>(null);
  // The Add or Edit material window. An empty materialId adds one.
  const [editing, setEditing] = useState<{ languageId: string; materialId: string } | null>(null);
  /** A long wait the page shows with the kitten bar: a round being prepared, or a LogosCat import. */
  const [preparing, setPreparing] = useState<"" | "round" | "import">("");
  const ready = setupComplete(setup);
  const pending = live !== null && !sameSetup(live, setup);
  const logRef = useRef<HTMLElement>(null);
  const hostHold = useRef<boolean | null>(null);
  const acceptActors = useRef(true);
  const sessionRef = useRef<string | null>(null);
  const playbackGen = useRef(0);
  const resetting = useRef(false);
  const awaitingSession = useRef(false);
  const speakHeld = useRef(false);
  const hostModeRef = useRef(false);
  const webRec = useRef<HoldRecording | null>(null);
  const webCancel = useRef(false);
  const pageAudio = useRef<HTMLAudioElement | null>(null);
  hostModeRef.current = hostMode;

  useEffect(() => {
    // Read-only: the lists for the language chosen in the panel. No session is touched.
    const language = setup.languageId;
    const params = new URLSearchParams({
      language_id: language || "en",
      material_id: setup.materialId,
      targets: setup.targets.join(","),
    });
    let gone = false;
    void fetch(`${HUB_HTTP}/catalog?${params}`)
      .then((response) => response.json())
      .then((body: Catalog) => {
        if (gone) return;
        const offered = {
          personalities: (body.personalities ?? []).map((item) => item.id),
          materials: (body.materials ?? []).map((item) => item.id),
          games: (body.games ?? []).map((item) => item.id),
        };
        setCatalog({
          languages: body.languages ?? [],
          materials: language ? (body.materials ?? []) : [],
          personalities: language ? (body.personalities ?? []) : [],
          games: language ? (body.games ?? []) : [],
        });
        setGames(language ? (body.games ?? []) : []);
        setPanelTeacher({ name: language ? (body.teacher_name ?? "") : "", summary: body.teacher_summary ?? "" });
        if (language) setSetup((current) => pruneSetup(current, language, offered));
      })
      .catch(() => setNotice("The material list is unavailable."));
    return () => {
      gone = true;
    };
  }, [setup.languageId, setup.materialId, setup.targets.join(","), catalogTick]);

  useEffect(() => {
    writeSetup(setup);
  }, [setup]);

  useEffect(() => {
    // The hub reads LogosCat. Logged out, or LogosCat down, it returns the local defaults.
    let gone = false;
    const headers: Record<string, string> = auth ? { Authorization: `Bearer ${auth.token}` } : {};
    const apply = (sets: LanguageSets) => {
      if (gone) return;
      setLanguageSets(sets);
      setSetup((current) => {
        const offered = sets.targets.map((item) => item.id);
        let languageId = current.languageId;
        let targets = current.targets;
        if (!languageId || firstVisit) {
          const first = firstChoice(sets, languageId);
          languageId = first.source;
          if (firstVisit && targets.length === 0) targets = first.targets;
        }
        targets = cleanTargets(
          targets.filter((code) => offered.includes(code)),
          languageId,
        );
        const next = { ...current, languageId, targets };
        return sameSetup(next, current) ? current : next;
      });
    };
    void fetch(`${HUB_HTTP}/logoscat/language-settings`, { headers })
      .then(async (response) => {
        if (response.status === 401) {
          tokenEnded();
          return;
        }
        apply((await response.json()) as LanguageSets);
      })
      .catch(() => apply(LOCAL_SETS));
    return () => {
      gone = true;
    };
  }, [auth, firstVisit]);

  useEffect(() => {
    const stored = readAuth();
    if (!stored) return;
    let gone = false;
    void fetch(`${HUB_HTTP}/logoscat/validate`, {
      method: "POST",
      headers: { Authorization: `Bearer ${stored.token}` },
    })
      .then((response) => {
        if (gone) return;
        if (response.status === 401) tokenEnded();
      })
      .catch(() => {
        /* a quiet hub keeps the stored token */
      });
    return () => {
      gone = true;
    };
  }, []);

  useEffect(() => {
    const socket = new WebSocket(HUB_WS);
    let closed = false;
    socket.onopen = () => {
      // A refresh starts nothing. The panel waits for Start.
      setStatus(sessionRef.current ? "Ready" : "Not started");
    };
    socket.onmessage = (event) => {
      void handleMessage(event.data as string);
    };
    socket.onclose = () => {
      if (!closed) setStatus("Disconnected");
      setPreparing("");
    };
    const queue: {
      generation: number;
      solution: SolutionView;
      altered: boolean;
      steer: string;
      playOnPage: boolean;
      speaker: string;
    }[] = [];
    let playing = false;
    let finishWhenIdle = false;
    let idleGeneration = 0;

    function handleMessage(raw: string) {
      const message = JSON.parse(raw) as {
        type: string;
        session_id?: string;
        transcript?: string;
        notice?: string;
        message?: string;
        final?: boolean;
        play_on_page?: boolean;
        solutions?: string[];
        language_id?: string;
        target_languages?: string[];
        material_id?: string;
        theme?: string;
        subject?: { important_words?: unknown };
        sentences?: Sentence[];
        materials?: Material[];
        personalities?: Personality[];
        personality_id?: string;
        buddy_name?: string;
        recognizer?: { ok?: boolean };
        altered?: boolean;
        bob_steer?: string;
        bob_why?: string;
        bob_pose?: string;
        pose?: string;
        bob_qa?: boolean;
        steer?: string;
        why?: string;
        status?: BobStatus;
        speaker?: string;
        teacher_name?: string;
        teacher_summary?: string;
        rob_line?: string;
        rob_why?: string;
        rob_quiet?: boolean;
        line?: string;
        quiet?: boolean;
        pieces?: HeardPiece[];
        notes?: TeacherNote[];
        teacher_mode?: string;
        mode?: string;
        game_id?: string;
        games?: GameListing[];
        game?: GameChrome | null;
        instruction?: string;
        phrase?: string;
        hint?: string;
        feedback?: string;
        feedback_text?: string;
        quest?: GameChrome["quest"];
        score?: GameChrome["score"];
        finished?: boolean;
        withheld?: boolean;
        buzzer?: boolean;
        source?: string;
        matches?: number;
        misses?: number;
        total?: number;
        closed?: number;
        mask_lines?: boolean;
        masked_lines?: string[];
        next?: string;
        miss_note?: { sentence_id?: string; explanation?: string; verdict?: string; expected?: string } | null;
        glosses?: GameChrome["glosses"];
        origin?: string;
        finish?: boolean;
        qa?: boolean;
      };
      if (message.type === "session" && message.session_id) {
        sessionRef.current = message.session_id;
        const nextName = message.buddy_name || "Peter";
        buddyNameRef.current = nextName;
        setBuddyName(nextName);
        const people = message.personalities ?? [];
        const chosen = people.find((item) => item.id === message.personality_id);
        setBuddySummary(chosen?.summary ?? "");
        setTheme(message.theme ?? "");
        setPracticeWords(practiceWordsFrom(message.subject));
        const sessionQa = typeof message.qa === "boolean" ? message.qa : message.bob_qa === true;
        setQa(sessionQa);
        setBobSteer(message.bob_steer ?? "");
        setBobWhy(message.bob_why ?? "");
        setBobPose(message.bob_pose ?? "");
        setBobStatus("idle");
        const nextTeacher = message.teacher_name ?? "";
        teacherNameRef.current = nextTeacher;
        setTeacherName(nextTeacher);
        setTeacherSummary(message.teacher_summary ?? "");
        setTeacherEmotion("EMOTION_NEUTRAL");
        setTeacherSpeaking(false);
        setRobLine(message.rob_line ?? "");
        setRobWhy(message.rob_why ?? "");
        setRobQuiet(message.rob_quiet === true);
        setRobStatus("idle");
        const sessionTeacherMode: TeacherMode = message.teacher_mode === "pedantic" ? "pedantic" : "relaxed";
        setCorrection(null);
        if (message.recognizer && message.recognizer.ok === false) {
          setNotice("The speech recognizer did not switch. Speech still uses the previous language.");
        }
        acceptActors.current = true;
        resetting.current = false;
        awaitingSession.current = false;
        setLines(sentencesToLines(message.sentences ?? [], nextName, message.teacher_name || "Savelij"));
        const nextGame = message.game_id ?? "";
        setGameId(nextGame);
        const listed = message.games ?? [];
        if (message.games) setGames(listed);
        const found = listed.find((item) => item.id === nextGame);
        setGameTitle(nextGame ? found?.title || nextGame : "Free speech");
        setGameChrome(nextGame ? (message.game ?? null) : null);
        setLive({
          languageId: message.language_id ?? "",
          targets: message.target_languages ?? [],
          hostMode: hostModeRef.current,
          qa: sessionQa,
          personalityId: message.personality_id ?? "",
          materialId: message.material_id ?? "",
          gameId: nextGame,
          gameOptions: nextGame ? sentOptions.current : {},
          teacherMode: sessionTeacherMode,
        });
        setStatus("Ready");
        setBusy(false);
        setPreparing("");
      } else if (message.type === "error") {
        acceptActors.current = true;
        resetting.current = false;
        setPreparing("");
        setNotice(message.message ?? "Something went wrong.");
        setBusy(false);
        setStatus(awaitingSession.current ? "Could not start" : sessionRef.current ? "Ready" : "Not started");
      } else if (message.type === "heard") {
        if (resetting.current || !acceptActors.current) return;
        if (message.session_id && sessionRef.current && message.session_id !== sessionRef.current) return;
        const pieces = (message.pieces ?? []).filter((piece) => (piece.text ?? "").trim());
        if (pieces.length > 0) {
          setLines((current) => [
            ...current,
            ...pieces.map((piece) => ({
              id: piece.id || crypto.randomUUID(),
              speaker: "You",
              text: piece.text ?? "",
            })),
          ]);
        } else if (message.transcript) {
          setLines((current) => [
            ...current,
            { id: crypto.randomUUID(), speaker: "You", text: message.transcript ?? "" },
          ]);
        }
        if (message.notice) setNotice(message.notice);
        if (message.final) setBusy(false);
      } else if (message.type === "actor") {
        if (resetting.current || !acceptActors.current) return;
        if (message.session_id && sessionRef.current && message.session_id !== sessionRef.current) return;
        const generation = playbackGen.current;
        for (const item of message.solutions ?? []) {
          const solution = decodeSolution(base64ToBytes(item));
          queue.push({
            generation,
            solution,
            altered: message.altered === true,
            steer: message.altered === true ? (message.steer ?? "").trim() : "",
            playOnPage: message.play_on_page === true,
            speaker:
              message.speaker ||
              (solution.actorId === "teacher-one" ? teacherNameRef.current || "Savelij" : ""),
          });
        }
        if (message.final) {
          finishWhenIdle = true;
          idleGeneration = generation;
        }
        if (message.altered) setBobPose("");
        void drain();
      } else if (message.type === "game") {
        if (resetting.current || !acceptActors.current) return;
        if (message.session_id && sessionRef.current && message.session_id !== sessionRef.current) return;
        setGameChrome((current) => ({
          game_id: message.game_id,
          finished: message.finished,
          instruction: message.instruction,
          phrase: message.phrase,
          hint: message.hint,
          feedback: message.feedback,
          feedback_text: message.feedback_text,
          quest: message.quest,
          score: message.score,
          steer: message.steer,
          withheld: message.withheld,
          buzzer: message.buzzer,
          source: message.source || current?.source || "",
          matches: message.matches,
          misses: message.misses,
          total: message.total,
          closed: message.closed,
          mask_lines: message.mask_lines === true,
          masked_lines: message.masked_lines ?? [],
          next: message.next ?? "",
          miss_note: message.miss_note,
          glosses: message.glosses ?? [],
          origin: message.origin ?? "",
          finish: message.finish === true,
        }));
        // A refused turn after the round has no heard or actor frame to release the controls.
        if (message.finished) setBusy(false);
        const note = message.miss_note;
        if (note?.sentence_id && note.explanation) {
          setLines((current) =>
            current.map((line) =>
              line.id === note.sentence_id
                ? {
                    ...line,
                    explanation: note.explanation || line.explanation,
                    verdict: note.verdict || line.verdict,
                    expected: note.expected || line.expected,
                  }
                : line,
            ),
          );
        }
        if (message.buzzer) playBeep();
      } else if (message.type === "teacher-notes") {
        if (resetting.current || !acceptActors.current) return;
        if (message.session_id && sessionRef.current && message.session_id !== sessionRef.current) return;
        const notes = message.notes ?? [];
        setLines((current) =>
          current.map((line) => {
            const note = notes.find((item) => item.sentence_id === line.id);
            if (!note?.note_id) return line;
            return { ...line, noteId: note.note_id, explanation: note.explanation ?? "" };
          }),
        );
      } else if (message.type === "teacher-mode") {
        const mode = message.mode;
        if (mode === "pedantic" || mode === "relaxed") {
          setLive((current) => (current ? { ...current, teacherMode: mode } : current));
        }
      } else if (message.type === "bob") {
        if (resetting.current || !acceptActors.current) return;
        if (message.session_id && sessionRef.current && message.session_id !== sessionRef.current) return;
        setBobSteer(message.steer ?? "");
        setBobWhy(message.why ?? "");
        setBobPose(message.pose ?? "");
        if (message.status === "thinking" || message.status === "failed" || message.status === "idle") {
          setBobStatus(message.status);
        }
      } else if (message.type === "rob") {
        if (resetting.current || !acceptActors.current) return;
        if (message.session_id && sessionRef.current && message.session_id !== sessionRef.current) return;
        setRobLine(message.line ?? "");
        setRobWhy(message.why ?? "");
        setRobQuiet(message.quiet === true);
        if (message.status === "thinking" || message.status === "failed" || message.status === "idle") {
          setRobStatus(message.status);
        }
      }
    }

    async function drain() {
      if (playing) return;
      playing = true;
      while (queue.length > 0) {
        const item = queue.shift();
        if (item && item.generation === playbackGen.current) {
          await showSolution(
            item.solution,
            item.generation,
            item.altered,
            item.steer,
            item.playOnPage,
            item.speaker,
          );
        }
      }
      playing = false;
      if (queue.length > 0) {
        void drain();
        return;
      }
      if (finishWhenIdle && idleGeneration === playbackGen.current) {
        finishWhenIdle = false;
        setBusy(false);
      } else if (finishWhenIdle) {
        finishWhenIdle = false;
      }
    }

    async function showSolution(
      solution: SolutionView,
      generation: number,
      altered: boolean,
      steer: string,
      playOnPage: boolean,
      namedSpeaker: string,
    ) {
      if (resetting.current || playbackGen.current !== generation) return;
      const teacherLine = solution.actorId === "teacher-one";
      const speaker = teacherLine ? namedSpeaker || teacherNameRef.current || "Savelij" : buddyNameRef.current;
      if (teacherLine) setTeacherEmotion(solution.emotion);
      else setEmotion(solution.emotion);
      setLines((current) => {
        const last = current[current.length - 1];
        if (last && last.text === solution.text && last.speaker === speaker) return current;
        return [
          ...current,
          { id: solution.solutionId || crypto.randomUUID(), speaker, text: solution.text, altered, steer },
        ];
      });
      if (!teacherLine) setAnimation("");
      if (playOnPage && solution.pcm.length > 0 && !hostModeRef.current) {
        if (teacherLine) setTeacherSpeaking(true);
        else setSpeaking(true);
        await playPcm(solution.pcm, (audio) => {
          pageAudio.current = audio;
        });
        if (pageAudio.current) pageAudio.current = null;
        if (playbackGen.current === generation) {
          if (teacherLine) setTeacherSpeaking(false);
          else setSpeaking(false);
        }
        return;
      }
      if (teacherLine) setTeacherSpeaking(false);
      else setSpeaking(false);
    }

    (window as unknown as { __lkSocket?: WebSocket }).__lkSocket = socket;
    return () => {
      closed = true;
      socket.close();
    };
  }, []);

  function toggleQa() {
    setSetup((current) => ({ ...current, qa: !current.qa }));
  }

  function pageSocket(): WebSocket | undefined {
    return (window as unknown as { __lkSocket?: WebSocket }).__lkSocket;
  }

  function speakDown(event: ReactPointerEvent<HTMLButtonElement>) {
    event.stopPropagation();
    if (roundOver || !sessionRef.current) return;
    const socket = pageSocket();
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setNotice("The hub is not connected.");
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    speakHeld.current = true;
    webCancel.current = false;
    if (!hostModeRef.current) {
      void startRecording()
        .then((recording) => {
          if (webCancel.current || !speakHeld.current) {
            void recording.stop();
            return;
          }
          webRec.current = recording;
        })
        .catch(() => {
          speakHeld.current = false;
          webRec.current = null;
          setNotice("The browser did not open the microphone.");
        });
      return;
    }
    socket.send(JSON.stringify({ type: "speak", down: true }));
  }

  function speakUp(event: ReactPointerEvent<HTMLButtonElement>) {
    if (!speakHeld.current) return;
    speakHeld.current = false;
    const target = event.currentTarget;
    if (target.hasPointerCapture?.(event.pointerId)) {
      target.releasePointerCapture(event.pointerId);
    }
    const recording = webRec.current;
    if (recording) {
      webCancel.current = false;
      const socket = pageSocket();
      setBusy(true);
      setNotice("");
      window.setTimeout(() => {
        void (async () => {
          webRec.current = null;
          const blob = await recording.stop();
          if (webCancel.current) {
            setBusy(false);
            return;
          }
          if (!blob.size) {
            setNotice("No speech detected.");
            setBusy(false);
            return;
          }
          if (!socket || socket.readyState !== WebSocket.OPEN || hostModeRef.current) {
            setBusy(false);
            return;
          }
          const bytes = new Uint8Array(await blob.arrayBuffer());
          socket.send(
            JSON.stringify({
              type: "audio",
              data: bytesToBase64(bytes),
              mime: blob.type || "audio/webm",
            }),
          );
        })();
      }, 1000);
      return;
    }
    if (!hostModeRef.current) {
      webCancel.current = true;
      return;
    }
    const socket = pageSocket();
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    setBusy(true);
    setNotice("");
    socket.send(JSON.stringify({ type: "speak", down: false }));
  }

  function send(payload: unknown) {
    const kind = (payload as { type?: string } | null)?.type;
    if (kind === "transcript" || kind === "audio") turnInFlight.current = true;
    const socket = (window as unknown as { __lkSocket?: WebSocket }).__lkSocket;
    if (awaitingSession.current) {
      setNotice("The new conversation is still loading.");
      return;
    }
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setNotice("The hub is not connected.");
      return;
    }
    setBusy(true);
    setNotice("");
    socket.send(JSON.stringify(payload));
  }

  /** One select with every setting. The hub builds the subject or deck once, here. */
  function beginFresh(params: Setup): boolean {
    const socket = (window as unknown as { __lkSocket?: WebSocket }).__lkSocket;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setNotice("The hub is not connected.");
      return false;
    }
    acceptActors.current = false;
    resetting.current = true;
    awaitingSession.current = true;
    playbackGen.current += 1;
    const known = catalog.personalities.find((item) => item.id === params.personalityId);
    if (known) {
      buddyNameRef.current = known.name;
      setBuddyName(known.name);
      setBuddySummary(known.summary);
    }
    sentOptions.current = params.gameId ? params.gameOptions : {};
    setPanelOpen(false);
    setStatus("Starting a new conversation");
    setPreparing("round");
    setTheme("");
    setDraft("");
    setEmotion("EMOTION_NEUTRAL");
    setAnimation("");
    setSpeaking(false);
    setBusy(true);
    setNotice("");
    socket.send(
      JSON.stringify({
        type: "select",
        user_id: "user-local",
        language_id: params.languageId,
        target_languages: params.targets,
        material_id: params.materialId,
        personality_id: params.personalityId,
        teacher_mode: params.teacherMode,
        game_id: params.gameId ?? "",
        game_options: params.gameId ? params.gameOptions : {},
        qa: params.qa,
      }),
    );
    return true;
  }

  /** Start: apply the mode on the hub if it changed, then open one session with the whole draft. */
  async function startTalk() {
    if (!setupComplete(setup) || busy) return;
    const chosen = setup;
    if (chosen.hostMode !== hostModeRef.current) {
      const applied = await applyHost(chosen.hostMode);
      if (!applied) {
        setNotice("The mode did not change. Nothing was started.");
        return;
      }
    }
    beginFresh(chosen);
  }

  function editSetup(change: Partial<Setup>) {
    setSetup((current) => ({ ...current, ...change }));
  }

  function chooseTeacherMode(mode: TeacherMode) {
    editSetup({ teacherMode: mode });
  }

  function chooseLanguage(language: string) {
    if (language === setup.languageId) return;
    // The lists for the new language load next. pruneSetup then drops ids that language does not have.
    // The new source is never one of its own targets.
    editSetup({ languageId: language, targets: cleanTargets(setup.targets, language) });
  }

  /** The end-of-round buttons. They keep the running session's settings and change only the game. */
  function chooseGame(nextGame: string) {
    if (!live) return;
    const gameOptions = nextGame === live.gameId ? live.gameOptions : {};
    if (nextGame !== live.gameId) editSetup({ gameId: nextGame, gameOptions });
    beginFresh({ ...live, gameId: nextGame, gameOptions });
  }

  async function importSession(session: WorkspaceSession) {
    if (!auth) return;
    setSessionsOpen(false);
    setNotice("");
    setPreparing("import");
    try {
      const response = await fetch(`${HUB_HTTP}/logoscat/import`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${auth.token}`,
        },
        body: JSON.stringify({
          workspace_session_id: session.id,
          language_id: setup.languageId || "en",
          name: session.name,
        }),
      });
      const body = (await response.json()) as {
        success?: boolean;
        error?: string;
        material_id?: string;
        language_id?: string;
        notice?: string;
      };
      if (response.status === 401) {
        tokenEnded();
        return;
      }
      if (!response.ok || !body.success || !body.material_id) {
        setNotice(body.error || "That session could not be read.");
        return;
      }
      // Added as a raw material and selected in the panel. Nothing starts until Start.
      editSetup({ languageId: body.language_id || setup.languageId || "en", materialId: body.material_id });
      setCatalogTick((tick) => tick + 1);
      setPanelOpen(true);
      setNotice(body.notice || "Added to Raw material. Press Start to talk about it.");
    } catch {
      setNotice("LogosCat is not reachable.");
    } finally {
      setPreparing((current) => (current === "import" ? "" : current));
    }
  }

  function editMaterial(id: string) {
    if (live?.materialId === id) {
      setNotice("That material is used by the running talk. Start another one first.");
      return;
    }
    setEditing({ languageId: setup.languageId, materialId: id });
  }

  function materialSaved(saved: SavedMaterial) {
    setEditing(null);
    // Selected in the panel. Nothing starts until Start.
    editSetup({ languageId: saved.languageId, materialId: saved.materialId });
    setCatalogTick((tick) => tick + 1);
    setNotice("Saved in Raw material. Press Start to talk about it.");
  }

  async function deleteMaterial(id: string, origin?: string) {
    if (live?.materialId === id) {
      setNotice("That material is used by the running talk. Start another one first.");
      return;
    }
    const route = origin === "own" ? "materials" : "logoscat/materials";
    try {
      const response = await fetch(`${HUB_HTTP}/${route}/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (!response.ok && response.status !== 404) {
        const body = (await response.json().catch(() => ({}))) as { error?: string };
        setNotice(body.error || "That material could not be deleted.");
        return;
      }
      setSetup((current) => (current.materialId === id ? { ...current, materialId: "" } : current));
      setCatalogTick((tick) => tick + 1);
    } catch {
      setNotice("The hub is not reachable.");
    }
  }

  /** LogosCat refused the token: it expired or was revoked. The page forgets it. */
  function tokenEnded() {
    clearAuth();
    setAuth(null);
    setSessionsOpen(false);
    setNotice(ENDED);
  }

  /** Forgets the token on this page. It stays valid on LogosCat until revoked there. */
  function disconnect() {
    setAuth(null);
    clearAuth();
    setSessionsOpen(false);
    setConnectOpen(false);
    setNotice("Disconnected. To end the token itself, revoke it on LogosCat, Connected apps.");
  }

  /** A new session with the running session's settings. The unapplied draft is ignored. */
  function resetConversation() {
    if (!live) return;
    beginFresh(live);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || busy || roundOver || !live) return;
    setDraft("");
    send({ type: "transcript", text });
  }

  useEffect(() => {
    let stopped = false;

    async function pull() {
      try {
        const response = await fetch(`${HUB_HTTP}/console`);
        if (!response.ok) throw new Error(String(response.status));
        const body = (await response.json()) as {
          host_mode?: boolean;
          refusal?: string;
          players?: PlayerRow[];
        };
        if (stopped) return;
        const reported = body.host_mode === true;
        if (hostHold.current !== null && reported !== hostHold.current) return;
        hostHold.current = null;
        setHostMode(reported);
        setRefusal(typeof body.refusal === "string" ? body.refusal : "");
        setPlayers(Array.isArray(body.players) ? body.players : []);
        setListDown(false);
      } catch {
        if (!stopped) setListDown(true);
      }
    }

    void pull();
    const timer = window.setInterval(() => void pull(), 1000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, []);

  function toggleHost() {
    editSetup({ hostMode: !setup.hostMode });
  }

  async function applyHost(next: boolean): Promise<boolean> {
    hostHold.current = next;
    try {
      const response = await fetch(`${HUB_HTTP}/host-mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ on: next }),
      });
      if (!response.ok) throw new Error(String(response.status));
      const body = (await response.json()) as { on?: boolean };
      const on = body.on === true;
      hostHold.current = on;
      hostModeRef.current = on;
      setHostMode(on);
      if (on) setRefusal("");
      setListDown(false);
      return on === next;
    } catch {
      hostHold.current = null;
      setListDown(true);
      return false;
    }
  }

  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [lines, bobSteer, qa]);

  const modeWatch = useRef(false);
  useEffect(() => {
    if (!modeWatch.current) {
      modeWatch.current = true;
      return;
    }
    webCancel.current = true;
    speakHeld.current = false;
    const recording = webRec.current;
    webRec.current = null;
    if (recording) void recording.stop();
    const audio = pageAudio.current;
    pageAudio.current = null;
    if (audio) audio.pause();
  }, [hostMode]);

  useEffect(() => {
    // After a turn the text box gets focus again, so the next line can be typed at once.
    if (busy || !turnInFlight.current) return;
    turnInFlight.current = false;
    lineInput.current?.focus();
  }, [busy]);

  function toggleSection(id: string) {
    setOpenSections((current) => {
      const open = !current[id];
      if (narrowViewport()) return open ? { [id]: true } : {};
      return { ...current, [id]: open };
    });
  }

  function sectionOpen(id: string): boolean {
    if (narrowViewport()) return openSections[id] === true;
    return openSections[id] !== false;
  }

  function startBlock() {
    const missing = [
      setup.languageId ? "" : "language",
      setup.personalityId ? "" : "buddy",
      setup.materialId ? "" : "raw material",
      setup.gameId === null ? "game" : "",
    ].filter(Boolean);
    const blocked = games.find((game) => game.id === setup.gameId && game.available === false);
    return (
      <div className="sticky bottom-0 mb-4 bg-lk-tint py-2">
        <button
          type="button"
          disabled={!ready || busy || Boolean(blocked)}
          onClick={() => void startTalk()}
          className="w-full rounded-full bg-lk-green px-5 py-3 text-white disabled:opacity-50"
        >
          {live ? "Start with these settings" : "Start"}
        </button>
        {missing.length > 0 ? (
          <p className="mt-2 text-xs text-lk-muted">Choose {missing.join(", ")}.</p>
        ) : blocked ? (
          <p className="mt-2 text-xs text-lk-red">
            {blocked.title}: {blocked.reason}.
          </p>
        ) : pending ? (
          <p className="mt-2 text-xs text-lk-red">Changed. The running talk keeps its settings until Start.</p>
        ) : null}
      </div>
    );
  }

  /** H12. A listening game hides what she said until its target closes. Your own lines always show. */
  function masked(line: Line): boolean {
    if (!gameId || !gameChrome?.mask_lines || line.speaker === "You") return false;
    const text = line.text.trim();
    if (!text) return false;
    return (gameChrome.masked_lines ?? []).some((open) => open.includes(text));
  }

  function chosenOptions() {
    // An option with one value left (e.g. translation dropped for want of a target) is no choice.
    return (games.find((game) => game.id === setup.gameId)?.options ?? []).filter(
      (option) => option.values.length > 1,
    );
  }

  function chooseActivity(id: string) {
    if (id === setup.gameId) return;
    editSetup({ gameId: id, gameOptions: {} });
  }

  /** Free speech first, then the games grouped by phase. A game that cannot start says why. */
  function activityList() {
    const suggested = live?.gameId ? games.find((game) => game.id === live.gameId)?.next || "" : "";
    return (
      <div className="flex flex-col gap-3">
        <button
          type="button"
          aria-pressed={setup.gameId === ""}
          onClick={() => chooseActivity("")}
          className={`w-full rounded-xl px-3 py-2 text-left ${setup.gameId === "" ? "bg-lk-primary text-white" : "bg-white"}`}
        >
          Free speech
        </button>
        {PHASES.map(([phase, label]) => {
          const rows = games.filter((game) => game.phase === phase);
          if (rows.length === 0) return null;
          return (
            <div key={phase}>
              <p className="mb-1 text-xs text-lk-label">{label}</p>
              <ul className="flex flex-col gap-1">
                {rows.map((game) => {
                  const chosen = game.id === setup.gameId;
                  const blocked = game.available === false;
                  const tags = [...(game.tags ?? []), ...(game.id === suggested ? ["Next"] : [])];
                  return (
                    <li key={game.id}>
                      <button
                        type="button"
                        aria-pressed={chosen}
                        disabled={blocked}
                        aria-describedby={blocked ? `reason-${game.id}` : undefined}
                        onClick={() => chooseActivity(game.id)}
                        className={`w-full rounded-xl px-3 py-2 text-left disabled:opacity-60 ${chosen ? "bg-lk-primary text-white" : "bg-white"}`}
                      >
                        <span className="flex items-baseline justify-between gap-2">
                          <span>{game.title}</span>
                          {game.last ? (
                            <span className="shrink-0 text-xs opacity-80">
                              {game.last.hit} of {game.last.total}
                            </span>
                          ) : null}
                        </span>
                        {game.summary ? <span className="block text-xs opacity-80">{game.summary}</span> : null}
                        {tags.length > 0 ? (
                          <span className="mt-1 flex flex-wrap gap-1">
                            {tags.map((tag) => (
                              <span
                                key={tag}
                                className={`rounded-full border px-2 text-[10px] uppercase tracking-wide ${chosen ? "border-white" : "border-lk-label"}`}
                              >
                                {tag}
                              </span>
                            ))}
                          </span>
                        ) : null}
                        {blocked ? (
                          <span id={`reason-${game.id}`} className="mt-1 block text-xs text-lk-red">
                            {game.reason}
                          </span>
                        ) : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>
    );
  }

  function hostBlock() {
    return (
      <section aria-label="Mode" className="rounded-3xl bg-white/90 p-4">
        <button
          type="button"
          aria-pressed={setup.hostMode}
          onClick={toggleHost}
          className={`mb-3 w-full rounded-xl px-3 py-2 text-left ${setup.hostMode ? "bg-lk-primary text-white" : "bg-white"}`}
        >
          {setup.hostMode ? "Botnet mode" : "Web mode"}
        </button>
        {setup.hostMode !== hostMode ? (
          <p className="mb-3 text-xs text-lk-red">
            The hub is in {hostMode ? "Botnet" : "Web"} mode. Start applies this choice.
          </p>
        ) : null}
        <p className="mb-2 text-xs tracking-[0.16em] uppercase text-lk-label">Listen</p>
        <p className="mb-3 text-sm text-lk-muted">Speak</p>
        {hostMode ? <p className="mb-3 break-all text-sm text-lk-muted">{DIAL_URL}</p> : null}
        {hostMode && refusal ? <p className="mb-3 text-sm text-lk-red">Attach refused: {refusal}</p> : null}
        {hostMode && listDown ? <p className="mb-3 text-sm text-lk-muted">The player list is unavailable.</p> : null}
        {hostMode ? <p className="mb-2 text-xs tracking-[0.16em] uppercase text-lk-label">Players</p> : null}
        {hostMode && players.length === 0 ? (
          <p className="text-sm text-lk-muted">No player attached</p>
        ) : null}
        {hostMode && players.length > 0 ? (
          <ul className="flex flex-col gap-2">
            {players.map((player) => (
              <li key={player.body_id} className="rounded-xl bg-white px-3 py-2 text-sm">
                <p className="flex items-baseline justify-between gap-2">
                  <span className="font-medium">{player.display_name}</span>
                  <span className={player.ready ? "text-lk-green" : "text-lk-red"}>
                    {player.ready ? "Ready" : player.reason}
                  </span>
                </p>
                <p className="mt-1 text-lk-muted">
                  <span className="text-lk-label">Role </span>
                  {player.role}
                </p>
                <p className="text-lk-muted">
                  <span className="text-lk-label">Steerer </span>
                  {player.steerer}
                </p>
                <p className="text-lk-muted">
                  <span className="text-lk-label">Speaking </span>
                  {player.speaking}
                </p>
                <p className="text-lk-muted">
                  <span className="text-lk-label">Mimics </span>
                  {player.stances.length > 0 ? player.stances.join(", ") : "none"}
                </p>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    );
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl">
      <aside
        className={`${panelOpen ? "fixed inset-0 z-20 block overflow-y-auto" : "hidden"} w-full bg-lk-tint/95 p-4 md:static md:z-auto md:block md:w-72 md:shrink-0 md:border-r md:border-lk-line`}
      >
        <div className="mb-4 flex items-center justify-between md:block">
          <p className="text-xs tracking-[0.2em] uppercase text-lk-label">Talk</p>
          <button type="button" className="text-sm md:hidden" onClick={() => setPanelOpen(false)}>
            Close
          </button>
        </div>
        <div className="hidden md:block">
          <PanelSection
            id="mode"
            title="Mode"
            summary={setup.hostMode ? "Botnet mode" : "Web mode"}
            open={sectionOpen("mode")}
            onToggle={toggleSection}
          >
            {hostBlock()}
          </PanelSection>
        </div>
        <PanelSection
          id="languages"
          title="Languages"
          summary={languagesLine(setup.languageId, setup.targets, catalog.languages)}
          open={sectionOpen("languages")}
          onToggle={toggleSection}
        >
          <LanguagesBlock
            sets={languageSets}
            source={setup.languageId}
            targets={setup.targets}
            known={catalog.languages}
            onSource={chooseLanguage}
            onTargets={(targets) => editSetup({ targets: cleanTargets(targets, setup.languageId) })}
          />
        </PanelSection>
        <PanelSection
          id="material"
          title="Raw material"
          summary={catalog.materials.find((item) => item.id === setup.materialId)?.title ?? "Choose one"}
          open={sectionOpen("material")}
          onToggle={toggleSection}
        >
          {setup.languageId ? (
            <ul className="flex flex-col gap-1">
              {catalog.materials.map((material) => (
                <li key={material.id} className="flex items-stretch gap-1">
                  <button
                    type="button"
                    aria-pressed={material.id === setup.materialId}
                    onClick={() => editSetup({ materialId: material.id })}
                    className={`min-w-0 flex-1 rounded-xl px-3 py-2 text-left ${material.id === setup.materialId ? "bg-lk-primary text-white" : "bg-white"}`}
                  >
                    {material.title}
                    {material.origin === "logoscat" ? (
                      <span className="block text-xs opacity-70">LogosCat session</span>
                    ) : material.origin === "own" ? (
                      <span className="block text-xs opacity-70">Your text</span>
                    ) : null}
                  </button>
                  {material.origin === "own" ? (
                    <button
                      type="button"
                      aria-label={`Edit ${material.title}`}
                      title="Edit this material"
                      onClick={() => editMaterial(material.id)}
                      className="shrink-0 rounded-xl bg-white px-2 text-sm"
                    >
                      ✎
                    </button>
                  ) : null}
                  {material.origin === "logoscat" || material.origin === "own" ? (
                    <button
                      type="button"
                      aria-label={`Delete ${material.title}`}
                      title={material.origin === "own" ? "Delete this material" : "Delete this imported session"}
                      onClick={() => void deleteMaterial(material.id, material.origin)}
                      className="shrink-0 rounded-xl bg-white px-2 text-sm text-lk-red"
                    >
                      ×
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-lk-muted">Choose a source language to see materials, games, and buddies.</p>
          )}
          {setup.languageId ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {setup.materialId ? (
                <button
                  type="button"
                  onClick={() => setReading({ languageId: setup.languageId, materialId: setup.materialId })}
                  className="rounded-full border border-lk-primary px-3 py-1 text-sm text-lk-ink"
                >
                  Read the text
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => setEditing({ languageId: setup.languageId, materialId: "" })}
                className="rounded-full border border-lk-primary px-3 py-1 text-sm text-lk-ink"
              >
                Add material
              </button>
            </div>
          ) : null}
        </PanelSection>
        <PanelSection
          id="activity"
          title="Activity"
          summary={
            setup.gameId === null
              ? "Choose one"
              : setup.gameId === ""
                ? "Free speech"
                : (games.find((game) => game.id === setup.gameId)?.title ?? setup.gameId)
          }
          open={sectionOpen("activity")}
          onToggle={toggleSection}
        >
          {setup.languageId ? activityList() : null}
        </PanelSection>
        {chosenOptions().length > 0 ? (
          <PanelSection
            id="options"
            title="Options"
            summary={chosenOptions()
              .map((option) => option.labels[setup.gameOptions[option.name] ?? option.default] ?? option.default)
              .join(", ")}
            open={sectionOpen("options")}
            onToggle={toggleSection}
          >
            {chosenOptions().map((option) => (
              <fieldset key={option.name} className="mb-2">
                <legend className="mb-1 text-xs text-lk-label">{option.name}</legend>
                <ul className="flex flex-col gap-1">
                  {option.values.map((value) => {
                    const chosen = (setup.gameOptions[option.name] ?? option.default) === value;
                    return (
                      <li key={value}>
                        <label className="flex items-center gap-2 rounded-xl bg-white px-3 py-2">
                          <input
                            type="radio"
                            name={`option-${option.name}`}
                            checked={chosen}
                            onChange={() =>
                              editSetup({ gameOptions: { ...setup.gameOptions, [option.name]: value } })
                            }
                          />
                          <span>{option.labels[value] ?? value}</span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </fieldset>
            ))}
          </PanelSection>
        ) : null}
        <PanelSection
          id="people"
          title="People"
          summary={
            (catalog.personalities.find((person) => person.id === setup.personalityId)?.name ?? "Choose a buddy") +
            (setup.gameId === "" && panelTeacher.name
              ? ` · ${panelTeacher.name}, ${setup.teacherMode === "pedantic" ? "pedantic" : "relaxed"}`
              : "")
          }
          open={sectionOpen("people")}
          onToggle={toggleSection}
        >
          {setup.languageId ? (
            <>
              <p className="mb-1 text-xs text-lk-label">Buddy</p>
              <ul className="mb-3 flex flex-col gap-1">
                {catalog.personalities.map((person) => (
                  <li key={person.id}>
                    <button
                      type="button"
                      aria-pressed={person.id === setup.personalityId}
                      onClick={() => editSetup({ personalityId: person.id })}
                      className={`w-full rounded-xl px-3 py-2 text-left ${person.id === setup.personalityId ? "bg-lk-primary text-white" : "bg-white"}`}
                    >
                      <span className="block">{person.name}</span>
                      <span className="block text-xs opacity-80">{person.summary}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {setup.gameId === "" && setup.languageId ? (
            <>
              <p className="mb-1 text-xs text-lk-label">Teacher</p>
              <div className="mb-3 rounded-xl bg-white px-3 py-2">
                {panelTeacher.name ? (
                  <>
                    <span className="block">{panelTeacher.name}</span>
                    <span className="block text-xs opacity-80">{panelTeacher.summary}</span>
                  </>
                ) : (
                  <span className="block text-sm text-lk-muted">No teacher in this language.</span>
                )}
              </div>
              {panelTeacher.name ? (
                <>
                  <p className="mb-1 text-xs text-lk-label">Teacher mode</p>
                  <ul className="mb-2 flex flex-col gap-1">
                    {(["relaxed", "pedantic"] as TeacherMode[]).map((mode) => (
                      <li key={mode}>
                        <button
                          type="button"
                          aria-pressed={setup.teacherMode === mode}
                          onClick={() => chooseTeacherMode(mode)}
                          className={`w-full rounded-xl px-3 py-2 text-left ${setup.teacherMode === mode ? "bg-lk-primary text-white" : "bg-white"}`}
                        >
                          {mode === "relaxed" ? "Relaxed" : "Pedantic"}
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
            </>
          ) : null}
        </PanelSection>
        <PanelSection
          id="qa"
          title="QA"
          summary={setup.qa ? "On" : "Off"}
          open={sectionOpen("qa")}
          onToggle={toggleSection}
        >
          <button
            type="button"
            aria-pressed={setup.qa}
            onClick={toggleQa}
            className={`w-full rounded-xl px-3 py-2 text-left ${setup.qa ? "bg-lk-primary text-white" : "bg-white"}`}
          >
            {setup.qa ? "On" : "Off"}
          </button>
        </PanelSection>
        {startBlock()}
        <p className="text-sm text-lk-muted">{theme}</p>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col gap-6 px-4 py-8">
        <div className="md:hidden">{hostBlock()}</div>
        <header className="flex flex-wrap items-end justify-between gap-3 rounded-3xl bg-white/90 p-4">
          <div>
            <p className="text-xs tracking-[0.2em] uppercase text-lk-label">
              {gameId ? gameTitle : "Free speech"}
              {live ? (
                <span className="normal-case tracking-normal">
                  {" · "}
                  {live.languageId}
                  {live.targets.length > 0 ? ` → ${live.targets.join(", ")}` : ""}
                </span>
              ) : null}
            </p>
            <h1 className="text-4xl text-lk-red">LogosKittens</h1>
            {theme && <p className="mt-2 max-w-xl text-lk-muted">{theme}</p>}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {auth ? (
              <>
                <p className="text-sm text-lk-muted">{displayName(auth.user)}</p>
                <button
                  type="button"
                  onClick={() => setSessionsOpen(true)}
                  className="rounded-full border border-lk-primary px-3 py-1 text-sm"
                >
                  Workspace sessions
                </button>
                <button
                  type="button"
                  onClick={disconnect}
                  className="rounded-full border border-lk-red px-3 py-1 text-sm text-lk-red"
                >
                  Disconnect
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setConnectOpen(true)}
                className="rounded-full border border-lk-primary px-3 py-1 text-sm"
              >
                Connect LogosCat
              </button>
            )}
            <button
              type="button"
              onClick={resetConversation}
              disabled={!live || busy}
              className="rounded-full border border-lk-primary px-3 py-1 text-sm disabled:opacity-50"
            >
              Reset conversation
            </button>
            <button
              type="button"
              className="rounded-full border border-lk-primary px-3 py-1 text-sm md:hidden"
              onClick={() => setPanelOpen(true)}
            >
              Talk
            </button>
            <p className="text-sm text-lk-muted">{status}</p>
          </div>
        </header>
        <section className={`grid gap-4 ${teacherName && (!gameId || gameId === TEACHER_GAME) ? "md:grid-cols-2" : "md:grid-cols-1"}`}>
          <ActorCard
            name={buddyName}
            role={buddySummary}
            emotion={emotion}
            animation={animation}
            speaking={speaking}
            ink="#ffffff"
            paper="#1e3a8a"
          />
          {teacherName && (!gameId || gameId === TEACHER_GAME) ? (
            <ActorCard
              name={teacherName}
              role={teacherSummary || "Teacher"}
              emotion={teacherEmotion}
              animation=""
              speaking={teacherSpeaking}
              ink="#ffffff"
              paper="#166534"
            />
          ) : null}
        </section>
        {qa && !gameId && (
          <section className="rounded-3xl bg-white/90 p-4 text-sm text-lk-muted">
            <p className="text-xs uppercase tracking-[0.16em] text-lk-label">BOB {bobStatus}</p>
            <p className="mt-2">{bobSteer || "No suggestion yet."}</p>
            {bobPose.trim() ? <p className="mt-1">Mimic: {bobPose.trim()}</p> : null}
            {bobWhy ? <p className="mt-1">{bobWhy}</p> : null}
          </section>
        )}
        {qa && !gameId && (
          <section className="rounded-3xl bg-white/90 p-4 text-sm text-lk-muted">
            <p className="text-xs uppercase tracking-[0.16em] text-lk-label">Rob {robStatus}</p>
            <p className="mt-2">
              {robQuiet ? "nothing to correct" : robLine.trim() || "No suggestion yet."}
            </p>
            {robWhy ? <p className="mt-1">{robWhy}</p> : null}
          </section>
        )}
        {preparing ? (
          <section aria-label="Preparing" className="rounded-3xl bg-white/90 p-4 text-sm text-lk-muted">
            <Preparing kind={preparing} />
          </section>
        ) : null}
        {gameId && preparing !== "round" ? (
          <section aria-label="Game" className="rounded-3xl bg-white/90 p-4 text-sm text-lk-muted">
            {gameChrome ? (
              <GameCard
                chrome={gameChrome}
                view={gameViews[gameId]}
                targets={live?.targets ?? []}
                known={catalog.languages}
                next={
                  games.find(
                    (game) => game.id === (gameChrome.next || games.find((item) => item.id === gameId)?.next),
                  ) ?? null
                }
                onNewRound={() => chooseGame(gameId)}
                onNext={(next) => chooseGame(next)}
                onFreeTalk={() => chooseGame("")}
                onFinish={() => send({ type: "game-end", session_id: sessionRef.current })}
                readText={games.find((game) => game.id === gameId)?.read_text}
                onReadText={
                  live?.materialId && gameId !== "review"
                    ? () => setReading({ languageId: live.languageId, materialId: live.materialId })
                    : undefined
                }
              />
            ) : (
              <p>Preparing the round.</p>
            )}
          </section>
        ) : null}
        <section ref={logRef} className="h-[8cm] overflow-y-auto rounded-3xl bg-white/90 p-4">
          <ol className="flex flex-col gap-2">
            {lines.map((line) => (
              <li key={line.id} className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                <span className="mr-2 text-xs uppercase tracking-wide text-lk-label">{line.speaker}</span>
                {masked(line) ? <span aria-label="Hidden until this line closes">…</span> : line.text}
                {line.verdict === "correct" ? <p className="text-xs text-lk-green">Correct</p> : null}
                {line.verdict === "wrong" ? (
                  line.expected ? (
                    <WordDiff heard={line.text} expected={line.expected} />
                  ) : (
                    <p className="text-xs text-lk-red">Wrong. {line.explanation}</p>
                  )
                ) : null}
                {qa && (line.altered || line.steer) ? (
                  <p className="mt-1 text-xs normal-case tracking-normal text-lk-red">altered by BOB</p>
                ) : null}
                {qa && line.steer ? (
                  <p className="text-xs normal-case tracking-normal text-lk-label">Suggested alteration: {line.steer}</p>
                ) : null}
                </div>
                {line.noteId || line.explanation ? (
                  <button
                    type="button"
                    aria-label={line.noteId ? "Correction" : "Miss"}
                    className="mt-1 h-3 w-3 shrink-0 rounded-full bg-lk-red"
                    onClick={() =>
                      setCorrection({ noteId: line.noteId || "", explanation: line.explanation || "" })
                    }
                  />
                ) : null}
              </li>
            ))}
            {qa && bobSteer.trim() && bobSteer.trim() !== lastShownSteer(lines) ? (
              <li>
                <p className="text-xs normal-case tracking-normal text-lk-label">
                  Next suggestion: {bobSteer.trim()}
                  {bobPose.trim() ? ` · ${bobPose.trim()}` : ""}
                </p>
              </li>
            ) : null}
          </ol>
        </section>
        <form onSubmit={onSubmit} className="flex flex-col gap-3 rounded-3xl bg-white/90 p-3 sm:flex-row">
          <label className="sr-only" htmlFor="line">
            Say a line
          </label>
          <input
            ref={lineInput}
            id="line"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={roundOver || !live}
            placeholder={!live ? "Press Start first" : roundOver ? "The round is over" : "Say something"}
            className="flex-1 rounded-full border border-lk-line bg-lk-tint px-4 py-3"
          />
          <button type="submit" disabled={busy || roundOver || !live} className="rounded-full bg-lk-primary px-5 py-3 text-white disabled:opacity-50">
            Send
          </button>
          <button
            type="button"
            disabled={roundOver || !live}
            onPointerDown={speakDown}
            onPointerUp={speakUp}
            onPointerCancel={speakUp}
            onLostPointerCapture={speakUp}
            onClick={(event) => event.preventDefault()}
            className="select-none rounded-full border border-lk-primary px-5 py-3 active:bg-lk-primary active:text-white disabled:opacity-50"
          >
            Speak
          </button>
        </form>
        {/* Free speech only: Bob, Rob, and the card's practice words do not run in a game. */}
        {qa && !gameId ? (
          <p className="rounded-xl bg-white/90 px-3 py-2 text-sm text-lk-muted">
            Outside the theme: {practiceWords.length > 0 ? practiceWords.join(", ") : "none on this talk"}
          </p>
        ) : null}
        {notice && <p className="rounded-xl bg-white/90 px-3 py-2 text-sm text-lk-muted">{notice}</p>}
      </main>
      {connectOpen ? (
        <ConnectPanel
          hubHttp={HUB_HTTP}
          onClose={() => setConnectOpen(false)}
          onConnected={(next) => {
            setAuth(next);
            setConnectOpen(false);
          }}
        />
      ) : null}
      {correction ? (
        <CorrectionPopup
          hubHttp={HUB_HTTP}
          sessionId={sessionRef.current || ""}
          noteId={correction.noteId}
          explanation={correction.explanation}
          onClose={() => setCorrection(null)}
        />
      ) : null}
      {sessionsOpen && auth ? (
        <SessionsPanel
          hubHttp={HUB_HTTP}
          token={auth.token}
          onEnded={tokenEnded}
          onClose={() => setSessionsOpen(false)}
          onPick={(session) => void importSession(session)}
        />
      ) : null}
      {editing ? (
        <MaterialEditor
          hubHttp={HUB_HTTP}
          languageId={editing.languageId}
          languageLabel={languageName(editing.languageId, catalog.languages)}
          materialId={editing.materialId || undefined}
          onClose={() => setEditing(null)}
          onSaved={materialSaved}
        />
      ) : null}
      {reading ? (
        <TextReader
          hubHttp={HUB_HTTP}
          languageId={reading.languageId}
          materialId={reading.materialId}
          onClose={() => setReading(null)}
        />
      ) : null}
    </div>
  );
}

function practiceWordsFrom(subject: { important_words?: unknown } | undefined): string[] {
  const words = subject?.important_words;
  if (!Array.isArray(words)) return [];
  return words.filter((item): item is string => typeof item === "string" && item.trim() !== "");
}

function sentencesToLines(sentences: Sentence[], buddyName: string, teacherName: string): Line[] {
  return sentences.map((sentence, index) => ({
    id: sentence.id || `restored-${index}`,
    speaker:
      sentence.speaker === "buddy" ? buddyName : sentence.speaker === "teacher" ? teacherName || "Savelij" : "You",
    text: sentence.text,
    altered: sentence.altered === true,
    steer: sentence.steer ?? "",
    noteId: sentence.note_id || "",
    explanation: sentence.explanation || "",
    verdict: sentence.verdict || "",
    expected: sentence.expected || "",
  }));
}

function CorrectionPopup({
  hubHttp,
  sessionId,
  noteId,
  explanation,
  onClose,
}: {
  hubHttp: string;
  sessionId: string;
  noteId: string;
  explanation: string;
  onClose: () => void;
}) {
  const [text, setText] = useState(explanation);
  const [pcm, setPcm] = useState<Uint8Array | null>(null);
  const [hearing, setHearing] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!noteId) return;
    let gone = false;
    const params = new URLSearchParams({ session_id: sessionId });
    void fetch(`${hubHttp}/teacher-notes/${noteId}?${params}`)
      .then(async (response) => {
        const body = (await response.json()) as { explanation?: string; pcm?: string };
        if (gone) return;
        if (!response.ok) {
          setMessage("The voice is not available.");
          return;
        }
        if (body.explanation) setText(body.explanation);
        if (body.pcm) setPcm(base64ToBytes(body.pcm));
      })
      .catch(() => {
        if (!gone) setMessage("The voice is not available.");
      });
    return () => {
      gone = true;
    };
  }, [hubHttp, noteId, sessionId]);

  async function hear() {
    if (!pcm || hearing) return;
    setHearing(true);
    try {
      await playPcm(pcm);
    } finally {
      setHearing(false);
    }
  }

  return (
    <div className="fixed inset-0 z-30 flex items-start justify-center bg-lk-ink/40 px-4 py-16" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Correction"
        className="w-full max-w-md rounded-2xl bg-lk-tint p-4 shadow-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-lg">{noteId ? "Correction" : "Miss"}</h2>
          <button type="button" className="rounded-full border border-lk-primary px-3 py-1 text-sm" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="text-sm text-lk-ink">{text}</p>
        {message ? <p className="mt-2 text-sm text-lk-red">{message}</p> : null}
        {noteId ? (
        <button
          type="button"
          onClick={() => void hear()}
          disabled={!pcm || hearing}
          className="mt-4 rounded-full bg-lk-primary px-4 py-2 text-white disabled:opacity-50"
        >
          {hearing ? "Hearing" : "Hear"}
        </button>
        ) : null}
      </div>
    </div>
  );
}

function lastShownSteer(lines: Line[]): string {
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const steer = lines[index]?.steer?.trim();
    if (steer) return steer;
  }
  return "";
}

function base64ToBytes(value: string): Uint8Array {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}
