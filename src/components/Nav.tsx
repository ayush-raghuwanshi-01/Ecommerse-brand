import { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';
import { useToast } from '../context/ToastContext';
import { useScrolled } from './bits';

export default function Nav() {
  const scrolled = useScrolled();
  const { count, setOpen } = useCart();
  const { user, logout } = useAuth();
  const [menu, setMenu] = useState(false);
  const navigate = useNavigate();
  const toast = useToast();

  return (
    <nav className={scrolled || menu ? 'scrolled' : ''}>
      <Link className="wordmark" to="/">
        BLACK&nbsp;HOUSE
      </Link>
      <div className="navlinks">
        <NavLink to="/shop">Collection</NavLink>
        <NavLink to="/story">Story</NavLink>
        <NavLink to="/bulk">Bulk Orders</NavLink>
        {user && ['staff', 'manager', 'admin'].includes(user.role) && (
          <NavLink to="/admin">Console</NavLink>
        )}
      </div>
      <div className="nav-actions">
        <button className="icon-btn" aria-label="Open cart" onClick={() => setOpen(true)}>
          Bag{count > 0 && <span className="count">{count}</span>}
        </button>
        {user ? (
          <div className="menu-wrap">
            <button className="icon-btn" onClick={() => setMenu((m) => !m)} aria-haspopup="menu">
              {user.full_name.split(' ')[0]}
            </button>
            {menu && (
              <div className="menu" role="menu" onMouseLeave={() => setMenu(false)}>
                <Link to="/orders" onClick={() => setMenu(false)}>My orders</Link>
                <Link to="/account" onClick={() => setMenu(false)}>Addresses</Link>
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
          <Link className="icon-btn" to="/login">Sign in</Link>
        )}
      </div>
    </nav>
  );
}
