import { marqueeItems } from "../../data/navLinks";
import styles from "./Marquee.module.css";

export interface MarqueeProps {
  items?: string[];
  /** Number of copies of the item list rendered. Must be even for a seamless loop. */
  copies?: number;
}

/**
 * Thin looping strip of brand attributes.
 * The track holds two identical halves and translates by exactly -50%, so the
 * loop is seamless. CSS handles the animation; nothing is driven from JS, and
 * it pauses entirely under prefers-reduced-motion.
 */
export default function Marquee({ items = marqueeItems, copies = 2 }: MarqueeProps) {
  const groups = Array.from({ length: copies }, (_, index) => index);

  return (
    <div className={styles.strip} aria-hidden="true">
      <div className={styles.track}>
        {groups.map((groupIndex) => (
          <div className={styles.group} key={groupIndex}>
            {items.map((item) => (
              <span className={styles.item} key={`${groupIndex}-${item}`}>
                {item}
              </span>
            ))}
          </div>
        ))}
      </div>
      {/* Screen-reader copy of the same attributes, since the strip is decorative. */}
      <p className="sr-only">{items.join(". ")}.</p>
    </div>
  );
}
