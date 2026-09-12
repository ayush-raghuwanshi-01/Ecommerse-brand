import { getWhatsAppLink } from "../../config";
import { WhatsAppGlyph } from "../WhatsAppGlyph/WhatsAppGlyph";
import styles from "./WhatsAppFab.module.css";

export interface WhatsAppFabProps {
  /** Pre-filled chat message. Falls back to config.defaultMessage. */
  message?: string;
  label?: string;
}

/**
 * Always-visible floating WhatsApp entry point, with a subtle pulsing ring.
 * Visible at every scroll position, including inside the hero.
 */
export default function WhatsAppFab({ message, label = "Chat on WhatsApp" }: WhatsAppFabProps) {
  return (
    <a
      className={styles.fab}
      href={getWhatsAppLink(message)}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={label}
    >
      <span className={styles.ring} aria-hidden="true" />
      <WhatsAppGlyph className={styles.icon} />
    </a>
  );
}
