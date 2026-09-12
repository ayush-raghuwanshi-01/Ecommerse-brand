import { describe, expect, it } from "vitest";
import { fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { setReducedMotionPreference } from "../test/setup";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";
import { useScrolled } from "./useScrolled";
import { useTilt } from "./useTilt";

function setScrollY(value: number): void {
  Object.defineProperty(window, "scrollY", { value, configurable: true, writable: true });
}

function stubRect(element: HTMLElement, width = 200, height = 240): void {
  Object.defineProperty(element, "getBoundingClientRect", {
    configurable: true,
    value: () => ({
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: width,
      bottom: height,
      width,
      height,
      toJSON: () => ({}),
    }),
  });
}

function Tilted({ disabled = false }: { disabled?: boolean }) {
  const tilt = useTilt<HTMLDivElement>({ max: 10, disabled });
  return (
    <div
      ref={tilt.ref}
      data-testid="tilt"
      onMouseMove={tilt.onMouseMove}
      onMouseLeave={tilt.onMouseLeave}
    />
  );
}

describe("useScrolled", () => {
  it("is false above the threshold and true past it", async () => {
    setScrollY(0);
    const { result } = renderHook(() => useScrolled(40));
    expect(result.current).toBe(false);

    setScrollY(120);
    window.dispatchEvent(new Event("scroll"));
    // The hook defers to requestAnimationFrame, so wait for the frame to land.
    await waitFor(() => expect(result.current).toBe(true));

    setScrollY(10);
    window.dispatchEvent(new Event("scroll"));
    await waitFor(() => expect(result.current).toBe(false));
  });
});

describe("usePrefersReducedMotion", () => {
  it("reports the OS motion preference", () => {
    setReducedMotionPreference(true);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(true);
  });

  it("defaults to false when the visitor has no preference set", () => {
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);
  });
});

describe("useTilt", () => {
  it("writes a perspective transform that follows the pointer", () => {
    render(<Tilted />);
    const element = screen.getByTestId("tilt");
    stubRect(element);

    fireEvent.mouseMove(element, { clientX: 150, clientY: 60 });
    expect(element.style.transform).toContain("perspective(1100px)");
    // 200x240 box: x=150 is a quarter right of centre, y=60 a quarter above it.
    // max=10 => rotateY +2.50deg; the X axis is inverted, so rotateX is +2.50deg.
    expect(element.style.transform).toMatch(/rotateX\(2\.50deg\)/);
    expect(element.style.transform).toMatch(/rotateY\(2\.50deg\)/);
  });

  it("settles back to neutral on mouseleave", () => {
    render(<Tilted />);
    const element = screen.getByTestId("tilt");
    stubRect(element);

    fireEvent.mouseMove(element, { clientX: 180, clientY: 20 });
    fireEvent.mouseLeave(element);
    expect(element.style.transform).toBe("perspective(1100px) rotateX(0deg) rotateY(0deg) scale(1)");
  });

  it("does nothing when disabled", () => {
    render(<Tilted disabled />);
    const element = screen.getByTestId("tilt");
    stubRect(element);

    fireEvent.mouseMove(element, { clientX: 180, clientY: 20 });
    expect(element.style.transform).toBe("");
  });
});
