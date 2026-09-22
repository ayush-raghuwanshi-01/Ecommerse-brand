import { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';
import { useToast } from '../context/ToastContext';
import { useWishlist } from '../context/WishlistContext';
import { useScrolled } from '../hooks/useScrolled';
import { IconBag, IconHeart, IconMenu, IconSearch, IconUser, IconX } from './bits';

export default function Nav() {
  const scrolled = useScrolled();
  const { count, setOpen } = useCart();
  const wishCount = useWishlist().count;
  const { user, logout } = useAuth();
  const [menu, setMenu] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [search, setSearch] = useState(false);
  const [q, setQ] = useState('');
  const navigate = useNavigate();
  const toast = useToast();

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const term = q.trim();
    setSearch(false);
    setQ('');
    navigate(term ? `/shop?q=${encodeURIComponent(term)}` : '/shop');
  };

  const links = (
    <>
      <NavLink to="/shop" end>
        Collection
      </NavLink>
      <NavLink to="/story">Story</NavLink>
      <NavLink to="/bulk">Bulk Orders</NavLink>
      <NavLink to="/contact">Contact</NavLink>
    </>
  );

  return (
    <nav className={scrolled || mobile ? 'scrolled' : ''}>
      <Link className="wordmark" to="/">
        BLACK&nbsp;HOUSE
      </Link>

      <div className="navlinks">{links}</div>

      <div className="nav-actions">
        <form className={search ? 'nav-search open' : 'nav-search'} onSubmit={submitSearch}>
          <input
            placeholder="Search coats, jackets…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search products"
          />
          <button
            type="submit"
            aria-label="Search"
            style={{
              background: 'none',
              border: 0,
              cursor: 'pointer',
              color: 'inherit',
              display: 'flex',
              padding: 0,
            }}
          >
            <IconSearch size={16} />
          </button>
        </form>
        <button
          className="icon-btn"
          aria-label="Search"
          aria-expanded={search}
          onClick={() => setSearch((s) => !s)}
          style={{ padding: '9px 11px' }}
        >
          <IconSearch size={15} />
        </button>

        {user ? (
          <div className="menu-wrap">
            <button className="icon-btn" onClick={() => setMenu((m) => !m)} aria-haspopup="menu">
              <IconUser size={15} />
              {user.full_name.split(' ')[0]}
            </button>
            {menu && (
              <div className="menu" role="menu" onMouseLeave={() => setMenu(false)}>
                <Link to="/orders" onClick={() => setMenu(false)}>
                  My orders
                </Link>
                <Link to="/account" onClick={() => setMenu(false)}>
                  Addresses
                </Link>
                {['staff', 'manager', 'admin'].includes(user.role) && (
                  <Link to="/admin" onClick={() => setMenu(false)}>
                    Staff console
                  </Link>
                )}
                <hr />
                <button
                  onClick={async () => {
                    setMenu(false);
                    await logout();
                    toast('Signed out.');
                    navigate('/');
                  }}
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link className="icon-btn" to="/login">
            <IconUser size={15} />
            Sign in
          </Link>
        )}

        <Link className="icon-btn wish-btn" to="/wishlist" aria-label="Wishlist">
          <IconHeart size={15} />
          {wishCount > 0 && <span className="count">{wishCount}</span>}
        </Link>
        <button className="icon-btn bag-btn" aria-label="Open cart" onClick={() => setOpen(true)}>
          <IconBag size={15} />
          Bag
          {count > 0 && <span className="count">{count}</span>}
        </button>

        <button
          className="hamburger"
          aria-label={mobile ? 'Close menu' : 'Open menu'}
          aria-expanded={mobile}
          onClick={() => setMobile((m) => !m)}
        >
          {mobile ? <IconX size={16} /> : <IconMenu size={16} />}
        </button>
      </div>

      <div className={mobile ? 'mobile-menu open' : 'mobile-menu'}>
        {links}
        <div className="mm-actions">
          <Link className="button small" to="/shop" onClick={() => setMobile(false)}>
            Shop the collection
          </Link>
          {!user && (
            <Link className="button ghost small" to="/login" onClick={() => setMobile(false)}>
              Sign in
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
