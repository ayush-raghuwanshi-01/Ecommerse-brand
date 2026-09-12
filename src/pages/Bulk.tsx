import { useState, type FormEvent } from 'react';
import { Seo } from '../components/bits';
import { useToast } from '../context/ToastContext';
import { ApiError, api } from '../lib/api';

export default function BulkPage() {
  const [form, setForm] = useState({
    name: '',
    business_name: '',
    email: '',
    phone: '',
    product_interest: '',
    estimated_qty: '',
    message: '',
  });
  const [sent, setSent] = useState(false);
  const toast = useToast();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/bulk-enquiries', {
        ...form,
        estimated_qty: form.estimated_qty ? Number(form.estimated_qty) : undefined,
      }, );
      setSent(true);
      toast('Enquiry received — our team will reach out.', 'success');
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Could not submit enquiry', 'error');
    }
  };

  return (
    <main className="page">
      <Seo title="Bulk orders — Black House" description="Uniforms and bulk outerwear production for teams and enterprises." />
      <div className="page-head">
        <p className="eyebrow">Uniforms & bulk</p>
        <h1>
          Outfitting a team? <em>Let’s talk.</em>
        </h1>
        <p className="dim">
          Hotels, studios, enterprises — small-batch production runs with the same cloth and
          finish as our retail line.
        </p>
      </div>

      {sent ? (
        <p className="ok banner">✓ Thank you — your enquiry is with our sales team. We reply within one working day.</p>
      ) : (
        <form className="panel narrow" onSubmit={submit}>
          <label>Your name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>Business name (optional)<input value={form.business_name} onChange={(e) => setForm({ ...form, business_name: e.target.value })} /></label>
          <label>Email<input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
          <label>Phone<input required pattern="[0-9]{10}" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
          <label>Product or category of interest<input required value={form.product_interest} onChange={(e) => setForm({ ...form, product_interest: e.target.value })} /></label>
          <label>Estimated quantity<input inputMode="numeric" value={form.estimated_qty} onChange={(e) => setForm({ ...form, estimated_qty: e.target.value.replace(/\D/g, '') })} /></label>
          <label>Message<textarea rows={4} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} /></label>
          <button className="button wide">Send enquiry</button>
        </form>
      )}
    </main>
  );
}
