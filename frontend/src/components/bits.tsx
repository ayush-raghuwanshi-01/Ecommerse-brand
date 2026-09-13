import { useEffect, useRef, type ReactNode } from 'react';
import { inr } from '../lib/format';

/** Scroll-reveal wrapper (respects prefers-reduced-motion via CSS). */
export function Reveal({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => e.isIntersecting && el.classList.add('visible'), {
      threshold: 0.12,
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return (
    <div ref={ref} className={`reveal ${className}`}>
      {children}
    </div>
  );
}

export function Price({ paise, className = '' }: { paise: number; className?: string }) {
  return <strong className={`price ${className}`}>{inr(paise)}</strong>;
}

export function Chip({ tone = 'gold', children }: { tone?: 'gold' | 'dim' | 'alert'; children: ReactNode }) {
  return <span className={`chip ${tone}`}>{children}</span>;
}

export function Seo({ title, description }: { title: string; description?: string }) {
  useEffect(() => {
    document.title = title;
    if (description) {
      let tag = document.querySelector('meta[name="description"]');
      if (!tag) {
        tag = document.createElement('meta');
        tag.setAttribute('name', 'description');
        document.head.appendChild(tag);
      }
      tag.setAttribute('content', description);
    }
  }, [title, description]);
  return null;
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="spinner-wrap" role="status">
      <span className="spinner" />
      <small>{label}…</small>
    </div>
  );
}
