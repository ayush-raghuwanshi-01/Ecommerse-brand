import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";
import { config, formatWhatsAppNumber, getProductEnquiryLink } from "./config";
import { products } from "./data/products";

// The real HeroCanvas needs a WebGL context, which jsdom does not provide.
// The lazy boundary + error boundary in Hero3D is what keeps that graceful,
// so stubbing the canvas here still exercises the real Hero3D wrapper.
vi.mock("./components/Hero3D/HeroCanvas", () => ({
  default: () => <div data-testid="hero-canvas-stub" />,
}));

describe("App", () => {
  it("renders every section the navigation targets", async () => {
    render(<App />);
    await screen.findByTestId("hero-canvas-stub");

    for (const id of ["top", "collection", "story", "contact"]) {
      expect(document.getElementById(id)).toBeTruthy();
    }
  });

  it("falls back to a static layer while the 3D chunk loads", () => {
    render(<App />);
    // Before the lazy canvas resolves, the hero still has content on screen.
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("outlive");
  });

  it("renders one collection card per product, each asking about its own piece", async () => {
    render(<App />);
    const links = await screen.findAllByRole("link", { name: /Enquire on WhatsApp/i });

    expect(links).toHaveLength(products.length);
    links.forEach((link, index) => {
      expect(link.getAttribute("href")).toBe(getProductEnquiryLink(products[index].name));
    });
  });

  it("routes every WhatsApp link through the single configured number", async () => {
    render(<App />);
    const links = Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href*="wa.me"]'));

    // Nav (desktop + mobile), hero, 6 products, WhatsApp card, footer, FAB.
    expect(links).toHaveLength(12);
    for (const link of links) {
      expect(link.getAttribute("href")).toContain(`https://wa.me/${config.whatsappNumber}`);
    }
  });

  it("opens external links without leaking window.opener", async () => {
    render(<App />);
    const links = Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href*="wa.me"]'));
    for (const link of links) {
      expect(link.getAttribute("target")).toBe("_blank");
      expect(link.getAttribute("rel")).toContain("noopener");
    }
  });

  it("points the nav and back-to-top links at real section ids", async () => {
    render(<App />);
    const anchors = Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]'));
    expect(anchors.length).toBeGreaterThan(0);
    for (const anchor of anchors) {
      const id = (anchor.getAttribute("href") ?? "").slice(1);
      expect(document.getElementById(id), `missing section for #${id}`).toBeTruthy();
    }
  });

  it("shows the studio line and hours from config on the WhatsApp card", async () => {
    render(<App />);
    expect(screen.getByText(formatWhatsAppNumber())).toBeTruthy();
    expect(screen.getByText(config.studioHours)).toBeTruthy();
    expect(screen.getByText(config.studioLocation)).toBeTruthy();
  });

  it("explains that the product art is illustrative", async () => {
    render(<App />);
    expect(screen.getAllByText("Illustrative")).toHaveLength(products.length);
  });
});
