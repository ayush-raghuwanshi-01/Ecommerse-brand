import type { Silhouette } from "../../types";
import styles from "./GarmentArt.module.css";

export interface GarmentArtProps {
  silhouette: Silhouette;
  /** Accessible name, e.g. "Line drawing of a bomber jacket". */
  label: string;
  className?: string;
}

interface SilhouetteDrawing {
  paths: string[];
  /** Button / rivet positions, drawn as small open circles. */
  dots?: ReadonlyArray<readonly [number, number]>;
}

/**
 * Placeholder garment line art.
 *
 * ───────────────────────────────────────────────────────────────────────────
 * PERSONALISE ME: there are no product photographs yet, so each piece is drawn
 * as an inline SVG silhouette — gold stroke, no fill. When real shots arrive,
 * add `photo?: string` to `Product` and render an <img> in Collection instead.
 * ───────────────────────────────────────────────────────────────────────────
 */
const drawings: Record<Silhouette, SilhouetteDrawing> = {
  bomber: {
    paths: [
      "M76 40 C85 35 115 35 124 40 L127 52 L73 52 Z",
      "M74 52 C63 56 56 64 53 76 L38 126 L34 146 L56 152 L66 120 L70 170",
      "M126 52 C137 56 144 64 147 76 L162 126 L166 146 L144 152 L134 120 L130 170",
      "M70 170 L130 170",
      "M68 170 L68 187 L132 187 L132 170",
      "M100 54 L100 170",
      "M38 138 L58 144",
      "M162 138 L142 144",
      "M78 138 L96 142",
      "M122 138 L104 142",
    ],
  },
  trench: {
    paths: [
      "M78 38 L100 58 L122 38 L127 48 L100 70 L73 48 Z",
      "M74 48 C62 52 55 62 52 74 L44 160 L62 164 L70 96 L72 205",
      "M126 48 C138 52 145 62 148 74 L156 160 L138 164 L130 96 L128 205",
      "M72 205 L128 205",
      "M71 136 L129 136",
      "M94 131 L106 131 L106 141 L94 141 Z",
      "M100 70 L100 136",
      "M100 172 L100 205",
      "M45 152 L62 156",
      "M155 152 L138 156",
    ],
    dots: [
      [90, 92],
      [90, 112],
      [110, 92],
      [110, 112],
    ],
  },
  hoodie: {
    paths: [
      "M72 46 C72 20 128 20 128 46 C128 58 116 66 100 66 C84 66 72 58 72 46 Z",
      "M81 46 C83 33 117 33 119 46",
      "M76 64 C64 68 57 78 54 90 L46 146 L66 152 L74 108 L70 180",
      "M124 64 C136 68 143 78 146 90 L154 146 L134 152 L126 108 L130 180",
      "M70 180 L130 180",
      "M68 180 L68 194 L132 194 L132 180",
      "M80 142 C88 150 112 150 120 142 L118 160 C110 166 90 166 82 160 Z",
      "M93 66 L91 98",
      "M107 66 L109 98",
      "M47 139 L66 145",
      "M153 139 L134 145",
    ],
  },
  overshirt: {
    paths: [
      "M84 42 L100 62 L116 42 L121 50 L100 72 L79 50 Z",
      "M80 52 C70 56 64 66 62 78 L56 152 L72 156 L78 104 L76 184",
      "M120 52 C130 56 136 66 138 78 L144 152 L128 156 L122 104 L124 184",
      "M76 184 L124 184",
      "M100 72 L100 184",
      "M78 106 L98 106 L98 122 L78 122 Z",
      "M102 106 L122 106 L122 122 L102 122 Z",
      "M78 112 L98 112",
      "M102 112 L122 112",
      "M57 145 L72 149",
      "M143 145 L128 149",
    ],
    dots: [
      [100, 88],
      [100, 136],
      [100, 168],
    ],
  },
  parka: {
    paths: [
      "M70 44 C70 16 130 16 130 44 C130 58 118 68 100 68 C82 68 70 58 70 44 Z",
      "M84 62 C90 67 110 67 116 62",
      "M74 66 C62 70 55 82 52 94 L46 170 L64 176 L72 118 L68 212",
      "M126 66 C138 70 145 82 148 94 L154 170 L136 176 L128 118 L132 212",
      "M68 212 L132 212",
      "M70 140 L130 140",
      "M72 158 L98 158 L98 180 L72 180 Z",
      "M102 158 L128 158 L128 180 L102 180 Z",
      "M100 68 L100 212",
      "M47 162 L64 168",
      "M153 162 L136 168",
    ],
  },
  vest: {
    paths: [
      "M78 40 C88 50 112 50 122 40",
      "M78 42 C70 48 66 70 66 96 L64 178",
      "M122 42 C130 48 134 70 134 96 L136 178",
      "M70 92 C85 98 115 98 130 92",
      "M64 178 L136 178",
      "M64 178 L64 190 L136 190 L136 178",
      "M100 50 L100 178",
      "M74 130 L94 130 L94 148 L74 148 Z",
      "M106 130 L126 130 L126 148 L106 148 Z",
    ],
  },
};

export default function GarmentArt({ silhouette, label, className }: GarmentArtProps) {
  const drawing = drawings[silhouette];
  const classNames = [styles.art, className ?? ""].filter(Boolean).join(" ");

  return (
    <svg
      className={classNames}
      viewBox="0 0 200 240"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      role="img"
      aria-label={label}
      focusable="false"
    >
      {drawing.paths.map((d) => (
        <path key={d} d={d} />
      ))}
      {drawing.dots?.map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={2.4} />
      ))}
    </svg>
  );
}
