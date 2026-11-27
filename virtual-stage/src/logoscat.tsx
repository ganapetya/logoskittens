import { FormEvent, ReactNode, useEffect, useState } from "react";

const AUTH_KEY = "logoskittens.logoscat";

export type LogosCatUser = {
  id: number;
  username?: string;
  email?: string;
};

/** A personal, read-only LogosCat app token (lkc_…). LogosKittens never sees a LogosCat password. */
export type LogosCatAuth = {
  token: string;
  user: LogosCatUser;
  expiresAt: string;
};

export const ENDED = "The LogosCat token expired or was revoked. Connect again.";

export type WorkspaceSession = {
  id: number;
  name: string;
  timestampStarted: string;
  itemCount: number;
};

export function readAuth(): LogosCatAuth | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as LogosCatAuth;
    // A login token stored before app tokens is dropped. It must be replaced by a Connect.
    if (!parsed || typeof parsed.token !== "string" || !parsed.token.startsWith("lkc_")) return null;
    if (!parsed.user || typeof parsed.user.id !== "number") return null;
    return {
      token: parsed.token,
      user: parsed.user,
      expiresAt: typeof parsed.expiresAt === "string" ? parsed.expiresAt : "",
    };
  } catch {
    return null;
  }
}

export function writeAuth(auth: LogosCatAuth) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
}

export function clearAuth() {
  localStorage.removeItem(AUTH_KEY);
}

export function displayName(user: LogosCatUser): string {
  return user.username || user.email || "LogosCat";
}

export function visibleMaterials<T extends { origin?: string; logoscat_user_id?: number }>(
  materials: T[],
  auth: LogosCatAuth | null,
): T[] {
  return materials.filter((item) => {
    if (item.origin !== "logoscat") return true;
    return auth !== null && item.logoscat_user_id === auth.user.id;
  });
}

type ConnectProps = {
  hubHttp: string;
  onClose: () => void;
  onConnected: (auth: LogosCatAuth) => void;
};

export function ConnectPanel({ hubHttp, onClose, onConnected }: ConnectProps) {
  const [token, setToken] = useState("");
  const [tokensUrl, setTokensUrl] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let gone = false;
    void fetch(`${hubHttp}/logoscat/info`)
      .then(async (response) => {
        const body = (await response.json()) as { tokens_url?: string };
        if (!gone && body.tokens_url) setTokensUrl(body.tokens_url);
      })
      .catch(() => {
        /* the link stays hidden; the paste still works */
      });
    return () => {
      gone = true;
    };
  }, [hubHttp]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const value = token.trim();
    if (!value.startsWith("lkc_")) {
      setMessage("Paste the token from LogosCat. It starts with lkc_.");
      return;
    }
    setPending(true);
    setMessage("");
    try {
      const response = await fetch(`${hubHttp}/logoscat/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: value }),
      });
      const body = (await response.json()) as {
        success?: boolean;
        error?: string;
        user?: LogosCatUser;
        expiresAt?: string;
      };
      if (!response.ok || !body.success || !body.user || typeof body.user.id !== "number") {
        setMessage(body.error || "LogosCat did not accept that token.");
        return;
      }
      const auth = { token: value, user: body.user, expiresAt: body.expiresAt || "" };
      writeAuth(auth);
      setToken("");
      onConnected(auth);
    } catch {
      setMessage("LogosCat is not reachable.");
    } finally {
      setPending(false);
    }
  }

  return (
    <Overlay title="Connect LogosCat" onClose={onClose}>
      <form className="flex flex-col gap-3" noValidate onSubmit={onSubmit}>
        <p className="text-sm text-lk-muted">
          Log in on LogosCat yourself, open Settings, Connected apps, and create a LogosKittens token. Paste it here.
          It can only read your workspace sessions and language settings. Your password never comes here.
        </p>
        {tokensUrl ? (
          <a
            href={tokensUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="self-start rounded-full border border-lk-primary px-3 py-1 text-sm"
          >
            Open LogosCat, Connected apps
          </a>
        ) : null}
        <label className="flex flex-col gap-1 text-sm">
          App token
          <input
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            autoComplete="off"
            spellCheck={false}
            placeholder="lkc_…"
            className="rounded-xl border border-lk-line bg-white px-3 py-2 font-mono"
          />
        </label>
        {message ? <p className="text-sm text-lk-red">{message}</p> : null}
        <button
          type="submit"
          disabled={pending || !token.trim()}
          className="rounded-full bg-lk-primary px-4 py-2 text-white disabled:opacity-50"
        >
          {pending ? "Connecting" : "Connect"}
        </button>
      </form>
    </Overlay>
  );
}

type SessionsProps = {
  hubHttp: string;
  token: string;
  onClose: () => void;
  onEnded: () => void;
  onPick: (session: WorkspaceSession) => void;
};

export function SessionsPanel({ hubHttp, token, onClose, onEnded, onPick }: SessionsProps) {
  const [sessions, setSessions] = useState<WorkspaceSession[] | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let gone = false;
    void fetch(`${hubHttp}/logoscat/workspace-sessions`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (response) => {
        const body = (await response.json()) as { success?: boolean; error?: string; sessions?: WorkspaceSession[] };
        if (gone) return;
        if (response.status === 401) {
          onEnded();
          return;
        }
        if (!response.ok || !body.success) {
          setMessage(body.error || "The session list is unavailable.");
          setSessions([]);
          return;
        }
        setSessions(Array.isArray(body.sessions) ? body.sessions : []);
      })
      .catch(() => {
        if (gone) return;
        setMessage("LogosCat is not reachable.");
        setSessions([]);
      });
    return () => {
      gone = true;
    };
  }, [hubHttp, token]);

  return (
    <Overlay title="Workspace sessions" onClose={onClose}>
      {sessions === null ? <p className="text-sm text-lk-muted">Loading workspace sessions...</p> : null}
      {message ? <p className="text-sm text-lk-red">{message}</p> : null}
      {sessions && sessions.length === 0 && !message ? (
        <p className="text-sm text-lk-muted">No workspace sessions yet.</p>
      ) : null}
      {sessions && sessions.length > 0 ? (
        <ul className="flex max-h-80 flex-col gap-2 overflow-y-auto">
          {sessions.map((session) => (
            <li key={session.id}>
              <button
                type="button"
                onClick={() => onPick(session)}
                className="w-full rounded-xl bg-white px-3 py-2 text-start"
              >
                <span className="block">
                  {session.name} ({session.itemCount === 1 ? "1 session item" : `${session.itemCount} session items`})
                </span>
                <span className="block text-xs text-lk-label">{sessionWhen(session.timestampStarted)}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </Overlay>
  );
}

function Overlay({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-30 flex items-start justify-center bg-lk-ink/40 px-4 py-16" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-md rounded-2xl bg-lk-tint p-4 shadow-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-lg">{title}</h2>
          <button type="button" className="rounded-full border border-lk-primary px-3 py-1 text-sm" onClick={onClose}>
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function sessionWhen(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
