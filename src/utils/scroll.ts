/**
 * Shared smooth-scroll helper. Anchor hrefs still work without JS thanks to
 * `scroll-behavior: smooth` in global.css; this exists for the cases where we
 * scroll programmatically and want to honour prefers-reduced-motion.
 */
export function scrollToSection(id: string, reducedMotion = false): void {
  const target = document.getElementById(id);
  if (!target) return;
  target.scrollIntoView({
    behavior: reducedMotion ? "auto" : "smooth",
    block: "start",
  });
}
