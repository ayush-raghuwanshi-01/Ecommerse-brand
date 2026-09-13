import { useEffect, useState } from 'react';

/**
 * True once the window has scrolled past `threshold` pixels.
 *
 * Lives in its own module (not beside the components in `components/bits.tsx`)
 * so that file exports only components and keeps React Fast Refresh working.
 */
export function useScrolled(threshold = 30): boolean {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > threshold);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [threshold]);

  return scrolled;
}
