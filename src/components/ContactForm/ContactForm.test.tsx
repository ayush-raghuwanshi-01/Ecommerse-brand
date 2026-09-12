import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { config } from "../../config";
import ContactForm from "./ContactForm";

function fillValidMessage(): void {
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Amrita Rao" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: "amrita@example.com" } });
  fireEvent.change(screen.getByLabelText(/phone/i), { target: { value: "+91 98765 00000" } });
  fireEvent.change(screen.getByLabelText("Message"), {
    target: { value: "Is the Foundry Bomber available in a 40?" },
  });
}

describe("ContactForm", () => {
  it("hands a populated mailto URL to the browser on submit", () => {
    const navigate = vi.fn();
    render(<ContactForm navigate={navigate} />);

    fillValidMessage();
    fireEvent.click(screen.getByRole("button", { name: "Send enquiry" }));

    expect(navigate).toHaveBeenCalledTimes(1);
    const url = new URL(navigate.mock.calls[0][0] as string);
    expect(url.protocol).toBe("mailto:");
    expect(url.pathname).toBe(config.contactEmail);
    expect(url.searchParams.get("subject")).toContain("Amrita Rao");
    expect(url.searchParams.get("body")).toContain("Is the Foundry Bomber available in a 40?");
  });

  it("validates instead of navigating when required fields are empty", () => {
    const navigate = vi.fn();
    render(<ContactForm navigate={navigate} />);

    fireEvent.click(screen.getByRole("button", { name: "Send enquiry" }));

    expect(navigate).not.toHaveBeenCalled();
    expect(screen.getByText("Please add your name.")).toBeTruthy();
    expect(screen.getByText("Please add an email address.")).toBeTruthy();
    expect(screen.getByText("A short message helps us reply properly.")).toBeTruthy();
  });

  it("rejects a malformed email address", () => {
    const navigate = vi.fn();
    render(<ContactForm navigate={navigate} />);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Amrita" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "amrita@" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send enquiry" }));

    expect(navigate).not.toHaveBeenCalled();
    expect(screen.getByText("That email address does not look complete.")).toBeTruthy();
  });

  it("clears a field error once the visitor types in it", () => {
    const navigate = vi.fn();
    render(<ContactForm navigate={navigate} />);

    fireEvent.click(screen.getByRole("button", { name: "Send enquiry" }));
    expect(screen.getByText("Please add your name.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Amrita" } });
    expect(screen.queryByText("Please add your name.")).toBeNull();
  });

  it("shows the handoff status, then clears it", async () => {
    render(<ContactForm navigate={vi.fn()} statusDurationMs={40} />);
    const status = screen.getByRole("status");
    expect(status.textContent).toBe("");

    fillValidMessage();
    fireEvent.click(screen.getByRole("button", { name: "Send enquiry" }));
    expect(status.textContent).toBe("Opening your email app…");

    await waitFor(() => expect(status.textContent).toBe(""));
  });

  it("can be pointed at another inbox without touching the component", () => {
    const navigate = vi.fn();
    render(<ContactForm navigate={navigate} to="studio@other.example" />);

    fillValidMessage();
    fireEvent.click(screen.getByRole("button", { name: "Send enquiry" }));

    expect(new URL(navigate.mock.calls[0][0] as string).pathname).toBe("studio@other.example");
  });
});
