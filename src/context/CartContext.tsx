import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, tokens } from '../lib/api';
import type { Cart } from '../lib/types';
import { useAuth } from './AuthContext';

interface CartState {
  cart: Cart | null;
  open: boolean;
  setOpen: (v: boolean) => void;
  refresh: () => Promise<void>;
  add: (variantId: string, qty?: number) => Promise<Cart>;
  setQty: (itemId: string, qty: number) => Promise<void>;
  remove: (itemId: string) => Promise<void>;
  applyCoupon: (code: string) => Promise<void>;
  removeCoupon: () => Promise<void>;
  count: number;
}

const CartCtx = createContext<CartState>(null as unknown as CartState);
export const useCart = () => useContext(CartCtx);

export function CartProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [cart, setCart] = useState<Cart | null>(null);
  const [open, setOpen] = useState(false);

  const refresh = useCallback(async () => {
    if (!tokens.access) {
      setCart(null);
      return;
    }
    try {
      setCart(await api.get<Cart>('/carts/me'));
    } catch {
      setCart(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [user, refresh]);

  const value: CartState = {
    cart,
    open,
    setOpen,
    refresh,
    count: cart?.items.reduce((n, i) => n + i.qty, 0) ?? 0,
    add: async (variantId, qty = 1) => {
      const c = await api.post<Cart>('/carts/me/items', { variant_id: variantId, qty });
      setCart(c);
      setOpen(true);
      return c;
    },
    setQty: async (itemId, qty) => {
      const c = await api.patch<Cart>(`/carts/me/items/${itemId}`, { qty });
      setCart(c);
    },
    remove: async (itemId) => {
      const c = await api.delete<Cart>(`/carts/me/items/${itemId}`);
      setCart(c);
    },
    applyCoupon: async (code) => {
      const c = await api.post<Cart>('/carts/me/coupon', { code });
      setCart(c);
    },
    removeCoupon: async () => {
      const c = await api.delete<Cart>('/carts/me/coupon');
      setCart(c);
    },
  };

  return <CartCtx.Provider value={value}>{children}</CartCtx.Provider>;
}
