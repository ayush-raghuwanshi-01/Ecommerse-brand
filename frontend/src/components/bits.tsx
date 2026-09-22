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

export function Chip({
  tone = 'gold',
  children,
}: {
  tone?: 'gold' | 'dim' | 'alert' | 'ok';
  children: ReactNode;
}) {
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

/* ── inline icon set (stroke-based, inherits currentColor) ─────────────── */
type IconProps = { size?: number; className?: string };

function Svg({ size = 18, className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const IconBag = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 7h12l1 13H5L6 7z" />
    <path d="M9 7a3 3 0 0 1 6 0" />
  </Svg>
);

export const IconSearch = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </Svg>
);

export const IconUser = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c1.5-4 5-6 8-6s6.5 2 8 6" />
  </Svg>
);

export const IconMenu = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </Svg>
);

export const IconX = (p: IconProps) => (
  <Svg {...p}>
    <path d="m6 6 12 12M18 6 6 18" />
  </Svg>
);

export const IconStar = ({ size = 14, className }: IconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
    aria-hidden="true"
  >
    <path d="M12 2.5l2.95 6.1 6.7.92-4.88 4.68 1.18 6.65L12 17.7l-5.95 3.15 1.18-6.65L2.35 9.52l6.7-.92L12 2.5z" />
  </svg>
);

export const IconTruck = (p: IconProps) => (
  <Svg {...p}>
    <path d="M1.5 6h13v10h-13z" />
    <path d="M14.5 9h4l3 3.5V16h-7" />
    <circle cx="6" cy="18" r="2" />
    <circle cx="17.5" cy="18" r="2" />
  </Svg>
);

export const IconReturn = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 8h13a5 5 0 0 1 0 10H8" />
    <path d="m7 4-4 4 4 4" />
  </Svg>
);

export const IconRupee = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 3h12M6 8h12M14 3c-3 0-5 1.5-5 4s2 4 5 4l-7 10" />
  </Svg>
);

export const IconInvoice = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 2.5h9l4 4V21.5H6z" />
    <path d="M14.5 2.5v5h4.5" />
    <path d="M9 12h7M9 16h5" />
  </Svg>
);

export const IconShield = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 2.5 4.5 5.5v6c0 5 3.5 8.5 7.5 10 4-1.5 7.5-5 7.5-10v-6L12 2.5z" />
    <path d="m8.8 11.8 2.2 2.2 4.2-4.5" />
  </Svg>
);

export const IconCheck = (p: IconProps) => (
  <Svg {...p}>
    <path d="m4.5 12.5 5 5 10-11" />
  </Svg>
);

export const IconArrow = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 12h16m0 0-6-6m6 6-6 6" />
  </Svg>
);

export const IconPhone = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5 3h4l1.5 5L8 10a12 12 0 0 0 6 6l2-2.5 5 1.5v4a2 2 0 0 1-2 2A17 17 0 0 1 3 5a2 2 0 0 1 2-2z" />
  </Svg>
);

export const IconMail = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="m3 7 9 6 9-6" />
  </Svg>
);

export const IconPin = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 21.5S5 14.7 5 9.8a7 7 0 0 1 14 0c0 4.9-7 11.7-7 11.7z" />
    <circle cx="12" cy="9.8" r="2.6" />
  </Svg>
);

export const IconHeart = ({ size = 18, className, filled = false }: IconProps & { filled?: boolean }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill={filled ? 'currentColor' : 'none'}
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
  >
    <path d="M12 20.5S3.5 15 3.5 8.9C3.5 6 5.7 4 8.2 4c1.7 0 3 .8 3.8 2.1C12.8 4.8 14.1 4 15.8 4c2.5 0 4.7 2 4.7 4.9 0 6.1-8.5 11.6-8.5 11.6z" />
  </svg>
);

export const IconInstagram = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="3" width="18" height="18" rx="5" />
    <circle cx="12" cy="12" r="4" />
    <circle cx="17.2" cy="6.8" r="0.9" fill="currentColor" stroke="none" />
  </Svg>
);

export const IconWhatsApp = ({ size = 18, className }: IconProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
    aria-hidden="true"
  >
    <path d="M12.04 2C6.56 2 2.1 6.45 2.1 11.93c0 1.75.46 3.45 1.34 4.95L2 22l5.25-1.38a9.96 9.96 0 0 0 4.79 1.22h.01c5.48 0 9.93-4.45 9.93-9.93A9.86 9.86 0 0 0 21.9 7.2a9.83 9.83 0 0 0-9.86-5.2zm0 18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.19 8.19 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.25-8.24a8.2 8.2 0 0 1 8.24 8.25c0 4.54-3.7 8.23-8.24 8.23zm4.52-6.16c-.25-.13-1.47-.72-1.69-.8-.23-.08-.4-.13-.56.12-.17.25-.64.8-.78.97-.15.16-.29.18-.54.06-.25-.12-1.05-.39-2-1.23-.73-.66-1.23-1.47-1.38-1.72-.14-.25-.01-.38.11-.5.11-.11.25-.29.37-.43.12-.15.16-.25.25-.41.08-.17.04-.31-.02-.43-.06-.13-.56-1.36-.77-1.86-.2-.48-.41-.42-.56-.43h-.48c-.17 0-.43.06-.66.31-.22.25-.86.85-.86 2.07 0 1.22.89 2.4 1.01 2.56.12.17 1.75 2.67 4.23 3.74.59.26 1.05.41 1.41.52.59.19 1.13.16 1.56.1.48-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.15-1.18-.06-.11-.23-.17-.48-.29z" />
  </svg>
);
