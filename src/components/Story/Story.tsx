import { config } from "../../config";
import { usePrefersReducedMotion } from "../../hooks/usePrefersReducedMotion";
import { useTilt } from "../../hooks/useTilt";
import Reveal from "../Reveal/Reveal";
import styles from "./Story.module.css";

export interface StoryProps {
  quote?: string;
  attribution?: string;
  paragraphs?: string[];
}

export default function Story({
  quote = "We would rather make forty of something well than four hundred of something adequate.",
  attribution = "Studio note, Run 01",
  paragraphs = [
    `${config.brandName} began in a two-room studio with one industrial machine and a rule: nothing leaves the room until it has been worn hard for a month. The rule still applies. Every silhouette goes through a wear test before it earns a name and a number.`,
    "We work in runs of forty to two hundred. Cloth is bought in fixed lots, so when a run ends it ends. What you buy is what was cut, and we keep a small stock of every cloth we have ever used, which is what makes repairs possible for as long as the garment lasts.",
  ],
}: StoryProps) {
  const reducedMotion = usePrefersReducedMotion();
  const tilt = useTilt<HTMLDivElement>({ max: 7, scale: 1.015, disabled: reducedMotion });

  return (
    <section className={styles.section} id="story" data-section aria-labelledby="story-title">
      <div className={styles.grid}>
        <Reveal className={styles.copy}>
          <h2 id="story-title" className="sr-only">
            The {config.brandName} story
          </h2>

          <blockquote className={styles.quote}>
            {quote}
            <span className={styles.attribution}>{attribution}</span>
          </blockquote>

          <div className={styles.body}>
            {paragraphs.map((paragraph) => (
              <p key={paragraph.slice(0, 24)}>{paragraph}</p>
            ))}
          </div>
        </Reveal>

        <Reveal delayMs={120}>
          <div
            ref={tilt.ref}
            className={styles.visual}
            onMouseMove={tilt.onMouseMove}
            onMouseLeave={tilt.onMouseLeave}
          >
            <span className={styles.innerFrame} aria-hidden="true" />
            <span className={styles.monogram} aria-hidden="true">
              BH
            </span>
            <span className={styles.caption}>
              Studio floor, Kanpur. Photography in production — placeholder panel.
            </span>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
