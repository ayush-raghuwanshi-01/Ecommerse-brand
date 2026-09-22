import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import ProductCard from '../components/ProductCard';
import {
  Chip,
  IconCheck,
  IconHeart,
  IconInvoice,
  IconReturn,
  IconRupee,
  IconWhatsApp,
  Reveal,
  Seo,
  Spinner,
} from '../components/bits';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';
import { useToast } from '../context/ToastContext';
import { useWishlist } from '../context/WishlistContext';
import { getWhatsAppLink } from '../config';
import { ApiError, api } from '../lib/api';
import { inr } from '../lib/format';
import { discountPct, type Page, type Product, type ProductListItem, type Variant } from '../lib/types';

const AVAIL_LABEL: Record<Variant['availability'], string> = {
  available: 'In stock',
  low_stock: 'Low stock',
  out_of_stock: 'Out of stock',
  upcoming: 'Coming soon',
  disabled: 'Unavailable',
};

export default function ProductPage() {
  const { slug } = useParams();
  const [product, setProduct] = useState<Product | null>(null);
  const [variant, setVariant] = useState<Variant | null>(null);
  const [qty, setQty] = useState(1);
  const [notFound, setNotFound] = useState(false);
  const [related, setRelated] = useState<ProductListItem[]>([]);
  const [imgIdx, setImgIdx] = useState(0);
  const { add } = useCart();
  const { user } = useAuth();
  const { has, toggle } = useWishlist();
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    setProduct(null);
    setVariant(null);
    setNotFound(false);
    setQty(1);
    setImgIdx(0);
    api
      .get<Product>(`/products/${slug}`)
      .then((p) => {
        setProduct(p);
        const first = p.variants.find((v) => v.availability === 'available') || p.variants[0];
        setVariant(first || null);
      })
      .catch(() => setNotFound(true));
    api
      .get<Page<ProductListItem>>('/products?page_size=4&sort_by=created_at&sort_dir=desc')
      .then((r) => setRelated(r.items.filter((i) => i.slug !== slug).slice(0, 3)))
      .catch(() => setRelated([]));
  }, [slug]);

  if (notFound)
    return (
      <main className="page">
        <p className="empty">
          This piece is no longer available.{' '}
          <Link to="/shop" className="textlink" style={{ whiteSpace: 'nowrap' }}>
            Back to the collection
          </Link>
        </p>
      </main>
    );
  if (!product)
    return (
      <main className="page">
        <Spinner label="Loading piece" />
      </main>
    );

  const purchasable =
    variant &&
    (variant.availability === 'available' ||
      variant.availability === 'low_stock' ||
      (variant.is_preorder && product.preorder_open));
  const notifyMode = variant && variant.availability === 'out_of_stock';
  const lowLeft =
    variant &&
    (variant.availability === 'low_stock' || variant.available_qty > 0) &&
    variant.available_qty <= 5;
  const primary = product.images[imgIdx] || product.images.find((i) => i.is_primary) || product.images[0];
  const off = discountPct(product.base_price_paise, product.mrp_paise);
  const wished = has(product.slug);

  const addToBag = async (goCheckout: boolean) => {
    if (!variant) return;
    try {
      await add(variant.id, qty, {
        product_id: product.id,
        product_name: product.name,
        variant_name: `Size ${variant.size}`,
        sku: variant.sku,
        size: variant.size,
        image_url: primary?.url || null,
        unit_price_paise: variant.price_paise,
      });
      if (goCheckout) navigate('/checkout');
      else toast(`${product.name} (${variant.size}) added to your bag.`, 'success');
    } catch (e) {
      toast(e instanceof ApiError ? e.message : 'Could not add to bag', 'error');
    }
  };

  const onWish = () => {
    toggle({
      id: product.id,
      name: product.name,
      slug: product.slug,
      short_description: product.short_description,
      status: product.status,
      product_type: product.product_type,
      base_price_paise: product.base_price_paise,
      mrp_paise: product.mrp_paise,
      is_preorder: product.is_preorder,
      preorder_open: product.preorder_open,
      primary_image_url: product.images.find((i) => i.is_primary)?.url ?? product.images[0]?.url ?? null,
      sizes_available: product.variants.map((v) => v.size),
    });
    toast(wished ? 'Removed from wishlist.' : 'Saved to your wishlist.', 'success');
  };

  const notifyMe = async () => {
    if (!variant) return;
    if (!user) {
      toast('Sign in to subscribe to restock alerts.', 'error');
      return;
    }
    try {
      await api.post('/restock-alerts', { variant_id: variant.id });
      toast(`We’ll email you when size ${variant.size} returns.`, 'success');
    } catch (e) {
      toast(e instanceof ApiError ? e.message : 'Already subscribed', 'error');
    }
  };

  return (
    <main className="page pdp">
      <Seo title={`${product.name} — Black House`} description={product.short_description || undefined} />
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/">Home</Link>
        <span className="sep">/</span>
        <Link to="/shop">Collection</Link>
        <span className="sep">/</span>
        <span className="current">{product.name}</span>
      </nav>

      <div className="pdp-grid">
        <div className="pdp-art">
          <div className="pdp-frame">
            {primary ? (
              <img src={primary.url} alt={primary.alt_text || product.name} />
            ) : (
              <span className="pc-placeholder" style={{ aspectRatio: '3/4' }}>
                Image coming soon
              </span>
            )}
            <div className="pdp-chips">
              {off > 0 && <Chip tone="gold">-{off}% off MRP</Chip>}
              {product.status === 'upcoming' && <Chip tone="gold">Coming soon</Chip>}
              {product.is_preorder && product.preorder_open && <Chip tone="gold">Pre-order open</Chip>}
              {product.status === 'out_of_stock' && <Chip tone="alert">Restocking soon</Chip>}
              {product.is_sale_item && <Chip tone="alert">Sale piece — exchange only</Chip>}
            </div>
          </div>
          {product.images.length > 1 && (
            <div className="pdp-thumbs">
              {product.images.map((img, i) => (
                <button
                  key={img.id}
                  className={i === imgIdx ? 'active' : ''}
                  onClick={() => setImgIdx(i)}
                  aria-label={`View image ${i + 1}`}
                >
                  <img src={img.url} alt="" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="pdp-info">
          <p className="eyebrow">{product.product_type || 'Outerwear'} · Numbered small batch</p>
          <div className="pdp-title-row">
            <h1>{product.name}</h1>
            <button
              className={`pdp-wish ${wished ? 'active' : ''}`}
              onClick={onWish}
              aria-label={wished ? 'Remove from wishlist' : 'Add to wishlist'}
              aria-pressed={wished}
            >
              <IconHeart size={20} filled={wished} />
            </button>
          </div>
          <p className="pdp-price">
            <strong>{inr(variant?.price_paise ?? product.base_price_paise)}</strong>
            {off > 0 && product.mrp_paise ? <s className="pdp-mrp">{inr(product.mrp_paise)}</s> : null}
            {off > 0 && <span className="pdp-off">{off}% off</span>}
            <small>incl. all taxes · GST {product.gst_percentage}%</small>
          </p>
          {lowLeft && (
            <p className="pdp-stock">
              <IconCheck size={13} />
              Only {variant?.available_qty} left in this size — order soon
            </p>
          )}
          {notifyMode && (
            <p className="pdp-stock out">Out of stock in this size — restocking in the next batch</p>
          )}
          <p className="lede">{product.short_description}</p>

          {product.is_preorder && product.preorder_fulfillment_note && (
            <p className="notice">
              ⏳ {product.preorder_fulfillment_note} Fulfilment may take longer than ready stock.
            </p>
          )}
          {product.status === 'out_of_stock' && product.restock_note && (
            <p className="notice">↻ {product.restock_note}</p>
          )}

          <fieldset className="sizes">
            <legend>
              Size
              <button
                type="button"
                className="textlink"
                style={{ border: 0 }}
                onClick={() => toast('True to size. Size up for layering.')}
              >
                Size guide
              </button>
            </legend>
            <div className="size-row">
              {product.variants.map((v) => (
                <button
                  key={v.id}
                  className={`size ${variant?.id === v.id ? 'selected' : ''} ${v.availability}`}
                  disabled={v.availability === 'disabled'}
                  onClick={() => setVariant(v)}
                  title={AVAIL_LABEL[v.availability]}
                >
                  {v.size}
                  <small>{AVAIL_LABEL[v.availability]}</small>
                </button>
              ))}
            </div>
          </fieldset>

          {purchasable ? (
            <div className="buy-row">
              <div className="stepper">
                <button onClick={() => setQty((n) => Math.max(1, n - 1))} aria-label="Decrease quantity">
                  −
                </button>
                <span>{qty}</span>
                <button onClick={() => setQty((n) => Math.min(10, n + 1))} aria-label="Increase quantity">
                  +
                </button>
              </div>
              <button className="button" onClick={() => addToBag(false)}>
                {variant?.is_preorder ? 'Pre-order now' : 'Add to bag'}
              </button>
              <button className="button ghost" onClick={() => addToBag(true)}>
                Buy now
              </button>
            </div>
          ) : notifyMode ? (
            <div className="buy-row">
              <button className="button wide" onClick={notifyMe}>
                Notify me when back in stock
              </button>
            </div>
          ) : (
            <p className="dim">This size is currently unavailable.</p>
          )}

          <div className="pdp-wa-row">
            <a
              className="button wa small"
              href={getWhatsAppLink(`Hello Black House, I am enquiring about ${product.name}.`)}
              target="_blank"
              rel="noreferrer noopener"
            >
              <IconWhatsApp size={15} />
              Enquire on WhatsApp
            </a>
          </div>

          <p className="coupon-hint">
            First order? Apply code <code>WELCOME500</code> at checkout to save ₹500 on orders above ₹10,000.
          </p>

          <div className="trust-row">
            <span className="trust-mini">
              <IconRupee size={19} />
              <span>Free shipping over ₹15,000</span>
            </span>
            <span className="trust-mini">
              <IconReturn size={19} />
              <span>7-day easy returns</span>
            </span>
            <span className="trust-mini">
              <IconInvoice size={19} />
              <span>GST invoice included</span>
            </span>
          </div>

          <div className="acc">
            <details open>
              <summary>
                The piece <span className="plus">+</span>
              </summary>
              <div className="acc-body">
                <p>{product.description || product.short_description}</p>
              </div>
            </details>
            <details>
              <summary>
                Fabric & care <span className="plus">+</span>
              </summary>
              <div className="acc-body">
                {product.fabric && <p>{product.fabric}.</p>}
                {product.care_instructions && <p>Care: {product.care_instructions}</p>}
                {!product.fabric && !product.care_instructions && <p>Details coming soon.</p>}
              </div>
            </details>
            <details>
              <summary>
                Fit & sizing <span className="plus">+</span>
              </summary>
              <div className="acc-body">
                {product.fit_info && <p>{product.fit_info}</p>}
                {product.size_guide && <p>{product.size_guide}</p>}
              </div>
            </details>
            <details>
              <summary>
                Shipping & returns <span className="plus">+</span>
              </summary>
              <div className="acc-body">
                <p>
                  Orders are confirmed by a personal phone call before dispatch, then ship within 5–8 business
                  days. Free shipping on orders above ₹15,000; easy 7-day returns. A GST invoice is included
                  with every order.
                </p>
              </div>
            </details>
          </div>
        </div>
      </div>

      {/* Sticky mobile buy bar */}
      {purchasable && (
        <div className="buybar" role="region" aria-label="Quick purchase">
          <span className="bb-price">
            <strong>{inr(variant?.price_paise ?? product.base_price_paise)}</strong>
            {off > 0 && product.mrp_paise && <s>{inr(product.mrp_paise)}</s>}
          </span>
          <button className="button small" onClick={() => addToBag(false)}>
            {variant?.is_preorder ? 'Pre-order now' : `Add to bag — ${variant?.size}`}
          </button>
        </div>
      )}

      {related.length > 0 && (
        <section className="related">
          <Reveal>
            <div className="section-head">
              <p className="eyebrow">Keep looking</p>
              <h2>
                You may also <em>like.</em>
              </h2>
            </div>
          </Reveal>
          <div className="card-grid">
            {related.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
