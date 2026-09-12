/**
 * ─────────────────────────────────────────────────────────────────────────────
 *  DESIGN TOKENS — single source of truth for the visual identity.
 * ─────────────────────────────────────────────────────────────────────────────
 *  These values are injected as `--bh-*` CSS custom properties on
 *  <html> by `installDesignTokens()` (called first thing in main.tsx), so CSS
 *  Modules consume `var(--bh-gold)` and TS (e.g. the Three.js materials in
 *  Hero3D) consumes `colors.gold` from the exact same object.
 *
 *  Change a value here and it changes everywhere.
 */

export const colors = {
  /** Warm near-black page background. */
  bg: "#0b0a08",
  /** Slightly lifted background for alternating sections. */
  bgAlt: "#141210",
  /** Card / panel surface. */
  surface: "#17140f",
  /** Hairline borders. */
  border: "#2b2620",
  /** Muted antique gold — the brand accent. Never a bright, neon gold. */
  gold: "#c9a24b",
  /** Bright gold, used sparingly for hover and highlights. */
  goldBright: "#e8c873",
  /** Warm off-white body copy. */
  text: "#ece4d3",
  /** Muted copy: captions, labels, secondary prose. */
  textDim: "#9a8f7a",
  /** Deep gold used for emissive glow in the 3D hero. */
  goldDeep: "#3a2c10",
} as const;

export type ColorToken = keyof typeof colors;

export const fonts = {
  /**
   * Headline family — a distinctive optical serif, set in sentence case.
   * Loaded from Google Fonts in index.html.
   */
  display: '"Fraunces", "Iowan Old Style", "Palatino Linotype", Georgia, serif',
  /** Body / UI family — a clean geometric sans. */
  body: '"Manrope", "Helvetica Neue", Helvetica, Arial, sans-serif',
} as const;

/** Deliberately small radius scale: nothing on this page is a pill except buttons. */
export const radii = {
  none: "0px",
  hair: "2px",
  soft: "4px",
  pill: "999px",
} as const;

export const spacing = {
  page: "clamp(20px, 5vw, 72px)",
  section: "clamp(72px, 12vh, 132px)",
  stack: "clamp(14px, 2vw, 22px)",
} as const;

export const motion = {
  revealMs: "720ms",
  fastMs: "220ms",
  /** Shared easing for every transition on the page. */
  ease: "cubic-bezier(0.16, 0.84, 0.24, 1)",
} as const;

/** Sticky nav height — kept here so section scroll-margins match it. */
export const navHeight = "72px";

const varMap: Record<string, string> = {
  "--bh-bg": colors.bg,
  "--bh-bg-alt": colors.bgAlt,
  "--bh-surface": colors.surface,
  "--bh-border": colors.border,
  "--bh-gold": colors.gold,
  "--bh-gold-bright": colors.goldBright,
  "--bh-gold-deep": colors.goldDeep,
  "--bh-text": colors.text,
  "--bh-text-dim": colors.textDim,

  "--bh-font-display": fonts.display,
  "--bh-font-body": fonts.body,

  "--bh-radius-hair": radii.hair,
  "--bh-radius-soft": radii.soft,
  "--bh-radius-pill": radii.pill,

  "--bh-space-page": spacing.page,
  "--bh-space-section": spacing.section,
  "--bh-space-stack": spacing.stack,

  "--bh-nav-height": navHeight,

  "--bh-motion-reveal": motion.revealMs,
  "--bh-motion-fast": motion.fastMs,
  "--bh-ease": motion.ease,
};

/**
 * Writes the tokens above onto :root as CSS custom properties.
 * Safe to call more than once.
 */
export function installDesignTokens(): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  for (const [name, value] of Object.entries(varMap)) {
    root.style.setProperty(name, value);
  }
}
