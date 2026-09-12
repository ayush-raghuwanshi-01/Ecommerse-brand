import { useCallback, useEffect, useState } from "react";
import type { MouseEvent } from "react";
import { config, getWhatsAppLink } from "../../config";
import { navLinks } from "../../data/navLinks";
import { usePrefersReducedMotion } from "../../hooks/usePrefersReducedMotion";
import { useScrolled } from "../../hooks/useScrolled";
import { scrollToSection } from "../../utils/scroll";
import type { NavLink } from "../../types";
import { WhatsAppGlyph } from "../WhatsAppGlyph/WhatsAppGlyph";
import styles from "./Nav.module.css";

export interface NavProps {
  links?: NavLink[];
}

export default function Nav({ links = navLinks }: NavProps) {
  const scrolled = useScrolled(40);
  const reducedMotion = usePrefersReducedMotion();
  const [menuOpen, setMenuOpen] = useState(false);

  // Close the mobile panel when the viewport grows past the collapse point.
  useEffect(() => {
    const media = window.matchMedia("(min-width: 801px)");
    const onChange = (event: MediaQueryListEvent): void => {
      if (event.matches) setMenuOpen(false);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  // Escape closes the panel and returns focus to the trigger.
  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [menuOpen]);

  const handleNavClick = useCallback(
    (event: MouseEvent<HTMLAnchorElement>, link: NavLink): void => {
      const targetId = link.href.replace("#", "");
      const target = document.getElementById(targetId);
      if (!target) return; // let the browser do its thing
      event.preventDefault();
      setMenuOpen(false);
      scrollToSection(targetId, reducedMotion);
    },
    [reducedMotion],
  );

  const navClassNames = [styles.nav, scrolled ? styles.stuck : ""].filter(Boolean).join(" ");

  return (
    <>
      <header className={navClassNames}>
        <a
          className={styles.wordmark}
          href="#top"
          onClick={(event) => handleNavClick(event, { id: "top", label: "Top", href: "#top" })}
        >
          {config.brandName}
          <span className={styles.mark} aria-hidden="true">
            .
          </span>
        </a>

        <nav className={styles.primaryNav} aria-label="Primary">
          <ul className={styles.links}>
            {links.map((link) => (
              <li key={link.id}>
                <a className={styles.link} href={link.href} onClick={(event) => handleNavClick(event, link)}>
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <a
          className={styles.cta}
          href={getWhatsAppLink()}
          target="_blank"
          rel="noopener noreferrer"
        >
          <WhatsAppGlyph className={styles.ctaIcon} />
          Chat on WhatsApp
        </a>

        <button
          type="button"
          className={styles.toggle}
          aria-expanded={menuOpen}
          aria-controls="mobile-nav-panel"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span className={styles.toggleBars} aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
        </button>
      </header>

      <div
        id="mobile-nav-panel"
        className={[styles.panel, menuOpen ? styles.panelOpen : ""].filter(Boolean).join(" ")}
        hidden={!menuOpen}
      >
        {links.map((link) => (
          <a
            key={link.id}
            className={styles.panelLink}
            href={link.href}
            onClick={(event) => handleNavClick(event, link)}
          >
            {link.label}
          </a>
        ))}
        <a
          className={`${styles.cta} ${styles.panelCta}`}
          href={getWhatsAppLink()}
          target="_blank"
          rel="noopener noreferrer"
          tabIndex={menuOpen ? 0 : -1}
        >
          <WhatsAppGlyph className={styles.ctaIcon} />
          Chat on WhatsApp
        </a>
      </div>
    </>
  );
}
