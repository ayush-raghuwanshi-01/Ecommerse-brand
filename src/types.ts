/** Shared domain types. No component prop lives here — those are colocated. */

/**
 * A single piece from the current run.
 *
 * `silhouette` selects the placeholder line-art drawn by <GarmentArt />.
 * PERSONALISE ME — when real product photography exists, add a
 * `photo?: string` field and have Collection prefer it over the SVG.
 */
export interface Product {
  id: string;
  name: string;
  /** Major units, e.g. 14800 for ₹14,800. Formatted by `formatPrice`. */
  price: number;
  /** Optional short status chip, e.g. "New" or "Restock". */
  tag?: string;
  silhouette: Silhouette;
}

export type Silhouette =
  | "bomber"
  | "trench"
  | "hoodie"
  | "overshirt"
  | "parka"
  | "vest";

/** A navigation entry that smooth-scrolls to a section id. */
export interface NavLink {
  id: string;
  label: string;
  /** In-page anchor, e.g. "#collection". */
  href: string;
}
