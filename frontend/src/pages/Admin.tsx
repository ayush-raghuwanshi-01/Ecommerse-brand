import { useCallback, useEffect, useState } from 'react';
import { Seo, Spinner } from '../components/bits';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ApiError, api } from '../lib/api';
import { dateFmt, inr, statusLabel } from '../lib/format';
import type { Order, Page, Reports } from '../lib/types';

const NEXT_STATUS: Record<string, string> = {
  confirmed: 'processing',
  processing: 'packed',
  packed: 'shipped',
  shipped: 'delivered',
  delivered: 'completed',
};

type Tab = 'orders' | 'inventory' | 'reports' | 'coupons';

export default function AdminPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>('orders');

  if (!user || !['staff', 'manager', 'admin'].includes(user.role)) {
    return (
      <main className="page">
        <Seo title="Console — Black House" />
        <p className="empty">
          Staff access only. Sign in with a staff, manager or admin account to open the console.
        </p>
      </main>
    );
  }

  return (
    <main className="page admin">
      <Seo title="Console — Black House" />
      <div className="page-head">
        <p className="eyebrow">Operations console</p>
        <h1>
          {user.full_name} <em>· {user.role}</em>
        </h1>
        <div className="tabs" role="tablist">
          {(['orders', 'inventory', 'reports', 'coupons'] as Tab[]).map((t) => (
            <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
              {statusLabel(t)}
            </button>
          ))}
        </div>
      </div>
      {tab === 'orders' && <OrdersTab />}
      {tab === 'inventory' && <InventoryTab canAdjust />}
      {tab === 'reports' && <ReportsTab />}
      {tab === 'coupons' && <CouponsTab canManage={user.role !== 'staff'} />}
    </main>
  );
}

function OrdersTab() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [status, setStatus] = useState('');
  const toast = useToast();

  const load = useCallback(() => {
    const q = status ? `?status=${status}` : '';
    api.get<Page<Order>>(`/orders${q}&page_size=50`.replace('?&', '?')).then((p) => setOrders(p.items)).catch(() => setOrders([]));
  }, [status]);
  useEffect(() => {
    load();
  }, [load]);

  const act = async (fn: () => Promise<unknown>, msg: string) => {
    try {
      await fn();
      toast(msg, 'success');
      load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : 'Action failed', 'error');
    }
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Orders</h2>
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
          <option value="">All statuses</option>
          {['pending_payment', 'confirmed', 'processing', 'packed', 'shipped', 'delivered', 'cancel_requested', 'cancelled'].map((s) => (
            <option key={s} value={s}>{statusLabel(s)}</option>
          ))}
        </select>
      </div>
      {!orders ? (
        <Spinner />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr><th>Order</th><th>Customer</th><th>Source</th><th>Payment</th><th>Status</th><th>Total</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td><strong>{o.number}</strong><br /><small>{dateFmt(o.created_at)}</small></td>
                  <td>{o.shipping_address.full_name}<br /><small>{o.shipping_address.postal_code}</small></td>
                  <td><span className="chip dim">{o.order_source}</span>{o.is_preorder && <span className="chip gold">pre</span>}</td>
                  <td><span className={`status ${o.payment_status}`}>{statusLabel(o.payment_status)}</span></td>
                  <td><span className={`status ${o.status}`}>{statusLabel(o.status)}</span></td>
                  <td>{inr(o.grand_total_paise)}</td>
                  <td className="actions-cell">
                    {NEXT_STATUS[o.status] && (
                      <button className="button tiny" onClick={() => act(() => api.post(`/orders/${o.id}/status`, { status: NEXT_STATUS[o.status] }), `Moved to ${NEXT_STATUS[o.status]}`)}>
                        → {statusLabel(NEXT_STATUS[o.status])}
                      </button>
                    )}
                    {o.status === 'cancel_requested' && (
                      <>
                        <button className="button tiny" onClick={() => act(() => api.post(`/orders/${o.id}/cancel-decision`, { approve: true }), 'Cancellation approved')}>Approve cancel</button>
                        <button className="button tiny ghost" onClick={() => act(() => api.post(`/orders/${o.id}/cancel-decision`, { approve: false }), 'Cancellation rejected')}>Reject</button>
                      </>
                    )}
                    {o.payment_status === 'pending_cod' && o.status !== 'cancelled' && (
                      <button className="button tiny ghost" onClick={() => act(() => api.post(`/orders/${o.id}/collect-cod`, { collected: true, method_note: 'cash' }), 'COD collected')}>Collect COD</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {orders.length === 0 && <p className="empty">No orders in this view.</p>}
        </div>
      )}
    </div>
  );
}

function InventoryTab({ canAdjust }: { canAdjust: boolean }) {
  const [rows, setRows] = useState<Page<unknown> | null>(null);
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [form, setForm] = useState({ variant_id: '', adjustment_type: 'increase', qty_change: '5', reason: '' });
  const toast = useToast();

  const load = () =>
    api.get<Page<Record<string, unknown>>>('/inventory/variants?page_size=100').then((p) => {
      setRows(p);
      setItems(p.items);
    });
  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Inventory (Bhopal warehouse)</h2>
        {canAdjust && (
          <form
            className="adj-form"
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api.post('/inventory/adjustments', {
                  variant_id: form.variant_id,
                  adjustment_type: form.adjustment_type,
                  qty_change:
                    ['decrease', 'damage', 'defect'].includes(form.adjustment_type)
                      ? -Math.abs(Number(form.qty_change))
                      : Math.abs(Number(form.qty_change)),
                  reason: form.reason || undefined,
                });
                toast('Inventory adjusted & ledgered.', 'success');
                void load();
              } catch (err) {
                toast(err instanceof ApiError ? err.message : 'Adjustment failed', 'error');
              }
            }}
          >
            <select value={form.variant_id} onChange={(e) => setForm({ ...form, variant_id: e.target.value })} required aria-label="Variant">
              <option value="">Select variant…</option>
              {items.map((v) => (
                <option key={String(v.variant_id)} value={String(v.variant_id)}>
                  {String(v.product_name)} · {String(v.size)} · {String(v.sku)}
                </option>
              ))}
            </select>
            <select value={form.adjustment_type} onChange={(e) => setForm({ ...form, adjustment_type: e.target.value })} aria-label="Adjustment type">
              {['increase', 'decrease', 'return', 'damage', 'defect', 'correction'].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <input type="number" min={1} value={form.qty_change} onChange={(e) => setForm({ ...form, qty_change: e.target.value })} aria-label="Quantity" />
            <input placeholder="Reason" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
            <button className="button tiny">Adjust</button>
          </form>
        )}
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr><th>SKU</th><th>Piece</th><th>Size</th><th>Available</th><th>Reserved</th><th>Sold</th><th>Damaged</th><th>Returned</th></tr>
          </thead>
          <tbody>
            {items.map((v) => (
              <tr key={String(v.variant_id)} className={Number(v.available_qty) === 0 ? 'row-alert' : ''}>
                <td>{String(v.sku)}</td>
                <td>{String(v.product_name)}</td>
                <td>{String(v.size)}</td>
                <td><strong>{String(v.available_qty)}</strong></td>
                <td>{String(v.reserved_qty)}</td>
                <td>{String(v.sold_qty)}</td>
                <td>{String(v.damaged_qty)}</td>
                <td>{String(v.returned_qty)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows && rows.meta.total === 0 && <p className="empty">No variants yet.</p>}
    </div>
  );
}

function ReportsTab() {
  const [report, setReport] = useState<Reports | null>(null);
  useEffect(() => {
    api.get<Reports>('/admin/reports?period_days=30').then(setReport).catch(() => setReport(null));
  }, []);
  if (!report) return <Spinner />;
  return (
    <div className="kpi-grid">
      <div className="kpi"><small>Orders (30d)</small><strong>{report.orders_total}</strong></div>
      <div className="kpi"><small>Revenue</small><strong>{inr(report.revenue_paise)}</strong></div>
      <div className="kpi"><small>Avg order</small><strong>{inr(report.aov_paise)}</strong></div>
      <div className="kpi"><small>Units sold</small><strong>{report.units_sold}</strong></div>
      <div className="panel span-2">
        <h2>Low stock</h2>
        <ul className="low-list">
          {report.low_stock_variants.map((v) => (
            <li key={v.sku}><span>{v.product_name} · {v.size} · {v.sku}</span><strong>{v.available_qty} left</strong></li>
          ))}
          {report.low_stock_variants.length === 0 && <li className="dim">All sizes healthy.</li>}
        </ul>
      </div>
      <div className="panel span-2">
        <h2>Revenue by source</h2>
        <ul className="low-list">
          {Object.entries(report.revenue_by_source).map(([k, v]) => (
            <li key={k}><span>{statusLabel(k)}</span><strong>{inr(v)}</strong></li>
          ))}
          {Object.keys(report.revenue_by_source).length === 0 && <li className="dim">No paid orders yet.</li>}
        </ul>
      </div>
    </div>
  );
}

function CouponsTab({ canManage }: { canManage: boolean }) {
  const [coupons, setCoupons] = useState<Array<Record<string, unknown>>>([]);
  const [form, setForm] = useState({ code: '', discount_value: '50000', min_order_paise: '1000000' });
  const toast = useToast();
  const load = () => api.get<Array<Record<string, unknown>>>('/coupons').then(setCoupons).catch(() => setCoupons([]));
  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Coupons</h2>
        {canManage && (
          <form
            className="adj-form"
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api.post('/coupons', {
                  code: form.code,
                  discount_type: 'fixed',
                  discount_value: Number(form.discount_value),
                  min_order_paise: Number(form.min_order_paise),
                });
                toast('Coupon created.', 'success');
                setForm({ code: '', discount_value: '50000', min_order_paise: '1000000' });
                void load();
              } catch (err) {
                toast(err instanceof ApiError ? err.message : 'Create failed', 'error');
              }
            }}
          >
            <input placeholder="CODE" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} required />
            <input type="number" value={form.discount_value} onChange={(e) => setForm({ ...form, discount_value: e.target.value })} aria-label="Discount paise" />
            <input type="number" value={form.min_order_paise} onChange={(e) => setForm({ ...form, min_order_paise: e.target.value })} aria-label="Min order paise" />
            <button className="button tiny">Create</button>
          </form>
        )}
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Code</th><th>Discount</th><th>Min order</th><th>Used</th><th>Active</th></tr></thead>
          <tbody>
            {coupons.map((c) => (
              <tr key={String(c.id)}>
                <td><strong>{String(c.code)}</strong></td>
                <td>{inr(Number(c.discount_value))}</td>
                <td>{inr(Number(c.min_order_paise))}</td>
                <td>{String(c.times_used)}</td>
                <td>{String(c.is_active) === 'true' ? '✓' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {coupons.length === 0 && <p className="empty">No coupons yet.</p>}
      </div>
    </div>
  );
}
