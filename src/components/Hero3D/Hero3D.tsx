import { lazy, Suspense } from "react";
import { usePrefersReducedMotion } from "../../hooks/usePrefersReducedMotion";
import { CanvasErrorBoundary } from "./CanvasErrorBoundary";
import styles from "./Hero3D.module.css";

// three.js is heavy, so the scene is a separate chunk and only fetched when the
// hero actually mounts. Suspense below is the graceful fallback boundary.
const HeroCanvas = lazy(() => import("./HeroCanvas"));

export interface Hero3DProps {
  /** Optional hook for telemetry if the 3D layer has to be skipped. */
  onFallback?: (error: Error) => void;
}

/**
 * Decorative 3D layer for the hero. Purely presentational: if it cannot load,
 * the gradient in `.fallback` stands in and the rest of the page is unaffected.
 */
export default function Hero3D({ onFallback }: Hero3DProps) {
  const reducedMotion = usePrefersReducedMotion();

  return (
    <div className={styles.layer} aria-hidden="true">
      <div className={styles.fallback} />
      <CanvasErrorBoundary fallback={null} onError={onFallback}>
        <Suspense fallback={null}>
          <HeroCanvas reducedMotion={reducedMotion} />
        </Suspense>
      </CanvasErrorBoundary>
    </div>
  );
}
