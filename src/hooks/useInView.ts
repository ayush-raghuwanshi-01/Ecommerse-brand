import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";

export interface UseInViewOptions {
  /** Fraction of the element that must be visible. */
  threshold?: number;
  rootMargin?: string;
  /** Stop observing after the first intersection. Default true. */
  once?: boolean;
}

export interface InViewResult<T extends Element> {
  ref: RefObject<T>;
  inView: boolean;
}

/**
 * IntersectionObserver hook backing the single, coordinated scroll-reveal pass.
 *
 * `once` defaults to true: elements reveal a single time on first appearance
 * and then stay put, so the page does not re-animate while scrolling.
 * Falls back to "already visible" where IntersectionObserver is unavailable.
 */
export function useInView<T extends Element>(
  options: UseInViewOptions = {},
): InViewResult<T> {
  const { threshold = 0.18, rootMargin = "0px 0px -8% 0px", once = true } = options;
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState<boolean>(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setInView(true);
            if (once) observer.unobserve(entry.target);
          } else if (!once) {
            setInView(false);
          }
        }
      },
      { threshold, rootMargin },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [threshold, rootMargin, once]);

  return { ref, inView };
}
