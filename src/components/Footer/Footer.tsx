import type { MouseEvent } from "react";
import { config, getWhatsAppLink } from "../../config";
import { usePrefersReducedMotion } from "../../hooks/usePrefersReducedMotion";
import { scrollToSection } from "../../utils/scroll";
import { WhatsAppGlyph } from "../WhatsAppGlyph/WhatsAppGlyph";
import styles from "./Footer.module.css";

export interface FooterProps {
  /** Shown after the copyright symbol. */
  year?: number;
}

export default function Footer({ year = new Date().getFullYear() }: FooterProps) {
  const reducedMotion = usePrefersReducedMotion();

  const onBackToTop = (event: MouseEvent<HTMLAnchorElement>): void => {
    const target = document.getElementById("top");
    if (!target) return;
    event.preventDefault();
    scrollToSection("top", reducedMotion);
  };

  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div>
          <p className={styles.wordmark}>
            {config.brandName}
            <span aria-hidden="true">.</span>
          </p>
          <p className={styles.tagline}>
            Small-batch outerwear, cut in runs of forty to two hundred. Enquiries are answered
            by the people who make the pieces.
          </p>
        </div>

        <nav aria-label="Social">
          <p className={styles.heading}>Elsewhere</p>
          <ul className={styles.list}>
            {config.socials.map((social) => (
              <li key={social.label}>
                {/*
                  PERSONALISE ME: these entries are still "#" in src/config.ts,
                  so they render as plain text rather than dead links. Put a
                  real URL in config and they become links automatically.
                */}
                {social.href === "#" ? (
                  <span className={styles.placeholder}>
                    {social.label} <span className={styles.soon}>soon</span>
                  </span>
                ) : (
                  <a
                    className={styles.link}
                    href={social.href}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {social.label}
                  </a>
                )}
              </li>
            ))}
          </ul>
        </nav>

        <nav aria-label="Contact">
          <p className={styles.heading}>Studio</p>
          <ul className={styles.list}>
            <li>
              <a
                className={styles.link}
                href={getWhatsAppLink()}
                target="_blank"
                rel="noopener noreferrer"
              >
                <WhatsAppGlyph className={styles.linkIcon} />
                WhatsApp
              </a>
            </li>
            <li>
              <a className={styles.link} href={`mailto:${config.contactEmail}`}>
                {config.contactEmail}
              </a>
            </li>
          </ul>
        </nav>
      </div>

      <div className={styles.bottom}>
        <p>
          © {year} {config.brandName}. All rights reserved.
        </p>
        <a className={styles.toTop} href="#top" onClick={onBackToTop}>
          <span className={styles.toTopLine} aria-hidden="true" />
          Back to top
        </a>
      </div>
    </footer>
  );
}
