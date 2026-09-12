import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { CanvasErrorBoundary } from "./CanvasErrorBoundary";
import Hero3D from "./Hero3D";

// jsdom has no WebGL context, so the real canvas cannot initialise here.
vi.mock("./HeroCanvas", () => import("./Hero3D.stub"));

function Thrower(): null {
  throw new Error("WebGL context unavailable");
}

describe("CanvasErrorBoundary", () => {
  it("swaps in the fallback when the 3D layer throws, and reports it", () => {
    const onError = vi.fn();
    // React logs caught render errors; silence it so the test output stays clean.
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);

    render(
      <CanvasErrorBoundary fallback={<div data-testid="fallback" />} onError={onError}>
        <Thrower />
      </CanvasErrorBoundary>,
    );

    expect(screen.getByTestId("fallback")).toBeTruthy();
    expect(onError).toHaveBeenCalledTimes(1);
    expect((onError.mock.calls[0][0] as Error).message).toBe("WebGL context unavailable");

    errorSpy.mockRestore();
    warnSpy.mockRestore();
  });

  it("renders its children when nothing throws", () => {
    render(
      <CanvasErrorBoundary fallback={<div data-testid="fallback" />}>
        <div data-testid="child" />
      </CanvasErrorBoundary>,
    );

    expect(screen.getByTestId("child")).toBeTruthy();
    expect(screen.queryByTestId("fallback")).toBeNull();
  });
});

describe("Hero3D", () => {
  it("always paints the static gradient layer, with or without a working canvas", async () => {
    const { container } = render(<Hero3D />);

    // Outer layer + static fallback are synchronous, so they exist immediately.
    const layer = container.firstElementChild as HTMLElement;
    expect(layer.children.length).toBeGreaterThanOrEqual(1);

    // The lazy canvas either resolves or is replaced by the boundary fallback.
    await screen.findByTestId("hero-canvas-stub");
  });
});
