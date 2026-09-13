import { Suspense, lazy, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import ProductCard from '../components/ProductCard';
import { Reveal, Seo } from '../components/bits';
import { getWhatsAppLink } from '../config';
import { api } from '../lib/api';
import type { Page, ProductListItem } from '../lib/types';

const Hero3D = lazy(() => import('../components/Hero3D'));

export default function Home() {
  const [products, setProducts] = useState<ProductListItem[]>([]);

  useEffect(() => {
    api
      .get<Page<ProductListItem>>('/products?page_size=4&sort_by=created_at&sort_dir=desc')
      .then((p) => setProducts(p.items))
      .catch(() => setProducts([]));
  }, []);

  return (
    <>
      <Seo
        title="Black House — Small-batch outerwear, Bhopal"
        description="Considered layers cut in small batches. Heavyweight cloth, gold hardware, made to stay."
      />
      <header id="top" className="hero">
        <img
          className="hero-image"
          src="/static/uploads/seed/campaign.jpg"
          alt="Black House campaign — model in a long black overcoat on a night street"
        />
        <Suspense fallback={null}>
          <Hero3D />
        </Suspense>
        <div className="scrim" />
        <div className="hero-copy">
          <p className="eyebrow">Independent outerwear · Bhopal, Madhya Pradesh</p>
          <h1>
            Made for the
            <br />
            <em>long way home.</em>
          </h1>
          <p className="lede">Small-batch layers for considered movement. Cut with intent, built to stay.</p>
          <div className="actions">
            <Link className="button" to="/shop">
              View the collection
            </Link>
            <a
              className="textlink"
              href={getWhatsAppLink('Hello Black House, I would like to view the collection.')}
            >
              Message us on WhatsApp ↗
            </a>
          </div>
        </div>
        <div className="hero-index">BH / 24—25</div>
      </header>

      <div className="marquee" aria-hidden="true">
        <div>
          Heavyweight cotton <i>•</i> Gold hardware <i>•</i> Small batch runs <i>•</i> Made to last <i>•</i>{' '}
          Heavyweight cotton <i>•</i> Gold hardware <i>•</i> Small batch runs <i>•</i> Made to last
        </div>
      </div>

      <section className="section">
        <Reveal className="section-head">
          <p className="eyebrow">The current line</p>
          <h2>
            Quiet forms. <em>Strong presence.</em>
          </h2>
          <p>Considered silhouettes, produced in limited runs and numbered by hand.</p>
        </Reveal>
        <div className="card-grid">
          {products.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
        <div className="center-cta">
          <Link className="button ghost" to="/shop">
            Browse all pieces
          </Link>
        </div>
      </section>

      <section className="section story">
        <Reveal className="story-copy">
          <p className="eyebrow">The house</p>
          <blockquote>“A wardrobe should become more itself with time.”</blockquote>
          <p>
            Black House began with a simple premise: the everyday layer deserves the same attention as the
            occasion piece.
          </p>
          <p>
            We work slowly, in small batches, with durable cloth and hardware that earns its patina. No noise.
            Just clothes with a point of view.
          </p>
          <Link className="textlink" to="/story">
            Read the full story →
          </Link>
        </Reveal>
        <Reveal className="story-panel">
          <div className="panel-mark">BH</div>
          <span>Material study / 2024</span>
        </Reveal>
      </section>

      <section className="section bulk-cta">
        <Reveal>
          <p className="eyebrow">Uniforms & bulk</p>
          <h2>
            Outfitting a team? <em>Let’s talk.</em>
          </h2>
          <p>
            Hotels, studios and enterprises — small-batch production runs for teams that care about what they
            wear.
          </p>
          <Link className="button" to="/bulk">
            Start a bulk enquiry
          </Link>
        </Reveal>
      </section>
    </>
  );
}
