/**
 * Settings, at #/settings, opened in its own tab so a running talk keeps going.
 * Two tabs: Speech (#/settings) and Models (#/settings/models, in models_settings.tsx).
 * Google speech: one credential (API key or service account), two switches, and per language a man's,
 * a woman's and Savelij's voice. Everything is stored on the hub. The credential is sent once and never
 * comes back to the page. Nothing here calls LogosCat.
 */

import { type ChangeEvent, useEffect, useState } from "react";
import { isRtl } from "./languages";
import { ModelsTab } from "./models_settings";
import { playPcm } from "./pcm";

const HUB_HTTP = import.meta.env.VITE_HUB_HTTP ?? "http://localhost:8090";

type Role = "man" | "woman" | "teacher";
type LanguageRow = {
  id: string;
  name: string;
  tts_locale: string;
  voices: Record<Role, string>;
  defaults: Record<Role, string>;
  ranked: { man: string[]; woman: string[] };
  stt_locale: string;
  stt_model: string;
};
type Settings = {
  tts_provider: "local" | "google";
  stt_provider: "local" | "google";
  credential_set: boolean;
  credential_kind: "" | "api_key" | "service_account";
  credential_hint: string;
  languages: LanguageRow[];
};
type Voice = { name: string; gender: string; family: string };

const ROLE_LABEL: Record<Role, string> = { man: "Man", woman: "Woman", teacher: "Teacher (Savelij)" };

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

function decode(base64: string): Uint8Array {
  const raw = atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let index = 0; index < raw.length; index += 1) bytes[index] = raw.charCodeAt(index);
  return bytes;
}

type Tab = "speech" | "models";

function tabFromHash(): Tab {
  return window.location.hash.startsWith("#/settings/models") ? "models" : "speech";
}

export function SettingsPage() {
  const [tab, setTab] = useState<Tab>(tabFromHash);

  useEffect(() => {
    const source = window.localStorage.getItem("logoskittens.source") ?? "";
    document.documentElement.dir = isRtl(source) ? "rtl" : "ltr";
    document.title = "LogosKittens settings";
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const tabs: { id: Tab; label: string; hash: string }[] = [
    { id: "speech", label: "Speech", hash: "#/settings" },
    { id: "models", label: "Models", hash: "#/settings/models" },
  ];

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-col gap-3 rounded-3xl bg-white/90 p-4">
        <div>
          <p className="text-xs tracking-[0.2em] uppercase text-lk-label">Settings</p>
          <h1 className="text-4xl text-lk-red">LogosKittens</h1>
        </div>
        <nav className="flex gap-2" role="tablist" aria-label="Settings">
          {tabs.map((item) => (
            <a
              key={item.id}
              href={item.hash}
              role="tab"
              aria-selected={tab === item.id}
              className={`rounded-full border px-4 py-1 text-sm ${
                tab === item.id ? "border-lk-primary bg-lk-primary text-white" : "border-lk-primary text-lk-ink"
              }`}
            >
              {item.label}
            </a>
          ))}
        </nav>
      </header>
      {tab === "speech" ? <SpeechTab /> : <ModelsTab />}
    </div>
  );
}

function SpeechTab() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [kind, setKind] = useState<"api_key" | "service_account">("api_key");
  const [secret, setSecret] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [voices, setVoices] = useState<Record<string, Voice[]>>({});

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!settings) return;
    for (const row of settings.languages) {
      void call<{ voices: Voice[] }>(`/speech/voices?language_id=${encodeURIComponent(row.id)}`)
        .then((found) => setVoices((current) => ({ ...current, [row.id]: found.voices })))
        .catch(() => undefined);
    }
  }, [settings?.credential_set, settings?.credential_hint]);

  async function load() {
    try {
      const found = await call<Settings>("/speech/settings");
      setSettings(found);
      if (found.credential_kind) setKind(found.credential_kind);
    } catch (exc) {
      setError(`The hub did not answer: ${(exc as Error).message}`);
    }
  }

  async function save(update: Record<string, unknown>, done: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const found = await call<Settings>("/speech/settings", { method: "PUT", body: JSON.stringify(update) });
      setSettings(found);
      setNotice(done);
      return true;
    } catch (exc) {
      setError((exc as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function saveCredential() {
    if (!secret.trim()) return;
    if (await save({ credential_kind: kind, credential: secret.trim() }, "Credential saved.")) {
      setSecret("");
      await test();
    }
  }

  async function test() {
    setBusy(true);
    setError("");
    try {
      const result = await call<{ ok: boolean; error?: string; voices_ms?: number; tts_ms?: number }>("/speech/test", {
        method: "POST",
      });
      if (result.ok) setNotice(`Google answered. Voice list ${result.voices_ms} ms, a short line ${result.tts_ms} ms.`);
      else setError(`Google refused: ${result.error}`);
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function forget() {
    setBusy(true);
    setError("");
    try {
      setSettings(await call<Settings>("/speech/credential", { method: "DELETE" }));
      setNotice("Credential removed. Voice and recognition are local again.");
    } catch (exc) {
      setError((exc as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function sample(languageId: string, role: Role, voice: string) {
    setError("");
    try {
      const found = await call<{ pcm: string; ms: number }>("/speech/sample", {
        method: "POST",
        body: JSON.stringify({ language_id: languageId, role, voice }),
      });
      setNotice(`${voice}: ${found.ms} ms.`);
      await playPcm(decode(found.pcm));
    } catch (exc) {
      setError((exc as Error).message);
    }
  }

  function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    void file.text().then(setSecret);
  }

  if (!settings) {
    return <div className="rounded-3xl bg-white/90 p-6">{error || "Loading settings…"}</div>;
  }

  const locked = !settings.credential_set || busy;

  return (
    <>
      <section className="rounded-3xl bg-white/90 p-4">
        <p className="max-w-2xl text-lk-muted">
          Google voice and recognition are optional. They are stored on this hub and work without LogosCat. A
          change applies from the next line.
        </p>
        {notice && <p className="mt-2 text-sm text-lk-green">{notice}</p>}
        {error && <p className="mt-2 text-sm text-lk-red">{error}</p>}
      </section>

      <section className="flex flex-col gap-3 rounded-3xl bg-white/90 p-4">
        <h2 className="text-xl text-lk-ink">Google Cloud credential</h2>
        <p className="text-sm text-lk-muted">
          {settings.credential_set
            ? `Saved: ${settings.credential_kind === "api_key" ? "API key" : "service account"} ${settings.credential_hint}`
            : "None saved. Use an API key restricted to Text-to-Speech and Speech-to-Text, or a service-account JSON."}
        </p>
        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="radio" checked={kind === "api_key"} onChange={() => setKind("api_key")} />
            API key
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" checked={kind === "service_account"} onChange={() => setKind("service_account")} />
            Service account JSON
          </label>
        </div>
        {kind === "api_key" ? (
          <input
            type="password"
            autoComplete="off"
            value={secret}
            onChange={(event) => setSecret(event.target.value)}
            placeholder={settings.credential_set ? "Paste a new key to replace the saved one" : "AIza…"}
            className="w-full rounded-xl border border-lk-line px-3 py-2 text-sm"
            dir="ltr"
          />
        ) : (
          <div className="flex flex-col gap-2">
            <textarea
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
              rows={4}
              placeholder='{"type": "service_account", "client_email": …, "private_key": …}'
              className="w-full rounded-xl border border-lk-line px-3 py-2 font-mono text-xs"
              dir="ltr"
            />
            <input type="file" accept="application/json,.json" onChange={readFile} className="text-sm" />
          </div>
        )}
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => void saveCredential()}
            disabled={busy || !secret.trim()}
            className="rounded-full border border-lk-primary px-3 py-1 text-sm disabled:opacity-50"
          >
            Save
          </button>
          <button
            type="button"
            onClick={() => void test()}
            disabled={locked}
            className="rounded-full border border-lk-primary px-3 py-1 text-sm disabled:opacity-50"
          >
            Test
          </button>
          <button
            type="button"
            onClick={() => void forget()}
            disabled={locked}
            className="rounded-full border border-lk-red px-3 py-1 text-sm text-lk-red disabled:opacity-50"
          >
            Remove
          </button>
        </div>
      </section>

      <section className="flex flex-col gap-3 rounded-3xl bg-white/90 p-4">
        <h2 className="text-xl text-lk-ink">Use Google</h2>
        <Switch
          label="Google voice (TTS)"
          hint="Off: Piper speaks. If a Google call fails, Piper speaks that line."
          on={settings.tts_provider === "google"}
          disabled={locked}
          onChange={(on) => void save({ tts_provider: on ? "google" : "local" }, on ? "Google voice is on." : "Piper voice is on.")}
        />
        <Switch
          label="Google recognition (STT)"
          hint="Off: whisper on this computer hears you. On: whisper is not loaded and Start is faster."
          on={settings.stt_provider === "google"}
          disabled={locked}
          onChange={(on) =>
            void save({ stt_provider: on ? "google" : "local" }, on ? "Google recognition is on." : "Whisper recognition is on.")
          }
        />
      </section>

      <section className="flex flex-col gap-4 rounded-3xl bg-white/90 p-4">
        <h2 className="text-xl text-lk-ink">Voices per language</h2>
        {!settings.credential_set && (
          <p className="text-sm text-lk-muted">The lists below are the shipped defaults until a credential is saved.</p>
        )}
        {settings.languages.map((row) => (
          <LanguageVoices
            key={row.id}
            row={row}
            voices={voices[row.id] ?? []}
            disabled={busy}
            canSample={settings.credential_set}
            onPick={(role, voice) =>
              void save(
                { voices: { [row.id]: { [role]: voice === row.defaults[role] ? "" : voice } } },
                `${row.name}: ${ROLE_LABEL[role]} is ${voice}.`,
              )
            }
            onRecognition={(locale, model) =>
              void save({ recognition: { [row.id]: { locale, model } } }, `${row.name}: recognition ${locale} ${model || "default"}.`)
            }
            onSample={(role, voice) => void sample(row.id, role, voice)}
          />
        ))}
      </section>
    </>
  );
}

function Switch(props: { label: string; hint: string; on: boolean; disabled: boolean; onChange: (on: boolean) => void }) {
  return (
    <label className={`flex items-start gap-3 ${props.disabled ? "opacity-60" : ""}`}>
      <input
        type="checkbox"
        className="mt-1"
        checked={props.on}
        disabled={props.disabled}
        onChange={(event) => props.onChange(event.target.checked)}
      />
      <span>
        <span className="block text-lk-ink">{props.label}</span>
        <span className="block text-sm text-lk-muted">{props.hint}</span>
      </span>
    </label>
  );
}

function LanguageVoices(props: {
  row: LanguageRow;
  voices: Voice[];
  disabled: boolean;
  canSample: boolean;
  onPick: (role: Role, voice: string) => void;
  onRecognition: (locale: string, model: string) => void;
  onSample: (role: Role, voice: string) => void;
}) {
  const { row } = props;
  const [locale, setLocale] = useState(row.stt_locale);
  const [model, setModel] = useState(row.stt_model);
  useEffect(() => {
    setLocale(row.stt_locale);
    setModel(row.stt_model);
  }, [row.stt_locale, row.stt_model]);

  function options(role: Role): string[] {
    const gender = role === "woman" ? "woman" : "man";
    const listed = props.voices.filter((item) => item.gender === gender).map((item) => item.name);
    const names = listed.length > 0 ? listed : row.ranked[gender];
    return names.includes(row.voices[role]) ? names : [row.voices[role], ...names];
  }

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-lk-line p-3">
      <p className="text-lg text-lk-ink" dir="auto">
        {row.name} <span className="text-sm text-lk-muted">{row.tts_locale}</span>
      </p>
      <div className="grid gap-3 md:grid-cols-3">
        {(["man", "woman", "teacher"] as Role[]).map((role) => (
          <div key={role} className="flex flex-col gap-1">
            <span className="text-xs tracking-[0.1em] uppercase text-lk-label">{ROLE_LABEL[role]}</span>
            <div className="flex items-center gap-2">
              <select
                value={row.voices[role]}
                disabled={props.disabled}
                onChange={(event) => props.onPick(role, event.target.value)}
                className="min-w-0 flex-1 rounded-xl border border-lk-line px-2 py-1 text-sm"
                dir="ltr"
              >
                {options(role).map((name) => (
                  <option key={name} value={name}>
                    {name}
                    {name === row.defaults[role] ? " (default)" : ""}
                  </option>
                ))}
              </select>
              <button
                type="button"
                title="Play a sample"
                disabled={!props.canSample}
                onClick={() => props.onSample(role, row.voices[role])}
                className="rounded-full border border-lk-primary px-2 py-1 text-sm disabled:opacity-50"
              >
                ▶
              </button>
            </div>
          </div>
        ))}
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-lk-muted">Recognition</summary>
        <div className="mt-2 flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-lk-label">Locale</span>
            <input
              value={locale}
              onChange={(event) => setLocale(event.target.value)}
              className="w-32 rounded-xl border border-lk-line px-2 py-1"
              dir="ltr"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-lk-label">Model (empty is Google's default)</span>
            <input
              value={model}
              onChange={(event) => setModel(event.target.value)}
              className="w-40 rounded-xl border border-lk-line px-2 py-1"
              dir="ltr"
            />
          </label>
          <button
            type="button"
            disabled={props.disabled}
            onClick={() => props.onRecognition(locale.trim(), model.trim())}
            className="rounded-full border border-lk-primary px-3 py-1 disabled:opacity-50"
          >
            Save recognition
          </button>
        </div>
      </details>
    </div>
  );
}
