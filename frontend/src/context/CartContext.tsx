import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, tokens } from '../lib/api';
import type { Cart, CartItem } from '../lib/types';
import { useAuth } from './AuthContext';

export interface CartItemMeta {
  product_id?: string;
  product_name?: string;
  variant_name?: string;
  sku?: string;
  size?: string;
  image_url?: string | null;
  unit_price_paise?: number;
}

interface CartState {
  cart: Cart | null;
  open: boolean;
  setOpen: (v: boolean) => void;
  refresh: () => Promise<void>;
  add: (variantId: string, qty?: number, meta?: CartItemMeta) => Promise<Cart>;
  setQty: (itemId: string, qty: number) => Promise<void>;
  remove: (itemId: string) => Promise<void>;
  clearCart: () => void;
  applyCoupon: (code: string) => Promise<void>;
  removeCoupon: () => Promise<void>;
  count: number;
}

const GUEST_CART_KEY = 'blackhouse_guest_cart';

function buildGuestCart(items: CartItem[]): Cart {
  const subtotal = items.reduce((sum, item) => sum + item.unit_price_paise_snapshot * item.qty, 0);
  const tax = Math.round((subtotal * 5) / 105);
  return {
    id: 'guest',
    items,
    coupon_code: null,
    totals: {
      currency: 'INR',
      subtotal_paise: subtotal,
      discount_paise: 0,
      shipping_paise: 0,
      tax_paise: tax,
      grand_total_paise: subtotal,
    },
    checkout_blocked: false,
    block_reasons: [],
  };
}

const CartCtx = createContext<CartState>(null as unknown as CartState);
export const useCart = () => useContext(CartCtx);

export function CartProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [cart, setCart] = useState<Cart | null>(() => {
    try {
      const stored = localStorage.getItem(GUEST_CART_KEY);
      if (stored) {
        const items = JSON.parse(stored) as CartItem[];
        return buildGuestCart(items);
      }
    } catch {
      // ignore
    }
    return null;
  });
  const [open, setOpen] = useState(false);

  const refresh = useCallback(async () => {
    if (!tokens.access) {
      try {
        const stored = localStorage.getItem(GUEST_CART_KEY);
        if (stored) {
          const items = JSON.parse(stored) as CartItem[];
          setCart(buildGuestCart(items));
        } else {
          setCart(null);
        }
      } catch {
        setCart(null);
      }
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
    add: async (variantId, qty = 1, meta) => {
      if (tokens.access) {
        const c = await api.post<Cart>('/carts/me/items', { variant_id: variantId, qty });
        setCart(c);
        setOpen(true);
        return c;
      }
      // Guest mode
      const currentItems = cart?.items ? [...cart.items] : [];
      const existingIndex = currentItems.findIndex((i) => i.variant_id === variantId);
      if (existingIndex > -1) {
        currentItems[existingIndex].qty += qty;
        currentItems[existingIndex].line_total_paise =
          currentItems[existingIndex].qty * currentItems[existingIndex].unit_price_paise_snapshot;
      } else {
        const unitPrice = meta?.unit_price_paise ?? 0;
        const newItem: CartItem = {
          id: `guest_item_${variantId}_${Date.now()}`,
          variant_id: variantId,
          product_id: meta?.product_id || '',
          product_name: meta?.product_name || 'Product',
          variant_name: meta?.variant_name || '',
          sku: meta?.sku || '',
          size: meta?.size || '',
          image_url: meta?.image_url || null,
          qty,
          unit_price_paise_snapshot: unitPrice,
          current_unit_price_paise: unitPrice,
          price_changed: false,
          is_available: true,
          is_preorder: false,
          available_qty: 99,
          line_total_paise: unitPrice * qty,
        };
        currentItems.push(newItem);
      }
      localStorage.setItem(GUEST_CART_KEY, JSON.stringify(currentItems));
      const newCart = buildGuestCart(currentItems);
      setCart(newCart);
      setOpen(true);
      return newCart;
    },
    setQty: async (itemId, qty) => {
      if (tokens.access) {
        const c = await api.patch<Cart>(`/carts/me/items/${itemId}`, { qty });
        setCart(c);
        return;
      }
      if (!cart) return;
      const currentItems = cart.items
        .map((i) => (i.id === itemId ? { ...i, qty, line_total_paise: i.unit_price_paise_snapshot * qty } : i))
        .filter((i) => i.qty > 0);
      localStorage.setItem(GUEST_CART_KEY, JSON.stringify(currentItems));
      setCart(buildGuestCart(currentItems));
    },
    remove: async (itemId) => {
      if (tokens.access) {
        const c = await api.delete<Cart>(`/carts/me/items/${itemId}`);
        setCart(c);
        return;
      }
      if (!cart) return;
      const currentItems = cart.items.filter((i) => i.id !== itemId);
      localStorage.setItem(GUEST_CART_KEY, JSON.stringify(currentItems));
      setCart(buildGuestCart(currentItems));
    },
    clearCart: () => {
      localStorage.removeItem(GUEST_CART_KEY);
      setCart(null);
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
