import type { Product } from "../types";

/**
 * ─────────────────────────────────────────────────────────────────────────────
 *  THE CURRENT RUN — 6 placeholder pieces.
 * ─────────────────────────────────────────────────────────────────────────────
 *  PERSONALISE ME: replace names and prices with the real line.
 *  There are no product photographs yet, so each card renders a hand-drawn
 *  inline SVG silhouette (see <GarmentArt />), clearly labelled illustrative.
 *  When real shots exist, add a `photo` field to `Product` and prefer it there.
 */
export const products: Product[] = [
  {
    id: "bh-001",
    name: "Foundry Bomber",
    price: 14800,
    tag: "New",
    silhouette: "bomber",
  },
  {
    id: "bh-002",
    name: "Longhouse Trench",
    price: 22400,
    silhouette: "trench",
  },
  {
    id: "bh-003",
    name: "Ash Hoodie, 480gsm",
    price: 7600,
    tag: "Restock",
    silhouette: "hoodie",
  },
  {
    id: "bh-004",
    name: "Second Shift Overshirt",
    price: 9200,
    silhouette: "overshirt",
  },
  {
    id: "bh-005",
    name: "Night Watch Parka",
    price: 26000,
    tag: "New",
    silhouette: "parka",
  },
  {
    id: "bh-006",
    name: "Ridgeline Vest",
    price: 8400,
    silhouette: "vest",
  },
];

/**
 * Prices are stored as major units and formatted for the locale.
 * Swap the locale/currency here if the store trades elsewhere.
 */
export function formatPrice(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}
