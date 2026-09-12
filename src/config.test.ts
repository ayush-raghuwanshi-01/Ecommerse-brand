import { describe, expect, it } from "vitest";
import {
  config,
  formatWhatsAppNumber,
  getProductEnquiryLink,
  getWhatsAppLink,
} from "./config";

describe("getWhatsAppLink", () => {
  it("points at the configured number with no digits repeated anywhere else", () => {
    const link = getWhatsAppLink("Hello");
    expect(link.startsWith(`https://wa.me/${config.whatsappNumber}?text=`)).toBe(true);
  });

  it("URL-encodes the pre-filled message", () => {
    expect(getWhatsAppLink("Hello Black House & co")).toContain(
      "text=Hello%20Black%20House%20%26%20co",
    );
  });

  it("falls back to the default message when given nothing", () => {
    const link = getWhatsAppLink();
    expect(decodeURIComponent(link.split("text=")[1])).toBe(config.defaultMessage);
  });

  it("falls back to the default message for whitespace-only input", () => {
    expect(getWhatsAppLink("   ")).toBe(getWhatsAppLink());
  });
});

describe("getProductEnquiryLink", () => {
  it("names the product in the pre-filled message", () => {
    const decoded = decodeURIComponent(getProductEnquiryLink("Foundry Bomber").split("text=")[1]);
    expect(decoded).toContain('"Foundry Bomber"');
    expect(decoded).toContain(config.brandName);
  });
});

describe("formatWhatsAppNumber", () => {
  it("renders the placeholder number readably", () => {
    expect(formatWhatsAppNumber()).toBe("+91 00000 00000");
  });
});
