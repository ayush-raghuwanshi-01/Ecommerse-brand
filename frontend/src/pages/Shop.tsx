import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import ProductCard from '../components/ProductCard';
import { Seo, Spinner } from '../components/bits';
import { api } from '../lib/api';
import type { Page, ProductListItem } from '../lib/types';

const TABS = [
  { id: 'all', label: 'All pieces' },
  { id: 'available', label: 'Available now' },
  { id: 'preorder', label: 'Pre-order' },
] as const;

const SORTS = [
  { id: 'featured', label: 'Sort: Featured' },
  { id: 'newest', label: 'Sort: Newest' },
  { id: 'price-asc', label: 'Price: Low to high' },
  { id: 'price-desc', label: 'Price: High to low' },
  { id: 'name', label: 'Name: A to Z' },
] as const;

export default function Shop() {
  const [items, setItems] = useState<ProductListItem[]>([]);
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('all');
  const [sort, setSort] = useState<(typeof SORTS)[number]['id']>('featured');
  const [loading, setLoading] = useState(true);
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';

  useEffect(() => {
    setLoading(true);
    const p = new URLSearchParams({ page_size: '50' });
    if (tab === 'preorder') p.set('preorder', 'true');
    if (q.trim()) p.set('q', q.trim());
    api
      .get<Page<ProductListItem>>(`/products?${p}`)
      .then((r) => {
        let list = r.items;
        if (tab === 'available') list = list.filter((i) => i.status === 'active');
        setItems(list);
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [tab, q]);

  const sorted = useMemo(() => {
    const list = [...items];
    switch (sort) {
      case 'price-asc':
        list.sort((a, b) => a.base_price_paise - b.base_price_paise);
        break;
      case 'price-desc':
        list.sort((a, b) => b.base_price_paise - a.base_price_paise);
        break;
      case 'name':
        list.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case 'newest':
        break; // API already returns newest-first
    }
    return list;
  }, [items, sort]);

  const setQuery = (term: string) => {
    const next = new URLSearchParams(params);
    if (term.trim()) next.set('q', term.trim());
    else next.delete('q');
    setParams(next, { replace: true });
  };

  return (
    <main className="page">
      <Seo
        title="The Collection — Black House"
        description="Small-batch outerwear: overcoats, trenches, field coats and bombers. GST-inclusive pricing, 7-day returns."
      />
      <div className="page-head">
        <p className="eyebrow">The current line</p>
        <h1>
          The <em>collection</em>
        </h1>
        {q && (
          <p className="dim" style={{ marginTop: 10 }}>
            Showing results for “{q}”
          </p>
        )}
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
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search products"
          />
          <div className="sort">
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as typeof sort)}
              aria-label="Sort products"
            >
              {SORTS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="shop-count">
        <span>{loading ? 'Loading…' : `${sorted.length} piece${sorted.length === 1 ? '' : 's'}`}</span>
        <span className="dim" style={{ fontSize: 12 }}>
          GST inclusive · Free shipping over ₹15,000
        </span>
      </div>

      {loading ? (
        <Spinner label="Loading the collection" />
      ) : sorted.length === 0 ? (
        <p className="empty">Nothing matches yet — try another filter or search.</p>
      ) : (
        <div className="card-grid">
          {sorted.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </div>
      )}
    </main>
  );
}
