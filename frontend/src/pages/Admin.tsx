import { useCallback, useEffect, useState } from 'react';
import { Seo, Spinner } from '../components/bits';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ApiError, api } from '../lib/api';
import { dateFmt, inr, statusLabel } from '../lib/format';
import type { Order, Page, Product, ProductListItem, Reports } from '../lib/types';

const NEXT_STATUS: Record<string, string> = {
  pending_payment: 'confirmed',
  confirmed: 'packed',
  processing: 'packed',
  packed: 'shipped',
  shipped: 'delivered',
  delivered: 'completed',
  return_requested: 'returned',
};

type Tab = 'orders' | 'catalog' | 'inventory' | 'reports';

export default function AdminPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>('orders');

  if (!user || !['staff', 'manager', 'admin'].includes(user.role)) {
    return (
      <main className="page">
        <Seo title="Console — Black House" />
        <p className="empty">
          Admin access only. Sign in with an admin or staff account to open the console.
        </p>
      </main>
    );
  }

  return (
    <main className="page admin">
      <Seo title="Console — Black House" />
      <div className="page-head">
        <p className="eyebrow">Operations & Catalog Console</p>
        <h1>
          {user.full_name} <em>· Admin</em>
        </h1>
        <div className="tabs" role="tablist">
          {(['orders', 'catalog', 'inventory', 'reports'] as Tab[]).map((t) => (
            <button
              key={t}
              role="tab"
              aria-selected={tab === t}
              className={tab === t ? 'active' : ''}
              onClick={() => setTab(t)}
            >
              {t === 'orders'
                ? 'Orders & Calls'
                : t === 'catalog'
                  ? 'Product Catalog'
                  : t === 'inventory'
                    ? 'Variant Stock'
                    : 'Summary'}
            </button>
          ))}
        </div>
      </div>
      {tab === 'orders' && <OrdersTab />}
      {tab === 'catalog' && <CatalogTab />}
      {tab === 'inventory' && <InventoryTab />}
      {tab === 'reports' && <ReportsTab />}
    </main>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   ORDERS & CALLS TAB
───────────────────────────────────────────────────────────────────────────── */
function OrdersTab() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [status, setStatus] = useState('');
  const toast = useToast();

  const load = useCallback(() => {
    const q = status ? `?status=${status}` : '';
    api
      .get<Page<Order>>(`/orders${q}&page_size=50`.replace('?&', '?'))
      .then((p) => setOrders(p.items))
      .catch(() => setOrders([]));
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
        <h2>Orders & Call Confirmations</h2>
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
          <option value="">All Orders</option>
          <option value="pending_payment">Placed (Needs Call)</option>
          <option value="confirmed">Confirmed by Call</option>
          <option value="packed">Packed</option>
          <option value="shipped">Shipped</option>
          <option value="delivered">Delivered</option>
          <option value="return_requested">Return Requested</option>
          <option value="returned">Return Resolved</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>
      {!orders ? (
        <Spinner />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Order</th>
                <th>Customer & Phone</th>
                <th>Address</th>
                <th>Items</th>
                <th>Status</th>
                <th>Total</th>
                <th>Call & Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>
                    <strong>{o.number}</strong>
                    <br />
                    <small>{dateFmt(o.created_at)}</small>
                  </td>
                  <td>
                    <strong>{o.shipping_address.full_name}</strong>
                    <br />
                    <a
                      href={`tel:${o.shipping_address.phone}`}
                      style={{ color: 'var(--accent)', textDecoration: 'underline' }}
                    >
                      📞 {o.shipping_address.phone}
                    </a>
                  </td>
                  <td>
                    <small>
                      {o.shipping_address.line1}, {o.shipping_address.city} ({o.shipping_address.postal_code})
                    </small>
                  </td>
                  <td>
                    <small>
                      {o.items.map((i) => `${i.product_name} (${i.variant_name}) × ${i.qty}`).join(', ')}
                    </small>
                  </td>
                  <td>
                    <span className={`status ${o.status}`}>{statusLabel(o.status)}</span>
                  </td>
                  <td>{inr(o.grand_total_paise)}</td>
                  <td className="actions-cell">
                    <a
                      className="button tiny"
                      style={{ background: '#25D366', color: '#fff', borderColor: '#25D366' }}
                      href={`https://wa.me/${o.shipping_address.phone?.replace(
                        /\D/g,
                        '',
                      )}?text=${encodeURIComponent(
                        `Hi ${o.shipping_address.full_name}, calling from Black House regarding your order ${o.number} (Total: ${inr(
                          o.grand_total_paise,
                        )}).`,
                      )}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      WhatsApp
                    </a>
                    {NEXT_STATUS[o.status] && (
                      <button
                        className="button tiny"
                        onClick={() =>
                          act(
                            () => api.post(`/orders/${o.id}/status`, { status: NEXT_STATUS[o.status] }),
                            `Moved to ${statusLabel(NEXT_STATUS[o.status])}`,
                          )
                        }
                      >
                        → {statusLabel(NEXT_STATUS[o.status])}
                      </button>
                    )}
                    {o.status === 'pending_payment' && (
                      <button
                        className="button tiny ghost"
                        onClick={() =>
                          act(
                            () => api.post(`/orders/${o.id}/status`, { status: 'cancelled' }),
                            'Order marked cancelled',
                          )
                        }
                      >
                        Cancel
                      </button>
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

/* ─────────────────────────────────────────────────────────────────────────────
   CATALOG MANAGEMENT TAB (Add Product, Edit Price, Add Variants)
───────────────────────────────────────────────────────────────────────────── */
function CatalogTab() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newProd, setNewProd] = useState({
    name: '',
    product_type: 'Shirt',
    base_price_paise: 299900,
    short_description: '',
    fabric: '100% Cotton',
  });
  const [newVariant, setNewVariant] = useState({
    size: 'M',
    sku: '',
    stock_qty: 10,
    price_paise: 299900,
  });

  const toast = useToast();

  const loadProducts = useCallback(() => {
    setLoading(true);
    api
      .get<Page<ProductListItem>>('/products?page_size=100')
      .then((p) => {
        setProducts(p.items);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  const loadProductDetail = (slug: string) => {
    api
      .get<Product>(`/products/${slug}`)
      .then(setSelectedProduct)
      .catch(() => null);
  };

  const handleCreateProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const slug = newProd.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/(^-|-$)/g, '');
      const created = await api.post<Product>('/products', {
        name: newProd.name,
        slug,
        product_type: newProd.product_type,
        base_price_paise: Number(newProd.base_price_paise),
        short_description: newProd.short_description || undefined,
        fabric: newProd.fabric || undefined,
        status: 'active',
      });
      toast(`Created product "${created.name}"`, 'success');
      setShowAddForm(false);
      setNewProd({
        name: '',
        product_type: 'Shirt',
        base_price_paise: 299900,
        short_description: '',
        fabric: '100% Cotton',
      });
      loadProducts();
      setSelectedProduct(created);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Failed to create product', 'error');
    }
  };

  const handleAddVariant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProduct) return;
    try {
      const generatedSku =
        newVariant.sku ||
        `${selectedProduct.slug.toUpperCase().slice(0, 4)}-${newVariant.size}-${Date.now().toString().slice(-4)}`;
      await api.post(`/products/${selectedProduct.id}/variants`, {
        sku: generatedSku,
        size: newVariant.size,
        price_paise: Number(newVariant.price_paise) || selectedProduct.base_price_paise,
        stock_qty: Number(newVariant.stock_qty),
        gst_percentage: 5.0,
      });
      toast(`Added size ${newVariant.size} with stock ${newVariant.stock_qty}`, 'success');
      setNewVariant({ size: 'M', sku: '', stock_qty: 10, price_paise: selectedProduct.base_price_paise });
      loadProductDetail(selectedProduct.slug);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Failed to add variant', 'error');
    }
  };

  const handleUpdateStock = async (variantId: string, currentStock: number, delta: number) => {
    try {
      await api.patch(`/products/variants/${variantId}`, {
        stock_qty: Math.max(0, currentStock + delta),
      });
      toast('Stock updated', 'success');
      if (selectedProduct) loadProductDetail(selectedProduct.slug);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Failed to update stock', 'error');
    }
  };

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Product & SKU Management</h2>
        <button className="button tiny" onClick={() => setShowAddForm(!showAddForm)}>
          {showAddForm ? 'Close Form' : '+ Add New Product'}
        </button>
      </div>

      {showAddForm && (
        <form
          className="panel"
          style={{ marginBottom: '1.5rem', borderColor: 'var(--accent-line)' }}
          onSubmit={handleCreateProduct}
        >
          <h3>Create New Product</h3>
          <div className="row-2">
            <label>
              Product Name *
              <input
                required
                placeholder="e.g. Pure Cotton Kurta"
                value={newProd.name}
                onChange={(e) => setNewProd({ ...newProd, name: e.target.value })}
              />
            </label>
            <label>
              Category / Type *
              <input
                required
                placeholder="e.g. Shirt, Kurta, Trousers"
                value={newProd.product_type}
                onChange={(e) => setNewProd({ ...newProd, product_type: e.target.value })}
              />
            </label>
          </div>
          <div className="row-2">
            <label>
              Base Price (paise, e.g. 299900 = ₹2,999) *
              <input
                type="number"
                required
                value={newProd.base_price_paise}
                onChange={(e) => setNewProd({ ...newProd, base_price_paise: Number(e.target.value) })}
              />
            </label>
            <label>
              Fabric details
              <input
                placeholder="e.g. Handloom Khadi Cotton"
                value={newProd.fabric}
                onChange={(e) => setNewProd({ ...newProd, fabric: e.target.value })}
              />
            </label>
          </div>
          <label>
            Short Description
            <textarea
              rows={2}
              placeholder="Brief story or product highlight..."
              value={newProd.short_description}
              onChange={(e) => setNewProd({ ...newProd, short_description: e.target.value })}
            />
          </label>
          <button className="button tiny" style={{ marginTop: '0.75rem' }}>
            Save Product
          </button>
        </form>
      )}

      {loading ? (
        <Spinner />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
          <div>
            <h3>All Products ({products.length})</h3>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Price</th>
                    <th>Sizes</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => (
                    <tr
                      key={p.id}
                      style={{
                        background: selectedProduct?.id === p.id ? 'rgba(154, 91, 11, 0.08)' : 'transparent',
                        cursor: 'pointer',
                      }}
                      onClick={() => loadProductDetail(p.slug)}
                    >
                      <td>
                        <strong>{p.name}</strong>
                        <br />
                        <small className="dim">{p.product_type}</small>
                      </td>
                      <td>{inr(p.base_price_paise)}</td>
                      <td>
                        <small>{p.sizes_available.join(', ') || 'None'}</small>
                      </td>
                      <td>
                        <button
                          className="button tiny ghost"
                          onClick={(e) => {
                            e.stopPropagation();
                            loadProductDetail(p.slug);
                          }}
                        >
                          Manage SKUs
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            {selectedProduct ? (
              <div className="panel">
                <h3>{selectedProduct.name} — Variants & Stock</h3>
                <p className="dim" style={{ fontSize: '0.9rem' }}>
                  Base price: {inr(selectedProduct.base_price_paise)} · {selectedProduct.product_type}
                </p>

                <div className="table-wrap" style={{ marginTop: '1rem' }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Size</th>
                        <th>SKU</th>
                        <th>Stock</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedProduct.variants.map((v) => (
                        <tr key={v.id}>
                          <td>
                            <strong>{v.size}</strong>
                          </td>
                          <td>
                            <small>{v.sku}</small>
                          </td>
                          <td>
                            <strong>{v.stock_qty}</strong>{' '}
                            <small className="dim">({v.available_qty} avail)</small>
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: '0.25rem' }}>
                              <button
                                className="button tiny ghost"
                                onClick={() => handleUpdateStock(v.id, v.stock_qty, -1)}
                              >
                                −1
                              </button>
                              <button
                                className="button tiny ghost"
                                onClick={() => handleUpdateStock(v.id, v.stock_qty, 1)}
                              >
                                +1
                              </button>
                              <button
                                className="button tiny"
                                onClick={() => handleUpdateStock(v.id, v.stock_qty, 5)}
                              >
                                +5
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {selectedProduct.variants.length === 0 && (
                    <p className="empty">No variants created yet for this product.</p>
                  )}
                </div>

                <form
                  onSubmit={handleAddVariant}
                  style={{
                    marginTop: '1.25rem',
                    padding: '0.75rem',
                    border: '1.5px dashed var(--border-strong)',
                    borderRadius: '4px',
                  }}
                >
                  <h4 style={{ margin: '0 0 0.5rem 0' }}>+ Add Size Variant</h4>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <select
                      value={newVariant.size}
                      onChange={(e) => setNewVariant({ ...newVariant, size: e.target.value })}
                      style={{ padding: '0.4rem' }}
                    >
                      {['XS', 'S', 'M', 'L', 'XL', 'XXL'].map((s) => (
                        <option key={s} value={s}>
                          Size {s}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      placeholder="Stock quantity"
                      value={newVariant.stock_qty}
                      onChange={(e) => setNewVariant({ ...newVariant, stock_qty: Number(e.target.value) })}
                      style={{ width: '100px', padding: '0.4rem' }}
                    />
                    <button className="button tiny">Add Size</button>
                  </div>
                </form>
              </div>
            ) : (
              <div className="panel" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
                <p className="dim">
                  👈 Select any product on the left to manage size variants and stock levels.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   INVENTORY TAB (Stock Ledger & Adjustment)
───────────────────────────────────────────────────────────────────────────── */
function InventoryTab() {
  const [rows, setRows] = useState<Page<unknown> | null>(null);
  const [items, setItems] = useState<Array<Record<string, unknown>>>([]);
  const [form, setForm] = useState({
    variant_id: '',
    adjustment_type: 'increase',
    qty_change: '5',
    reason: '',
  });
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
        <h2>Stock Overview & Ledger</h2>
        <form
          className="adj-form"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await api.post('/inventory/adjustments', {
                variant_id: form.variant_id,
                adjustment_type: form.adjustment_type,
                qty_change: ['decrease', 'damage', 'defect'].includes(form.adjustment_type)
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
          <select
            value={form.variant_id}
            onChange={(e) => setForm({ ...form, variant_id: e.target.value })}
            required
            aria-label="Variant"
          >
            <option value="">Select SKU…</option>
            {items.map((v) => (
              <option key={String(v.variant_id)} value={String(v.variant_id)}>
                {String(v.product_name)} · {String(v.size)} ({String(v.sku)})
              </option>
            ))}
          </select>
          <select
            value={form.adjustment_type}
            onChange={(e) => setForm({ ...form, adjustment_type: e.target.value })}
            aria-label="Adjustment type"
          >
            {['increase', 'decrease', 'return', 'damage', 'correction'].map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <input
            type="number"
            min="1"
            value={form.qty_change}
            onChange={(e) => setForm({ ...form, qty_change: e.target.value })}
            style={{ width: '70px' }}
          />
          <button className="button tiny">Adjust</button>
        </form>
      </div>

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>SKU</th>
              <th>Product</th>
              <th>Size</th>
              <th>Available</th>
              <th>Reserved</th>
              <th>Sold</th>
            </tr>
          </thead>
          <tbody>
            {items.map((v) => (
              <tr key={String(v.variant_id)} className={Number(v.available_qty) === 0 ? 'row-alert' : ''}>
                <td>{String(v.sku)}</td>
                <td>{String(v.product_name)}</td>
                <td>{String(v.size)}</td>
                <td>
                  <strong>{String(v.available_qty)}</strong>
                </td>
                <td>{String(v.reserved_qty)}</td>
                <td>{String(v.sold_qty)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows && rows.meta.total === 0 && <p className="empty">No variants in inventory yet.</p>}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   REPORTS TAB
───────────────────────────────────────────────────────────────────────────── */
function ReportsTab() {
  const [report, setReport] = useState<Reports | null>(null);

  useEffect(() => {
    api
      .get<Reports>('/admin/reports?period_days=30')
      .then(setReport)
      .catch(() => setReport(null));
  }, []);

  if (!report) return <Spinner />;

  return (
    <div className="kpi-grid">
      <div className="kpi">
        <small>Total Orders</small>
        <strong>{report.orders_total}</strong>
      </div>
      <div className="kpi">
        <small>Revenue</small>
        <strong>{inr(report.revenue_paise)}</strong>
      </div>
      <div className="kpi">
        <small>Avg Order Value</small>
        <strong>{inr(report.aov_paise)}</strong>
      </div>
      <div className="kpi">
        <small>Units Sold</small>
        <strong>{report.units_sold}</strong>
      </div>

      <div className="panel span-2">
        <h2>Low Stock Alert (&lt; 3 units)</h2>
        <ul className="low-list">
          {report.low_stock_variants.map((v) => (
            <li key={v.sku}>
              <span>
                {v.product_name} · Size {v.size} ({v.sku})
              </span>
              <strong style={{ color: 'var(--alert)' }}>{v.available_qty} left</strong>
            </li>
          ))}
          {report.low_stock_variants.length === 0 && <li className="dim">All variants are well-stocked.</li>}
        </ul>
      </div>
    </div>
  );
}
