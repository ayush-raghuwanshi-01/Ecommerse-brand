import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Seo, Spinner } from '../components/bits';
import { useToast } from '../context/ToastContext';
import { ApiError, api } from '../lib/api';
import { dateFmt, inr, statusLabel } from '../lib/format';
import type { Order, Page } from '../lib/types';

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  useEffect(() => {
    api
      .get<Page<Order>>('/orders/me?page_size=50')
      .then((p) => setOrders(p.items))
      .catch(() => setOrders([]));
  }, []);

  return (
    <main className="page">
      <Seo title="My orders — Black House" />
      <h1>
        Your <em>orders</em>
      </h1>
      {!orders ? (
        <Spinner />
      ) : orders.length === 0 ? (
        <p className="empty">
          No orders yet. <Link to="/shop">Browse the collection →</Link>
        </p>
      ) : (
        <div className="order-list">
          {orders.map((o) => (
            <Link className="order-row" key={o.id} to={`/order/${o.id}`}>
              <div>
                <strong>{o.number}</strong>
                <small>
                  {dateFmt(o.created_at)} · {o.items.length} piece(s)
                </small>
              </div>
              <span className={`status ${o.status}`}>{statusLabel(o.status)}</span>
              <strong>{inr(o.grand_total_paise)}</strong>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}

const CANCEL_REASONS = [
  'ordered_by_mistake',
  'changed_mind',
  'payment_issue',
  'delivery_delay',
  'customer_request',
  'other',
];

export function OrderDetailPage() {
  const { id } = useParams();
  const [order, setOrder] = useState<Order | null>(null);
  const [tracking, setTracking] = useState<Record<string, unknown> | null>(null);
  const [reason, setReason] = useState(CANCEL_REASONS[0]);
  const [params] = useSearchParams();
  const toast = useToast();

  const load = () =>
    api
      .get<Order>(`/orders/me/${id}`)
      .then(setOrder)
      .catch(() => setOrder(null));
  useEffect(() => {
    void load();
    api
      .get<Record<string, unknown>>(`/shipments/order/${id}/tracking`)
      .then(setTracking)
      .catch(() => null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!order)
    return (
      <main className="page">
        <Spinner />
      </main>
    );

  const cancellable = ['pending_payment', 'confirmed', 'processing'].includes(order.status);

  return (
    <main className="page order-detail">
      <Seo title={`Order ${order.number} — Black House`} />
      {params.get('placed') && (
        <p className="ok banner">✓ Order {order.number} placed. We’ve emailed you the confirmation.</p>
      )}
      <div className="od-head">
        <div>
          <p className="eyebrow">Order</p>
          <h1>{order.number}</h1>
          <small>
            {dateFmt(order.created_at)} · {order.order_source} · {order.payment_method.toUpperCase()}
          </small>
        </div>
        <div className="od-status">
          <span className={`status ${order.status}`}>{statusLabel(order.status)}</span>
          <span className="chip dim">Payment: {statusLabel(order.payment_status)}</span>
        </div>
      </div>

      <div className="checkout-grid">
        <div className="panel">
          <h2>Pieces</h2>
          {order.items.map((i) => (
            <div className="sum-line" key={i.id}>
              <span>
                {i.product_name} · {i.variant_name} × {i.qty}
                {i.is_preorder && <small className="chip gold"> pre-order</small>}
                {i.estimated_fulfillment_note && (
                  <small className="dim"> — {i.estimated_fulfillment_note}</small>
                )}
              </span>
              <span>{inr(i.total_paise)}</span>
            </div>
          ))}
          <hr />
          <div className="sum-line">
            <span>Subtotal</span>
            <span>{inr(order.subtotal_paise)}</span>
          </div>
          {order.discount_paise > 0 && (
            <div className="sum-line">
              <span>Discount</span>
              <span>−{inr(order.discount_paise)}</span>
            </div>
          )}
          <div className="sum-line">
            <span>Shipping</span>
            <span>{order.shipping_paise === 0 ? 'Free' : inr(order.shipping_paise)}</span>
          </div>
          <div className="sum-line">
            <span>GST included</span>
            <span>{inr(order.tax_paise)}</span>
          </div>
          <div className="sum-line grand">
            <span>Total</span>
            <span>{inr(order.grand_total_paise)}</span>
          </div>

          {cancellable && (
            <div className="cancel-box">
              <label>
                Need to cancel?
                <select value={reason} onChange={(e) => setReason(e.target.value)}>
                  {CANCEL_REASONS.map((r) => (
                    <option key={r} value={r}>
                      {statusLabel(r)}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="button ghost"
                onClick={async () => {
                  try {
                    await api.post(`/orders/me/${order.id}/cancel-request`, { reason });
                    toast('Cancellation requested — our team will review.', 'success');
                    void load();
                  } catch (e) {
                    toast(e instanceof ApiError ? e.message : 'Could not request cancellation', 'error');
                  }
                }}
              >
                Request cancellation
              </button>
            </div>
          )}
        </div>

        <aside className="panel">
          <h2>Delivery</h2>
          <address className="dim">
            {order.shipping_address.full_name}
            <br />
            {order.shipping_address.line1}
            {order.shipping_address.line2 ? `, ${order.shipping_address.line2}` : ''}
            <br />
            {order.shipping_address.city}, {order.shipping_address.state} {order.shipping_address.postal_code}
          </address>
          {tracking && (
            <p className="ok">
              📦 {statusLabel(String(tracking.status))}
              {tracking.tracking_number ? ` · ${tracking.tracking_number}` : ''}
              <br />
              <small className="dim">Estimated delivery 5–8 days from dispatch</small>
            </p>
          )}
          <h2>Timeline</h2>
          <ol className="timeline">
            {order.history.map((h, idx) => (
              <li key={idx}>
                <strong>{statusLabel(h.to_status)}</strong>
                <small>
                  {dateFmt(h.created_at)}
                  {h.note ? ` · ${h.note}` : ''}
                </small>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </main>
  );
}
