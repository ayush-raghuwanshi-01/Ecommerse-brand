import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { Link } from 'react-router-dom';
import { IconCheck, IconWhatsApp, IconX } from '../components/bits';
import { useCart } from '../context/CartContext';
import { useWishlist } from '../context/WishlistContext';
import { useToast } from '../context/ToastContext';
import { getWhatsAppLink } from '../config';
import { ApiError, api } from '../lib/api';
import { inr } from '../lib/format';
import { discountPct, type Product, type Variant } from '../lib/types';

/**
 * Quick-view modal (the "Quick view" pattern used by Juxar & co.): a fast path
 * from the grid to "add to bag" without leaving the page. Fetches the full
 * product, lets you pick a size, and still links out to the full piece page.
 */
interface QuickViewState {
  open: (slug: string) => void;
  close: () => void;
}

const QuickViewCtx = createContext<QuickViewState>(null as unknown as QuickViewState);
export const useQuickView = () => useContext(QuickViewCtx);

export function QuickViewProvider({ children }: { children: ReactNode }) {
  const [slug, setSlug] = useState<string | null>(null);
  const [product, setProduct] = useState<Product | null>(null);
  const [variant, setVariant] = useState<Variant | null>(null);
  const [qty, setQty] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [imgIdx, setImgIdx] = useState(0);

  const { add } = useCart();
  const { has, toggle } = useWishlist();
  const toast = useToast();

  const open = useCallback((s: string) => {
    setSlug(s);
    setProduct(null);
    setVariant(null);
    setQty(1);
    setImgIdx(0);
    setError(false);
    setLoading(true);
    api
      .get<Product>(`/products/${s}`)
      .then((p) => {
        setProduct(p);
        const first = p.variants.find((v) => v.availability === 'available') || p.variants[0];
        setVariant(first || null);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  const close = useCallback(() => setSlug(null), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close();
    addEventListener('keydown', onKey);
    return () => removeEventListener('keydown', onKey);
  }, [close]);

  useEffect(() => {
    if (slug) document.body.style.overflow = 'hidden';
    else document.body.style.overflow = '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [slug]);

  const addToBag = async () => {
    if (!product || !variant) return;
    try {
      const primary = product.images.find((i) => i.is_primary) || product.images[0];
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
      close();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : 'Could not add to bag', 'error');
    }
  };

  const purchasable =
    variant &&
    (variant.availability === 'available' ||
      variant.availability === 'low_stock' ||
      (variant.is_preorder && product?.preorder_open));
  const off = product ? discountPct(product.base_price_paise, product.mrp_paise) : 0;

  if (!slug) return <>{children}</>;

  const listImg = product
    ? {
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
      }
    : null;

  return (
    <QuickViewCtx.Provider value={{ open, close }}>
      {children}
      <div className="qv-scrim" onClick={close} role="dialog" aria-modal="true" aria-label="Quick view">
        <div className="qv" onClick={(e) => e.stopPropagation()}>
          <button className="qv-close" onClick={close} aria-label="Close quick view">
            <IconX size={16} />
          </button>

          {loading ? (
            <div className="qv-loading">
              <span className="spinner" />
            </div>
          ) : error || !product ? (
            <div className="qv-loading">
              <p className="dim">This piece could not be loaded.</p>
            </div>
          ) : (
            <div className="qv-grid">
              <div className="qv-gallery">
                <img
                  src={product.images[imgIdx]?.url ?? ''}
                  alt={product.name}
                  onClick={() =>
                    setImgIdx((i) => (i + 1) % Math.max(1, product.images.length))
                  }
                />
                {product.images.length > 1 && (
                  <div className="qv-thumbs">
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

              <div className="qv-info">
                <p className="eyebrow">{product.product_type || 'Outerwear'}</p>
                <h3>{product.name}</h3>
                <p className="qv-price">
                  <strong>{inr(variant?.price_paise ?? product.base_price_paise)}</strong>
                  {off > 0 && product.mrp_paise ? (
                    <s>{inr(product.mrp_paise)}</s>
                  ) : null}
                  {off > 0 && <span className="qv-off">{off}% off</span>}
                  <small>incl. GST</small>
                </p>
                <p className="dim qv-short">{product.short_description}</p>

                <div className="size-row" role="radiogroup" aria-label="Size">
                  {product.variants.map((v) => (
                    <button
                      key={v.id}
                      role="radio"
                      aria-checked={variant?.id === v.id}
                      className={`size sm ${variant?.id === v.id ? 'selected' : ''} ${v.availability}`}
                      disabled={v.availability === 'disabled'}
                      onClick={() => setVariant(v)}
                    >
                      {v.size}
                    </button>
                  ))}
                </div>

                {purchasable ? (
                  <div className="qv-buy">
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
                ) : (
                  <p className="dim" style={{ fontSize: 13 }}>
                    Selected size unavailable right now.
                  </p>
                )}

                <div className="qv-actions">
                  <Link className="textlink" to={`/product/${product.slug}`} onClick={close}>
                    Full details →
                  </Link>
                  {listImg && (
                    <button
                      className={`textlink ${has(product.slug) ? 'active-wish' : ''}`}
                      onClick={() => {
                        toggle(listImg);
                        toast(has(product.slug) ? 'Removed from wishlist.' : 'Saved to your wishlist.', 'success');
                      }}
                    >
                      {has(product.slug) ? '♥ Saved' : '♡ Save to wishlist'}
                    </button>
                  )}
                  <a
                    className="textlink"
                    href={getWhatsAppLink(`Hello Black House, I am enquiring about ${product.name}.`)}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    <IconWhatsApp size={13} /> WhatsApp
                  </a>
                </div>

                <div className="qv-trust">
                  <span>
                    <IconCheck size={13} /> 7-day returns
                  </span>
                  <span>
                    <IconCheck size={13} /> COD & UPI
                  </span>
                  <span>
                    <IconCheck size={13} /> GST invoice
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </QuickViewCtx.Provider>
  );
}
