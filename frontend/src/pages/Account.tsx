import { useEffect, useState } from 'react';
import { Seo } from '../components/bits';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ApiError, api } from '../lib/api';
import type { Address } from '../lib/types';

const EMPTY = {
  full_name: '',
  phone: '',
  line1: '',
  line2: '',
  landmark: '',
  city: '',
  state: 'Madhya Pradesh',
  postal_code: '',
  address_type: 'home',
  is_default_shipping: false,
  is_default_billing: false,
};

export default function AccountPage() {
  const { user } = useAuth();
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [form, setForm] = useState<typeof EMPTY | null>(null);
  const toast = useToast();

  const load = () =>
    api
      .get<Address[]>('/addresses')
      .then(setAddresses)
      .catch(() => setAddresses([]));
  useEffect(() => {
    void load();
  }, []);

  return (
    <main className="page">
      <Seo title="Account — Black House" />
      <h1>
        Hello, <em>{user?.full_name.split(' ')[0]}</em>
      </h1>
      <p className="dim">
        {user?.email} · {user?.role}
      </p>

      <div className="panel">
        <div className="panel-head">
          <h2>Addresses</h2>
          <button className="button small" onClick={() => setForm(form ? null : { ...EMPTY })}>
            {form ? 'Cancel' : 'Add address'}
          </button>
        </div>

        {form && (
          <form
            className="addr-form"
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api.post('/addresses', { ...form, country: 'IN' });
                setForm(null);
                toast('Address saved.', 'success');
                void load();
              } catch (err) {
                toast(err instanceof ApiError ? err.message : 'Could not save address', 'error');
              }
            }}
          >
            <div className="row-2">
              <label>
                Full name
                <input
                  required
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                />
              </label>
              <label>
                Phone
                <input
                  required
                  pattern="[0-9]{10}"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
              </label>
            </div>
            <label>
              Line 1
              <input
                required
                value={form.line1}
                onChange={(e) => setForm({ ...form, line1: e.target.value })}
              />
            </label>
            <label>
              Line 2<input value={form.line2} onChange={(e) => setForm({ ...form, line2: e.target.value })} />
            </label>
            <div className="row-2">
              <label>
                City
                <input
                  required
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                />
              </label>
              <label>
                State
                <input
                  required
                  value={form.state}
                  onChange={(e) => setForm({ ...form, state: e.target.value })}
                />
              </label>
            </div>
            <label>
              PIN code
              <input
                required
                pattern="[1-9][0-9]{5}"
                maxLength={6}
                value={form.postal_code}
                onChange={(e) => setForm({ ...form, postal_code: e.target.value.replace(/\D/g, '') })}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={form.is_default_shipping}
                onChange={(e) => setForm({ ...form, is_default_shipping: e.target.checked })}
              />{' '}
              Default shipping
            </label>
            <button className="button">Save address</button>
          </form>
        )}

        <div className="addr-grid">
          {addresses.map((a) => (
            <div className="addr-card" key={a.id}>
              <strong>{a.full_name}</strong>
              <small>
                {a.line1}
                {a.line2 ? `, ${a.line2}` : ''}
                <br />
                {a.city}, {a.state} {a.postal_code}
              </small>
              <div className="chips">
                <span className="chip dim">{a.address_type}</span>
                {a.is_default_shipping && <span className="chip gold">shipping</span>}
                {a.is_default_billing && <span className="chip gold">billing</span>}
              </div>
              <button
                className="textlink"
                onClick={async () => {
                  await api.delete(`/addresses/${a.id}`);
                  void load();
                }}
              >
                Delete
              </button>
            </div>
          ))}
          {addresses.length === 0 && !form && <p className="empty">No addresses saved yet.</p>}
        </div>
      </div>
    </main>
  );
}
