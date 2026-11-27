import { useEffect, useRef, useState } from "react";

type Loaded = { title: string; text: string } | { error: string } | null;

/**
 * The Read the text window. It fetches one material from the hub when it opens; the catalog list never carries the
 * sentences. Escape, the Close button, or a click outside closes it, and focus goes back where it was.
 */
export function TextReader({
  hubHttp,
  languageId,
  materialId,
  onClose,
}: {
  hubHttp: string;
  languageId: string;
  materialId: string;
  onClose: () => void;
}) {
  const [loaded, setLoaded] = useState<Loaded>(null);
  const close = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let alive = true;
    setLoaded(null);
    const params = new URLSearchParams({ language_id: languageId });
    void fetch(`${hubHttp}/materials/${encodeURIComponent(materialId)}?${params}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(String(response.status));
        const body = (await response.json()) as { title?: string; text?: string };
        if (alive) setLoaded({ title: body.title ?? "", text: body.text ?? "" });
      })
      .catch(() => {
        if (alive) setLoaded({ error: "The text could not be loaded." });
      });
    return () => {
      alive = false;
    };
  }, [hubHttp, languageId, materialId]);

  // The page re-renders while she speaks. The latest onClose is read through a ref, so focus moves only once.
  const closing = useRef(onClose);
  closing.current = onClose;
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    close.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") closing.current();
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      before?.focus?.();
    };
  }, []);

  const title = loaded && "title" in loaded ? loaded.title : "The text";
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-lk-ink/50 p-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="text-reader-title"
        className="flex max-h-[85vh] w-full max-w-xl flex-col rounded-3xl bg-lk-tint p-5 text-lk-ink shadow-xl"
      >
        <div className="mb-3 flex items-start justify-between gap-3">
          <h2 id="text-reader-title" dir="auto" className="text-lg">
            {title || "The text"}
          </h2>
          <button
            ref={close}
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-full border border-lk-primary px-3 py-1 text-sm"
          >
            Close
          </button>
        </div>
        <div className="min-h-0 overflow-y-auto">
          {loaded === null ? (
            <p className="text-lk-muted">Loading…</p>
          ) : "error" in loaded ? (
            <p className="text-lk-red">{loaded.error}</p>
          ) : (
            <p dir="auto" className="whitespace-pre-wrap leading-relaxed">
              {loaded.text}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
