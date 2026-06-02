declare namespace NodeJS {
  interface ProcessEnv {
    NODE_ENV: string;
    VUE_ROUTER_MODE: 'hash' | 'history' | 'abstract' | undefined;
    VUE_ROUTER_BASE: string | undefined;
    APP_VERSION: string;
    VITE_SESSION_API_BASE_URL?: string;
    VITE_CHAT_API_BASE_URL?: string;
    VITE_API_BASE_URL?: string;
    VITE_AUTH_KEY?: string;
    VITE_SESSION_API_PROXY_TARGET?: string;
    VITE_CHAT_API_PROXY_TARGET?: string;
  }
}

interface ImportMetaEnv {
  readonly VITE_SESSION_API_BASE_URL: string;
  readonly VITE_CHAT_API_BASE_URL: string;
  readonly VITE_AUTH_KEY: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
