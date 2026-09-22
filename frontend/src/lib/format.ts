export const inr = (paise: number): string => `₹${Math.round(paise / 100).toLocaleString('en-IN')}`;

export const dateFmt = (iso: string | null | undefined): string =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';

export const ORDER_FLOW = [
  'pending_payment',
  'confirmed',
  'packed',
  'shipped',
  'delivered',
] as const;

export const statusLabel = (s: string): string => {
  if (s === 'pending_payment') return 'Placed (Pending Call)';
  if (s === 'confirmed') return 'Confirmed by Call';
  if (s === 'processing') return 'Confirmed by Call';
  if (s === 'return_requested') return 'Return Requested';
  if (s === 'returned') return 'Return Resolved';
  return s
    .split('_')
    .map((w) => w[0]?.toUpperCase() + w.slice(1))
    .join(' ');
};
