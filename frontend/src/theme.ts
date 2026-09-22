/**
 * Design tokens (light theme). Keep in sync with the CSS custom properties in
 * `styles.css` — this object is for values needed inside inline styles/JS
 * (e.g. dynamic colour logic) so they don't drift from the stylesheet.
 */
export const theme = {
  colors: {
    background: '#ffffff',
    soft: '#f7f4ee',
    ink: '#17140f',
    card: '#ffffff',
    border: '#eae5da',
    accent: '#9a5b0b',
    accentDeep: '#7c4a08',
    text: '#2b2721',
    dim: '#6f6858',
    ok: '#1f7a4d',
    alert: '#c2452d',
  },
} as const;

/** Free shipping threshold (paise) — mirrors `free_shipping_threshold_paise` seeded in the backend settings. */
export const FREE_SHIPPING_THRESHOLD_PAISE = 1_500_000;
