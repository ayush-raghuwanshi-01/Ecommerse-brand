export const inr = (paise: number): string => `₹${Math.round(paise / 100).toLocaleString('en-IN')}`;

export const dateFmt = (iso: string | null | undefined): string =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';

export const ORDER_FLOW = [
  'pending_payment',
  'confirmed',
  'processing',
  'packed',
  'shipped',
  'delivered',
  'completed',
] as const;

export const statusLabel = (s: string): string =>
  s
    .split('_')
    .map((w) => w[0]?.toUpperCase() + w.slice(1))
    .join(' ');
