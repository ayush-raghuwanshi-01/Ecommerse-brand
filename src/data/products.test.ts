import { describe, expect, it } from "vitest";
import { marqueeItems, navLinks } from "./navLinks";
import { formatPrice, products } from "./products";

describe("products", () => {
  it("ships six pieces for the gallery", () => {
    expect(products).toHaveLength(6);
  });

  it("gives every piece a unique id and name", () => {
    expect(new Set(products.map((p) => p.id)).size).toBe(products.length);
    expect(new Set(products.map((p) => p.name)).size).toBe(products.length);
  });

  it("formats prices without decimals", () => {
    expect(formatPrice(14800)).toBe("₹14,800");
  });
});

describe("navLinks", () => {
  it("uses in-page anchors", () => {
    for (const link of navLinks) {
      expect(link.href.startsWith("#")).toBe(true);
      expect(link.href).toBe(`#${link.id}`);
    }
  });

  it("has marquee copy to loop", () => {
    expect(marqueeItems.length).toBeGreaterThan(2);
  });
});
