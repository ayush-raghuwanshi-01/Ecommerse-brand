import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { ProductListItem } from '../lib/types';

/**
 * Device-local wishlist (heart). Stored in localStorage so a shopper can
 * shortlist pieces across sessions on the same device — the same behaviour
 * reference D2C stores ship before accounts are mandatory.
 */
interface WishlistState {
  items: ProductListItem[];
  count: number;
  has: (slug: string) => boolean;
  toggle: (product: ProductListItem) => void;
  remove: (slug: string) => void;
}

const KEY = 'blackhouse_wishlist';

const WishlistCtx = createContext<WishlistState>(null as unknown as WishlistState);

export const useWishlist = () => useContext(WishlistCtx);

function load(): ProductListItem[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as ProductListItem[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function WishlistProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ProductListItem[]>(load);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(items));
    } catch {
      /* private mode — wishlist stays in-memory */
    }
  }, [items]);

  const has = (slug: string) => items.some((i) => i.slug === slug);

  const toggle = (product: ProductListItem) =>
    setItems((prev) =>
      prev.some((i) => i.slug === product.slug)
        ? prev.filter((i) => i.slug !== product.slug)
        : [{ ...product }, ...prev],
    );

  const remove = (slug: string) => setItems((prev) => prev.filter((i) => i.slug !== slug));

  return (
    <WishlistCtx.Provider value={{ items, count: items.length, has, toggle, remove }}>
      {children}
    </WishlistCtx.Provider>
  );
}
