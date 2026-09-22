/**
 * Runtime configuration for the storefront.
 *
 * Every value comes from a `VITE_*` environment variable (see `.env.example`)
 * with a development-friendly fallback, so the app boots with zero config and
 * can be re-pointed at another environment without a code change.
 *
 * Nothing secret belongs here — Vite inlines these strings into the JS bundle,
 * which is public. Keys that authorise actions (Razorpay key id, JWTs) are
 * handed out by the backend at request time instead.
 */

const env = import.meta.env;

function firstDefined(...values: (string | undefined)[]): string {
  for (const value of values) {
    if (value !== undefined && value !== '') return value;
  }
  return '';
}

/** Normalise a phone number to the digits-only form wa.me expects. */
function normalisePhone(raw: string): string {
  return raw.replace(/[^\d]/g, '');
}

export const config = {
  /** Brand identity */
  brandName: firstDefined(env.VITE_BRAND_NAME, 'Black House'),
  brandTagline: firstDefined(env.VITE_BRAND_TAGLINE, 'Small-batch outerwear'),

  /** Contact channels */
  contactEmail: firstDefined(env.VITE_CONTACT_EMAIL, 'hello@blackhouse.example'),
  whatsappNumber: normalisePhone(firstDefined(env.VITE_WHATSAPP_NUMBER, '919999999999')),
  supportPhone: normalisePhone(env.VITE_SUPPORT_PHONE ?? ''),

  /**
   * Registered business identity, printed on the legal pages and invoices.
   *
   * ⚠ These placeholders must be replaced with real registered details before
   * launch. The Consumer Protection (E-Commerce) Rules 2020 require the seller's
   * legal name, address and contact details to be displayed, and Razorpay checks
   * them during KYC. See docs/ROADMAP.md "Business inputs still needed".
   */
  legalName: firstDefined(env.VITE_LEGAL_NAME, env.VITE_BRAND_NAME, 'Black House'),
  addressLine1: firstDefined(env.VITE_ADDRESS_LINE1, '—'),
  addressLine2: firstDefined(env.VITE_ADDRESS_LINE2, ''),
  city: firstDefined(env.VITE_CITY, 'Bhopal'),
  state: firstDefined(env.VITE_STATE, 'Madhya Pradesh'),
  postalCode: firstDefined(env.VITE_POSTAL_CODE, '462001'),
  country: firstDefined(env.VITE_COUNTRY, 'India'),
  gstin: firstDefined(env.VITE_GSTIN, ''),
  cin: firstDefined(env.VITE_CIN, ''),

  /** Policy terms surfaced on the legal pages and at checkout. */
  returnWindowDays: Number(env.VITE_RETURN_WINDOW_DAYS ?? 7),
  shippingSlaDays: firstDefined(env.VITE_SHIPPING_SLA, '5–8 business days'),
  supportHours: firstDefined(env.VITE_SUPPORT_HOURS, 'Monday–Saturday, 10:00–18:00 IST'),

  /** Canonical origin, used for canonical URLs, sitemap and OG metadata. */
  siteUrl: firstDefined(env.VITE_SITE_URL, '').replace(/\/+$/, ''),

  /** API base path used by the typed client in `lib/api.ts` */
  apiBase: firstDefined(env.VITE_API_BASE_URL, '/api/v1').replace(/\/+$/, ''),

  /** Optional third-party integrations (empty string = disabled) */
  gaMeasurementId: env.VITE_GA_MEASUREMENT_ID ?? '',
  sentryDsn: env.VITE_SENTRY_DSN ?? '',

  /** `development` | `staging` | `production` — build-time label, not a guard */
  appEnv: firstDefined(env.VITE_APP_ENV, env.MODE),
  isDev: env.DEV,
} as const;

/**
 * Build a WhatsApp deep link. Returns an empty string when no business number
 * is configured, so callers can hide the affordance instead of linking to
 * `https://wa.me/?text=…`.
 */
export const getWhatsAppLink = (message: string): string =>
  config.whatsappNumber ? `https://wa.me/${config.whatsappNumber}?text=${encodeURIComponent(message)}` : '';

export default config;
