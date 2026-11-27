/// <reference types="vite/client" />


interface ImportMetaEnv {
  readonly VITE_HUB_WS?: string;
  readonly VITE_HUB_HTTP?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
