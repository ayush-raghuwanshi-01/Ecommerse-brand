import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Seo, Spinner } from '../components/bits';
import { useCart } from '../context/CartContext';
import { useToast } from '../context/ToastContext';
import { ApiError, api } from '../lib/api';
import { inr } from '../lib/format';
import type { PlaceOrderResult } from '../lib/types';

interface PinResult {
  serviceable: boolean;
  shipping_charge_paise: number;
  estimated_delivery_days: string;
  reason: string | null;
}

const EMPTY_ADDR = {
  full_name: '',
  phone: '',
  line1: '',
  line2: '',
  landmark: '',
  city: '',
  state: 'Madhya Pradesh',
  postal_code: '',
};

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

export default function Checkout() {
  const { cart, refresh } = useCart();
  const [addr, setAddr] = useState(EMPTY_ADDR);
  const [sameBilling, setSameBilling] = useState(true);
  const [method, setMethod] = useState<'razorpay' | 'cod'>('razorpay');
  const [pin, setPin] = useState<PinResult | null>(null);
  const [placing, setPlacing] = useState(false);
  const [mockSession, setMockSession] = useState<PlaceOrderResult | null>(null);
  const [notes, setNotes] = useState('');
  const navigate = useNavigate();
  const toast = useToast();

  useEffect(() => {
    if (addr.postal_code.length === 6) {
      api
        .post<PinResult>('/checkout/pincode-check', {
          postal_code: addr.postal_code,
          subtotal_paise: cart?.totals.subtotal_paise,
        })
        .then(setPin)
        .catch(() => setPin(null));
    } else setPin(null);
  }, [addr.postal_code, cart?.totals.subtotal_paise]);

  if (!cart)
    return (
      <main className="page">
        <Spinner />
      </main>
    );
  if (cart.items.length === 0 && !mockSession)
    return (
      <main className="page">
        <Seo title="Checkout — Black House" />
        <p className="empty">Your bag is empty.</p>
      </main>
    );

  const place = async () => {
    setPlacing(true);
    try {
      const created = await api.post<{ id: string }>('/addresses', {
        ...addr,
        country: 'IN',
        address_type: 'home',
        is_default_shipping: true,
        is_default_billing: sameBilling,
      });
      const result = await api.post<PlaceOrderResult>(
        '/checkout/orders',
        {
          shipping_address_id: created.id,
          billing_address_id: sameBilling ? created.id : undefined,
          payment_method: method,
          customer_notes: notes || undefined,
        },
        { 'Idempotency-Key': crypto.randomUUID() },
      );
      await refresh();
      if (!result.requires_payment) {
        navigate(`/order/${result.order.id}?placed=1`);
        return;
      }
      const session = result.payment_session!;
      if (session.mock) {
        setMockSession(result);
        return;
      }
      // Live Razorpay checkout
      await new Promise<void>((resolve, reject) => {
        const load = () => {
          if (!window.Razorpay) return reject(new Error('Razorpay SDK unavailable'));
          const rzp = new window.Razorpay({
            key: session.key_id,
            amount: session.amount_paise,
            currency: session.currency,
            name: 'Black House',
            description: `Order ${session.order_number}`,
            order_id: session.provider_order_id,
            handler: async (resp: { razorpay_payment_id: string; razorpay_signature: string }) => {
              try {
                await api.post('/payments/verify', {
                  order_id: result.order.id,
                  razorpay_payment_id: resp.razorpay_payment_id,
                  razorpay_signature: resp.razorpay_signature,
                });
                navigate(`/order/${result.order.id}?placed=1`);
                resolve();
              } catch (e) {
                reject(e as Error);
              }
            },
            modal: { ondismiss: () => reject(new Error('Payment cancelled')) },
          });
          rzp.open();
        };
        if (window.Razorpay) return load();
        const s = document.createElement('script');
        s.src = 'https://checkout.razorpay.com/v1/checkout.js';
        s.onload = load;
        s.onerror = () => reject(new Error('Razorpay SDK unavailable'));
        document.body.appendChild(s);
      });
    } catch (e) {
      toast(e instanceof ApiError ? e.message : 'Checkout failed', 'error');
    } finally {
      setPlacing(false);
    }
  };

  const mockPay = async () => {
    if (!mockSession) return;
    try {
      await api.post(`/payments/mock-capture/${mockSession.order.id}`);
      navigate(`/order/${mockSession.order.id}?placed=1`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : 'Payment failed', 'error');
    }
  };

  const shipping = pin?.serviceable ? pin.shipping_charge_paise : null;

  return (
    <main className="page checkout">
      <Seo title="Checkout — Black House" />
      <h1>
        <em>Checkout</em>
      </h1>

      {mockSession ? (
        <div className="mock-pay" role="dialog" aria-label="Test payment">
          <p className="eyebrow">Test gateway</p>
          <h2>Pay {inr(mockSession.order.grand_total_paise)}</h2>
          <p className="dim">
            Order {mockSession.order.number} · Razorpay keys are not configured, so this sandbox simulates a
            successful UPI/card capture.
          </p>
          <div className="actions">
            <button className="button" onClick={mockPay}>
              Pay now (test)
            </button>
            <button className="button ghost" onClick={() => navigate(`/order/${mockSession.order.id}`)}>
              Pay later
            </button>
          </div>
        </div>
      ) : (
        <div className="checkout-grid">
          <form
            className="panel"
            onSubmit={(e) => {
              e.preventDefault();
              void place();
            }}
          >
            <h2>Shipping address</h2>
            <label>
              Full name
              <input
                required
                value={addr.full_name}
                onChange={(e) => setAddr({ ...addr, full_name: e.target.value })}
              />
            </label>
            <label>
              Phone
              <input
                required
                pattern="[0-9]{10}"
                value={addr.phone}
                onChange={(e) => setAddr({ ...addr, phone: e.target.value })}
              />
            </label>
            <label>
              Address line 1
              <input
                required
                value={addr.line1}
                onChange={(e) => setAddr({ ...addr, line1: e.target.value })}
              />
            </label>
            <label>
              Address line 2
              <input value={addr.line2} onChange={(e) => setAddr({ ...addr, line2: e.target.value })} />
            </label>
            <label>
              Landmark
              <input value={addr.landmark} onChange={(e) => setAddr({ ...addr, landmark: e.target.value })} />
            </label>
            <div className="row-2">
              <label>
                City
                <input
                  required
                  value={addr.city}
                  onChange={(e) => setAddr({ ...addr, city: e.target.value })}
                />
              </label>
              <label>
                State
                <input
                  required
                  value={addr.state}
                  onChange={(e) => setAddr({ ...addr, state: e.target.value })}
                />
              </label>
            </div>
            <label>
              PIN code
              <input
                required
                inputMode="numeric"
                pattern="[1-9][0-9]{5}"
                maxLength={6}
                value={addr.postal_code}
                onChange={(e) => setAddr({ ...addr, postal_code: e.target.value.replace(/\D/g, '') })}
              />
            </label>
            {pin &&
              (pin.serviceable ? (
                <p className="ok">
                  ✓ Serviceable · delivery in {pin.estimated_delivery_days} days · shipping{' '}
                  {pin.shipping_charge_paise === 0 ? 'free' : inr(pin.shipping_charge_paise)}
                </p>
              ) : (
                <p className="alert-text">✗ {pin.reason}</p>
              ))}
            <label className="check">
              <input
                type="checkbox"
                checked={sameBilling}
                onChange={(e) => setSameBilling(e.target.checked)}
              />{' '}
              Billing address same as shipping
            </label>

            <h2>Payment</h2>
            <div className="pay-methods">
              <label className={`pay ${method === 'razorpay' ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="pay"
                  checked={method === 'razorpay'}
                  onChange={() => setMethod('razorpay')}
                />
                <div>
                  <strong>UPI / Card / Netbanking</strong>
                  <small>Securely via Razorpay</small>
                </div>
              </label>
              <label className={`pay ${method === 'cod' ? 'selected' : ''}`}>
                <input type="radio" name="pay" checked={method === 'cod'} onChange={() => setMethod('cod')} />
                <div>
                  <strong>Cash on Delivery</strong>
                  <small>No extra fee · pay at your door</small>
                </div>
              </label>
            </div>

            <label>
              Order notes (optional)
              <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </label>
            <button
              className="button wide"
              disabled={placing || (pin !== null && !pin.serviceable) || cart.checkout_blocked}
            >
              {placing ? 'Placing order…' : method === 'cod' ? 'Place COD order' : 'Place order & pay'}
            </button>
            {cart.checkout_blocked && (
              <ul className="block-reasons">
                {cart.block_reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
          </form>

          <aside className="panel summary">
            <h2>Order summary</h2>
            {cart.items.map((i) => (
              <div className="sum-line" key={i.id}>
                <span>
                  {i.product_name} · {i.size} × {i.qty}
                </span>
                <span>{inr(i.line_total_paise)}</span>
              </div>
            ))}
            <hr />
            <div className="sum-line">
              <span>Subtotal</span>
              <span>{inr(cart.totals.subtotal_paise)}</span>
            </div>
            {cart.totals.discount_paise > 0 && (
              <div className="sum-line">
                <span>Discount {cart.coupon_code && `(${cart.coupon_code})`}</span>
                <span>−{inr(cart.totals.discount_paise)}</span>
              </div>
            )}
            <div className="sum-line">
              <span>Shipping</span>
              <span>{shipping === null ? '—' : shipping === 0 ? 'Free' : inr(shipping)}</span>
            </div>
            <div className="sum-line">
              <span>GST included</span>
              <span>{inr(cart.totals.tax_paise)}</span>
            </div>
            <div className="sum-line grand">
              <span>To pay</span>
              <span>{inr(cart.totals.grand_total_paise + (shipping ?? 0))}</span>
            </div>
            <small>Prices include GST. A GST-compliant invoice follows delivery.</small>
          </aside>
        </div>
      )}
    </main>
  );
}
