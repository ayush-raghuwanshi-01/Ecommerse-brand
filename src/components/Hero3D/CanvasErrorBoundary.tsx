import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

export interface CanvasErrorBoundaryProps {
  children: ReactNode;
  /** Rendered instead of the canvas when WebGL is unavailable or Three throws. */
  fallback: ReactNode;
  onError?: (error: Error) => void;
}

interface CanvasErrorBoundaryState {
  failed: boolean;
}

/**
 * WebGL is not guaranteed on every device. This keeps a failed 3D hero from
 * taking the rest of the page down with it.
 */
export class CanvasErrorBoundary extends Component<
  CanvasErrorBoundaryProps,
  CanvasErrorBoundaryState
> {
  override state: CanvasErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): CanvasErrorBoundaryState {
    return { failed: true };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surfaced rather than swallowed so a real regression is still visible.
    console.warn("[Hero3D] 3D hero disabled:", error, info.componentStack);
    this.props.onError?.(error);
  }

  override render(): ReactNode {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
