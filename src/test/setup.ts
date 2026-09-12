/**
 * jsdom does not implement several browser APIs this app relies on.
 * These minimal stand-ins keep the component tests honest about the code paths
 * they exercise (IntersectionObserver reveals, matchMedia motion preferences,
 * anchor scrolling) without pretending to be a real browser.
 */
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

type MediaListener = (event: MediaQueryListEvent) => void;

let mediaMatches = false;

/** Test hook: flip what `matchMedia("(prefers-reduced-motion: reduce)")` returns. */
export function setReducedMotionPreference(value: boolean): void {
  mediaMatches = value;
}

const createMediaQueryList = (query: string): MediaQueryList => {
  const listeners = new Set<MediaListener>();
  const add = (listener: MediaListener | null): void => {
    if (listener) listeners.add(listener);
  };
  const remove = (listener: MediaListener | null): void => {
    if (listener) listeners.delete(listener);
  };

  return {
    get matches() {
      return query.includes("prefers-reduced-motion") ? mediaMatches : false;
    },
    media: query,
    onchange: null,
    addEventListener: (_type: string, listener: EventListenerOrEventListenerObject): void =>
      add(listener as MediaListener),
    removeEventListener: (_type: string, listener: EventListenerOrEventListenerObject): void =>
      remove(listener as MediaListener),
    addListener: (listener: MediaListener | null): void => add(listener),
    removeListener: (listener: MediaListener | null): void => remove(listener),
    dispatchEvent: (): boolean => false,
  } as unknown as MediaQueryList;
};

if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: createMediaQueryList,
  });
}

class StubIntersectionObserver implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = "";
  readonly thresholds: ReadonlyArray<number> = [0];
  private callback: IntersectionObserverCallback;

  constructor(callback: IntersectionObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element): void {
    // Treat everything as on-screen so reveal content is present.
    this.callback(
      [
        {
          isIntersecting: true,
          intersectionRatio: 1,
          target,
          time: Date.now(),
          rootBounds: null,
          boundingClientRect: target.getBoundingClientRect(),
          intersectionRect: target.getBoundingClientRect(),
        },
      ],
      this,
    );
  }

  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

if (typeof globalThis.IntersectionObserver === "undefined") {
  Object.defineProperty(globalThis, "IntersectionObserver", {
    writable: true,
    configurable: true,
    value: StubIntersectionObserver,
  });
}

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn();
}

afterEach(() => {
  cleanup();
  mediaMatches = false;
});
