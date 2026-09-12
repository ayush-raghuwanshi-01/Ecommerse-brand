import { config, formatWhatsAppNumber, getWhatsAppLink } from "../../config";
import { WhatsAppGlyph } from "../WhatsAppGlyph/WhatsAppGlyph";
import styles from "./WhatsAppCard.module.css";

export interface WhatsAppCardProps {
  title?: string;
  /** Pre-filled chat message. Falls back to config.defaultMessage. */
  message?: string;
}

export default function WhatsAppCard({
  title = "WhatsApp is the quicker route.",
  message,
}: WhatsAppCardProps) {
  return (
    <aside className={styles.card} aria-labelledby="whatsapp-card-title">
      <h3 className={styles.title} id="whatsapp-card-title">
        {title}
      </h3>

      <div>
        <span className={styles.numberLabel}>Studio line</span>
        {/* Placeholder number — change whatsappNumber in src/config.ts */}
        <p className={styles.number}>{formatWhatsAppNumber()}</p>
      </div>

      <a
        className={styles.button}
        href={getWhatsAppLink(message)}
        target="_blank"
        rel="noopener noreferrer"
      >
        <WhatsAppGlyph className={styles.buttonIcon} />
        Chat on WhatsApp
      </a>

      <div className={styles.details}>
        <p className={styles.detailRow}>{config.studioHours}</p>
        <p className={styles.detailRow}>{config.studioLocation}</p>
      </div>
    </aside>
  );
}
