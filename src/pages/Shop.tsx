import { useEffect, useState } from 'react';
import ProductCard from '../components/ProductCard';
import { Seo, Spinner } from '../components/bits';
import { api } from '../lib/api';
import type { Page, ProductListItem } from '../lib/types';

const TABS = [
  { id: 'all', label: 'All' },
  { id: 'available', label: 'Available now' },
  { id: 'preorder', label: 'Pre-order' },
] as const;

export default function Shop() {
  const [items, setItems] = useState<ProductListItem[]>([]);
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('all');
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ page_size: '50' });
    if (tab === 'preorder') params.set('preorder', 'true');
    if (q.trim()) params.set('q', q.trim());
    api
      .get<Page<ProductListItem>>(`/products?${params}`)
      .then((p) => {
        let list = p.items;
        if (tab === 'available') list = list.filter((i) => i.status === 'active');
        setItems(list);
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [tab, q]);

  return (
    <main className="page">
      <Seo title="The Collection — Black House" description="Small-batch outerwear: overcoats, trenches, field coats." />
      <div className="page-head">
        <p className="eyebrow">The current line</p>
        <h1>
          The <em>collection</em>
        </h1>
        <div className="shop-controls">
          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                className={tab === t.id ? 'active' : ''}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <input
            className="search"
            placeholder="Search pieces…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search products"
          />
        </div>
      </div>
      {loading ? (
        <Spinner label="Loading the collection" />
      ) : items.length === 0 ? (
        <p className="empty">Nothing matches yet — try another filter.</p>
      ) : (
        <div className="card-grid">
          {items.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </main>
  );
}
