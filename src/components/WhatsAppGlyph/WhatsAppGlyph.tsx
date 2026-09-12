export interface WhatsAppGlyphProps {
  className?: string;
  /** Decorative by default — callers label the surrounding link/button. */
  title?: string;
}

/**
 * The WhatsApp mark, inlined once so it inherits `currentColor`
 * and never needs an image request.
 */
export function WhatsAppGlyph({ className, title }: WhatsAppGlyphProps) {
  const labelled = Boolean(title);
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      role={labelled ? "img" : undefined}
      aria-hidden={labelled ? undefined : true}
      focusable="false"
    >
      {labelled ? <title>{title}</title> : null}
      <path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.86 9.86 0 0 0 4.79 1.22h.01c5.46 0 9.9-4.45 9.9-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2Zm0 1.9c2.14 0 4.15.84 5.66 2.35a7.94 7.94 0 0 1 2.34 5.66c0 4.41-3.59 8-8 8a8.03 8.03 0 0 1-4.1-1.12l-.3-.18-3.1.82.83-3.03-.19-.31a7.94 7.94 0 0 1-1.22-4.18c0-4.41 3.59-8 8-8Zm-3.3 4.02c-.17 0-.45.06-.68.32-.24.25-.9.88-.9 2.14s.92 2.48 1.05 2.65c.13.17 1.8 2.76 4.37 3.87 2.14.92 2.57.74 3.04.69.47-.05 1.5-.61 1.71-1.2.21-.6.21-1.1.15-1.21-.06-.11-.23-.17-.49-.3-.26-.13-1.5-.74-1.73-.82-.23-.09-.4-.13-.57.13-.17.25-.65.82-.8.99-.15.17-.29.19-.55.06-.26-.13-1.1-.4-2.09-1.29-.77-.69-1.29-1.53-1.44-1.79-.15-.26-.02-.4.11-.53.12-.12.26-.3.39-.44.13-.15.17-.25.26-.42.09-.17.04-.32-.02-.44-.06-.13-.56-1.35-.77-1.85-.2-.48-.4-.42-.56-.43h-.48Z" />
    </svg>
  );
}
