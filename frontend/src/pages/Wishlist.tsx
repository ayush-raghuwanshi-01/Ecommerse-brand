import { Link } from 'react-router-dom';
import ProductCard from '../components/ProductCard';
import { IconHeart, Seo } from '../components/bits';
import { useWishlist } from '../context/WishlistContext';

export default function WishlistPage() {
  const { items, remove } = useWishlist();

  return (
    <main className="page">
      <Seo
        title="Wishlist — Black House"
        description="Pieces you’ve shortlisted for later. Saved on this device."
      />
      <div className="page-head">
        <p className="eyebrow">Saved for later</p>
        <h1>
          Your <em>wishlist</em>
        </h1>
        <p className="dim">
          {items.length > 0
            ? `${items.length} piece${items.length === 1 ? '' : 's'} saved on this device.`
            : 'Tap the heart on any piece to keep it here.'}
        </p>
      </div>

      {items.length === 0 ? (
        <div className="wish-empty">
          <span className="de-icon">
            <IconHeart size={26} />
          </span>
          <p className="dim">Nothing saved yet — numbered runs don’t wait long.</p>
          <Link className="button" to="/shop">
            Shop the collection
          </Link>
        </div>
      ) : (
        <div className="card-grid">
          {items.map((p) => (
            <div className="wish-cell" key={p.slug}>
              <ProductCard product={p} />
              <button className="wish-remove" onClick={() => remove(p.slug)}>
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
