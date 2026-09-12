import type { MouseEvent, ReactNode } from "react";
import Hero3D from "../Hero3D/Hero3D";
import { config, getWhatsAppLink } from "../../config";
import { usePrefersReducedMotion } from "../../hooks/usePrefersReducedMotion";
import { scrollToSection } from "../../utils/scroll";
import { WhatsAppGlyph } from "../WhatsAppGlyph/WhatsAppGlyph";
import styles from "./Hero.module.css";

export interface HeroProps {
  /** Editorial headline. Pass JSX to control which word is set in gold italic. */
  headline?: ReactNode;
  subheading?: string;
}

const defaultHeadline: ReactNode = (
  <>
    Outerwear made to <em>outlive</em> the season.
  </>
);

export default function Hero({
  headline = defaultHeadline,
  subheading = "Heavyweight cloth, gold hardware, runs of forty to two hundred pieces. Cut once, worn for years.",
}: HeroProps) {
  const reducedMotion = usePrefersReducedMotion();

  const onCollectionClick = (event: MouseEvent<HTMLAnchorElement>): void => {
    const target = document.getElementById("collection");
    if (!target) return;
    event.preventDefault();
    scrollToSection("collection", reducedMotion);
  };

  return (
    <section className={styles.hero} id="top" data-section aria-label={`${config.brandName} — introduction`}>
      <Hero3D />
      <div className={styles.scrim} />
      <div className={styles.frame} />

      <div className={styles.content}>
        <h1 className={styles.headline}>{headline}</h1>

        <p className={styles.subheading}>{subheading}</p>

        <div className={styles.actions}>
          <a className={styles.primary} href="#collection" onClick={onCollectionClick}>
            View the collection
          </a>
          <a
            className={styles.secondary}
            href={getWhatsAppLink()}
            target="_blank"
            rel="noopener noreferrer"
          >
            <WhatsAppGlyph className={styles.secondaryIcon} />
            Message us on WhatsApp
          </a>
        </div>
      </div>

      <div className={styles.meta}>
        <span className={styles.metaItem}>Small-batch outerwear</span>
        <span className={styles.metaItem}>Cut and sewn in Kanpur</span>
        <span className={styles.metaItem}>Run 04 in production</span>
      </div>
    </section>
  );
}
