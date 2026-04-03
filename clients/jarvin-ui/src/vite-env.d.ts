/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_JARVIN_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
