import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Chip, Seo, Spinner } from '../components/bits';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';
import { useToast } from '../context/ToastContext';
import { getWhatsAppLink } from '../config';
import { ApiError, api } from '../lib/api';
import { inr } from '../lib/format';
import type { Product, Variant } from '../lib/types';

const AVAIL_LABEL: Record<Variant['availability'], string> = {
  available: 'Available',
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
  const { add } = useCart();
  const { user } = useAuth();
  const toast = useToast();

  useEffect(() => {
    setProduct(null);
    setVariant(null);
    setNotFound(false);
    api
      .get<Product>(`/products/${slug}`)
      .then((p) => {
        setProduct(p);
        const first = p.variants.find((v) => v.availability === 'available') || p.variants[0];
        setVariant(first || null);
      })
      .catch(() => setNotFound(true));
  }, [slug]);

  if (notFound)
    return (
      <main className="page">
        <p className="empty">This piece is no longer available.</p>
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

  const addToBag = async () => {
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
      toast(`${product.name} (${variant.size}) added to your bag.`, 'success');
    } catch (e) {
      toast(e instanceof ApiError ? e.message : 'Could not add to bag', 'error');
    }
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

  const primary = product.images.find((i) => i.is_primary) || product.images[0];

  return (
    <main className="page pdp">
      <Seo title={`${product.name} — Black House`} description={product.short_description || undefined} />
      <div className="pdp-grid">
        <div className="pdp-art">
          {primary ? (
            <img src={primary.url} alt={primary.alt_text || product.name} />
          ) : (
            <span className="pc-placeholder">Image coming soon</span>
          )}
          <div className="pdp-chips">
            {product.status === 'upcoming' && <Chip tone="gold">Coming soon</Chip>}
            {product.is_preorder && product.preorder_open && <Chip tone="gold">Pre-order open</Chip>}
            {product.status === 'out_of_stock' && <Chip tone="alert">Restocking soon</Chip>}
            {product.is_sale_item && <Chip tone="alert">Sale piece — exchange only</Chip>}
          </div>
        </div>

        <div className="pdp-info">
          <p className="eyebrow">{product.product_type || 'Outerwear'} · Numbered small batch</p>
          <h1>{product.name}</h1>
          <p className="pdp-price">
            {inr(variant?.price_paise ?? product.base_price_paise)} <small>incl. GST</small>
          </p>
          <p className="lede">{product.short_description}</p>
          {product.description && <p className="dim">{product.description}</p>}

          {product.is_preorder && product.preorder_fulfillment_note && (
            <p className="notice">
              ⏳ {product.preorder_fulfillment_note} Fulfilment may take longer than ready stock.
            </p>
          )}
          {product.status === 'out_of_stock' && product.restock_note && (
            <p className="notice">↻ {product.restock_note}</p>
          )}

          <fieldset className="sizes">
            <legend>Size</legend>
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
              <button className="button" onClick={addToBag}>
                {variant?.is_preorder ? 'Pre-order now' : 'Add to bag'}
              </button>
            </div>
          ) : notifyMode ? (
            <button className="button ghost" onClick={notifyMe}>
              Notify me when back
            </button>
          ) : (
            <p className="dim">This size is currently unavailable.</p>
          )}

          <a
            className="textlink"
            href={getWhatsAppLink(`Hello Black House, I am enquiring about ${product.name}.`)}
          >
            Enquire on WhatsApp ↗
          </a>

          <dl className="spec">
            {product.fabric && (
              <>
                <dt>Fabric</dt>
                <dd>{product.fabric}</dd>
              </>
            )}
            {product.fit_info && (
              <>
                <dt>Fit</dt>
                <dd>{product.fit_info}</dd>
              </>
            )}
            {product.size_guide && (
              <>
                <dt>Size guide</dt>
                <dd>{product.size_guide}</dd>
              </>
            )}
            {product.care_instructions && (
              <>
                <dt>Care</dt>
                <dd>{product.care_instructions}</dd>
              </>
            )}
          </dl>
        </div>
      </div>
    </main>
  );
}
