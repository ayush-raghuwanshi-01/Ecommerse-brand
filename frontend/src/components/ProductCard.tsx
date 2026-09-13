import { Link } from 'react-router-dom';
import { inr } from '../lib/format';
import type { ProductListItem } from '../lib/types';
import { Chip } from './bits';

export default function ProductCard({ product }: { product: ProductListItem }) {
  const statusChip =
    product.status === 'upcoming' ? (
      <Chip tone="gold">Coming soon{product.preorder_open ? ' · Pre-order open' : ''}</Chip>
    ) : product.status === 'out_of_stock' ? (
      <Chip tone="alert">Restocking soon</Chip>
    ) : product.is_preorder ? (
      <Chip tone="gold">Pre-order</Chip>
    ) : null;

  return (
    <article className="product-card">
      <Link to={`/product/${product.slug}`} className="pc-art">
        {product.primary_image_url ? (
          <img src={product.primary_image_url} alt={product.name} loading="lazy" />
        ) : (
          <span className="pc-placeholder">Image coming soon</span>
        )}
        {statusChip && <div className="pc-chip">{statusChip}</div>}
      </Link>
      <div className="pc-meta">
        <div>
          <h3>{product.name}</h3>
          <small>{product.short_description}</small>
        </div>
        <strong>{inr(product.base_price_paise)}</strong>
      </div>
      {product.sizes_available.length > 0 && (
        <small className="pc-sizes">Sizes {product.sizes_available.join(' · ')}</small>
      )}
    </article>
  );
}
