import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { IconShield, Seo, Spinner } from '../components/bits';
import { useCart } from '../context/CartContext';
import { useToast } from '../context/ToastContext';
import { ApiError, api } from '../lib/api';
import { inr } from '../lib/format';
import type { Order } from '../lib/types';

interface PinResult {
  serviceable: boolean;
  shipping_charge_paise: number;
  estimated_delivery_days: string;
  reason: string | null;
}

interface GuestOrderResponse {
  order: Order;
  message: string;
  whatsapp_link: string;
}

const EMPTY_ADDR = {
  full_name: '',
  phone: '',
  email: '',
  line1: '',
  line2: '',
  landmark: '',
  city: 'Bhopal',
  state: 'Madhya Pradesh',
  postal_code: '',
};

export default function Checkout() {
  const { cart, clearCart } = useCart();
  const [addr, setAddr] = useState(EMPTY_ADDR);
  const [pin, setPin] = useState<PinResult | null>(null);
  const [placing, setPlacing] = useState(false);
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
    } else {
      setPin(null);
    }
  }, [addr.postal_code, cart?.totals.subtotal_paise]);

  if (!cart)
    return (
      <main className="page">
        <Spinner />
      </main>
    );

  if (cart.items.length === 0)
    return (
      <main className="page">
        <Seo title="Checkout — Black House" />
        <p className="empty">Your bag is empty.</p>
      </main>
    );

  const place = async () => {
    setPlacing(true);
    try {
      const payload = {
        customer_name: addr.full_name,
        customer_phone: addr.phone,
        customer_email: addr.email || undefined,
        shipping_address: {
          full_name: addr.full_name,
          phone: addr.phone,
          line1: addr.line1,
          line2: addr.line2 || undefined,
          landmark: addr.landmark || undefined,
          city: addr.city,
          state: addr.state,
          postal_code: addr.postal_code,
          country: 'IN',
        },
        items: cart.items.map((i) => ({
          variant_id: i.variant_id,
          qty: i.qty,
        })),
        customer_notes: notes || undefined,
      };

      const result = await api.post<GuestOrderResponse>('/checkout/guest', payload);
      clearCart();
      toast('Order placed successfully!', 'success');
      navigate(`/order/${result.order.number}?placed=1`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : 'Checkout failed', 'error');
    } finally {
      setPlacing(false);
    }
  };

  const shipping = pin?.serviceable ? pin.shipping_charge_paise : 0;

  return (
    <main className="page checkout">
      <Seo title="Checkout — Black House" />
      <div className="page-head" style={{ marginBottom: '1rem' }}>
        <p className="eyebrow">Secure checkout</p>
        <h1>
          Review & <em>place order</em>
        </h1>
      </div>

      {/* How we confirm — keeps the real phone-confirmation business model visible */}
      <div className="callout">
        <strong>📞 Every order is personally confirmed by a phone call before dispatch.</strong>
        <p>
          No online payment is required now. Our team will verify your address, answer any sizing questions,
          and arrange your preferred payment method (Cash on Delivery or UPI).
        </p>
      </div>

      <div className="checkout-grid">
        <form
          className="panel"
          onSubmit={(e) => {
            e.preventDefault();
            void place();
          }}
        >
          <h2>Delivery details</h2>
          <label>
            Full name *
            <input
              required
              placeholder="e.g. Rahul Sharma"
              value={addr.full_name}
              onChange={(e) => setAddr({ ...addr, full_name: e.target.value })}
            />
          </label>
          <label>
            Phone number (for call confirmation) *
            <input
              required
              pattern="[0-9]{10}"
              placeholder="10-digit mobile number"
              value={addr.phone}
              onChange={(e) => setAddr({ ...addr, phone: e.target.value.replace(/\D/g, '') })}
            />
          </label>
          <label>
            Email address (optional, for invoice copy)
            <input
              type="email"
              placeholder="name@example.com"
              value={addr.email}
              onChange={(e) => setAddr({ ...addr, email: e.target.value })}
            />
          </label>
          <label>
            Street address *
            <input
              required
              placeholder="House/Flat no., building, street"
              value={addr.line1}
              onChange={(e) => setAddr({ ...addr, line1: e.target.value })}
            />
          </label>
          <label>
            Area / Landmark (optional)
            <input
              placeholder="Near park, landmark, etc."
              value={addr.landmark}
              onChange={(e) => setAddr({ ...addr, landmark: e.target.value })}
            />
          </label>
          <div className="row-2">
            <label>
              City *
              <input
                required
                value={addr.city}
                onChange={(e) => setAddr({ ...addr, city: e.target.value })}
              />
            </label>
            <label>
              State *
              <input
                required
                value={addr.state}
                onChange={(e) => setAddr({ ...addr, state: e.target.value })}
              />
            </label>
          </div>
          <label>
            PIN code *
            <input
              required
              inputMode="numeric"
              pattern="[1-9][0-9]{5}"
              maxLength={6}
              placeholder="6-digit postal code"
              value={addr.postal_code}
              onChange={(e) => setAddr({ ...addr, postal_code: e.target.value.replace(/\D/g, '') })}
            />
          </label>

          {pin &&
            (pin.serviceable ? (
              <p className="ok">
                ✓ Serviceable · estimated delivery in {pin.estimated_delivery_days} days · shipping{' '}
                {pin.shipping_charge_paise === 0 ? 'free' : inr(pin.shipping_charge_paise)}
              </p>
            ) : (
              <p className="alert-text">✗ {pin.reason || 'This PIN code is currently unserviceable.'}</p>
            ))}

          <label style={{ marginTop: '1rem' }}>
            Special instructions / sizing notes (optional)
            <textarea
              rows={2}
              placeholder="Any fit preferences, landmark guidance or best call timing..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </label>

          <button
            className="button wide"
            style={{ marginTop: '1.25rem', minHeight: 52 }}
            disabled={placing || (pin !== null && !pin.serviceable)}
          >
            {placing ? 'Placing order…' : 'Place order (Confirm by phone)'}
          </button>
        </form>

        <aside className="panel summary">
          <h2 style={{ fontSize: 22 }}>Order summary</h2>
          {cart.items.map((i) => (
            <div className="sum-item" key={i.id}>
              {i.image_url && <img src={i.image_url} alt="" />}
              <div className="si-meta">
                <strong>{i.product_name}</strong>
                <small>
                  {i.size} × {i.qty}
                </small>
              </div>
              <span className="si-price">{inr(i.line_total_paise)}</span>
            </div>
          ))}
          <hr />
          <div className="sum-line">
            <span>Subtotal</span>
            <span>{inr(cart.totals.subtotal_paise)}</span>
          </div>
          <div className="sum-line">
            <span>Shipping</span>
            <span>{shipping === 0 ? 'Free' : inr(shipping)}</span>
          </div>
          <div className="sum-line">
            <span>GST included</span>
            <span>{inr(cart.totals.tax_paise)}</span>
          </div>
          <div className="sum-line grand">
            <span>Estimated total</span>
            <span>{inr(cart.totals.grand_total_paise + shipping)}</span>
          </div>

          <div
            style={{
              marginTop: '1.25rem',
              padding: '0.85rem 1rem',
              border: '1.5px dashed var(--accent-line)',
              background: 'var(--accent-soft)',
              borderRadius: 'var(--r-sm)',
              fontSize: '0.85rem',
              color: 'var(--text)',
              lineHeight: 1.5,
            }}
          >
            ✨ <strong>Prepaid discount available:</strong> pay via UPI when our team calls to confirm and
            receive an additional discount on your final invoice.
          </div>

          <div className="callout secure" style={{ marginTop: '1rem' }}>
            <strong>
              <IconShield size={14} /> Secure & verifiable
            </strong>
            <p>
              Prices include GST. A GST invoice is issued with every order; delivery and payment are finalized
              over the confirmation call.
            </p>
          </div>

          <div className="pay-badges" aria-label="Payment methods">
            <span className="pay-badge">UPI</span>
            <span className="pay-badge">COD</span>
            <span className="pay-badge">Razorpay</span>
            <span className="pay-badge">Cards</span>
          </div>
        </aside>
      </div>
    </main>
  );
}
