import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useToast } from '../context/ToastContext';
import { FREE_SHIPPING_THRESHOLD_PAISE } from '../theme';
import { IconBag, IconCheck } from './bits';
import { ApiError } from '../lib/api';
import { inr } from '../lib/format';

export default function CartDrawer() {
  const { cart, open, setOpen, setQty, remove, applyCoupon, removeCoupon } = useCart();
  const [code, setCode] = useState('');
  const navigate = useNavigate();
  const toast = useToast();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    addEventListener('keydown', onKey);
    return () => removeEventListener('keydown', onKey);
  }, [setOpen]);

  if (!open) return null;

  const subtotal = cart?.totals.subtotal_paise ?? 0;
  const missingForFree = Math.max(0, FREE_SHIPPING_THRESHOLD_PAISE - subtotal);
  const progress = Math.min(100, Math.round((subtotal / FREE_SHIPPING_THRESHOLD_PAISE) * 100));

  return (
    <div className="drawer-scrim" onClick={() => setOpen(false)}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Shopping bag">
        <header>
          <h3>
            Your bag{' '}
            {cart && cart.items.length > 0 && (
              <small style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 14, color: '#6f6858' }}>
                · {cart.items.reduce((n, i) => n + i.qty, 0)}
              </small>
            )}
          </h3>
          <button className="icon-btn" onClick={() => setOpen(false)} aria-label="Close cart">
            ✕
          </button>
        </header>

        {!cart || cart.items.length === 0 ? (
          <div className="drawer-empty">
            <span className="de-icon">
              <IconBag size={26} />
            </span>
            <p>Your bag is empty — the collection awaits.</p>
            <Link
              className="button"
              to="/shop"
              onClick={() => setOpen(false)}
            >
              Shop the collection
            </Link>
          </div>
        ) : (
          <>
            {missingForFree > 0 ? (
              <div className="ship-progress">
                <span>
                  Add <strong>{inr(missingForFree)}</strong> more to unlock <strong>free shipping</strong>
                </span>
                <div className="sp-track" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
                  <div className="sp-fill" style={{ width: `${progress}%` }} />
                </div>
              </div>
            ) : (
              <div className="ship-progress done">
                <span>
                  <IconCheck size={13} /> You’ve unlocked free shipping
                </span>
                <div className="sp-track">
                  <div className="sp-fill" style={{ width: '100%' }} />
                </div>
              </div>
            )}

            <div className="drawer-items">
              {cart.items.map((item) => (
                <div className="drawer-item" key={item.id}>
                  {item.image_url && <img src={item.image_url} alt={item.product_name} loading="lazy" />}
                  <div className="di-meta">
                    <strong>{item.product_name}</strong>
                    <small>
                      {item.variant_name}
                      {item.is_preorder ? ' · Pre-order' : ''}
                    </small>
                    {item.price_changed && (
                      <small className="alert">Price updated to {inr(item.current_unit_price_paise)}</small>
                    )}
                    {!item.is_available && (
                      <small className="alert">Only {item.available_qty} left — adjust to checkout</small>
                    )}
                    <div className="di-actions">
                      <div className="stepper">
                        <button onClick={() => setQty(item.id, item.qty - 1)} aria-label="Decrease quantity">
                          −
                        </button>
                        <span>{item.qty}</span>
                        <button onClick={() => setQty(item.id, item.qty + 1)} aria-label="Increase quantity">
                          +
                        </button>
                      </div>
                      <button className="textlink" onClick={() => remove(item.id)}>
                        Remove
                      </button>
                    </div>
                  </div>
                  <strong className="di-price">{inr(item.line_total_paise)}</strong>
                </div>
              ))}
            </div>

            <div className="coupon-row">
              {cart.coupon_code ? (
                <>
                  <span className="chip gold">{cart.coupon_code} applied</span>
                  <button className="textlink" onClick={() => removeCoupon()}>
                    Remove
                  </button>
                </>
              ) : (
                <>
                  <input
                    placeholder="Coupon code (try WELCOME500)"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    aria-label="Coupon code"
                  />
                  <button
                    className="button small"
                    onClick={async () => {
                      try {
                        await applyCoupon(code);
                        toast('Coupon applied.', 'success');
                        setCode('');
                      } catch (e) {
                        toast(e instanceof ApiError ? e.message : 'Coupon invalid', 'error');
                      }
                    }}
                  >
                    Apply
                  </button>
                </>
              )}
            </div>

            {cart.checkout_blocked && (
              <ul className="block-reasons">
                {cart.block_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}

            <div className="drawer-totals">
              <div>
                <span>Subtotal</span>
                <span>{inr(cart.totals.subtotal_paise)}</span>
              </div>
              {cart.totals.discount_paise > 0 && (
                <div>
                  <span>Discount</span>
                  <span>−{inr(cart.totals.discount_paise)}</span>
                </div>
              )}
              <div>
                <span>GST included</span>
                <span>{inr(cart.totals.tax_paise)}</span>
              </div>
              <div className="grand">
                <span>Total</span>
                <span>{inr(cart.totals.grand_total_paise)}</span>
              </div>
              <small>Shipping calculated at checkout · Free over ₹15,000</small>
            </div>

            <button
              className="button wide"
              disabled={cart.checkout_blocked}
              onClick={() => {
                setOpen(false);
                navigate('/checkout');
              }}
            >
              Proceed to checkout
            </button>
            <button className="textlink drawer-continue" onClick={() => setOpen(false)}>
              or continue shopping
            </button>
          </>
        )}
      </aside>
    </div>
  );
}
