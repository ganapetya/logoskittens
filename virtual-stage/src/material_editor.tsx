import { useEffect, useRef, useState } from "react";

/** What the hub said after a save: the material to select. */
export type SavedMaterial = { materialId: string; languageId: string };

/**
 * Add or edit a material the user writes. It is stored in the hub's own SQLite file, never on LogosCat.
 * With `materialId` the window loads that material and saves with PUT; without it, it adds one with POST.
 */
export function MaterialEditor({
  hubHttp,
  languageId,
  languageLabel,
  materialId,
  onClose,
  onSaved,
}: {
  hubHttp: string;
  languageId: string;
  languageLabel: string;
  materialId?: string;
  onClose: () => void;
  onSaved: (saved: SavedMaterial) => void;
}) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(Boolean(materialId));
  const first = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!materialId) return;
    let alive = true;
    const params = new URLSearchParams({ language_id: languageId });
    void fetch(`${hubHttp}/materials/${encodeURIComponent(materialId)}?${params}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(String(response.status));
        const body = (await response.json()) as { title?: string; text?: string };
        if (!alive) return;
        setTitle(body.title ?? "");
        setText(body.text ?? "");
      })
      .catch(() => {
        if (alive) setError("The material could not be loaded.");
      })
      .finally(() => {
        if (alive) setBusy(false);
      });
    return () => {
      alive = false;
    };
  }, [hubHttp, languageId, materialId]);

  const closing = useRef(onClose);
  closing.current = onClose;
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    first.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") closing.current();
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      before?.focus?.();
    };
  }, []);

  async function save() {
    setError("");
    setBusy(true);
    try {
      const response = await fetch(
        materialId ? `${hubHttp}/materials/${encodeURIComponent(materialId)}` : `${hubHttp}/materials`,
        {
          method: materialId ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ language_id: languageId, title, text }),
        },
      );
      const body = (await response.json().catch(() => ({}))) as {
        success?: boolean;
        error?: string;
        material_id?: string;
        language_id?: string;
      };
      if (!response.ok || !body.success || !body.material_id) {
        setError(body.error || "The material could not be saved.");
        return;
      }
      onSaved({ materialId: body.material_id, languageId: body.language_id || languageId });
    } catch {
      setError("The hub is not reachable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-lk-ink/50 p-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby="material-editor-title"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
        className="flex max-h-[90vh] w-full max-w-xl flex-col gap-3 rounded-3xl bg-lk-tint p-5 text-lk-ink shadow-xl"
      >
        <div className="flex items-start justify-between gap-3">
          <h2 id="material-editor-title" className="text-lg">
            {materialId ? "Edit material" : "Add material"}
          </h2>
          <span className="shrink-0 rounded-full bg-white px-3 py-1 text-sm">{languageLabel}</span>
        </div>
        <label className="flex flex-col gap-1 text-sm">
          Title
          <input
            ref={first}
            dir="auto"
            value={title}
            maxLength={120}
            onChange={(event) => setTitle(event.target.value)}
            className="rounded-xl border border-lk-line bg-white px-3 py-2 text-base"
          />
        </label>
        <label className="flex min-h-0 flex-col gap-1 text-sm">
          Text, several sentences
          <textarea
            dir="auto"
            value={text}
            rows={10}
            maxLength={20000}
            onChange={(event) => setText(event.target.value)}
            className="min-h-[10rem] resize-y rounded-xl border border-lk-line bg-white px-3 py-2 text-base leading-relaxed"
          />
        </label>
        <p className="text-xs text-lk-muted">Stored on this computer only. It is not sent to LogosCat.</p>
        {error ? <p className="text-sm text-lk-red">{error}</p> : null}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-full border border-lk-primary px-4 py-1 text-sm">
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded-full bg-lk-primary px-4 py-1 text-sm text-white disabled:opacity-50"
          >
            Save
          </button>
        </div>
      </form>
    </div>
  );
}
