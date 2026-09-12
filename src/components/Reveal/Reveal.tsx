import type { CSSProperties, ElementType, ReactNode } from "react";
import { useInView } from "../../hooks/useInView";
import { usePrefersReducedMotion } from "../../hooks/usePrefersReducedMotion";
import styles from "./Reveal.module.css";

export interface RevealProps {
  children: ReactNode;
  /** Rendered element. Defaults to a div. */
  as?: ElementType;
  /** Optional stagger offset within the single coordinated reveal pass. */
  delayMs?: number;
  className?: string;
  id?: string;
}

/**
 * Fades and lifts its children once, when they first enter the viewport.
 * Under prefers-reduced-motion the content is simply present.
 */
export default function Reveal({
  children,
  as: Tag = "div",
  delayMs = 0,
  className,
  id,
}: RevealProps) {
  const reducedMotion = usePrefersReducedMotion();
  const { ref, inView } = useInView<HTMLDivElement>({ threshold: 0.15 });

  const show = reducedMotion || inView;
  const classNames = [styles.reveal, show ? styles.visible : "", className ?? ""]
    .filter(Boolean)
    .join(" ");
  const style: CSSProperties = delayMs > 0 ? { transitionDelay: `${delayMs}ms` } : {};

  return (
    <Tag ref={ref} id={id} className={classNames} style={style}>
      {children}
    </Tag>
  );
}
