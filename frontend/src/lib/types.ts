/** API payload types mirroring backend schemas (paise integers everywhere). */

export interface Totals {
  subtotal_paise: number;
  discount_paise: number;
  shipping_paise: number;
  tax_paise: number;
  grand_total_paise: number;
  currency: string;
}

export interface Variant {
  id: string;
  sku: string;
  size: string;
  price_paise: number;
  gst_percentage: number;
  stock_qty: number;
  reserved_qty: number;
  available_qty: number;
  is_active: boolean;
  is_purchasable: boolean;
  is_preorder: boolean;
  availability: 'available' | 'low_stock' | 'out_of_stock' | 'upcoming' | 'disabled';
}

export interface ProductImage {
  id: string;
  url: string;
  alt_text: string | null;
  is_primary: boolean;
}

export interface ProductListItem {
  id: string;
  name: string;
  slug: string;
  short_description: string | null;
  status: string;
  product_type?: string | null;
  base_price_paise: number;
  is_preorder: boolean;
  preorder_open: boolean;
  primary_image_url: string | null;
  sizes_available: string[];
}

export interface Product {
  id: string;
  name: string;
  slug: string;
  short_description: string | null;
  description: string | null;
  status: string;
  product_type: string | null;
  fabric: string | null;
  fit_info: string | null;
  care_instructions: string | null;
  size_guide: string | null;
  base_price_paise: number;
  gst_percentage: number;
  is_preorder: boolean;
  preorder_open: boolean;
  preorder_fulfillment_note: string | null;
  restock_expected_at: string | null;
  restock_note: string | null;
  is_sale_item: boolean;
  variants: Variant[];
  images: ProductImage[];
}

export interface CartItem {
  id: string;
  variant_id: string;
  product_id: string;
  product_name: string;
  variant_name: string;
  sku: string;
  size: string;
  image_url: string | null;
  qty: number;
  unit_price_paise_snapshot: number;
  current_unit_price_paise: number;
  price_changed: boolean;
  is_available: boolean;
  is_preorder: boolean;
  available_qty: number;
  line_total_paise: number;
}

export interface Cart {
  id: string;
  items: CartItem[];
  coupon_code: string | null;
  totals: Totals;
  checkout_blocked: boolean;
  block_reasons: string[];
}

export interface Address {
  id: string;
  full_name: string;
  phone: string;
  line1: string;
  line2: string | null;
  landmark: string | null;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  address_type: string;
  is_default_shipping: boolean;
  is_default_billing: boolean;
}

export interface OrderItem {
  id: string;
  product_name: string;
  variant_name: string;
  sku: string;
  product_image_url: string | null;
  unit_price_paise: number;
  qty: number;
  discount_paise: number;
  total_paise: number;
  tax_paise: number;
  is_preorder: boolean;
  estimated_fulfillment_note: string | null;
}

export interface OrderHistoryEvent {
  from_status: string | null;
  to_status: string;
  note: string | null;
  created_at: string;
}

export interface Order {
  id: string;
  number: string;
  status: string;
  payment_method: string;
  payment_status: string;
  fulfillment_status: string;
  order_source: string;
  subtotal_paise: number;
  discount_paise: number;
  shipping_paise: number;
  tax_paise: number;
  grand_total_paise: number;
  is_preorder: boolean;
  customer_notes: string | null;
  internal_notes: string | null;
  billing_address: Record<string, string>;
  shipping_address: Record<string, string>;
  items: OrderItem[];
  history: OrderHistoryEvent[];
  created_at: string;
  delivered_at: string | null;
  cancellation_reason: string | null;
}

export interface PaymentSession {
  provider: string;
  provider_order_id: string;
  key_id: string;
  amount_paise: number;
  currency: string;
  order_number: string;
  mock: boolean;
}

export interface PlaceOrderResult {
  order: Order;
  payment_session: PaymentSession | null;
  requires_payment: boolean;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: 'customer' | 'staff' | 'manager' | 'admin';
  is_active: boolean;
  is_email_verified: boolean;
}

export interface Page<T> {
  items: T[];
  meta: { page: number; page_size: number; total: number; pages: number };
}

export interface Reports {
  period_days: number;
  orders_total: number;
  revenue_paise: number;
  aov_paise: number;
  units_sold: number;
  orders_by_status: Record<string, number>;
  revenue_by_source: Record<string, number>;
  low_stock_variants: Array<{ sku: string; product_name: string; size: string; available_qty: number }>;
}
