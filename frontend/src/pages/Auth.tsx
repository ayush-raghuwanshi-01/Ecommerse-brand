import { useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Seo } from '../components/bits';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { ApiError } from '../lib/api';

export default function AuthPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [busy, setBusy] = useState(false);
  const { login, register } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === 'login') await login(email, password);
      else await register({ email, password, full_name: name, phone: phone || undefined });
      toast(mode === 'login' ? 'Welcome back.' : 'Account created — welcome to Black House.', 'success');
      navigate(params.get('next') || '/');
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Authentication failed', 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page auth-page">
      <Seo title={mode === 'login' ? 'Sign in — Black House' : 'Create account — Black House'} />
      <form className="panel narrow" onSubmit={submit}>
        <p className="eyebrow">Members</p>
        <h1>
          {mode === 'login' ? (
            <>
              Sign <em>in</em>
            </>
          ) : (
            <>
              Create <em>account</em>
            </>
          )}
        </h1>
        {mode === 'register' && (
          <>
            <label>
              Full name
              <input required value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label>
              Phone (optional)
              <input
                inputMode="numeric"
                pattern="[0-9]{10}"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </label>
          </>
        )}
        <label>
          Email
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input
            required
            type="password"
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <button className="button wide" disabled={busy}>
          {busy ? 'One moment…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>
        <button
          type="button"
          className="textlink"
          onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
        >
          {mode === 'login' ? 'New here? Create an account' : 'Already a member? Sign in'}
        </button>
        <p className="dim small-note">
          Demo logins — customer@example.com / Customer@12345 · staff@blackhouse.example / Staff@12345 ·
          manager@blackhouse.example / Manager@12345 · admin@blackhouse.example / Admin@12345
        </p>
      </form>
    </main>
  );
}
