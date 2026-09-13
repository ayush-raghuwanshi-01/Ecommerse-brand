/// <reference types="vite/client" />

/**
 * Typed contract for every browser-visible environment variable.
 *
 * Vite statically replaces `import.meta.env.VITE_*` at build time, so a typo
 * here silently becomes `undefined` at runtime. Declaring the shape keeps that
 * from happening and documents what the app is configurable by.
 */
interface ImportMetaEnv {
  /** Base path (or absolute URL) of the commerce API, e.g. `/api/v1`. */
  readonly VITE_API_BASE_URL?: string;
  /** Dev-server proxy target for `/api` and `/static` (node-side only). */
  readonly VITE_DEV_PROXY_TARGET?: string;
  /** Comma-separated extra hosts allowed by the dev server (node-side only). */
  readonly VITE_DEV_ALLOWED_HOSTS?: string;

  readonly VITE_BRAND_NAME?: string;
  readonly VITE_BRAND_TAGLINE?: string;
  readonly VITE_CONTACT_EMAIL?: string;
  readonly VITE_WHATSAPP_NUMBER?: string;
  readonly VITE_SUPPORT_PHONE?: string;

  readonly VITE_GA_MEASUREMENT_ID?: string;
  readonly VITE_SENTRY_DSN?: string;

  readonly VITE_APP_ENV?: string;
  readonly MODE: string;
  readonly DEV: boolean;
  readonly PROD: boolean;
  readonly BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
