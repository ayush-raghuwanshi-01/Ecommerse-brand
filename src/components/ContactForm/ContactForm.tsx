import { useCallback, useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { config } from "../../config";
import { composeMailto } from "../../utils/mailto";
import styles from "./ContactForm.module.css";

export interface ContactFormProps {
  /** Where the composed message is sent. Defaults to config.contactEmail. */
  to?: string;
  /** Milliseconds the "opening your email app…" status stays on screen. */
  statusDurationMs?: number;
  /**
   * Hands the composed `mailto:` URL to the browser. Isolated here so the
   * handoff has exactly one place to change (and so it can be observed).
   */
  navigate?: (url: string) => void;
}

interface FormValues {
  name: string;
  email: string;
  phone: string;
  message: string;
}

type FormField = keyof FormValues;
type FormErrors = Partial<Record<FormField, string>>;
type FormStatus = "idle" | "opening";

const emptyValues: FormValues = { name: "", email: "", phone: "", message: "" };

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/**
 * Client-side contact form.
 *
 * On submit it builds a `mailto:` URL from `config.contactEmail` with the
 * subject and body populated from the fields, then hands off to the visitor's
 * own email client via `window.location.href`.
 *
 * ───────────────────────────────────────────────────────────────────────────
 * PERSONALISE ME: set `contactEmail` in src/config.ts. To move to a real form
 * service (Formspree, Basin, a serverless route, …) replace `composeMailto`
 * and the `window.location.href` assignment in `handleSubmit` — nothing else
 * in this component or anywhere else on the page needs to change.
 * ───────────────────────────────────────────────────────────────────────────
 */
const openInMailClient = (url: string): void => {
  window.location.href = url;
};

export default function ContactForm({
  to = config.contactEmail,
  statusDurationMs = 6000,
  navigate = openInMailClient,
}: ContactFormProps) {
  const [values, setValues] = useState<FormValues>(emptyValues);
  const [errors, setErrors] = useState<FormErrors>({});
  const [status, setStatus] = useState<FormStatus>("idle");
  const statusTimer = useRef<number | null>(null);

  const clearStatusTimer = useCallback((): void => {
    if (statusTimer.current !== null) {
      window.clearTimeout(statusTimer.current);
      statusTimer.current = null;
    }
  }, []);

  useEffect(() => clearStatusTimer, [clearStatusTimer]);

  const update =
    (field: FormField) =>
    (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>): void => {
    const value = event.target.value;
    setValues((previous) => ({ ...previous, [field]: value }));
    setErrors((previous) => {
      if (!previous[field]) return previous;
      const next = { ...previous };
      delete next[field];
      return next;
    });
  };

  const validate = (candidate: FormValues): FormErrors => {
    const next: FormErrors = {};
    if (!candidate.name.trim()) next.name = "Please add your name.";
    if (!candidate.email.trim()) next.email = "Please add an email address.";
    else if (!EMAIL_PATTERN.test(candidate.email.trim()))
      next.email = "That email address does not look complete.";
    if (!candidate.message.trim()) next.message = "A short message helps us reply properly.";
    return next;
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const nextErrors = validate(values);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    navigate(composeMailto(values, to));

    clearStatusTimer();
    setStatus("opening");
    statusTimer.current = window.setTimeout(() => {
      setStatus("idle");
      statusTimer.current = null;
    }, statusDurationMs);
  };

  const hasError = (field: FormField): boolean => Boolean(errors[field]);

  return (
    <form className={styles.form} onSubmit={handleSubmit} noValidate>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="contact-name">
          Name
        </label>
        <input
          id="contact-name"
          name="name"
          type="text"
          autoComplete="name"
          className={[styles.input, hasError("name") ? styles.invalid : ""].filter(Boolean).join(" ")}
          placeholder="Your name"
          value={values.name}
          onChange={update("name")}
          aria-invalid={hasError("name")}
          aria-describedby={hasError("name") ? "contact-name-error" : undefined}
        />
        {hasError("name") ? (
          <span id="contact-name-error" className={styles.error} role="alert">
            {errors.name}
          </span>
        ) : null}
      </div>

      <div className={styles.row}>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="contact-email">
            Email
          </label>
          <input
            id="contact-email"
            name="email"
            type="email"
            autoComplete="email"
            className={[styles.input, hasError("email") ? styles.invalid : ""].filter(Boolean).join(" ")}
            placeholder="you@example.com"
            value={values.email}
            onChange={update("email")}
            aria-invalid={hasError("email")}
            aria-describedby={hasError("email") ? "contact-email-error" : undefined}
          />
          {hasError("email") ? (
            <span id="contact-email-error" className={styles.error} role="alert">
              {errors.email}
            </span>
          ) : null}
        </div>

        <div className={styles.field}>
          <label className={styles.label} htmlFor="contact-phone">
            Phone <span className={styles.optional}>optional</span>
          </label>
          <input
            id="contact-phone"
            name="phone"
            type="tel"
            autoComplete="tel"
            className={styles.input}
            placeholder="If a call is easier"
            value={values.phone}
            onChange={update("phone")}
          />
        </div>
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="contact-message">
          Message
        </label>
        <textarea
          id="contact-message"
          name="message"
          rows={4}
          className={[styles.textarea, hasError("message") ? styles.invalid : ""].filter(Boolean).join(" ")}
          placeholder="Which piece, which size, when you would like it."
          value={values.message}
          onChange={update("message")}
          aria-invalid={hasError("message")}
          aria-describedby={hasError("message") ? "contact-message-error" : undefined}
        />
        {hasError("message") ? (
          <span id="contact-message-error" className={styles.error} role="alert">
            {errors.message}
          </span>
        ) : null}
      </div>

      <div className={styles.actions}>
        <button type="submit" className={styles.submit} disabled={status === "opening"}>
          Send enquiry
        </button>
        {/* The live region stays mounted so screen readers announce the change. */}
        <span className={styles.status} role="status" aria-live="polite">
          {status === "opening" ? "Opening your email app…" : ""}
        </span>
      </div>

      <p className={styles.note}>
        This opens your own email client with the message already written out — nothing is
        stored on this page and no data leaves your device. It can be pointed at a hosted form
        service or a small backend later without changing anything else here.
      </p>
    </form>
  );
}
