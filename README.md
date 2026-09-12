# Black House

A single-page brand and lead-generation site for **Black House**, a small-batch,
dark-luxury outerwear label. It is deliberately *not* a store: the goal is a
premium editorial look and two working contact paths — a WhatsApp deep link and
a contact form.

Everything is client-side. There is no backend, no API route and no build-time
data fetching.

## Quick start

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # typecheck + production build into dist/
npm run preview    # serve the production build
npm run typecheck  # tsc --noEmit
npm test           # vitest, single run
npm run test:watch
```

## Stack

- **Vite 5 + React 18 + TypeScript** (strict)
- **CSS Modules** for every component — no Tailwind, no UI kit
- **@react-three/fiber + @react-three/drei** for the 3D hero (React-idiomatic Three.js)
- **Vitest + Testing Library** for the test suite

## What to personalise

Almost everything you will want to change lives in two files.

### `src/config.ts` — business details

| Key | What it controls |
| --- | --- |
| `brandName` | Wordmark, hero, footer, `<title>`, email subjects |
| `whatsappNumber` | **Digits only, international format, no `+`.** Currently the placeholder `910000000000` |
| `contactEmail` | Inbox the contact form `mailto:`s into |
| `studioHours`, `studioLocation` | Copy on the WhatsApp card |
| `socials` | Footer social links. Entries still set to `"#"` render as plain text rather than dead links — put a real URL in and they become links automatically |
| `defaultMessage` | Pre-filled chat text when no product-specific message is supplied |

Every WhatsApp link on the page is built by `getWhatsAppLink()` (or
`getProductEnquiryLink()` for the collection cards). **Never hardcode the number
or a `wa.me` URL anywhere else** — a test in `src/App.test.tsx` asserts that all
12 WhatsApp links on the rendered page route through the configured number.

### `src/data/products.ts` — the collection

Six placeholder pieces with `id`, `name`, `price`, optional `tag` and
`silhouette`. Prices are major units and formatted by `formatPrice`.

There are **no product photographs yet**, so each card renders a hand-drawn
inline SVG silhouette (`src/components/GarmentArt/GarmentArt.tsx`), labelled
"Illustrative". When real shots exist, add `photo?: string` to the `Product`
type in `src/types.ts` and have `<Collection />` prefer it over the SVG.

### `src/theme.ts` — visual identity

One typed object holding colours, type families, radii, spacing and motion
values. `installDesignTokens()` writes them onto `<html>` as `--bh-*` custom
properties at bootstrap, so **CSS Modules and TypeScript read the same source**
(the Three.js materials in `HeroCanvas.tsx` use `colors.gold` directly). Change
a value once and it changes everywhere.

| Token | Value |
| --- | --- |
| Background | `#0b0a08` (warm near-black) |
| Alt background | `#141210` |
| Card surface | `#17140f` |
| Hairline border | `#2b2620` |
| Gold accent | `#c9a24b` (muted antique gold) |
| Bright gold | `#e8c873` |
| Text | `#ece4d3` |
| Dim text | `#9a8f7a` |

Type is **Fraunces** (headlines, sentence case) + **Manrope** (body/UI), loaded
from Google Fonts via a `<link>` in `index.html`. Swap those two families there
and in `theme.ts` if the identity changes; self-host with `@fontsource/*` if you
need to avoid the third-party request.

## File tree

```
index.html                     fonts, meta, favicon
public/favicon.svg
src/
  main.tsx                     installs design tokens, mounts <App />
  App.tsx                      section order + skip link
  config.ts                    ← brand name, WhatsApp number, email, hours
  theme.ts                     ← design tokens (single source of truth)
  types.ts                     Product, Silhouette, NavLink
  data/
    products.ts                the six pieces + formatPrice
    navLinks.ts                nav entries + marquee copy
  hooks/
    useScrolled.ts             sticky-nav threshold
    useInView.ts               IntersectionObserver, one-shot
    usePrefersReducedMotion.ts
    useTilt.ts                 pointer-tracked 3D tilt, no library
  utils/
    scroll.ts                  smooth-scroll that respects reduced motion
    mailto.ts                  builds the contact-form mailto: URL
  styles/global.css            reset, base type, focus ring, motion policy
  test/setup.ts                jsdom stand-ins for matchMedia / IntersectionObserver
  components/
    Nav/                       sticky, transparent → blurred on scroll
    Hero/                      full-viewport, scrim, two CTAs
    Hero3D/                    lazy Canvas + Suspense + error boundary
      HeroCanvas.tsx           torus knot, point lights, drei Environment/Sparkles
      CanvasErrorBoundary.tsx  keeps a WebGL failure from taking the page down
    Marquee/                   CSS-only looping attribute strip
    Collection/                horizontal scroll-snap gallery
    GarmentArt/                inline SVG garment line art
    Story/                     pull quote + copy | tilt panel
    Contact/                   two-column layout
    ContactForm/               controlled form → mailto:
    WhatsAppCard/              number, hours, chat button
    Footer/                    wordmark, socials, WhatsApp, back to top
    WhatsAppFab/               fixed button with pulsing ring
    WhatsAppGlyph/             the WhatsApp mark, inlined once
    Reveal/                    the single coordinated scroll-reveal pass
```

## Behaviour worth knowing

- **One reveal pass.** `<Reveal />` wraps section headers and panels and applies
  a single fade plus slight rise on first appearance via `useInView`. There is
  no per-element scatter animation.
- **Motion is opt-out everywhere.** Marquee, reveal, FAB pulse ring, hero
  rotation, hero parallax, `Sparkles` drift, tilt and smooth scrolling all check
  `prefers-reduced-motion`. The 3D hero also pauses when `document.visibilityState`
  is `hidden`.
- **The 3D hero cannot break the page.** `HeroCanvas` is a lazy chunk wrapped in
  `<Suspense>` and a `CanvasErrorBoundary`. If WebGL is unavailable, the static
  gold gradient in `Hero3D.module.css` stands in and the rest of the site works.
- **The contact form is honest about itself.** It composes a `mailto:` URL and
  assigns it to `window.location.href`, then shows "Opening your email app…" for
  a few seconds. The note under the form explains the mechanism. To move to a
  hosted form service or a small backend, change `composeMailto` in
  `src/utils/mailto.ts` and the `navigate` prop on `<ContactForm />` — nothing
  else needs to move.
- **Focus states** are a single 2px bright-gold outline on `:focus-visible` for
  every interactive element, defined once in `global.css`.
- **Responsive** down to 375px: the nav collapses to a menu button below 800px,
  the gallery cards narrow, the story and contact grids stack, and the hero
  CTAs go full-width.

## Tests

```
src/config.test.ts                       WhatsApp link helpers, number formatting
src/utils/mailto.test.ts                 subject/body/recipient composition
src/data/products.test.ts                product shape, price formatting, nav anchors
src/hooks/hooks.test.tsx                 useScrolled, usePrefersReducedMotion, useTilt
src/components/ContactForm/*.test.tsx    validation, mailto handoff, status message
src/components/Hero3D/*.test.tsx         error boundary + static fallback
src/App.test.tsx                         rendered page: sections, links, config wiring
```

`src/App.test.tsx` renders the whole page in jsdom (with the WebGL canvas
stubbed, since jsdom has no GL context) and asserts the real structure: six
product cards each enquiring about their own piece, twelve WhatsApp links all
using `config.whatsappNumber`, and every in-page anchor resolving to a section
that actually exists.
