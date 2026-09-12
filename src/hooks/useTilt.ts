import { useMemo, useRef } from "react";
import type { RefObject } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";

export interface UseTiltOptions {
  /** Maximum rotation in degrees on each axis. */
  max?: number;
  /** Slight scale-up while hovered. */
  scale?: number;
  /** Disable entirely (used for prefers-reduced-motion). */
  disabled?: boolean;
}

export interface TiltProps<T extends HTMLElement> {
  ref: RefObject<T>;
  onMouseMove: (event: ReactMouseEvent<T>) => void;
  onMouseLeave: (event: ReactMouseEvent<T>) => void;
}

/**
 * Pointer-tracked 3D tilt with no library: writes
 * `transform: perspective(...) rotateX(...) rotateY(...) scale(...)`
 * straight onto the element during mousemove and settles it on mouseleave.
 *
 * The CSS transition on the element does the smoothing.
 */
export function useTilt<T extends HTMLElement>({
  max = 7,
  scale = 1.015,
  disabled = false,
}: UseTiltOptions = {}): TiltProps<T> {
  const ref = useRef<T | null>(null);

  return useMemo(() => {
    const apply = (transform: string): void => {
      const node = ref.current;
      if (node) node.style.transform = transform;
    };

    const reset = "perspective(1100px) rotateX(0deg) rotateY(0deg) scale(1)";

    const onMouseMove = (event: ReactMouseEvent<T>): void => {
      if (disabled) return;
      const node = event.currentTarget;
      const rect = node.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      // -0.5 .. 0.5 from the element centre
      const px = (event.clientX - rect.left) / rect.width - 0.5;
      const py = (event.clientY - rect.top) / rect.height - 0.5;
      apply(
        `perspective(1100px) rotateX(${(-py * max).toFixed(2)}deg) ` +
          `rotateY(${(px * max).toFixed(2)}deg) scale(${scale})`,
      );
    };

    const onMouseLeave = (): void => {
      apply(reset);
    };

    return { ref, onMouseMove, onMouseLeave };
  }, [max, scale, disabled]);
}
