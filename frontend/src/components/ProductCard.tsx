import { Link } from 'react-router-dom';
import { useQuickView } from '../context/QuickViewContext';
import { useWishlist } from '../context/WishlistContext';
import { useToast } from '../context/ToastContext';
import { inr } from '../lib/format';
import { discountPct, type ProductListItem } from '../lib/types';
import { Chip, IconHeart } from './bits';

export default function ProductCard({ product }: { product: ProductListItem }) {
  const { open } = useQuickView();
  const { has, toggle } = useWishlist();
  const toast = useToast();

  const statusChip =
    product.status === 'upcoming' ? (
      <Chip tone="gold">Coming soon{product.preorder_open ? ' · Pre-order open' : ''}</Chip>
    ) : product.status === 'out_of_stock' ? (
      <Chip tone="alert">Sold out · restocking</Chip>
    ) : product.is_preorder ? (
      <Chip tone="gold">Pre-order</Chip>
    ) : null;

  const off = discountPct(product.base_price_paise, product.mrp_paise);
  const wished = has(product.slug);

  const onWish = () => {
    toggle(product);
    toast(wished ? 'Removed from wishlist.' : 'Saved to your wishlist.', 'success');
  };

  return (
    <article className="product-card">
      <div className="pc-artwrap">
        <Link to={`/product/${product.slug}`} className="pc-art" aria-label={product.name}>
          {product.primary_image_url ? (
            <img
              src={product.primary_image_url}
              alt={product.name}
              loading="lazy"
              className="pc-img-1"
            />
          ) : (
            <span className="pc-placeholder">Image coming soon</span>
          )}
          {product.secondary_image_url && (
            <img
              src={product.secondary_image_url}
              alt=""
              loading="lazy"
              className="pc-img-2"
              aria-hidden="true"
            />
          )}
          <span className="pc-overlay">
            <button
              type="button"
              className="pc-qv"
              onClick={(e) => {
                e.preventDefault();
                open(product.slug);
              }}
            >
              Quick view
            </button>
            <Link to={`/product/${product.slug}`} className="pc-view">
              Full details
            </Link>
          </span>
        </Link>
        {(statusChip || off > 0) && (
          <div className="pc-badges">
            {off > 0 && <span className="badge-off">-{off}%</span>}
            {statusChip}
          </div>
        )}
        <button
          className={`pc-wish ${wished ? 'active' : ''}`}
          onClick={onWish}
          aria-label={wished ? 'Remove from wishlist' : 'Add to wishlist'}
          aria-pressed={wished}
        >
          <IconHeart size={16} filled={wished} />
        </button>
      </div>

      <div className="pc-meta">
        {product.product_type && <span className="pc-type">{product.product_type}</span>}
        <h3>
          <Link to={`/product/${product.slug}`}>{product.name}</Link>
        </h3>
        <div className="pc-price-row">
          <span className="pc-price">{inr(product.base_price_paise)}</span>
          {off > 0 && product.mrp_paise ? (
            <>
              <s className="pc-mrp">{inr(product.mrp_paise)}</s>
              <span className="pc-off">{off}% off</span>
            </>
          ) : (
            <span className="pc-gst">incl. GST</span>
          )}
        </div>
        {product.sizes_available.length > 0 && (
          <small className="pc-sizes">Sizes {product.sizes_available.join(' · ')}</small>
        )}
      </div>
    </article>
  );
}
