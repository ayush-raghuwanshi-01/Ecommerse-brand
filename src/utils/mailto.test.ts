import { describe, expect, it } from "vitest";
import { config } from "../config";
import { buildEnquiryBody, buildEnquirySubject, composeMailto } from "./mailto";

const fields = {
  name: "  Amrita Rao ",
  email: "amrita@example.com",
  phone: "+91 98765 00000",
  message: "Is the Foundry Bomber available in a 40?",
};

describe("composeMailto", () => {
  it("targets the configured inbox", () => {
    expect(composeMailto(fields).startsWith(`mailto:${config.contactEmail}?`)).toBe(true);
  });

  it("accepts an explicit recipient", () => {
    expect(composeMailto(fields, "studio@other.example")).toContain("mailto:studio@other.example?");
  });

  it("puts the visitor's name and brand in the subject", () => {
    const url = new URL(composeMailto(fields));
    expect(url.searchParams.get("subject")).toBe(
      `Enquiry from Amrita Rao — ${config.brandName} website`,
    );
  });

  it("round-trips the fields through the encoded body", () => {
    const url = new URL(composeMailto(fields));
    const body = url.searchParams.get("body") ?? "";
    expect(body).toContain("Name: Amrita Rao");
    expect(body).toContain("Email: amrita@example.com");
    expect(body).toContain("Phone: +91 98765 00000");
    expect(body).toContain("Is the Foundry Bomber available in a 40?");
  });
});

describe("buildEnquiryBody", () => {
  it("says so when the optional phone field was skipped", () => {
    expect(buildEnquiryBody({ ...fields, phone: "  " })).toContain("Phone: not given");
  });
});

describe("buildEnquirySubject", () => {
  it("degrades gracefully with no name", () => {
    expect(buildEnquirySubject("  ")).toContain("Enquiry from the website");
  });
});
