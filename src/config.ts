/**
 * ─────────────────────────────────────────────────────────────────────────────
 *  BUSINESS CONFIG — the only file you should need to edit to personalise.
 * ─────────────────────────────────────────────────────────────────────────────
 *  Everything the business owns lives here: brand name, the WhatsApp number,
 *  the contact inbox, studio hours and social links.
 *
 *  RULE: no component is allowed to hardcode the WhatsApp number or build a
 *  wa.me URL by hand. Always go through `getWhatsAppLink()`.
 */

export const config = {
  /** Shown in the nav wordmark, the hero, the footer and <title>. */
  brandName: "Black House",

  /**
   * PERSONALISE ME — WhatsApp number, digits only, international format,
   * no "+", spaces, dashes or parentheses.
   *
   *   India        -> "919876543210"
   *   UK           -> "447700900123"
   *   US           -> "14155550123"
   *
   * The value below is a placeholder and will not reach a real phone.
   */
  whatsappNumber: "910000000000",

  /** PERSONALISE ME — the inbox the contact form mailto:s into. */
  contactEmail: "hello@blackhouse.example",

  /**
   * PERSONALISE ME — studio hours / response-time copy shown on the
   * WhatsApp card. Plain prose, no markup.
   */
  studioHours:
    "Studio hours: Tuesday to Saturday, 11:00 to 19:00 IST. We answer within one working day.",
  studioLocation:
    "Unit 14, Loom House, Kanpur Road — visits by appointment.",

  /**
   * PERSONALISE ME — social links. Set `href` to "#" (or remove the entry)
   * until the real profiles exist.
   */
  socials: [
    { label: "Instagram", href: "#" },
    { label: "Lookbook", href: "#" },
    { label: "Journal", href: "#" },
  ] as ReadonlyArray<{ label: string; href: string }>,

  /** Default pre-fill used when no product-specific message is supplied. */
  defaultMessage:
    "Hello Black House — I found you on the site and I would like to know more.",
} as const;

export type WhatsAppMessage = string;

/**
 * The single source of truth for every WhatsApp link on the site.
 * @param message Pre-filled chat text. Falls back to `config.defaultMessage`.
 */
export function getWhatsAppLink(message?: WhatsAppMessage): string {
  const text = message && message.trim().length > 0 ? message : config.defaultMessage;
  return `https://wa.me/${config.whatsappNumber}?text=${encodeURIComponent(text)}`;
}

/**
 * Builds the product-specific enquiry link used on the collection cards.
 * Kept next to `getWhatsAppLink` so the wording stays consistent everywhere.
 */
export function getProductEnquiryLink(productName: string): string {
  return getWhatsAppLink(
    `Hello Black House — I would like to enquire about "${productName}" from the current run.`,
  );
}

/**
 * Formats `config.whatsappNumber` for display, e.g. "910000000000" -> "+91 00000 00000".
 * Purely cosmetic — the link helper above always uses the raw digits.
 */
export function formatWhatsAppNumber(): string {
  const digits = config.whatsappNumber.replace(/\D/g, "");
  if (digits.length < 8) return `+${digits}`;
  const country = digits.slice(0, digits.length - 10);
  const area = digits.slice(-10, -5);
  const line = digits.slice(-5);
  return `+${country} ${area} ${line}`;
}
