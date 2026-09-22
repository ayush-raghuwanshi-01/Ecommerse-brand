import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import ProductCard from '../components/ProductCard';
import {
  IconArrow,
  IconCheck,
  IconInstagram,
  IconInvoice,
  IconReturn,
  IconRupee,
  Reveal,
  Seo,
} from '../components/bits';
import { config, getWhatsAppLink } from '../config';
import { inr } from '../lib/format';
import { api } from '../lib/api';
import type { Page, ProductListItem } from '../lib/types';

const CATEGORIES = [
  { label: 'Overcoats', img: '/static/uploads/seed/cat-overcoats.jpg' },
  { label: 'Trenches', img: '/static/uploads/seed/cat-trenches.jpg' },
  { label: 'Field Coats', img: '/static/uploads/seed/field-coat.jpg' },
  { label: 'Bombers', img: '/static/uploads/seed/rook.jpg' },
  { label: 'The Drop', img: '/static/uploads/seed/campaign.jpg' },
  { label: 'Story', img: '/static/uploads/seed/story.jpg' },
];

const WHY = [
  '100% made in Bhopal — designed & cut in-house, never white-labelled imports',
  'numbered small-batch runs — when a run ends, it ends',
  'what you see is what arrives — photographed on, not airbrushed',
  'XS to XXL, same standards on every size',
  '7-day easy returns · COD & UPI available',
];

const REVIEWS = [
  {
    quote:
      'The overcoat has real weight without feeling heavy. It has completely replaced my office coat, and the gold hardware gets better every week.',
    name: 'Arjun',
    detail: 'The Waypoint · Bengaluru',
    initials: 'AM',
  },
  {
    quote:
      'Ordered on a Tuesday, confirmed by phone the same evening, delivered in six days. The fit is exactly as shown on the site.',
    name: 'Sneha',
    detail: 'The Longline · Pune',
    initials: 'SI',
  },
  {
    quote:
      'We outfitted our hotel staff with a bulk order. The quality surprised us at this price point — we have already planned the next run.',
    name: 'Rohit',
    detail: 'Bulk order · Mumbai',
    initials: 'RA',
  },
];

const GRAM = [
  { img: '/static/uploads/seed/waypoint.jpg', cap: 'The Waypoint, run №3' },
  { img: '/static/uploads/seed/story.jpg', cap: 'Cutting day in the atelier' },
  { img: '/static/uploads/seed/longline.jpg', cap: 'The Longline, belt detail' },
  { img: '/static/uploads/seed/transit.jpg', cap: 'The Transit, packed for B2B' },
  { img: '/static/uploads/seed/overcast.jpg', cap: 'Rain test, The Overcast' },
  { img: '/static/uploads/seed/field-coat.jpg', cap: 'Field coat twill, up close' },
];

export default function Home() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [featured, setFeatured] = useState<ProductListItem | null>(null);
  const [email, setEmail] = useState('');
  const [subscribed, setSubscribed] = useState(false);

  useEffect(() => {
    api
      .get<Page<ProductListItem>>('/products?page_size=8&sort_by=created_at&sort_dir=desc')
      .then((p) => {
        setProducts(p.items);
        const first = p.items.find((i) => i.status === 'active') || p.items[0];
        if (first) setFeatured(first);
      })
      .catch(() => setProducts([]));
  }, []);

  return (
    <>
      <Seo
        title="Black House — Small-batch outerwear, made in Bhopal"
        description="Wool overcoats, trenches, field coats and bombers in numbered runs. MRP strike prices, free shipping over ₹15,000, 7-day returns, COD & UPI."
      />

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <header id="top" className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Autumn—Winter 24/25 · Bhopal</p>
          <h1>
            Made for the
            <br />
            <em>long way home.</em>
          </h1>
          <p className="lede">
            Small-batch outerwear cut by hand in Bhopal — heavyweight wool and cotton, numbered runs,
            built to outlast seasons.
          </p>
          <div className="actions">
            <Link className="button" to="/shop">
              Shop the collection <IconArrow className="arr" size={15} />
            </Link>
            <Link className="button ghost" to="/story">
              Our story
            </Link>
          </div>
          <div className="hero-micro">
            <span className="hm-item">
              <span className="hm-stars" aria-hidden="true">
                ★★★★★
              </span>
              Loved by early customers
            </span>
            <span className="hm-item">
              <IconRupee size={16} />
              Free shipping over ₹15,000
            </span>
            <span className="hm-item">
              <IconReturn size={16} />
              7-day easy returns
            </span>
          </div>
        </div>

        <div className="hero-visual">
          <div className="hero-frame">
            <img
              src="/static/uploads/seed/campaign.jpg"
              alt="Black House campaign — model in a long charcoal overcoat"
            />
            <span className="hero-tag">AW 24/25 · Numbered run</span>
          </div>
          {featured && (
            <Link to={`/product/${featured.slug}`} className="hero-card">
              {featured.primary_image_url && <img src={featured.primary_image_url} alt="" />}
              <span>
                <span className="hc-name">{featured.name}</span>
                <span className="hc-sub">{featured.short_description}</span>
                <span className="hc-price">{inr(featured.base_price_paise)}</span>
              </span>
              <span className="hc-cta">View</span>
            </Link>
          )}
        </div>
      </header>

      {/* ── Marquee ──────────────────────────────────────────────────────── */}
      <div className="marquee" aria-hidden="true">
        <div>
          Heavyweight wool <i>•</i> Gold hardware <i>•</i> Numbered small-batch runs <i>•</i> Made in
          Bhopal <i>•</i> 7-day returns <i>•</i> Heavyweight wool <i>•</i> Gold hardware <i>•</i>{' '}
          Numbered small-batch runs <i>•</i> Made in Bhopal <i>•</i> 7-day returns <i>•</i>
        </div>
      </div>

      {/* ── Circular category quick-nav ─────────────────────────────────── */}
      <section className="cat-circles" aria-label="Shop by category">
        <div className="cat-circles-row">
          {CATEGORIES.map((c) => (
            <Link key={c.label} to={c.label === 'Story' ? '/story' : '/shop'} className="cat-circle">
              <span className="cc-img">
                <img src={c.img} alt="" loading="lazy" />
              </span>
              <span className="cc-label">{c.label}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* ── Trust bar ────────────────────────────────────────────────────── */}
      <div className="trustbar">
        <Reveal>
          <div className="trust-item">
            <span className="trust-icon">
              <IconRupee size={20} />
            </span>
            <span>
              <strong>Free shipping</strong>
              <small>On all orders above ₹15,000</small>
            </span>
          </div>
        </Reveal>
        <Reveal>
          <div className="trust-item">
            <span className="trust-icon">
              <IconReturn size={20} />
            </span>
            <span>
              <strong>7-day easy returns</strong>
              <small>No questions asked</small>
            </span>
          </div>
        </Reveal>
        <Reveal>
          <div className="trust-item">
            <span className="trust-icon">
              <IconCheck size={20} />
            </span>
            <span>
              <strong>COD & UPI accepted</strong>
              <small>Pay the way you prefer</small>
            </span>
          </div>
        </Reveal>
        <Reveal>
          <div className="trust-item">
            <span className="trust-icon">
              <IconInvoice size={20} />
            </span>
            <span>
              <strong>GST invoice</strong>
              <small>With every single order</small>
            </span>
          </div>
        </Reveal>
      </div>

      {/* ── Bestsellers ──────────────────────────────────────────────────── */}
      <section className="section tight">
        <Reveal className="section-head">
          <p className="eyebrow">The current line</p>
          <h2>
            Quiet forms. <em>Strong presence.</em>
          </h2>
          <p>Considered silhouettes, produced in limited runs and numbered by hand.</p>
        </Reveal>
        <div className="card-grid">
          {products.slice(0, 4).map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
        <div className="center-cta">
          <Link className="button ghost" to="/shop">
            Browse all pieces <IconArrow className="arr" size={15} />
          </Link>
        </div>
      </section>

      {/* ── Offer code band ─────────────────────────────────────────────── */}
      <section className="offer-band" aria-label="First order offer">
        <div className="offer-band-inner">
          <strong>₹500 off your first order</strong>
          <span>
            CODE: <code>WELCOME500</code> · also: free shipping over ₹15,000
          </span>
        </div>
      </section>

      {/* ── Full-bleed campaign band ────────────────────────────────────── */}
      <section className="band-campaign">
        <img src="/static/uploads/seed/campaign.jpg" alt="" aria-hidden="true" />
        <div className="bc-scrim" />
        <div className="bc-copy">
          <p className="eyebrow light">The AW drop</p>
          <h2>
            Numbered by hand.
            <br />
            <em>Worn for years.</em>
          </h2>
          <Link className="button amber" to="/shop">
            Shop now <IconArrow className="arr" size={15} />
          </Link>
        </div>
      </section>

      {/* ── Category tiles ───────────────────────────────────────────────── */}
      <section className="section section-soft">
        <Reveal className="section-head">
          <p className="eyebrow">Shop by category</p>
          <h2>
            Find your <em>layer.</em>
          </h2>
        </Reveal>
        <div className="cat-tiles">
          {CATEGORIES.slice(0, 4).map((c) => (
            <Link to="/shop" className="cat-tile" key={c.label}>
              <img src={c.img} alt={c.label} loading="lazy" />
              <span className="ct-label">
                <strong>{c.label}</strong>
                <span>Shop →</span>
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* ── Story band ───────────────────────────────────────────────────── */}
      <section className="section">
        <div className="story">
          <Reveal>
            <img
              className="story-img"
              src="/static/uploads/seed/story.jpg"
              alt="A tailor stitching charcoal wool in the Black House atelier"
              loading="lazy"
            />
          </Reveal>
          <Reveal className="story-copy">
            <p className="eyebrow">The house</p>
            <blockquote>“A wardrobe should become more itself with time.”</blockquote>
            <ul className="why-list">
              {WHY.map((w) => (
                <li key={w}>
                  <IconCheck size={14} />
                  {w}
                </li>
              ))}
            </ul>
            <Link className="textlink" to="/story">
              Read the full story <IconArrow size={14} />
            </Link>
          </Reveal>
        </div>
      </section>

      {/* ── Reviews ──────────────────────────────────────────────────────── */}
      <section className="section section-soft">
        <Reveal className="section-head">
          <p className="eyebrow">As worn by actual customers</p>
          <h2>
            Word of <em>mouth.</em>
          </h2>
        </Reveal>
        <div className="reviews-grid">
          {REVIEWS.map((r) => (
            <Reveal key={r.name}>
              <div className="review-card">
                <span className="review-stars" aria-label="5 out of 5 stars">
                  ★★★★★
                </span>
                <blockquote>“{r.quote}”</blockquote>
                <div className="review-who">
                  <span className="review-avatar">{r.initials}</span>
                  <span>
                    <strong>
                      {r.name} · <small>{r.detail}</small>
                    </strong>
                  </span>
                  <span className="review-verified">
                    <IconCheck size={11} /> Verified
                  </span>
                </div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── On the gram ──────────────────────────────────────────────────── */}
      <section className="section">
        <Reveal className="section-head">
          <p className="eyebrow">On the gram</p>
          <h2>
            <em>@{config.instagramHandle}</em>
          </h2>
          <p>From the cutting table to your feed — follow the house for drop alerts.</p>
        </Reveal>
        <div className="ig-grid">
          {GRAM.map((g) => (
            <a
              key={g.cap}
              className="ig-tile"
              href={`https://instagram.com/${config.instagramHandle}`}
              target="_blank"
              rel="noreferrer noopener"
              aria-label={g.cap}
            >
              <img src={g.img} alt="" loading="lazy" />
              <span className="ig-hover">
                <IconInstagram size={20} />
              </span>
            </a>
          ))}
        </div>
      </section>

      {/* ── Bulk B2B band ────────────────────────────────────────────────── */}
      <section className="band-ink">
        <Reveal>
          <p className="eyebrow">Uniforms & bulk</p>
          <h2>
            Outfitting a team? <em>Let’s talk.</em>
          </h2>
          <p>
            Hotels, studios and enterprises — small-batch production runs for teams that care about
            what they wear.
          </p>
          <div className="actions" style={{ justifyContent: 'center' }}>
            <Link className="button amber" to="/bulk">
              Start a bulk enquiry <IconArrow className="arr" size={15} />
            </Link>
            <a
              className="textlink"
              style={{ color: '#d8cdb8' }}
              href={getWhatsAppLink('Hello Black House, I would like a bulk order quotation.')}
            >
              WhatsApp us directly ↗
            </a>
          </div>
        </Reveal>
      </section>

      {/* ── Newsletter ───────────────────────────────────────────────────── */}
      <section className="section">
        <Reveal className="newsletter">
          <p className="eyebrow">The house list</p>
          <h2>
            First to know, <em>first to have.</em>
          </h2>
          <p>Numbered runs sell out. Join the list for early access and members-only pricing.</p>
          {subscribed ? (
            <p className="ok">
              ✓ You’re on the list — we’ll be in touch when the next run opens.
            </p>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (email.trim()) setSubscribed(true);
              }}
            >
              <input
                type="email"
                required
                placeholder="Your email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                aria-label="Email address"
              />
              <button className="button" type="submit">
                Join
              </button>
            </form>
          )}
          <small>No spam — one or two emails a season, unsubscribe anytime.</small>
        </Reveal>
      </section>
    </>
  );
}
