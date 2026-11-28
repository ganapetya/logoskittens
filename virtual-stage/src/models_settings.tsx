/**
 * Settings, Models tab (#/settings/models): the xAI and OpenAI keys, and for the buddy, Bob, Rob and Wren
 * the provider, model and think level. .env gives the defaults; a value saved here wins until Reset to .env.
 * A key is sent once and never comes back to the page.
 */

import { useEffect, useState } from "react";

const HUB_HTTP = import.meta.env.VITE_HUB_HTTP ?? "http://localhost:8090";

type Provider = "local" | "xai" | "openai";
type KeyRow = { provider: Provider; label: string; set: boolean; source: "" | "page" | "env"; hint: string; env_name: string };
type ElementRow = {
  id: string;
  label: string;
  role: string;
  providers: { id: Provider; label: string }[];
  provider: Provider;
  model: string;
  think: string;
  base_url: string;
  key_set: boolean;
  source: "" | "page" | "env";
  error: string;
};
type ModelSettings = { keys: KeyRow[]; elements: ElementRow[]; think_levels: Record<Provider, string[]> };

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${HUB_HTTP}${path}`, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (body as { detail?: unknown }).detail;
    throw new Error(typeof detail === "string" ? detail : `HTTP ${response.status}`);
  }
  return body as T;
}

export function ModelsTab() {
  const [settings, setSettings] = useState<ModelSettings | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Model ids a Test returned, per provider. They fill the model lists.
  const [listed, setListed] = useState<Partial<Record<Provider, string[]>>>({});

  useEffect(() => {
    void call<ModelSettings>("/models/settings")
      .then(setSettings)
      .catch((exc: Error) => setError(`The hub did not answer: ${exc.message}`));
  }, []);

  async function run(work: () => Promise<ModelSettings | void>, done: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const found = await work();
      if (found) setSettings(found);
      if (done) setNotice(done);
      return true;
    } catch (exc) {
      setError((exc as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  const put = (body: unknown) => call<ModelSettings>("/models/settings", { method: "PUT", body: JSON.stringify(body) });

  async function test(provider: Provider, key = "") {
    await run(async () => {
      const result = await call<{ ok: boolean; error: string; models: string[] }>("/models/test", {
        method: "POST",
        body: JSON.stringify({ provider, key }),
      });
      if (!result.ok) throw new Error(`${provider === "xai" ? "xAI" : "OpenAI"} refused: ${result.error}`);
      setListed((current) => ({ ...current, [provider]: result.models }));
    }, "");
    setNotice((current) => current || `${provider === "xai" ? "xAI" : "OpenAI"} answered. Its models are in the lists below.`);
  }

  if (!settings) return <div className="rounded-3xl bg-white/90 p-6">{error || "Loading models…"}</div>;

  return (
    <>
      <section className="rounded-3xl bg-white/90 p-4">
        <p className="max-w-2xl text-lk-muted">
          Which model each part of LogosKittens uses. .env gives the defaults; a value saved here wins until Reset to
          .env. Keys stay on this hub. A change applies from the next call.
        </p>
        {notice && <p className="mt-2 text-sm text-lk-green">{notice}</p>}
        {error && <p className="mt-2 text-sm text-lk-red">{error}</p>}
      </section>

      <section className="flex flex-col gap-3 rounded-3xl bg-white/90 p-4">
        <h2 className="text-xl text-lk-ink">API keys</h2>
        {settings.keys.map((row) => (
          <KeyEditor
            key={row.provider}
            row={row}
            busy={busy}
            onSave={(key) =>
              run(async () => {
                const found = await put({ keys: { [row.provider]: key } });
                await test(row.provider);
                return found;
              }, `${row.label} key saved.`)
            }
            onTest={(key) => void test(row.provider, key)}
            onForget={() =>
              void run(
                () => call<ModelSettings>(`/models/key/${row.provider}`, { method: "DELETE" }),
                `${row.label} key removed from this page.`,
              )
            }
          />
        ))}
      </section>

      <section className="flex flex-col gap-3 rounded-3xl bg-white/90 p-4">
        <h2 className="text-xl text-lk-ink">Models</h2>
        {settings.elements.map((row) => (
          <ElementEditor
            key={row.id}
            row={row}
            busy={busy}
            thinkLevels={settings.think_levels}
            listed={listed}
            onSave={(choice) => void run(() => put({ elements: { [row.id]: choice } }), `${row.label} saved.`)}
            onReset={() =>
              void run(
                () => call<ModelSettings>(`/models/element/${row.id}`, { method: "DELETE" }),
                `${row.label} is back to .env.`,
              )
            }
          />
        ))}
      </section>
    </>
  );
}

function Source(props: { source: "" | "page" | "env" }) {
  if (!props.source) return null;
  return (
    <span className="rounded-full bg-lk-tint px-2 py-0.5 text-xs text-lk-label">
      {props.source === "page" ? "set here" : "from .env"}
    </span>
  );
}

function KeyEditor(props: {
  row: KeyRow;
  busy: boolean;
  onSave: (key: string) => Promise<boolean>;
  onTest: (key: string) => void;
  onForget: () => void;
}) {
  const { row } = props;
  const [secret, setSecret] = useState("");
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-lk-line p-3">
      <p className="flex flex-wrap items-center gap-2 text-lk-ink">
        {row.label} <Source source={row.source} />
        <span className="text-sm text-lk-muted" dir="ltr">
          {row.set ? row.hint : `None. Paste one, or set ${row.env_name} in .env.`}
        </span>
      </p>
      <div className="flex flex-wrap gap-2">
        <input
          type="password"
          autoComplete="off"
          value={secret}
          onChange={(event) => setSecret(event.target.value)}
          placeholder={row.set ? "Paste a new key to replace it" : row.provider === "xai" ? "xai-…" : "sk-…"}
          className="min-w-0 basis-full rounded-xl border border-lk-line px-3 py-1 text-sm md:flex-1 md:basis-0"
          dir="ltr"
        />
        <button
          type="button"
          disabled={props.busy || !secret.trim()}
          onClick={() => void props.onSave(secret.trim()).then((ok) => ok && setSecret(""))}
          className="rounded-full border border-lk-primary px-3 py-1 text-sm disabled:opacity-50"
        >
          Save
        </button>
        <button
          type="button"
          disabled={props.busy || (!row.set && !secret.trim())}
          onClick={() => props.onTest(secret.trim())}
          className="rounded-full border border-lk-primary px-3 py-1 text-sm disabled:opacity-50"
        >
          Test
        </button>
        <button
          type="button"
          disabled={props.busy || row.source !== "page"}
          title={row.source === "env" ? "This key comes from .env; edit .env to remove it." : ""}
          onClick={props.onForget}
          className="rounded-full border border-lk-red px-3 py-1 text-sm text-lk-red disabled:opacity-50"
        >
          Remove
        </button>
      </div>
    </div>
  );
}

function ElementEditor(props: {
  row: ElementRow;
  busy: boolean;
  thinkLevels: Record<Provider, string[]>;
  listed: Partial<Record<Provider, string[]>>;
  onSave: (choice: { provider: Provider; model: string; think: string }) => void;
  onReset: () => void;
}) {
  const { row } = props;
  const [provider, setProvider] = useState<Provider>(row.provider);
  const [model, setModel] = useState(row.model);
  const [think, setThink] = useState(row.think);
  useEffect(() => {
    setProvider(row.provider);
    setModel(row.model);
    setThink(row.think);
  }, [row.provider, row.model, row.think]);

  const changed = provider !== row.provider || model !== row.model || think !== row.think;
  const known = props.listed[provider] ?? [];
  const levels = props.thinkLevels[provider] ?? [];

  function pickProvider(next: Provider) {
    setProvider(next);
    // Another provider's model and think level do not carry over. Empty means its default.
    if (next !== row.provider) {
      setModel("");
      setThink("");
    } else {
      setModel(row.model);
      setThink(row.think);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-lk-line p-3">
      <p className="flex flex-wrap items-center gap-2">
        <span className="text-lg text-lk-ink">{row.label}</span>
        <Source source={row.source} />
        <span className="text-sm text-lk-muted">{row.role}</span>
      </p>
      {row.error && <p className="text-sm text-lk-red">{row.error}</p>}
      <div className="grid gap-3 md:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs tracking-[0.1em] uppercase text-lk-label">Provider</span>
          <select
            value={provider}
            disabled={props.busy}
            onChange={(event) => pickProvider(event.target.value as Provider)}
            className="rounded-xl border border-lk-line px-2 py-1"
          >
            {row.providers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs tracking-[0.1em] uppercase text-lk-label">Model</span>
          <input
            list={`models-${row.id}`}
            value={model}
            disabled={props.busy}
            onChange={(event) => setModel(event.target.value)}
            placeholder="Empty is the provider's default"
            className="rounded-xl border border-lk-line px-2 py-1"
            dir="ltr"
          />
          <datalist id={`models-${row.id}`}>
            {known.map((id) => (
              <option key={id} value={id} />
            ))}
          </datalist>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs tracking-[0.1em] uppercase text-lk-label">Think</span>
          <select
            value={think}
            disabled={props.busy}
            onChange={(event) => setThink(event.target.value)}
            className="rounded-xl border border-lk-line px-2 py-1"
          >
            <option value="">Default</option>
            {levels.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>
      </div>
      {provider !== "local" && provider === row.provider && !row.key_set && (
        <p className="text-sm text-lk-red">No key for this provider. Add one under API keys.</p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={props.busy || !changed}
          onClick={() => props.onSave({ provider, model: model.trim(), think })}
          className="rounded-full bg-lk-primary px-3 py-1 text-sm text-white disabled:opacity-50"
        >
          Save
        </button>
        <button
          type="button"
          disabled={props.busy || row.source !== "page"}
          onClick={props.onReset}
          className="rounded-full border border-lk-primary px-3 py-1 text-sm disabled:opacity-50"
        >
          Reset to .env
        </button>
      </div>
    </div>
  );
}
