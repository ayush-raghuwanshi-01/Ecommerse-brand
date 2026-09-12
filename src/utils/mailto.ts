import { config } from "../config";

export interface MailtoFields {
  name: string;
  email: string;
  /** Optional — the form leaves it blank when the visitor skips it. */
  phone: string;
  message: string;
}

/** Subject line used for contact-form enquiries. */
export function buildEnquirySubject(name: string): string {
  const trimmed = name.trim();
  return `Enquiry from ${trimmed.length > 0 ? trimmed : "the website"} — ${config.brandName} website`;
}

/** Plain-text body, laid out so it is easy to read in any email client. */
export function buildEnquiryBody(fields: MailtoFields): string {
  return [
    `Name: ${fields.name.trim()}`,
    `Email: ${fields.email.trim()}`,
    `Phone: ${fields.phone.trim().length > 0 ? fields.phone.trim() : "not given"}`,
    "",
    fields.message.trim(),
    "",
    `— Sent from the ${config.brandName} website contact form.`,
  ].join("\n");
}

/**
 * Builds the `mailto:` URL the contact form navigates to.
 *
 * ───────────────────────────────────────────────────────────────────────────
 * PERSONALISE ME: `config.contactEmail` is the inbox this lands in.
 * To move to a hosted form service or a small backend, replace this function
 * and the `window.location.href` assignment in <ContactForm />.
 * ───────────────────────────────────────────────────────────────────────────
 */
export function composeMailto(fields: MailtoFields, to: string = config.contactEmail): string {
  const params = new URLSearchParams({
    subject: buildEnquirySubject(fields.name),
    body: buildEnquiryBody(fields),
  });
  return `mailto:${to}?${params.toString()}`;
}
