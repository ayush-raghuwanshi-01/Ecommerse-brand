import type { NavLink } from "../types";

/** Primary navigation. `href` must match a rendered section id. */
export const navLinks: NavLink[] = [
  { id: "collection", label: "Collection", href: "#collection" },
  { id: "story", label: "Story", href: "#story" },
  { id: "contact", label: "Contact", href: "#contact" },
];

/** Plain-language attributes that loop in the <Marquee /> strip. */
export const marqueeItems: string[] = [
  "Heavyweight cotton",
  "Gold hardware",
  "Small batch runs",
  "Made to last",
  "Cut and sewn in small numbers",
  "Repairs kept possible",
];
